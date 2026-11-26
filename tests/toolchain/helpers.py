"""Shared builders for the toolchain tests (standard library only)."""
import hashlib
import io
import pathlib
import stat
import sys
import tarfile
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "scripts"))

AMD64_URL = "https://example.invalid/alpha/v1.2.3/alpha-1.2.3-linux-amd64.tar.gz"
ARM64_URL = "https://example.invalid/alpha/v1.2.3/alpha-1.2.3-linux-arm64.tar.gz"
ZERO = "0" * 64
SCRIPT = b"#!/bin/sh\necho alpha 1.2.3\n"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def tar_bytes(entries, mode="w:gz"):
    """entries: list of (name, kind, payload, perm) with kind in file|dir|symlink|hardlink|chr|fifo."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode=mode) as archive:
        for name, kind, payload, perm in entries:
            info = tarfile.TarInfo(name)
            info.mode = perm
            if kind == "file":
                info.size = len(payload)
                archive.addfile(info, io.BytesIO(payload))
            elif kind == "dir":
                info.type = tarfile.DIRTYPE
                archive.addfile(info)
            elif kind == "symlink":
                info.type = tarfile.SYMTYPE
                info.linkname = payload
                archive.addfile(info)
            elif kind == "hardlink":
                info.type = tarfile.LNKTYPE
                info.linkname = payload
                archive.addfile(info)
            elif kind == "chr":
                info.type = tarfile.CHRTYPE
                archive.addfile(info)
            elif kind == "fifo":
                info.type = tarfile.FIFOTYPE
                archive.addfile(info)
    return buffer.getvalue()


def zip_bytes(entries):
    """entries: list of (name, payload, unix_mode)."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, payload, mode in entries:
            info = zipfile.ZipInfo(name)
            info.external_attr = mode << 16
            archive.writestr(info, payload)
    return buffer.getvalue()


def good_archive(version="1.2.3", prefix=None):
    top = prefix or f"alpha-{version}"
    return tar_bytes([
        (f"{top}/", "dir", None, 0o755),
        (f"{top}/bin/", "dir", None, 0o755),
        (f"{top}/bin/alpha", "file", SCRIPT, 0o755),
        (f"{top}/README", "file", b"readme\n", 0o644),
    ])


ARCH_ENTRIES = {
    "amd64": "  - name: amd64\n    runner: ubuntu-24.04\n    runner_private: ubuntu-24.04\n",
    "arm64": "  - name: arm64\n    runner: ubuntu-24.04-arm\n    runner_private: \"\"\n",
}


def write_config(root, *names):
    """config/project.yaml of a test root listing the given architectures (CR-57 PA-30: `check` reads the list from it)."""
    path = pathlib.Path(root) / "config" / "project.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("schema_version: 1\narchitectures:\n" + "".join(ARCH_ENTRIES[name] for name in names))


def without_arm64(text):
    """The same manifest text with the arm64 artifact table of the `alpha` tool removed."""
    start = text.index("[tools.alpha.artifacts.arm64]")
    return text[:start] + text[text.index("[tools.gitlike]"):]


def manifest_text(*, amd64_sha=ZERO, arm64_sha=ZERO, extra_tools="", head='schema_version = 1\n', alpha_extra="", amd64_url=AMD64_URL,
                  arm64_url=ARM64_URL, version="1.2.3"):
    return f'''{head}
[tools.alpha]
version = "{version}"
profiles = ["lab", "operator"]
source = "download"
format = "tar.gz"
strip = 1
binaries = ["bin/alpha"]
smoke = ["alpha", "--version"]
smoke_match = "alpha {version}"
{alpha_extra}
[tools.alpha.artifacts.amd64]
url = "{amd64_url}"
sha256 = "{amd64_sha}"

[tools.alpha.artifacts.arm64]
url = "{arm64_url}"
sha256 = "{arm64_sha}"

[tools.gitlike]
version_min = "1:2.0"
profiles = ["lab"]
source = "apt"
package = "git"
smoke = ["git", "--version"]
{extra_tools}'''


class FakeFetcher:
    """Serves bytes by URL and counts calls. No sockets."""

    def __init__(self, routes):
        self.routes = dict(routes)
        self.calls = []

    def __call__(self, url, max_bytes):
        self.calls.append(url)
        data = self.routes[url]
        if isinstance(data, BaseException):
            raise data
        return io.BytesIO(data)


def tree(path):
    """A comparable snapshot of a directory tree: relative path, type, size or link target."""
    out = []
    root = pathlib.Path(path)
    if not root.exists():
        return None
    for item in sorted(root.rglob("*")):
        rel = item.relative_to(root).as_posix()
        if item.is_symlink():
            out.append((rel, "link", str(item.readlink())))
        elif item.is_dir():
            out.append((rel, "dir", None))
        else:
            out.append((rel, "file", item.stat().st_size, stat.S_IMODE(item.stat().st_mode)))
    return out
