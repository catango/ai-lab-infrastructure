#!/usr/bin/python
# The user-level deny layer of the AI user (CR-57 follow-up R-2, plan PR 4a; PA-47, PA-50, PA-51, PA-A34, PA-A35).
# Standard library only. It runs as root and writes exactly two paths in the AI user's home: `~/.claude` (created when missing, owner
# the AI user, mode 0700) and `~/.claude/settings.json` (root:root, mode 0644, immutable). The AI user owns the directory, so a root
# write by path is a link attack: everything here works on descriptors (openat with O_NOFOLLOW, fstatat without following, mkdirat,
# renameat, unlinkat), and no step after the first two looks at a path again. No shell, no attribute command, no recursion.
# The logic is in plain functions with a small `Ops` object for the calls that need root, so tests/ansible/test_claude_user_deny.py can
# run every case as an ordinary user, with a seam between two steps of the module.
import errno
import fcntl
import json
import os
import pwd
import stat
import struct

DOCUMENTATION = r"""
module: claude_user_deny
short_description: Write the user-level deny layer of the AI user (root-owned, immutable) without following a link
options:
  user: {description: The AI user; its home comes from the account database, type: str, required: true}
  action:
    description: >-
      write (place ~/.claude/settings.json; a dry run reports and writes nothing) or probe (try the immutable attribute on a scratch
      file in a root-owned directory on the filesystem of the home; changes nothing).
    type: str
    choices: [write, probe]
    default: write
  deny_list: {description: The lab-wide deny list (one entry per line, comments with #), type: path, required: false}
"""

FS_IMMUTABLE_FL = 0x10
# FS_IOC_GETFLAGS and FS_IOC_SETFLAGS are _IOR('f', 1, long) and _IOW('f', 2, long): the numbers depend on the size of a long.
_LONG = struct.calcsize("l")
FS_IOC_GETFLAGS = (2 << 30) | (_LONG << 16) | (ord("f") << 8) | 1
FS_IOC_SETFLAGS = (1 << 30) | (_LONG << 16) | (ord("f") << 8) | 2
MOVE_ASIDE = "mv ~/.claude/settings.json ~/.claude/settings.json.pre-lab"
CAPABILITY = "CAP_LINUX_IMMUTABLE"
PROBE_NAME = ".ai-lab-attribute-probe"
DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
FILE_READ = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC


class Refusal(Exception):
    """A refusal or a failure: nothing was changed beyond what the message says."""


class Ops:
    """The calls that need root or a kernel feature. Tests replace them; the module itself never calls the kernel for these directly."""

    def owner_of(self, info):
        return info.st_uid, info.st_gid

    def device_of(self, info):
        return info.st_dev

    def fchown(self, fd, uid, gid):
        os.fchown(fd, uid, gid)

    def get_flags(self, fd):
        buffer = bytearray(_LONG)
        fcntl.ioctl(fd, FS_IOC_GETFLAGS, buffer, True)
        return struct.unpack("=i", bytes(buffer[:4]))[0]

    def set_flags(self, fd, flags):
        fcntl.ioctl(fd, FS_IOC_SETFLAGS, struct.pack("=i", flags).ljust(_LONG, b"\0"))

    def seam(self, name):
        """A point between two steps; a test runs a rename or a planted link here. Does nothing."""


