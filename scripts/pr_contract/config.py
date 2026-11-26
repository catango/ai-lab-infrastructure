"""The policy inputs that the pr-contract rules read from the configuration of the BASE commit (ADR-009 decision 14, SC-20).

Only text of the base commit reaches this module: the clients fetch `config/project.yaml` at the base SHA and never the head.
There is no YAML library and no process: `parse_yaml` is a strict reader of THREE keys, `architectures`, `operator_paths`
and `operator_endpoints`, in a small subset of YAML, and everything else in the file is not interpreted. Anything of those
keys outside the subset raises ConfigError, so PC-8 and PC-9 fail closed instead of guessing. The subset:

    architectures: []                 # or a block list of mappings, the only two forms
    architectures:
      - name: amd64                   # keys name, runner, runner_private; values plain, "double" or 'single' quoted,
        runner: ubuntu-24.04          # of letters, digits, `.`, `_`, `-` only (no escapes); an omitted value is null
        runner_private: ubuntu-24.04

    operator_paths: []                # or a block list of plain strings, the only two forms (PC-8, CR-57 PA-A6)
    operator_paths:
      - scripts/operator/             # one plain string per item: letters, digits, `.`, `_`, `-`, `/`, and `*` only
      - ansible/operator.yml          # as the last two characters `*/`; no quotes, no flow style, no mapping items
      - ansible/roles/operator_*/

    operator_endpoints: []            # or a block list of plain strings (host names), the same two forms (SC-20, C-6)
    operator_endpoints:
      - api.github.com                # letters, digits, `.`, `-`, `_`

The three keys may appear in any order, each at most once. Comments, blank lines, and any other top-level key are skipped. Flow
style, anchors, aliases, tags, tabs, block scalars, a repeated key, a quoted key, and a second YAML document are errors. Plain
values that YAML would not read as a string (numbers, true, false, null) are errors; quote them in `architectures`, and
avoid them in the two lists. tests/pr-contract/test_pc9_inputs.py and test_operator_paths.py compare this reader with
`yq -o=json` on this repository's file and on the fixtures.

`architectures` is a list of mappings with `name`, `runner` (the label for a public repository), and `runner_private` (the label
for a private one). An empty label means the repository has no runner for that architecture. When the key is absent the default
applies: amd64 on the hosted runner only. This repository supports amd64 only (CR-57 PA-30, O-24); a repository that supports
another architecture lists it in its own configuration.

`operator_paths` is the operator set of rule PC-8. `operator_paths(config)` returns its entries as a tuple, an empty tuple for an
explicit `[]` (PC-8 is then inactive), and raises ConfigError for a missing or malformed key (PC-8 then fails closed). An entry
matches a path (`is_operator_path`) as an exact path, or as a directory prefix when it ends with `/`, or as the prefix left when
a final `*/` loses its `*` (`ansible/roles/operator_*/` is the prefix `ansible/roles/operator_`). Matching is case-sensitive.
`operator_endpoints(config)` returns the hosts an operator script may call as a tuple, or None when the key is absent (the check
that reads it decides what absence means: it fails closed while `operator_paths` is non-empty).
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
_LIST_KEYS = ("operator_paths", "operator_endpoints")
_TOP_LIST_KEY = re.compile(r"(?P<key>operator_paths|operator_endpoints):(?P<rest>(?: .*)?)")
_KEY_START = re.compile(
    r"""(?:["'](?P<quoted>architectures|operator_paths|operator_endpoints)|\? |<<|"""
    r"""(?P<key>architectures|operator_paths|operator_endpoints)(?![A-Za-z0-9_.-]))""")
_ITEM = re.compile(rf"(?P<indent> *)- +(?P<val>[A-Za-z0-9_.][A-Za-z0-9_./*-]*){_COMMENT}")
_PATH_ENTRY = re.compile(r"[A-Za-z0-9_.][A-Za-z0-9_./-]*(?:\*/)?")
_HOST = re.compile(r"[A-Za-z0-9_.][A-Za-z0-9_.-]*")
MAX_ENTRY = 200
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


DEFAULT_ARCHITECTURES = (Arch("amd64", "ubuntu-24.04", "ubuntu-24.04"),)


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
    keys = {}
    for number, line in enumerate(lines):
        if line[:1] in ("", " ", "#") or line.startswith("- ") or line == "-":
            seen_content = seen_content or not _skipped(line)
            continue
        if re.match(r"(?:---|\.\.\.)(?: |$)", line):
            if line.startswith("---") and not seen_content:
                continue
            raise ConfigError("more than one YAML document")
        seen_content = True
        found = _KEY_START.match(line)
        if found:
            key = found.group("key")
            shape = _TOP_KEY if key == "architectures" else _TOP_LIST_KEY
            if key is None or not shape.fullmatch(line):
                raise ConfigError(f"{key or 'a supported'} key is not in the supported form")
            if key in keys:
                raise ConfigError(f"{key} key is repeated")
            keys[key] = number
    out = {}
    for key, number in keys.items():
        out[key] = _read_block(lines, number) if key == "architectures" else _read_list(lines, number, key)
    return out


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


def _read_list(lines, index, key):
    """The block list of plain strings (or `[]`) under the top-level key on lines[index]."""
    rest = _TOP_LIST_KEY.fullmatch(lines[index]).group("rest")
    if _EMPTY_LIST.fullmatch(rest):
        return []
    if not _NOTHING.fullmatch(rest):
        raise ConfigError(f"{key} is not a block list or []")
    items, item_indent = [], None
    for line in lines[index + 1:]:
        if _skipped(line):
            if "\t" in line:
                raise ConfigError(f"tab in {key}")
            continue
        if line[0] == "\t":
            raise ConfigError(f"tab in {key}")
        if line[0] not in " -":
            break
        item = _ITEM.fullmatch(line)
        if not item:
            raise ConfigError(f"{key} is outside the supported form")
        indent = len(item.group("indent"))
        if item_indent not in (None, indent):
            raise ConfigError(f"{key} list indentation changes")
        item_indent = indent
        if _NOT_A_STRING.fullmatch(item.group("val")):
            raise ConfigError(f"{key} value is not a string")
        items.append(item.group("val"))
    if not items:
        raise ConfigError(f"{key} is not a block list or []")
    return items


def _string_list(config, key):
    """The value of `key` as a tuple of strings, None when the key is absent; anything else that is not a list of strings raises."""
    if config is None:
        return None
    if not isinstance(config, dict):
        raise ConfigError("configuration is not a mapping")
    if key not in config:
        return None
    items = config[key]
    if not isinstance(items, list) or not all(isinstance(item, str) for item in items):
        raise ConfigError(f"{key} is not a list of strings")
    if len(set(items)) != len(items):
        raise ConfigError(f"{key} has a repeated entry")
    return tuple(items)


def _path_entry_valid(entry):
    if len(entry) > MAX_ENTRY or not _PATH_ENTRY.fullmatch(entry):
        return False
    body = entry[:-2] if entry.endswith("*/") else entry[:-1] if entry.endswith("/") else entry
    return all(part not in ("", ".", "..") for part in body.split("/"))


def operator_paths(config):
    """The PC-8 operator set of a parsed base configuration, as a tuple (empty for an explicit `[]`). A missing file or key and
    anything malformed raise ConfigError: PC-8 fails closed, never passes."""
    paths = _string_list(config, "operator_paths")
    if paths is None:
        raise ConfigError("operator_paths is missing")
    if not all(_path_entry_valid(entry) for entry in paths):
        raise ConfigError("operator_paths entry is not valid")
    return paths


def operator_endpoints(config):
    """The hosts an operator script may call, as a tuple, or None when the key (or the file) is absent. Malformed raises."""
    hosts = _string_list(config, "operator_endpoints")
    if hosts is not None and not all(len(h) <= MAX_ENTRY and _HOST.fullmatch(h) for h in hosts):
        raise ConfigError("operator_endpoints entry is not valid")
    return hosts


def is_operator_path(path, entries):
    """Whether `path` matches an entry: the exact path, or the prefix of an entry ending `/`, or of an entry ending `*/` (the
    star dropped). Case-sensitive; an entry never matches by any other rule."""
    for entry in entries:
        if entry.endswith("*/"):
            if path.startswith(entry[:-2]):
                return True
        elif entry.endswith("/"):
            if path.startswith(entry):
                return True
        elif path == entry:
            return True
    return False


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
