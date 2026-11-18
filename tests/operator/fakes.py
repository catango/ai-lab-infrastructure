"""Fakes for the facts tests: a system with canned files and a command runner that records its calls."""
import helpers  # noqa: F401
from operator_lib import process

ADDRESS = "192.0.2.77"
ACCOUNT = "canaryaccount"
OTHER_ACCOUNT = "othercanary"
HOSTNAME = "canary-host-01"
BOOT_ID = "11111111-2222-3333-4444-555555555555"

PASSWD = (f"root:x:0:0:root:/root:/bin/bash\n{ACCOUNT}:x:1000:1000::/home/{ACCOUNT}:/bin/bash\n"
          f"{OTHER_ACCOUNT}:x:1001:1001::/home/{OTHER_ACCOUNT}:/bin/bash\nsvc:x:998:998::/nonexistent:/usr/sbin/nologin\n"
          "nobody:x:65534:65534:nobody:/nonexistent:/usr/sbin/nologin\n")
GROUP = f"root:x:0:\nsudo:x:27:{ACCOUNT},{OTHER_ACCOUNT}\nadmin:x:999:{ACCOUNT}\nusers:x:100:\n"
TCP = ("  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode\n"
       "   0: 00000000:0016 00000000:0000 0A 00000000:00000000 00:00000000 00000000     0        0 1 1 0\n"
       "   1: 0100007F:1F90 00000000:0000 0A 00000000:00000000 00:00000000 00000000     0        0 2 1 0\n"
       "   2: 0100007F:D431 0100007F:1F90 01 00000000:00000000 00:00000000 00000000     0        0 3 1 0\n")
TCP6 = ("  sl  local_address                         remote_address                        st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode\n"
        "   0: 00000000000000000000000000000000:0016 00000000000000000000000000000000:0000 0A 00000000:00000000 00:00000000 00000000     0        0 4 1 0\n")
DPKG = "".join(f"Package: p{n}\nStatus: install ok installed\n\n" for n in range(7))
FILES = {
    "/etc/os-release": 'NAME="Ubuntu"\nID=ubuntu\nVERSION_ID="24.04"\n',
    "/proc/meminfo": "MemTotal:        1006904 kB\nMemFree: 1 kB\nSwapTotal:        524288 kB\n",
    "/proc/sys/kernel/osrelease": "6.8.0-1017-oracle\n",
    "/proc/sys/kernel/random/boot_id": BOOT_ID + "\n",
    "/etc/passwd": PASSWD,
    "/etc/group": GROUP,
    "/proc/net/tcp": TCP,
    "/proc/net/tcp6": TCP6,
    "/var/lib/dpkg/status": DPKG,
    "/run/systemd/timesync/synchronized": "",
    "/etc/ufw/ufw.conf": "ENABLED=yes\n",
    "/etc/hostname": HOSTNAME + "\n",
}


class FakeSystem:
    def __init__(self, files=None, dirs=("/run/systemd/timesync",)):
        self.files = dict(FILES if files is None else files)
        self.dirs = set(dirs)
        self.reads = []
        self.boot_id = BOOT_ID

    def read(self, path, limit=1_048_576):
        self.reads.append(path)
        if path == "/proc/sys/kernel/random/boot_id":
            return self.boot_id + "\n"
        return self.files.get(path)

    def exists(self, path):
        return path in self.files or path in self.dirs

    def statvfs(self, path):
        return (50 * 1024**3, 30 * 1024**3)

    def cpu_count(self):
        return 2

    def machine(self):
        return "x86_64"

    def python_version(self):
        return "3.13"


SSHD_T = (f"port 22\nlistenaddress {ADDRESS}:22\nlistenaddress [::]:22\npermitrootlogin without-password\n"
          f"passwordauthentication no\npubkeyauthentication yes\nallowusers {ACCOUNT}\n")
NFT = (f"table inet filter {{\n\tchain input {{\n\t\ttype filter hook input priority filter; policy drop;\n"
       f"\t\tip saddr {ADDRESS} tcp dport 22 accept\n\t}}\n\tchain forward {{\n\t\ttype filter hook forward priority filter; policy accept;\n\t}}\n}}\n"
       "table ip nat {\n\tchain postrouting {\n\t\ttype nat hook postrouting priority srcnat; policy accept;\n\t}\n}\n")
SUDOERS_D = "/etc/sudoers.d\n/etc/sudoers.d/90-cloud-init-users\n/etc/sudoers.d/README\n"


class FakeRunner:
    """Records every call. Returns canned output for known commands and a missing command for the rest."""

    def __init__(self, canned=None, git_version="git version 2.43.0\n"):
        self.calls = []
        self.canned = {
            ("git", "--version"): (0, git_version),
            ("sudo", "sshd", "-T"): (0, SSHD_T),
            ("sudo", "nft", "list", "ruleset"): (0, NFT),
            ("sudo", "find", "/etc/sudoers.d", "-maxdepth", "1", "-type", "f"): (0, SUDOERS_D),
            ("sudo", "-n", "true"): (1, ""),
        }
        self.canned.update(canned or {})

    def __call__(self, argv, **kw):
        self.calls.append((tuple(argv), kw))
        if tuple(argv) not in self.canned:
            raise process.CommandMissing("command not found or not executable")
        code, out = self.canned[tuple(argv)]
        return process.Result(code, out, "", False)

    def privileged(self):
        return [argv for argv, _ in self.calls if argv[0] == "sudo"]
