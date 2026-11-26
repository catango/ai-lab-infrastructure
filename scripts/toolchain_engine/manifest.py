"""Manifest loading, static validation (design 3.2 rules 1 to 6), and typed access."""
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Dict, List, Optional, Tuple

from .errors import ManifestError

SCHEMA_VERSION = 1
ARCHES = ("amd64", "arm64")
PROFILES = ("lab", "operator")
SOURCES = ("download", "apt", "pip")
FORMATS = ("binary", "tar.gz", "tar.xz", "zip")
MAX_BYTES_DEFAULT = 512 * 1024 * 1024
MAX_BYTES_LIMIT = 2 * 1024 * 1024 * 1024

_NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,40}")
_VERSION = re.compile(r"[0-9]+(\.[0-9]+)*([-+][0-9A-Za-z.+_-]+)?")
_VERSION_MIN = re.compile(r"[0-9][0-9A-Za-z.+:~_-]*")
_PACKAGE = re.compile(r"[a-z0-9][a-z0-9.+-]{0,60}")
_URL = re.compile(r"https://[A-Za-z0-9._~%+:/@=?-]+")
_BINARY = re.compile(r"[A-Za-z0-9._+-]+(/[A-Za-z0-9._+-]+)*")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_META = re.compile(r"[;&|$`<>(){}\\\"'\n\r\t]")
_REQ = re.compile(r"([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9.+!_-]+)((?: --hash=sha256:[0-9a-f]{64})+)")

_COMMON = {"profiles", "source", "smoke", "smoke_match"}
_ALLOWED = {
    "download": _COMMON | {"version", "format", "strip", "binaries", "max_bytes", "artifacts"},
    "apt": _COMMON | {"version_min", "package"},
    "pip": _COMMON | {"lockfile", "binaries"},
}


@dataclass(frozen=True)
class Artifact:
    url: str
    sha256: str


@dataclass(frozen=True)
class Tool:
    name: str
    source: str
    profiles: Tuple[str, ...]
    smoke: Tuple[str, ...]
    smoke_match: Optional[str] = None
    version: Optional[str] = None
    version_min: Optional[str] = None
    package: Optional[str] = None
    format: Optional[str] = None
    strip: int = 0
    binaries: Tuple[str, ...] = ()
    max_bytes: int = MAX_BYTES_DEFAULT
    lockfile: Optional[str] = None
    artifacts: Dict[str, Artifact] = field(default_factory=dict)


@dataclass(frozen=True)
class Manifest:
    tools: Dict[str, Tool]

    def for_profile(self, profile):
        return [tool for tool in self.tools.values() if profile in tool.profiles]


def load(path):
    try:
        data = Path(path).read_bytes()
    except OSError:
        raise ManifestError("manifest not found or unreadable") from None
    try:
        return tomllib.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError):
        raise ManifestError("manifest is not valid TOML") from None


def configured_architectures(root):
    """(names, errors): the architectures of `config/project.yaml` under ROOT, read with the strict reader of pr-contract.

    The engine stays generic (ADR-008 decision 8, CR-57 PA-30): the repository decides which architectures it supports. A missing
    file or key means the default of that reader. The reader is imported here and not at the top, because the copy of the engine
    that lab setup installs has no `pr_contract` next to it and never calls `check`.
    """
    where = "config/project.yaml"
    try:
        from pr_contract import config as project_config
        from pr_contract.errors import ConfigError
    except ImportError:
        return (), [f"{where}: cannot be read (scripts/pr_contract is not next to the engine)"]
    path = Path(root) / "config" / "project.yaml"
    try:
        parsed = project_config.parse_yaml(path.read_text(encoding="utf-8")) if path.is_file() else None
        names = tuple(arch.name for arch in project_config.architectures(parsed))
    except (OSError, UnicodeDecodeError):
        return (), [f"{where}: cannot be read"]
    except ConfigError as error:
        return (), [f"{where}: architectures cannot be read ({error})"]
    errors = [f"{where}: architecture {name} is not known to the engine (expected one of {', '.join(ARCHES)})" for name in names if name not in ARCHES]
    if not names:
        errors.append(f"{where}: architectures lists none")
    return names, errors


def check_file(path, root, configured=True):
    """All validation errors for a manifest file (empty list means valid). Never raises for bad content.

    CONFIGURED true (`check`): every download tool has an artifact for exactly the architectures of `config/project.yaml` and
    for no other (CR-57 PA-30, O-4). False (install, verify, list): the artifacts are checked for form only, because the engine
    copy that lab setup installs has no configuration file beside it.
    """
    try:
        raw = load(path)
    except ManifestError as error:
        return [str(error).replace("valid TOML", "valid TOML (TOML syntax error)")]
    if not configured:
        return validate(raw, Path(root))
    names, errors = configured_architectures(root)
    return errors + validate(raw, Path(root), names)