# ---------------------------------------------------------------------------------------------------------------- the content
def parse_deny_list(text):
    """The entries of the lab-wide list in order: one per line, blank lines and lines starting with # skipped."""
    entries = [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if not entries:
        raise Refusal("the lab-wide deny list holds no entry")
    if len(set(entries)) != len(entries):
        raise Refusal("the lab-wide deny list names an entry twice")
    return entries


def canonical_content(entries):
    """The canonical object of PA-47, as two-space JSON with a final newline: nothing outside it (R2-O3)."""
    layer = {"enableAllProjectMcpServers": False, "permissions": {"deny": list(entries), "disableBypassPermissionsMode": "disable"}}
    return (json.dumps(layer, indent=2) + "\n").encode("utf-8")


# ---------------------------------------------------------------------------------------------------------------- helpers
def _errno_name(error):
    return errno.errorcode.get(error.errno, str(error.errno))


def _attribute_failure(account, error):
    """The message of a failed attribute call: the errno, and what the lab admin can do (PA-51)."""
    cause = f"errno {_errno_name(error)} ({os.strerror(error.errno)})" if error.errno else "an unknown error"
    hint = f" Without {CAPABILITY} not even root can set it." if error.errno == errno.EPERM else ""
    return (f"account {account}: the filesystem of the home directory does not support the immutable attribute, or the capability is "
            f"missing: {cause}.{hint} Move the home to a filesystem that supports it, or select -e lab_deny_layer=managed and accept that "
            f"the deny rules then depend on the managed file being in force")


def _same(first, second):
    return (first.st_dev, first.st_ino) == (second.st_dev, second.st_ino)


def _open_directory(path, dir_fd=None):
    return os.open(path, DIRECTORY, dir_fd=dir_fd)


def _is_root(ops, info):
    return ops.owner_of(info) == (0, 0)


def _clear_quietly(ops, fd):
    try:
        ops.set_flags(fd, ops.get_flags(fd) & ~FS_IMMUTABLE_FL)
    except OSError:
        pass


# ---------------------------------------------------------------------------------------------------------------- the write (PA-50)
def _open_home(ops, account, uid, home):
    if not os.path.isabs(home):
        raise Refusal(f"account {account}: the home directory {home} is not an absolute path")
    try:
        info = os.lstat(home)
    except OSError as error:
        raise Refusal(f"account {account}: the home directory {home} cannot be read ({_errno_name(error)})") from None
    if stat.S_ISLNK(info.st_mode):
        raise Refusal(f"account {account}: the home directory {home} is a link; nothing was changed")
    if not stat.S_ISDIR(info.st_mode):
        raise Refusal(f"account {account}: the home directory {home} is not a directory; nothing was changed")
    if ops.owner_of(info)[0] != uid:
        raise Refusal(f"account {account}: the home directory {home} is not owned by it; nothing was changed")
    try:
        fd = _open_directory(home)
    except OSError as error:
        raise Refusal(f"account {account}: the home directory {home} cannot be opened without following a link ({_errno_name(error)})") from None
    if not _same(os.fstat(fd), info):
        os.close(fd)
        raise Refusal(f"account {account}: the home directory {home} changed while it was checked; nothing was changed")
    return fd


def _open_claude(ops, account, uid, gid, home_fd, claude, check_mode):
    """(descriptor or None, created): the checked `.claude` directory. None only in a dry run that would create it."""
    try:
        info = os.stat(".claude", dir_fd=home_fd, follow_symlinks=False)
    except FileNotFoundError:
        info = None
    if info is None:
        if check_mode:
            return None, False
        os.mkdir(".claude", 0o700, dir_fd=home_fd)
        fd = _open_directory(".claude", home_fd)
        ops.fchown(fd, uid, gid)
        os.fchmod(fd, 0o700)
        return fd, True
    if stat.S_ISLNK(info.st_mode):
        raise Refusal(f"account {account}: {claude} is a link; nothing was changed")
    if not stat.S_ISDIR(info.st_mode):
        raise Refusal(f"account {account}: {claude} is not a directory; nothing was changed")
    try:
        fd = _open_directory(".claude", home_fd)
    except OSError as error:
        raise Refusal(f"account {account}: {claude} cannot be opened without following a link ({_errno_name(error)})") from None
    checked = os.fstat(fd)
    if not _same(checked, info) or ops.owner_of(checked)[0] != uid:
        os.close(fd)
        raise Refusal(f"account {account}: {claude} is not owned by it (or changed while it was checked); nothing was changed")
    return fd, False


def _inspect_settings(ops, account, uid, claude_fd, path, content):
    """(state, descriptor): 'absent', 'current' (nothing to do) or 'replace'. Anything else is a refusal that removes nothing."""
    try:
        info = os.stat("settings.json", dir_fd=claude_fd, follow_symlinks=False)
    except FileNotFoundError:
        return "absent", None
    if stat.S_ISLNK(info.st_mode):
        raise Refusal(f"account {account}: {path} is a link; nothing was changed. A link is an investigation for the lab admin")
    if not stat.S_ISREG(info.st_mode):
        raise Refusal(f"account {account}: {path} is not a regular file; nothing was changed. This is an investigation for the lab admin")
    if info.st_nlink != 1:
        raise Refusal(f"account {account}: {path} is hard-linked; nothing was changed. This is an investigation for the lab admin")
    owner = ops.owner_of(info)
    if owner[0] == uid:
        raise Refusal(f"account {account}: {path} is owned by it, so lab setup does not touch it; nothing was changed. The account moves it "
                      f"aside in a plain terminal with: {MOVE_ASIDE} and the lab admin runs lab setup again")
    if owner != (0, 0):
        raise Refusal(f"account {account}: {path} is not owned by root or by it; nothing was changed. This is an investigation for the lab admin")
    fd = os.open("settings.json", FILE_READ, dir_fd=claude_fd)
    if not _same(os.fstat(fd), info):
        os.close(fd)
        raise Refusal(f"account {account}: {path} changed while it was checked; nothing was changed")
    try:
        with os.fdopen(os.dup(fd), "rb") as handle:
            current = handle.read(len(content) + 1)
        try:
            immutable = bool(ops.get_flags(fd) & FS_IMMUTABLE_FL)
        except OSError:
            immutable = False
        if current == content and immutable and stat.S_IMODE(info.st_mode) == 0o644:
            os.close(fd)
            return "current", None
    except BaseException:
        os.close(fd)
        raise
    return "replace", fd


def _remove_created_directory(home_fd, created):
    if created:
        try:
            os.rmdir(".claude", dir_fd=home_fd)
        except OSError:
            pass


def place_layer(ops, account, uid, gid, home, content, check_mode=False):
    """Place ~/.claude/settings.json of the account. Returns {"changed", "actions"}; raises Refusal. See PA-50, steps 1 to 6."""
    claude, path = os.path.join(home, ".claude"), os.path.join(home, ".claude", "settings.json")
    home_fd = _open_home(ops, account, uid, home)
    claude_fd, old_fd, created = None, None, False
    try:
        ops.seam("after-home-open")
        claude_fd, created = _open_claude(ops, account, uid, gid, home_fd, claude, check_mode)
        if claude_fd is None:
            return {"changed": True, "actions": [f"create {claude} and write {path}"]}
        ops.seam("after-claude-open")
        state, old_fd = _inspect_settings(ops, account, uid, claude_fd, path, content)
        if state == "current":
            return {"changed": False, "actions": []}
        if check_mode:
            return {"changed": True, "actions": [f"{'replace' if state == 'replace' else 'write'} {path}"]}
        _write(ops, account, claude_fd, home_fd, created, old_fd, path, content)
        return {"changed": True, "actions": ([f"create {claude}"] if created else []) + [f"{'replace' if state == 'replace' else 'write'} {path}"]}
    finally:
        for fd in (old_fd, claude_fd, home_fd):
            if fd is not None:
                os.close(fd)


def _write(ops, account, claude_fd, home_fd, created, old_fd, path, content):
    temporary = f".settings.json.ai-lab-{os.getpid()}"
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=claude_fd)
    except OSError as error:
        raise Refusal(f"account {account}: {path} cannot be written ({_errno_name(error)}); nothing was changed") from None
    written = None
    try:
        written = os.fstat(fd)
        os.write(fd, content)
        ops.fchown(fd, 0, 0)
        os.fchmod(fd, 0o644)
        os.fsync(fd)
        ops.seam("before-rename")
        cleared = False
        if old_fd is not None:  # a file with the attribute cannot be replaced: clear it through its descriptor, just before the rename
            ops.set_flags(old_fd, ops.get_flags(old_fd) & ~FS_IMMUTABLE_FL)
            cleared = True
        try:
            os.rename(temporary, "settings.json", src_dir_fd=claude_fd, dst_dir_fd=claude_fd)
        except OSError as error:
            if cleared:
                try:
                    ops.set_flags(old_fd, ops.get_flags(old_fd) | FS_IMMUTABLE_FL)
                except OSError:
                    pass
            raise Refusal(f"account {account}: {path} cannot be replaced ({_errno_name(error)}); nothing else was changed") from None
        temporary = None
    except BaseException:
        if temporary:
            try:
                os.unlink(temporary, dir_fd=claude_fd)
            except OSError:
                pass
        os.close(fd)
        raise
    os.close(fd)
    _protect(ops, account, claude_fd, home_fd, created, path, written)


