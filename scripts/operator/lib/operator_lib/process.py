"""The only place that starts a subprocess (acceptance S-11). No shell, a fixed command allowlist, a minimal child
environment, no secret in argv or the environment, bounded output, and a timeout.

OCI calls are read-only here too: only list, get, and inspect verbs reach the CLI (design section 4 rule 10).
"""
import os
import re
import signal
import subprocess
import tempfile
from dataclasses import dataclass

DEFAULT_ALLOW = frozenset({"oci", "ssh", "git"})
READ_VERBS = frozenset({"list", "get", "inspect"})
MAX_OUTPUT = 4 * 1024 * 1024
_ENV_KEY = re.compile(r"[A-Z][A-Z0-9_]{0,63}")


class PolicyViolation(Exception):
    """The call is outside the allowlist. Nothing was started."""


class CommandMissing(Exception):
    """The command is not installed or not executable."""


class CommandTimeout(Exception):
    """The command did not finish in time and was killed."""


@dataclass
class Result:
    returncode: int
    stdout: str
    stderr: str
    truncated: bool


def oci_verb_allowed(argv):
    """oci <service> [<resource>...] <verb> ... where the verb is list, get, or inspect, or oci --version."""
    if list(argv) == ["oci", "--version"]:
        return True
    tokens = []
    for item in argv[1:]:
        if item.startswith("-"):
            break
        tokens.append(item)
    return len(tokens) >= 2 and tokens[-1] in READ_VERBS


def _check(argv, allow, allow_exact, secrets, extra_env):
    if isinstance(argv, (str, bytes)) or not isinstance(argv, (list, tuple)) or not argv:
        raise PolicyViolation("a command must be a non-empty list of arguments")
    if not all(isinstance(item, str) and "\0" not in item for item in argv) or not argv[0]:
        raise PolicyViolation("arguments must be strings without NUL")
    exact = tuple(argv) in allow_exact
    if not exact:
        if "/" in argv[0] or argv[0] not in allow:
            raise PolicyViolation("command not in the allowlist")
        if argv[0] == "oci" and not oci_verb_allowed(argv):
            raise PolicyViolation("only list, get, and inspect OCI calls are allowed")
    live = [s for s in secrets if s]
    if any(s in item for s in live for item in argv):
        raise PolicyViolation("a secret must not be passed in arguments")
    env = dict(extra_env or {})
    for key, value in env.items():
        if not isinstance(key, str) or not _ENV_KEY.fullmatch(key) or not isinstance(value, str) or "\0" in value or "\n" in value:
            raise PolicyViolation("invalid environment entry")
        if any(s in value for s in live):
            raise PolicyViolation("a secret must not be passed in the environment")
    return env


def _child_env(path, extra):
    env = {"PATH": path if path is not None else os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
    if os.environ.get("HOME"):
        env["HOME"] = os.environ["HOME"]
    env.update(extra)
    return env


def _read(handle, cap):
    handle.seek(0)
    data = handle.read(cap + 1)
    return data[:cap].decode("utf-8", errors="replace"), len(data) > cap


def run(argv, *, allow=DEFAULT_ALLOW, allow_exact=frozenset(), secrets=(), extra_env=None, timeout=60, cwd=None,
        max_output=MAX_OUTPUT, path=None, input_text=None):
    """Run one allowlisted command and return its Result. A non-zero exit status is returned, not raised."""
    extra = _check(argv, allow, allow_exact, secrets, extra_env)
    env = _child_env(path, extra)
    data = input_text.encode("utf-8") if input_text is not None else None
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        try:
            proc = subprocess.Popen(list(argv), shell=False, stdin=subprocess.PIPE if data is not None else subprocess.DEVNULL,
                                    stdout=out, stderr=err, env=env, cwd=cwd, start_new_session=True)
        except (FileNotFoundError, PermissionError, NotADirectoryError):
            raise CommandMissing("command not found or not executable") from None
        try:
            proc.communicate(input=data, timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                proc.kill()
            proc.wait()
            raise CommandTimeout("command timed out") from None
        stdout, cut_out = _read(out, max_output)
        stderr, cut_err = _read(err, max_output)
    return Result(proc.returncode, stdout, stderr, cut_out or cut_err)
