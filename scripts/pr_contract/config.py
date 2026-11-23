"""The policy inputs that rule PC-9 reads from the configuration of the BASE commit (ADR-009 decision 14, SC-20).

Only text of the base commit reaches this module: the clients fetch `config/project.yaml` at the base SHA and never the head.
There is no YAML library and no process: `parse_yaml` is a strict reader of ONE key, `architectures`, in a small subset of
YAML, and everything else in the file is not interpreted. Anything of that key outside the subset raises ConfigError, so PC-9
fails closed instead of guessing. The subset:

    architectures: []                 # or a block list of mappings, the only two forms
    architectures:
      - name: arm64                   # keys name, runner, runner_private; values plain, "double" or 'single' quoted,
        runner: ""                    # of letters, digits, `.`, `_`, `-` only (no escapes); an omitted value is null
        runner_private: ubuntu-24.04

Comments, blank lines, and any other top-level key are skipped. Flow style, anchors, aliases, tags, tabs, block scalars,
a second `architectures` key, and a second YAML document are errors. Plain values that YAML would not read as a string
(numbers, true, false, null) are errors; quote them. tests/pr-contract/test_pc9_inputs.py compares this reader with
`yq -o=json` on this repository's file and on the fixtures.

`architectures` is a list of mappings with `name`, `runner` (the label for a public repository), and `runner_private` (the label
for a private one). An empty label means the repository has no runner for that architecture. When the key is absent the default
applies: amd64 on the hosted runner, and arm64 on the free public ARM64 runner with no private one, because no metered ARM64
runner is used (design section 7, Q14).
"""
import re
from dataclasses import dataclass

from .errors import ConfigError

MAX_TEXT = 65536
_NAME = re.compile(r"[a-z0-9_]{1,32}")
_LABEL = re.compile(r"[A-Za-z0-9_.-]{0,64}")
_KEYS = frozenset({"name", "runner", "runner_private"})

_PLAIN = r"[A-Za-z0-9_.][A-Za-z0-9_.-]*"
_VALUE = rf"(?:{_PLAIN}|\"[A-Za-z0-9_.-]*\"|'[A-Za-z0-9_.-]*')"
_COMMENT = r"(?: +#.*)?"
_TOP_KEY = re.compile(r"architectures:(?P<rest>(?: .*)?)")
_EMPTY_LIST = re.compile(rf" +\[\]{_COMMENT}")
_NOTHING = re.compile(_COMMENT)
_FIRST = re.compile(rf"(?P<indent> *)-(?P<gap> +)(?P<key>[a-z_]+):(?: +(?P<val>{_VALUE}))?{_COMMENT}")
_NEXT = re.compile(rf"(?P<indent> +)(?P<key>[a-z_]+):(?: +(?P<val>{_VALUE}))?{_COMMENT}")
_NOT_A_STRING = re.compile(r"(?i)(?:true|false|null|~|yes|no|on|off|y|n)|[-+.]?[0-9].*")


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


def _scalar(text):
    if text is None:
        return None
    if text[0] in "\"'":
        return text[1:-1]
    if _NOT_A_STRING.fullmatch(text):
        raise ConfigError("architectures value is not a string")
    return text


def _skipped(line):
    return line.strip(" ") == "" or line.lstrip(" ").startswith("#")


def parse_yaml(text):
    """{"architectures": value} when the file has that key in the subset above, else {}. Everything else is not read."""
    if not isinstance(text, str) or len(text.encode("utf-8", "replace")) > MAX_TEXT or "\x00" in text:
        raise ConfigError("configuration unreadable")
    lines = [line[:-1] if line.endswith("\r") else line for line in text.split("\n")]
    seen_content = False
    keys = []
    for number, line in enumerate(lines):
        if line[:1] in ("", " ", "#") or line.startswith("- ") or line == "-":
            seen_content = seen_content or not _skipped(line)
            continue
        if re.match(r"(?:---|\.\.\.)(?: |$)", line):
            if line.startswith("---") and not seen_content:
                continue
            raise ConfigError("more than one YAML document")
        seen_content = True
        if re.match(r"""(?:["']architectures|\? |<<|architectures(?![A-Za-z0-9_.-]))""", line):
            if not _TOP_KEY.fullmatch(line):
                raise ConfigError("architectures key is not in the supported form")
            keys.append(number)
    if not keys:
        return {}
    if len(keys) > 1:
        raise ConfigError("architectures key is repeated")
    return {"architectures": _read_block(lines, keys[0])}


def _read_block(lines, index):
    rest = _TOP_KEY.fullmatch(lines[index]).group("rest")
    if _EMPTY_LIST.fullmatch(rest):
        return []
    if not _NOTHING.fullmatch(rest):
        raise ConfigError("architectures is not a block list or []")
    items, current, column, item_indent = [], None, None, None
    for line in lines[index + 1:]:
        if _skipped(line):
            if "\t" in line:
                raise ConfigError("tab in architectures")
            continue
        if line[0] == "\t":
            raise ConfigError("tab in architectures")
        if line[0] not in " -":
            break
        first = _FIRST.fullmatch(line)
        if first:
            indent = len(first.group("indent"))
            if item_indent not in (None, indent):
                raise ConfigError("architectures list indentation changes")
            item_indent, column = indent, indent + 1 + len(first.group("gap"))
            current = {}
            items.append(current)
            match = first
        else:
            match = _NEXT.fullmatch(line)
            if not match or current is None or len(match.group("indent")) != column:
                raise ConfigError("architectures is outside the supported form")
        key = match.group("key")
        if key in current:
            raise ConfigError("architectures key is repeated in an entry")
        current[key] = _scalar(match.group("val"))
    return items or None


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
