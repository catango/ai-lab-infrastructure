"""Shared helpers of the lab fixtures (CR-57 PA-A8, PA-A25, PA-A13, PA-A26, PA-A31, PA-A32).

The same tests run in two places. In the gate they run the files of this repository as the current user, in temporary directories.
In the PA-28 job (tests/ansible/pa28-lab.sh) they run the files that lab setup installed, as the AI user: TOKEN_STEP and LAB_CHECK
name the installed files and RUN_AS names the account (the tests then work in a directory that account can write).
"""
import hashlib
import importlib.machinery
import importlib.util
import os
import pathlib
import pty
import select
import shutil
import stat
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOLS = ROOT / "ansible" / "roles" / "lab_tools" / "files"
SSH_MODULE = ROOT / "ansible" / "roles" / "ssh_hardening" / "library" / "ssh_hardening_audit.py"
TOKEN_STEP = pathlib.Path(os.environ.get("TOKEN_STEP", TOOLS / "token-step"))
LAB_CHECK = pathlib.Path(os.environ.get("LAB_CHECK", TOOLS / "lab-check"))
RUN_AS = os.environ.get("RUN_AS", "")
INSTALLED = bool(os.environ.get("TOKEN_STEP") or os.environ.get("LAB_CHECK"))
PLAIN_PATH = "/usr/bin:/bin"
# runuser lives in /usr/sbin on Debian, which the callers' PATH (a plain user's) does not list.
RUNUSER = shutil.which("runuser", path="/usr/sbin:/sbin:/usr/bin:/bin") or "runuser"


def load(name, path):
    """Import a script that has no .py name or lives outside the import path, without writing bytecode."""
    sys.dont_write_bytecode = True
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def as_user(argv):
    return [RUNUSER, "-u", RUN_AS, "--", *argv] if RUN_AS else list(argv)


def scratch(test):
    """A temporary directory the account under test can use."""
    tmp = tempfile.TemporaryDirectory(dir=os.environ.get("LAB_TEST_TMP") or None)
    test.addCleanup(tmp.cleanup)
    base = pathlib.Path(tmp.name)
    if RUN_AS:
        os.chmod(base, 0o777)
    return base


def tree_hash(path):
    """A hash of names, types, modes, link targets, and contents under path (the tree must be unchanged by a read-only run)."""
    digest = hashlib.sha256()
    for current, dirs, files in os.walk(path):
        dirs.sort()
        for name in sorted(dirs + files):
            full = os.path.join(current, name)
            info = os.lstat(full)
            digest.update(f"{os.path.relpath(full, path)} {stat.S_IFMT(info.st_mode)} {stat.S_IMODE(info.st_mode)}\n".encode())
            if stat.S_ISLNK(info.st_mode):
                digest.update(os.readlink(full).encode())
            elif stat.S_ISREG(info.st_mode):
                digest.update(pathlib.Path(full).read_bytes())
    return digest.hexdigest()


def run(argv, env=None, stdin=None, timeout=60):
    done = subprocess.run(as_user(argv), env=env if env is not None else {"PATH": PLAIN_PATH}, stdin=stdin, capture_output=True,
                          text=True, timeout=timeout, check=False)
    return done.returncode, done.stdout + done.stderr


def run_pty(argv, env, replies=(), timeout=30):
    """Run a command with a pseudo-terminal as stdin, stdout, and stderr. replies: (prompt, text) pairs, each sent once, after the
    prompt first appears. Returns (exit status, terminal output)."""
    pid, master = pty.fork()
    if pid == 0:
        try:
            os.execvpe(as_user(argv)[0], as_user(argv), env)
        finally:
            os._exit(127)
    output = b""
    pending = list(replies)
    deadline = time.monotonic() + timeout
    status = None
    while status is None and time.monotonic() < deadline:
        ready, _, _ = select.select([master], [], [], 0.2)
        if ready:
            try:
                chunk = os.read(master, 4096)
            except OSError:
                chunk = b""
            output += chunk
            for item in list(pending):
                if item[0].encode() in output:
                    os.write(master, item[1].encode() + b"\n")
                    pending.remove(item)
        done, state = os.waitpid(pid, os.WNOHANG)
        if done:
            status = os.waitstatus_to_exitcode(state)
    if status is None:
        os.kill(pid, 9)
        os.waitpid(pid, 0)
        status = -9
    try:
        while True:
            chunk = os.read(master, 4096)
            if not chunk:
                break
            output += chunk
    except OSError:
        pass
    os.close(master)
    return status, output.decode("utf-8", "replace")


STUB_GH = r"""#!/bin/sh
# A stand-in for gh. It keeps its state and its log next to itself, because the token step starts it with no environment.
here=$(cd "$(dirname "$0")" && pwd)
state="$here/../state"
printf '%s\n' "$*" >>"$here/../calls.log"
env | sed 's/=.*//' | sort >"$here/../env-names.txt"
case "$1 $2" in
  "auth status") [ -f "$state/logged-in" ] ;;
  "auth login") cat >"$here/../stdin-token.txt"; touch "$state/logged-in" ;;
  "auth logout") rm -f "$state/logged-in" ;;
  "auth setup-git") : >"$state/setup-git" ;;
  "api -i")
    printf 'HTTP/2.0 200 OK\r\nX-Oauth-Scopes: %s\r\nGithub-Authentication-Token-Expiration: 2099-01-01 00:00:00 UTC\r\n\r\n' "$(cat "$state/scopes")"
    printf '{"login":"%s","id":42}\n' "$(cat "$state/login")"
    ;;
  *) exit 1 ;;
esac
"""


def make_prefix(base, login="machine-bot", scopes="repo, workflow, read:org", conf=True):
    """A prefix directory with a stub gh in bin/ and the lab configuration in lab/lab.conf."""
    prefix = base / "prefix"
    for sub in ("bin", "state", "lab"):
        (prefix / sub).mkdir(parents=True)
    gh = prefix / "bin" / "gh"
    gh.write_text(STUB_GH)
    gh.chmod(0o755)
    (prefix / "state" / "login").write_text(login)
    (prefix / "state" / "scopes").write_text(scopes)
    if conf:
        (prefix / "lab" / "lab.conf").write_text("machine_login=machine-bot\nowner=owner\n")
    for sub in ("bin", "state", "lab"):
        (prefix / sub).chmod(0o777)
    os.chmod(prefix, 0o777)
    for path in (prefix / "lab" / "lab.conf",):
        if path.exists():
            path.chmod(0o644)
    return prefix