def parse(raw):
    tools = {}
    for name, entry in raw["tools"].items():
        artifacts = {arch: Artifact(a["url"], a["sha256"]) for arch, a in entry.get("artifacts", {}).items()}
        tools[name] = Tool(
            name=name, source=entry["source"], profiles=tuple(entry["profiles"]), smoke=tuple(entry.get("smoke", ())),
            smoke_match=entry.get("smoke_match"), version=entry.get("version"), version_min=entry.get("version_min"),
            package=entry.get("package"), format=entry.get("format"), strip=entry.get("strip", 0),
            binaries=tuple(entry.get("binaries", ())), max_bytes=entry.get("max_bytes", MAX_BYTES_DEFAULT),
            lockfile=entry.get("lockfile"), artifacts=artifacts)
    return Manifest(tools)


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def validate(raw, root, architectures=None):
    """ARCHITECTURES: the names a download tool must have artifacts for and may only have; None means any known name, none required."""
    errors: List[str] = []
    if raw.get("schema_version") != SCHEMA_VERSION or not _is_int(raw.get("schema_version")):
        errors.append("schema_version: missing or unknown (expected 1)")
    for key in raw:
        if key not in ("schema_version", "tools"):
            errors.append(f"{key}: unknown key")
    tools = raw.get("tools")
    if not isinstance(tools, dict) or not tools:
        errors.append("tools: missing or empty")
        return errors
    seen: Dict[str, str] = {}
    for name, entry in tools.items():
        label = f"tools.{name}"
        if not isinstance(name, str) or not _NAME.fullmatch(name):
            errors.append(f"{label}: invalid tool name")
            continue
        if not isinstance(entry, dict):
            errors.append(f"{label}: must be a table")
            continue
        errors.extend(_validate_tool(label, entry, Path(root), architectures))
        binaries = entry.get("binaries")
        if isinstance(binaries, list):
            for binary in binaries:
                if isinstance(binary, str) and _BINARY.fullmatch(binary):
                    base = PurePosixPath(binary).name
                    if base in seen and seen[base] != name:
                        errors.append(f"{label}.binaries: '{base}' is also provided by tools.{seen[base]}")
                    seen.setdefault(base, name)
    return errors


def _validate_tool(label, entry, root, architectures=None):
    errors: List[str] = []
    source = entry.get("source")
    if source not in SOURCES:
        errors.append(f"{label}.source: must be one of download, apt, pip")
        return errors
    for key in entry:
        if key not in _ALLOWED[source]:
            errors.append(f"{label}.{key}: unknown key for source {source}")
    profiles = entry.get("profiles")
    if (not isinstance(profiles, list) or not profiles or any(p not in PROFILES for p in profiles)
            or len(set(profiles)) != len(profiles)):
        errors.append(f"{label}.profiles: must be a non-empty subset of lab, operator")
    smoke = entry.get("smoke")
    if (not isinstance(smoke, list) or not smoke or any(not isinstance(a, str) or not a or _META.search(a) for a in smoke)):
        errors.append(f"{label}.smoke: must be a non-empty array of plain arguments (no shell strings)")
    match = entry.get("smoke_match")
    if match is not None and (not isinstance(match, str) or not match or _META.search(match)):
        errors.append(f"{label}.smoke_match: must be a plain non-empty string")
    if source in ("download", "pip") and match is None:
        errors.append(f"{label}.smoke_match: required for {source}")
    if source == "download":
        errors.extend(_validate_download(label, entry, architectures))
    elif source == "apt":
        errors.extend(_validate_apt(label, entry))
    else:
        errors.extend(_validate_pip(label, entry, root))
    return errors


def _validate_binaries(label, entry):
    binaries = entry.get("binaries")
    if (not isinstance(binaries, list) or not binaries
            or any(not isinstance(b, str) or not _BINARY.fullmatch(b) or ".." in b.split("/") for b in binaries)):
        return [f"{label}.binaries: must be a non-empty array of relative paths without '..' or shell characters"]
    return []


