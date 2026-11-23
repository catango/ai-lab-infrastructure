"""The policy inputs that rule PC-9 reads from the configuration of the BASE commit (ADR-009 decision 14, SC-20).

Only text of the base commit reaches this module: the clients fetch `config/project.yaml` at the base SHA and never the head.
The YAML is parsed by `yq -o=json` (the tool the policy checks use; the pr-contract job installs it from the base toolchain),
run without a shell and with a timeout. Standard library otherwise.

`architectures` is a list of mappings with `name`, `runner` (the label for a public repository), and `runner_private` (the label
for a private one). An empty label means the repository has no runner for that architecture. When the key is absent the default
applies: amd64 on the hosted runner, and arm64 on the free public ARM64 runner with no private one, because no metered ARM64
runner is used (design section 7, Q14).
"""
import json
import re
import shutil
import subprocess
from dataclasses import dataclass

from .errors import ConfigError, InputError

MAX_TEXT = 65536
YQ_TIMEOUT_SECONDS = 10
_NAME = re.compile(r"[a-z0-9_]{1,32}")
_LABEL = re.compile(r"[A-Za-z0-9_.-]{0,64}")
_KEYS = frozenset({"name", "runner", "runner_private"})


@dataclass(frozen=True)
class Arch:
    name: str
    runner: str = ""
    runner_private: str = ""

    def runner_for(self, private):
        return self.runner_private if private else self.runner


DEFAULT_ARCHITECTURES = (
    Arch("amd64", "ubuntu-24.04", "ubuntu-24.04"),
    Arch("arm64", "ubuntu-24.04-arm", ""),
)


def parse_yaml(text):
    """One YAML document that is a mapping, as a dict. An empty document is an empty mapping."""
    if not isinstance(text, str) or len(text.encode("utf-8", "replace")) > MAX_TEXT or "\x00" in text:
        raise ConfigError("configuration unreadable")
    yq = shutil.which("yq")
    if yq is None:
        raise InputError("yq not found")
    try:
        done = subprocess.run([yq, "-o=json", "."], input=text, capture_output=True, text=True,
                              timeout=YQ_TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.SubprocessError, ValueError):
        raise ConfigError("configuration unreadable") from None
    if done.returncode != 0:
        raise ConfigError("configuration unreadable")
    try:
        value = json.loads(done.stdout)
    except (ValueError, RecursionError):
        raise ConfigError("configuration unreadable") from None
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError("configuration is not a mapping")
    return value


def architectures(config):
    """The architectures of a parsed base configuration (None or without the key: the default). Anything else malformed raises."""
    if config is None:
        return DEFAULT_ARCHITECTURES
    if not isinstance(config, dict):
        raise ConfigError("configuration is not a mapping")
    if "architectures" not in config:
        return DEFAULT_ARCHITECTURES
    items = config["architectures"]
    if not isinstance(items, list):
        raise ConfigError("architectures is not a list")
    out, seen = [], set()
    for item in items:
        if not isinstance(item, dict) or set(item) - _KEYS:
            raise ConfigError("architectures entry is not valid")
        name = item.get("name")
        if not isinstance(name, str) or not _NAME.fullmatch(name) or name in seen:
            raise ConfigError("architectures name is not valid")
        labels = []
        for key in ("runner", "runner_private"):
            value = item.get(key)
            value = "" if value is None else value
            if not isinstance(value, str) or not _LABEL.fullmatch(value):
                raise ConfigError("architectures runner is not valid")
            labels.append(value)
        seen.add(name)
        out.append(Arch(name, *labels))
    return tuple(out)
