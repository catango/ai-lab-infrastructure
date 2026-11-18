"""Raw-output directory (design section 4 rule 7): mode 700, files mode 600, a size cap, and cleanup of the oldest files.
Raw responses stay here and never enter the repository."""
import os
import re
import stat

_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}")


class RawDirError(Exception):
    pass


class RawDir:
    def __init__(self, path, cap_bytes):
        self.path = os.fspath(path)
        self.cap = int(cap_bytes)
        try:
            info = os.lstat(self.path)
        except FileNotFoundError:
            os.makedirs(self.path, mode=0o700, exist_ok=True)
            info = os.lstat(self.path)
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise RawDirError("the raw-output path is not a plain directory")
        if info.st_uid != os.getuid():
            raise RawDirError("the raw-output directory is owned by another user")
        os.chmod(self.path, 0o700)

    def _entries(self):
        for name in os.listdir(self.path):
            full = os.path.join(self.path, name)
            info = os.lstat(full)
            if stat.S_ISREG(info.st_mode):
                yield name, full, info

    def size(self):
        return sum(info.st_size for _, _, info in self._entries())

    def write(self, name, data):
        if not isinstance(name, str) or not _NAME.fullmatch(name):
            raise RawDirError("invalid file name")
        target = os.path.join(self.path, name)
        existing = 0
        if os.path.lexists(target):
            info = os.lstat(target)
            existing = info.st_size if stat.S_ISREG(info.st_mode) else 0
        if self.size() - existing + len(data) > self.cap:
            raise RawDirError("the size cap of the raw-output directory would be exceeded")
        temp = os.path.join(self.path, f".tmp-{os.getpid()}")
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
            os.replace(temp, target)
        finally:
            if os.path.lexists(temp):
                os.unlink(temp)

    def cleanup(self, keep_bytes):
        """Remove the oldest files until at most keep_bytes remain. Returns the number removed."""
        entries = sorted(self._entries(), key=lambda item: (item[2].st_mtime, item[0]))
        total = sum(info.st_size for _, _, info in entries)
        removed = 0
        for _, full, info in entries:
            if total <= keep_bytes:
                break
            os.unlink(full)
            total -= info.st_size
            removed += 1
        return removed