def _protect(ops, account, claude_fd, home_fd, created, path, written):
    """Set the attribute on the written inode, read it back, and check that the entry is still that inode (PA-50 steps 4 and 6)."""
    protected = os.open("settings.json", FILE_READ, dir_fd=claude_fd)
    try:
        if not _same(os.fstat(protected), written):
            _remove_entry(claude_fd, os.fstat(protected))
            raise Refusal(f"account {account}: {path} was replaced while it was written; the new file was removed and nothing is protected")
        ops.seam("before-attr")
        try:
            ops.set_flags(protected, ops.get_flags(protected) | FS_IMMUTABLE_FL)
            if not ops.get_flags(protected) & FS_IMMUTABLE_FL:
                raise OSError(errno.ENOTSUP, "the attribute does not read back")
        except OSError as error:
            _remove_entry(claude_fd, os.fstat(protected))
            _remove_created_directory(home_fd, created)
            raise Refusal(_attribute_failure(account, error)) from None
        try:
            now = os.stat("settings.json", dir_fd=claude_fd, follow_symlinks=False)
        except FileNotFoundError:
            now = None
        if now is None or not _same(now, written):
            # The account renamed the file between the rename and the attribute call. Clear the attribute through the descriptor so
            # no immutable file is stuck in its directory, and remove the stray file wherever it went in this directory.
            _clear_quietly(ops, protected)
            _remove_by_inode(claude_fd, written)
            raise Refusal(f"account {account}: {path} was not the file that lab setup wrote (renamed during the run); the attribute was "
                          "cleared and the stray file removed")
    finally:
        os.close(protected)