def _validate_download(label, entry, architectures=None):
    errors = []
    version = entry.get("version")
    version_ok = isinstance(version, str) and bool(_VERSION.fullmatch(version))
    if not version_ok:
        errors.append(f"{label}.version: must be an exact version such as 1.2.3 (no latest, ranges, or wildcards)")
    fmt = entry.get("format")
    if fmt not in FORMATS:
        errors.append(f"{label}.format: must be one of binary, tar.gz, tar.xz, zip")
    strip = entry.get("strip", 0)
    if not _is_int(strip) or not 0 <= strip <= 5:
        errors.append(f"{label}.strip: must be an integer from 0 to 5")
    max_bytes = entry.get("max_bytes", MAX_BYTES_DEFAULT)
    if not _is_int(max_bytes) or not 1 <= max_bytes <= MAX_BYTES_LIMIT:
        errors.append(f"{label}.max_bytes: must be an integer from 1 to {MAX_BYTES_LIMIT}")
    errors.extend(_validate_binaries(label, entry))
    if fmt == "binary":
        binaries = entry.get("binaries")
        if strip != 0 or not isinstance(binaries, list) or len(binaries) != 1 or "/" in str(binaries[0]):
            errors.append(f"{label}.format: binary requires strip 0 and exactly one binary name without a directory")
    artifacts = entry.get("artifacts")
    if not isinstance(artifacts, dict):
        return errors + [f"{label}.artifacts: missing (one table per architecture of config/project.yaml is required)"]
    listed = ARCHES if architectures is None else architectures
    for arch in (listed if architectures is not None else ()):
        if arch not in artifacts:
            errors.append(f"{label}.artifacts.{arch}: missing (config/project.yaml lists {arch})")
    if architectures is None and not artifacts:
        errors.append(f"{label}.artifacts: missing (at least one architecture is required)")
    for arch, artifact in artifacts.items():
        alabel = f"{label}.artifacts.{arch}"
        if arch not in ARCHES:
            errors.append(f"{alabel}: unknown architecture (expected {' or '.join(ARCHES)})")
            continue
        if architectures is not None and arch not in architectures:
            errors.append(f"{alabel}: artifact for an unlisted architecture (config/project.yaml lists {', '.join(architectures)})")
            continue
        if not isinstance(artifact, dict):
            errors.append(f"{alabel}: must be a table")
            continue
        for key in artifact:
            if key not in ("url", "sha256"):
                errors.append(f"{alabel}.{key}: unknown key")
        url = artifact.get("url")
        if not isinstance(url, str) or not url.startswith("https://") or not _URL.fullmatch(url):
            errors.append(f"{alabel}.url: must be an https URL without shell characters")
        else:
            if "latest" in url.lower():
                errors.append(f"{alabel}.url: contains 'latest' (pin an exact version)")
            if version_ok and version not in url:
                errors.append(f"{alabel}.url: does not contain the version")
        sha = artifact.get("sha256")
        if not isinstance(sha, str) or not _SHA256.fullmatch(sha):
            errors.append(f"{alabel}.sha256: must be 64 lowercase hex characters")
    return errors


def _validate_apt(label, entry):
    errors = []
    package = entry.get("package")
    if not isinstance(package, str) or not _PACKAGE.fullmatch(package):
        errors.append(f"{label}.package: missing or invalid")
    minimum = entry.get("version_min")
    if not isinstance(minimum, str) or not _VERSION_MIN.fullmatch(minimum):
        errors.append(f"{label}.version_min: missing or invalid (apt tools use a minimum version)")
    return errors


def _validate_pip(label, entry, root):
    errors = _validate_binaries(label, entry)
    lockfile = entry.get("lockfile")
    if not isinstance(lockfile, str) or not _BINARY.fullmatch(lockfile) or ".." in lockfile.split("/"):
        return errors + [f"{label}.lockfile: must be a relative path inside the repository"]
    path = (root / lockfile)
    if not path.is_file():
        return errors + [f"{label}.lockfile: file not found"]
    errors.extend(f"{label}.lockfile: {message}" for message in check_lock(path))
    return errors


def logical_lines(text):
    """Requirement lines with continuations joined and comments dropped."""
    out, current = [], ""
    for line in text.splitlines():
        stripped = line.strip()
        if not current and (not stripped or stripped.startswith("#")):
            continue
        if stripped.endswith("\\"):
            current += " " + stripped[:-1].strip()
            continue
        out.append((current + " " + stripped).strip())
        current = ""
    if current:
        out.append(current.strip())
    return [" ".join(line.split()) for line in out]


def check_lock(path):
    """Static check of a hash-locked requirements file: every line pinned with == and hashed."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ["unreadable"]
    lines = logical_lines(text)
    if not lines:
        return ["no requirements"]
    errors = []
    for line in lines:
        if _REQ.fullmatch(line):
            continue
        if re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*==", line):
            errors.append("a requirement has no sha256 hash or a malformed hash")
        elif re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*\s*[<>~!]", line) or re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*\s", line):
            errors.append("a requirement is not pinned with ==")
        else:
            errors.append("unsupported line (only name==version with hashes is allowed)")
    return errors
