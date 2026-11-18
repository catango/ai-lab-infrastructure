"""Host facts (design section 5.1, scope host): what a machine can say about itself, as yes/no, counts, sizes, and versions.

Everything is read from /proc and /etc through a System object (so that tests can supply files), or from `git --version`.
Nothing here prints an address, account name, hostname, or key. The privileged facts are parsed from command output that the
facts script obtains, and only counts and yes/no leave this module.
"""
import hashlib
import ipaddress
import json
import os
import platform
import re
import secrets

from . import process, profiles
from .rawdir import RawDir

READ_LIMIT = 1_048_576
STATE_NAME = "state.json"
MAX_HASHES = 50
UNKNOWN = "unknown"
_VERSION_PREFIX = re.compile(r"[0-9]+\.[0-9]+")
_GIT_VERSION = re.compile(r"git version ([0-9]+\.[0-9]+(?:\.[0-9]+)?)")
_SUDO_GROUPS = ("sudo", "admin", "wheel")


class RealSystem:
    """Reads fixed system paths. Symlinks are followed on purpose: /etc/os-release is one on Ubuntu. The operator's own
    state files are read elsewhere (State, write_allowlist) and are never followed through a symlink."""

    def read(self, path, limit=READ_LIMIT):
        try:
            fd = os.open(path, os.O_RDONLY)
        except OSError:
            return None
        try:
            with os.fdopen(fd, "rb") as handle:
                return handle.read(limit).decode("utf-8", errors="replace")
        except OSError:
            return None

    def exists(self, path):
        return os.path.lexists(path)

    def statvfs(self, path):
        try:
            info = os.statvfs(path)
        except OSError:
            return None
        return info.f_frsize * info.f_blocks, info.f_frsize * info.f_bavail

    def cpu_count(self):
        return os.cpu_count()

    def machine(self):
        return platform.machine()

    def python_version(self):
        return ".".join(platform.python_version_tuple()[:2])


def yes_no(value):
    return UNKNOWN if value is None else ("yes" if value else "no")


def _kb(text, key):
    match = re.search(rf"^{key}:\s+([0-9]+) kB", text or "", re.M)
    return int(match.group(1)) // 1024 if match else None


def _passwd_logins(text):
    count = 0
    for line in (text or "").splitlines():
        parts = line.split(":")
        if len(parts) >= 7 and parts[2].isdigit() and 1000 <= int(parts[2]) < 65534 and not parts[6].endswith(("nologin", "false")):
            count += 1
    return count


def _sudo_members(text):
    members = set()
    for line in (text or "").splitlines():
        parts = line.split(":")
        if len(parts) >= 4 and parts[0] in _SUDO_GROUPS:
            members.update(m for m in parts[3].split(",") if m)
    return len(members)


def _listening_ports(system):
    ports = set()
    for name in ("/proc/net/tcp", "/proc/net/tcp6"):
        for line in (system.read(name) or "").splitlines()[1:]:
            fields = line.split()
            if len(fields) > 3 and fields[3] == "0A" and ":" in fields[1]:
                try:
                    ports.add(int(fields[1].rsplit(":", 1)[1], 16))
                except ValueError:
                    continue
    return ports


def os_name(system):
    text = system.read("/etc/os-release") or ""
    ident = re.search(r'^ID=("?)([a-z]+)\1$', text, re.M)
    version = re.search(r'^VERSION_ID="?([0-9.]+)"?$', text, re.M)
    return f"{ident.group(2)}-{version.group(1)}" if ident and version else None


def arch_name(system):
    return {"x86_64": "x86-64", "amd64": "x86-64", "aarch64": "arm64", "arm64": "arm64"}.get(system.machine())


def git_facts(runner):
    try:
        result = runner(["git", "--version"], allow=frozenset({"git"}), timeout=15)
    except (process.CommandMissing, process.CommandTimeout, process.PolicyViolation):
        return {"git_present": "no"}
    match = _GIT_VERSION.search(result.stdout) if result.returncode == 0 else None
    return {"git_present": "yes", "git_version": match.group(1)} if match else {"git_present": "no"}


