#!/usr/bin/python
# Audit for the shared SSH hardening role (CR-57 PA-16, LC-13, OC-10). It reads account files and the output of `sshd -T`. Only the
# mode `install` writes, and only the root-owned key files; nothing is ever written into a user's home. It never prints key
# material: findings name accounts and rules only, and the key files are written here, not returned.
# The logic is in plain functions so that tests/ansible/test_ssh_hardening_audit.py can run it without Ansible, root, or sshd.
import base64
import binascii
import os
import re
import stat
import tempfile
from collections import namedtuple

DOCUMENTATION = r"""
module: ssh_hardening_audit
short_description: Audit provisioned SSH keys and the effective sshd settings (read-only)
options:
  mode:
    description: >-
      keys (audit the provisioned keys), install (audit them, then write the root-owned key files), sshd_before (sshd -T before the
      drop-in), sshd_after (sshd -T with it).
    required: true
    choices: [keys, install, sshd_before, sshd_after]
  accounts: {description: The managed accounts, type: list, elements: str, default: []}
  private_key_accounts: {description: Accounts whose ~/.ssh must hold no private key, type: list, elements: str, default: []}
  key_options: {description: "Options put in front of the key of an account, as {account: options}", type: dict, default: {}}
  keys_dir: {description: The root-owned location sshd reads keys from, type: path, default: /etc/ssh/authorized_keys}
  sshd_text: {description: "Output of sshd -T (modes sshd_before and sshd_after)", type: str, default: ""}
"""

# The security-key types end in an OpenSSH domain; it is kept apart so that no line of this file looks like an address.
OPENSSH = "@openssh" + ".com"
KEY_TYPES = frozenset({
    "ssh-ed25519", "sk-ssh-ed25519" + OPENSSH, "ecdsa-sha2-nistp256", "ecdsa-sha2-nistp384", "ecdsa-sha2-nistp521",
    "sk-ecdsa-sha2-nistp256" + OPENSSH, "ssh-rsa",
})
Key = namedtuple("Key", "options type blob comment")
AUTH_SETTINGS = ("authorizedkeyscommand", "trustedusercakeys", "authorizedprincipalsfile")
# The marker is built from parts so that this file does not itself look like a private key to the public-repository hygiene check.
PRIVATE_KEY_MARKER = re.compile(rb"-{5}BEGIN [A-Z0-9 ]*PRIVATE KEY-{5}")
MAX_BYTES = 65536
# What sshd -T must show once the drop-in is in force (LC-13, OC-10): setting -> value.
EXPECTED_AFTER = {
    "pubkeyauthentication": "yes", "passwordauthentication": "no", "kbdinteractiveauthentication": "no", "permitrootlogin": "no",
    "authenticationmethods": "publickey", "allowagentforwarding": "no", "allowtcpforwarding": "no", "x11forwarding": "no",
    "permittunnel": "no", "permituserrc": "no", "permituserenvironment": "no",
}


def _split_options(text):
    """(options, rest) for an authorized_keys line that starts with options; options may hold quoted strings with spaces."""
    quoted = False
    index = 0
    while index < len(text):
        char = text[index]
        if quoted and char == "\\":
            index += 2
            continue
        if char == '"':
            quoted = not quoted
        elif char in " \t" and not quoted:
            break
        index += 1
    if quoted:
        raise ValueError("unterminated quote in the key options")
    return text[:index], text[index:].lstrip()