def _remove_entry(claude_fd, info):
    """Remove `settings.json` if it is the given inode (the new file); an unrelated entry is left alone."""
    try:
        current = os.stat("settings.json", dir_fd=claude_fd, follow_symlinks=False)
    except OSError:
        return
    if _same(current, info):
        try:
            os.unlink("settings.json", dir_fd=claude_fd)
        except OSError:
            pass


def _remove_by_inode(claude_fd, info):
    """Remove the entries of this one directory (no recursion) that are the given inode."""
    for entry in os.listdir(claude_fd):
        try:
            current = os.stat(entry, dir_fd=claude_fd, follow_symlinks=False)
            if _same(current, info):
                os.unlink(entry, dir_fd=claude_fd)
        except OSError:
            continue


# ---------------------------------------------------------------------------------------------------------------- the probe (PA-51)
def probe_attribute(ops, account, home):
    """Try the attribute on a scratch file in a root-owned directory on the filesystem of the home; leave nothing behind."""
    try:
        home_info = os.lstat(home)
        parent = os.path.dirname(os.path.normpath(home))
        parent_info = os.lstat(parent)
    except OSError as error:
        raise Refusal(f"account {account}: the home directory {home} or its parent cannot be read ({_errno_name(error)})") from None
    if (not stat.S_ISDIR(parent_info.st_mode) or not _is_root(ops, parent_info) or stat.S_IMODE(parent_info.st_mode) & 0o022):
        raise Refusal(f"account {account}: no root-owned directory that others cannot write is the parent of {home}, so the attribute "
                      "cannot be probed without a directory the account controls")
    if ops.device_of(home_info) != ops.device_of(parent_info):
        raise Refusal(f"account {account}: the parent of {home} is not on the same filesystem as the home (the home is a mount of its own), "
                      "so no root-owned directory on that filesystem is available for the probe")
    parent_fd = _open_directory(parent)
    fd = None
    try:
        try:
            fd = os.open(PROBE_NAME, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=parent_fd)
        except OSError as error:
            raise Refusal(f"account {account}: the probe file cannot be created in {parent} ({_errno_name(error)})") from None
        try:
            ops.set_flags(fd, ops.get_flags(fd) | FS_IMMUTABLE_FL)
            if not ops.get_flags(fd) & FS_IMMUTABLE_FL:
                raise OSError(errno.ENOTSUP, "the attribute does not read back")
        except OSError as error:
            _clear_quietly(ops, fd)
            raise Refusal(_attribute_failure(account, error)) from None
        ops.set_flags(fd, ops.get_flags(fd) & ~FS_IMMUTABLE_FL)
        return f"the immutable attribute can be set and cleared on the filesystem of {home}"
    finally:
        if fd is not None:
            os.close(fd)
            try:
                os.unlink(PROBE_NAME, dir_fd=parent_fd)
            except OSError:
                pass
        os.close(parent_fd)


# ---------------------------------------------------------------------------------------------------------------- Ansible
def main():
    from ansible.module_utils.basic import AnsibleModule

    module = AnsibleModule(
        argument_spec={"user": {"type": "str", "required": True},
                       "action": {"type": "str", "default": "write", "choices": ["write", "probe"]},
                       "deny_list": {"type": "path", "required": False}},
        supports_check_mode=True)
    user = module.params["user"]
    try:
        entry = pwd.getpwnam(user)  # the account database, never the environment
    except KeyError:
        module.fail_json(msg=f"account {user} does not exist")
    if entry.pw_uid == 0:
        module.fail_json(msg=f"account {user} is root; the layer is for the AI user only")
    ops = Ops()
    try:
        if module.params["action"] == "probe":
            module.exit_json(changed=False, msg=probe_attribute(ops, user, entry.pw_dir))
        if not module.params["deny_list"]:
            module.fail_json(msg="deny_list is required for action write")
        fd = os.open(module.params["deny_list"], FILE_READ)
        with os.fdopen(fd, "rb") as handle:
            entries = parse_deny_list(handle.read(1 << 20).decode("utf-8"))
        result = place_layer(ops, user, entry.pw_uid, entry.pw_gid, entry.pw_dir, canonical_content(entries), module.check_mode)
    except (Refusal, OSError, UnicodeDecodeError) as error:
        module.fail_json(msg=str(error))
    module.exit_json(changed=result["changed"], actions=result["actions"], path=os.path.join(entry.pw_dir, ".claude", "settings.json"),
                     entries=len(entries))


if __name__ == "__main__":
    main()