def collect_host(system, runner):
    """The host facts that need no state and no privilege, in output order."""
    facts = {"python_version": system.python_version()}
    kernel = _VERSION_PREFIX.match(system.read("/proc/sys/kernel/osrelease") or "")
    facts["kernel_version"] = kernel.group(0) if kernel else UNKNOWN
    facts.update(git_facts(runner))
    meminfo = system.read("/proc/meminfo")
    facts["memory_mb"] = _kb(meminfo, "MemTotal")
    facts["swap_mb"] = _kb(meminfo, "SwapTotal")
    facts["cpu_threads"] = system.cpu_count()
    disk = system.statvfs("/")
    facts["disk_gb_total"] = disk[0] // 1024**3 if disk else None
    facts["disk_gb_free"] = disk[1] // 1024**3 if disk else None
    if system.exists("/run/systemd/timesync/synchronized"):
        facts["ntp_synchronized"] = "yes"
    elif system.exists("/run/systemd/timesync"):
        facts["ntp_synchronized"] = "no"
    else:
        facts["ntp_synchronized"] = UNKNOWN
    facts["login_accounts"] = _passwd_logins(system.read("/etc/passwd")) if system.read("/etc/passwd") is not None else None
    facts["sudo_group_members"] = _sudo_members(system.read("/etc/group")) if system.read("/etc/group") is not None else None
    ports = _listening_ports(system)
    facts["listening_tcp_ports"] = len(ports)
    facts["ssh_listening"] = yes_no(22 in ports)
    facts["firewall_nftables_enabled"] = yes_no(system.exists("/etc/systemd/system/multi-user.target.wants/nftables.service"))
    ufw = system.read("/etc/ufw/ufw.conf")
    facts["firewall_ufw_enabled"] = UNKNOWN if ufw is None else yes_no(re.search(r"^ENABLED=yes\s*$", ufw, re.M) is not None)
    dpkg = system.read("/var/lib/dpkg/status", limit=64 * 1024 * 1024)
    facts["installed_packages"] = None if dpkg is None else len(re.findall(r"^Package: ", dpkg, re.M))
    return {key: (UNKNOWN if value is None else value) for key, value in facts.items()}


def egress_address(environ):
    """The client address from $SSH_CLIENT, or None. Never printed."""
    parts = str(environ.get("SSH_CLIENT", "")).split()
    if len(parts) != 3:
        return None
    try:
        return str(ipaddress.ip_address(parts[0]))
    except ValueError:
        return None


class State:
    """Local state in a private directory: a salt, hashes of the egress addresses seen, a run count, and the boot ID."""

    def __init__(self, directory):
        self.dir = RawDir(directory, cap_bytes=64 * 1024)
        self.data = self._load()
        self.fresh = not self.data
        self.data.setdefault("version", 1)
        self.data.setdefault("salt", secrets.token_hex(16))
        self.data.setdefault("hashes", [])
        self.data.setdefault("runs", 0)
        self.data.setdefault("observations", 0)
        self.data.setdefault("persisted", False)

    def _load(self):
        path = os.path.join(self.dir.path, STATE_NAME)
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, "rb") as handle:
                data = json.loads(handle.read(65536).decode("utf-8"))
        except (OSError, ValueError, UnicodeDecodeError):
            return {}
        if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("hashes"), list) \
                or not all(isinstance(h, str) and re.fullmatch(r"[0-9a-f]{16}", h) for h in data["hashes"]) \
                or not isinstance(data.get("salt"), str) or not re.fullmatch(r"[0-9a-f]{32}", data["salt"]) \
                or not all(isinstance(data.get(k, 0), int) for k in ("runs", "observations")):
            return {}
        return data

    def record(self, system, address):
        """Update the state for this run and return the facts that depend on it."""
        data = self.data
        data["runs"] += 1
        boot = (system.read("/proc/sys/kernel/random/boot_id") or "").strip()
        previous = data.get("boot_id")
        if previous and boot and previous != boot:
            data["persisted"] = True
        if boot:
            data["boot_id"] = boot
        if address:
            digest = hashlib.sha256(bytes.fromhex(data["salt"]) + address.encode()).hexdigest()[:16]
            data["observations"] += 1
            if digest not in data["hashes"]:
                data["hashes"] = (data["hashes"] + [digest])[-MAX_HASHES:]
        distinct = len(data["hashes"])
        if address is None or data["observations"] < 2:
            stable = UNKNOWN
        else:
            stable = yes_no(distinct == 1)
        return {"runs": data["runs"], "home_persists": "yes" if data["persisted"] else UNKNOWN, "egress_known": yes_no(address is not None),
                "egress_distinct": distinct, "egress_stable": stable}

    def save(self):
        self.dir.write(STATE_NAME, json.dumps(self.data, sort_keys=True).encode("utf-8"))