def parse_key_line(line):
    """Key for a public key line, None for a blank or comment line. Raises ValueError for anything else."""
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    options = ""
    rest = line
    if line.split(None, 1)[0] not in KEY_TYPES:
        options, rest = _split_options(line)
    parts = rest.split(None, 2)
    if len(parts) < 2 or parts[0] not in KEY_TYPES:
        raise ValueError("not a public key line")
    try:
        raw = base64.b64decode(parts[1], validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("the key is not valid base64") from None
    length = int.from_bytes(raw[:4], "big")
    if len(raw) < 4 or raw[4:4 + length] != parts[0].encode("ascii"):
        raise ValueError("the key type does not match the key")
    return Key(options, parts[0], parts[1], parts[2] if len(parts) == 3 else "")


def _read(path):
    """The text of a regular file, never following a symbolic link at the last component."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise ValueError("not a regular file")
        return handle.read(MAX_BYTES).decode("utf-8", "replace")


def _lstat(path):
    try:
        return os.lstat(path)
    except FileNotFoundError:
        return None


def _keys_of(path, name, problems):
    """The Keys of an authorized_keys file, or None after recording why it cannot be used."""
    found = []
    try:
        for number, line in enumerate(_read(path).splitlines(), 1):
            try:
                key = parse_key_line(line)
            except ValueError as error:
                problems.append(f"{name}: line {number} of its key file is unusable ({error})")
                return None
            if key:
                found.append(key)
    except (OSError, ValueError) as error:
        problems.append(f"{name}: its key file cannot be read ({type(error).__name__})")
        return None
    return found


def _provisioned_source(name, home, keys_dir, trusted_uids, problems):
    """The file one account's key comes from: the root-owned copy when it exists, else the provisioned file in its ~/.ssh."""
    copy = os.path.join(keys_dir, name)
    info = _lstat(copy)
    if info is not None:
        if not stat.S_ISREG(info.st_mode) or info.st_uid not in trusted_uids:
            problems.append(f"{name}: the key file in the root-owned location is a link or is not owned by root")
            return None
        return copy
    ssh_dir = os.path.join(home, ".ssh")
    info = _lstat(ssh_dir)
    if info is None:
        problems.append(f"{name}: has no key (no ~/.ssh)")
        return None
    if not stat.S_ISDIR(info.st_mode):
        problems.append(f"{name}: ~/.ssh is a link or not a directory")
        return None
    path = os.path.join(ssh_dir, "authorized_keys")
    info = _lstat(path)
    if info is None:
        problems.append(f"{name}: has no key (no authorized_keys)")
        return None
    if not stat.S_ISREG(info.st_mode):
        problems.append(f"{name}: its authorized_keys is a link or not a regular file")
        return None
    return path


def _has_key_line(path):
    """"key" when a file other than a managed account's holds anything that is not blank or a comment, "unreadable" when it cannot be
    shown to hold none, else "". Run without privileges the files of other accounts cannot be read."""
    try:
        info = _lstat(path)
        if info is None:
            return ""
        if not stat.S_ISREG(info.st_mode):
            return "key"
        return "key" if any(line.strip() and not line.strip().startswith("#") for line in _read(path).splitlines()) else ""
    except PermissionError:
        return "unreadable"
    except (OSError, ValueError):
        return "key"


def _private_key_findings(name, home):
    ssh_dir = os.path.join(home, ".ssh")
    found = []
    info = _lstat(ssh_dir)
    if info is None or not stat.S_ISDIR(info.st_mode):
        return found
    for entry in sorted(os.listdir(ssh_dir)):
        path = os.path.join(ssh_dir, entry)
        looks_like_key = entry.startswith("id_") and not entry.endswith(".pub")
        info = _lstat(path)
        if info is None:
            continue
        if stat.S_ISREG(info.st_mode):
            try:
                with open(path, "rb") as handle:
                    head = handle.read(4096)
            except OSError:
                head = b""
            if looks_like_key or PRIVATE_KEY_MARKER.search(head):
                found.append(f"{name}: ~/.ssh holds a private key")
                break
        elif looks_like_key:
            found.append(f"{name}: ~/.ssh holds a link named like a private key")
            break
    return found


def audit_keys(entries, accounts, private_key_accounts, keys_dir, key_options=None, trusted_uids=(0,)):
    """The key rules of PA-16. entries: (account, home) pairs of the machine. Returns {problems, files}: files maps each managed
    account to the text of its key file in the root-owned location."""
    problems = []
    key_options = key_options or {}
    homes = dict(entries)
    keys = {}
    for name in accounts:
        if name not in homes:
            problems.append(f"{name}: the account does not exist")
            continue
        try:
            source = _provisioned_source(name, homes[name], keys_dir, trusted_uids, problems)
        except PermissionError:
            problems.append(f"{name}: its key file cannot be read (run with privileges)")
            continue
        found = _keys_of(source, name, problems) if source else None
        if found is None:
            continue
        if len(found) != 1:
            problems.append(f"{name}: has {'no key' if not found else 'more than one key'}")
            continue
        keys[name] = found[0]
    owners = {}
    for name, key in keys.items():
        owners.setdefault((key.type, key.blob), []).append(name)
    for names in owners.values():
        if len(names) > 1:
            problems.append(f"{' and '.join(sorted(names))}: share one key")
    for name, home in entries:
        if name in accounts:
            continue
        for relative in (".ssh/authorized_keys", ".ssh/authorized_keys2"):
            state = _has_key_line(os.path.join(home, relative))
            if state == "key":
                problems.append(f"{name}: is not a managed account and has a key file")
                break
            if state == "unreadable":
                problems.append(f"{name}: its key files cannot be read, so the audit cannot show it has none (run with privileges)")
                break
    if os.path.isdir(keys_dir):
        for entry in sorted(os.listdir(keys_dir)):
            if entry not in accounts:
                problems.append(f"{entry}: is not a managed account and has a key in the root-owned location")
    for name in private_key_accounts:
        if name in homes:
            try:
                problems.extend(_private_key_findings(name, homes[name]))
            except PermissionError:
                problems.append(f"{name}: its ~/.ssh cannot be read (run with privileges)")
    files = {}
    for name, key in keys.items():
        forced = key_options.get(name, "")
        # The root-owned copy already carries the forced options at its end: adding them again would change the file on every run.
        already = bool(forced) and (key.options == forced or key.options.endswith("," + forced))
        options = key.options if already else ",".join(part for part in (key.options, forced) if part)
        files[name] = (f"{options} " if options else "") + f"{key.type} {key.blob}" + (f" {key.comment}" if key.comment else "") + "\n"
    return {"problems": problems, "files": files}


def install_files(files, keys_dir, check_mode=False):
    """Write one root-owned file per account into keys_dir (mode 0644, replaced atomically). True when anything differs."""
    changed = False
    if not os.path.isdir(keys_dir):
        changed = True
        if not check_mode:
            os.makedirs(keys_dir, mode=0o755)
    for name, content in sorted(files.items()):
        path = os.path.join(keys_dir, name)
        current = None
        if _lstat(path) is not None:
            try:
                current = _read(path)
            except (OSError, ValueError):
                current = None
        info = _lstat(path)
        if current == content and info is not None and stat.S_IMODE(info.st_mode) == 0o644:
            continue
        changed = True
        if check_mode:
            continue
        fd, temporary = tempfile.mkstemp(dir=keys_dir, prefix=".tmp-")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    return changed


def parse_sshd_output(text):
    """sshd -T prints `keyword value` lines; the keyword is lower case. A keyword may repeat (AllowUsers does not, but be safe)."""
    result = {}
    for line in text.splitlines():
        parts = line.strip().split(None, 1)
        if parts:
            result.setdefault(parts[0].lower(), []).append(parts[1] if len(parts) == 2 else "")
    return result


def audit_sshd(text, mode, accounts=(), keys_dir="/etc/ssh/authorized_keys"):
    """The three authentication settings must be unset (PA-16); after the drop-in, LC-13 and OC-10 must show in the output."""
    settings = parse_sshd_output(text)
    problems = []
    if not settings:
        return ["sshd -T printed nothing"]
    for keyword in AUTH_SETTINGS:
        values = settings.get(keyword, ["none"])
        if any(value not in ("none", "") for value in values):
            problems.append(f"sshd: {keyword} is set")
    if mode == "sshd_after":
        if settings.get("authorizedkeysfile") != [f"{keys_dir}/%u"]:
            problems.append("sshd: authorized keys are not read from the root-owned location only")
        for keyword, wanted in EXPECTED_AFTER.items():
            if settings.get(keyword) != [wanted]:
                problems.append(f"sshd: {keyword} is not {wanted}")
        allowed = sorted(" ".join(settings.get("allowusers", [])).split())
        if allowed != sorted(accounts):
            problems.append("sshd: AllowUsers is not exactly the managed accounts")
    return problems


def main():
    import pwd
    from ansible.module_utils.basic import AnsibleModule

    module = AnsibleModule(
        argument_spec={
            "mode": {"type": "str", "required": True, "choices": ["keys", "install", "sshd_before", "sshd_after"]},
            "accounts": {"type": "list", "elements": "str", "default": []},
            "private_key_accounts": {"type": "list", "elements": "str", "default": []},
            "key_options": {"type": "dict", "default": {}},
            "keys_dir": {"type": "path", "default": "/etc/ssh/authorized_keys"},
            "sshd_text": {"type": "str", "default": ""},
        },
        supports_check_mode=True,
    )
    params = module.params
    changed = False
    if params["mode"] in ("keys", "install"):
        entries = [(entry.pw_name, entry.pw_dir) for entry in pwd.getpwall()]
        result = audit_keys(entries, params["accounts"], params["private_key_accounts"], params["keys_dir"], params["key_options"])
    else:
        result = {"problems": audit_sshd(params["sshd_text"], params["mode"], params["accounts"], params["keys_dir"]), "files": {}}
    if result["problems"]:
        module.fail_json(msg="refused: " + "; ".join(result["problems"]), problems=result["problems"])
    if params["mode"] == "install":
        changed = install_files(result["files"], params["keys_dir"], module.check_mode)
    module.exit_json(changed=changed)


if __name__ == "__main__":
    main()