def parse_sshd(text):
    """From `sshd -T` output: only yes/no and a count. Addresses and user lists are never read out."""
    settings = {}
    ports = 0
    for line in (text or "").splitlines():
        key, _, value = line.partition(" ")
        if key == "port":
            ports += 1
        elif key in ("passwordauthentication", "permitrootlogin", "pubkeyauthentication"):
            settings[key] = value.strip()
    return {
        "sshd_password_auth_off": yes_no(settings["passwordauthentication"] == "no") if "passwordauthentication" in settings else UNKNOWN,
        "sshd_root_login_off": yes_no(settings["permitrootlogin"] == "no") if "permitrootlogin" in settings else UNKNOWN,
        "sshd_pubkey_auth_on": yes_no(settings["pubkeyauthentication"] == "yes") if "pubkeyauthentication" in settings else UNKNOWN,
        "sshd_port_count": ports if ports else UNKNOWN,
    }


def parse_nft(text):
    """From `nft list ruleset`: counts of tables and chains, and whether an input chain drops by default."""
    lines = [line.strip() for line in (text or "").splitlines()]
    return {
        "nft_tables": sum(1 for line in lines if line.startswith("table ")),
        "nft_chains": sum(1 for line in lines if line.startswith("chain ")),
        "nft_input_policy_drop": yes_no(any(re.search(r"hook input\b[^;]*;\s*policy drop", line) for line in lines)),
    }


def count_sudoers_d(text):
    return sum(1 for line in (text or "").splitlines() if line.startswith("/etc/sudoers.d/"))


def profile_entry(system, facts):
    """The machine-profile entry (design section 3.3): only keys whose values pass the profile validation."""
    candidate = {"arch": arch_name(system), "os": os_name(system), "memory_mb": facts.get("memory_mb"), "cpu_threads": facts.get("cpu_threads"),
                 "disk_gb": facts.get("disk_gb_total"), "bandwidth_mbit": facts.get("bandwidth_mbit")}
    entry = {}
    for key, value in candidate.items():
        if value is None or value == UNKNOWN:
            continue
        try:
            profiles.check_entry("host", {key: value})
        except profiles.ProfileError:
            continue
        entry[key] = value
    return entry


def render_toml(entry):
    return [f'{key} = "{value}"' if isinstance(value, str) else f"{key} = {value}" for key, value in entry.items()]


def write_allowlist(home, address):
    """Add the address to the operator-local allowlist (outside the clone, mode 600). Returns the number of entries."""
    directory = RawDir(os.path.join(home, ".config", "operator"), cap_bytes=64 * 1024)
    path = os.path.join(directory.path, "ssh-allowlist")
    entries = set()
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as handle:
            for line in handle.read(65536).decode("utf-8", errors="replace").split():
                try:
                    entries.add(str(ipaddress.ip_address(line)))
                except ValueError:
                    continue
    except OSError:
        pass
    entries.add(address)
    directory.write("ssh-allowlist", ("\n".join(sorted(entries)) + "\n").encode("utf-8"))
    return len(entries)


def state_dir(home):
    return os.path.join(home, ".local", "state", "operator", "facts")
