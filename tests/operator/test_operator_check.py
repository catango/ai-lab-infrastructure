"""CR-57 PA-A14, PA-A18, PA-A26, PA-A30: the operator check (OC-1 to OC-12) and the run launcher, against a fake machine.

The machine is a temporary tree (an /etc, homes, a prefix with the installation, a state directory, a process table); commands that
need root, the network, or a package manager (sudo, dpkg-query, apt-config, sshd -T) are answered by a small fake. Nothing here needs
root. The PA-28 job runs the installed check as the operator user on a real Debian 13 (tests/ansible/pa28-operator.sh).
"""
import base64
import fcntl
import hashlib
import importlib.machinery
import importlib.util
import os
import pathlib
import pwd
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import helpers
from helpers import ROOT

TOOLS = ROOT / "ansible" / "roles" / "operator_tools" / "files"
SSH_MODULE = ROOT / "ansible" / "roles" / "ssh_hardening" / "library" / "ssh_hardening_audit.py"
ME = os.getuid()
AT = helpers.AT
COMMIT = "a" * 40
TOKEN = "gh" + "p_" + "A" * 24  # assembled at run time: no token-shaped text in the repository


def load(name, path):
    sys.dont_write_bytecode = True
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


operator_check = load("operator_check", TOOLS / "operator-check")
operator_run = load("operator_run", TOOLS / "operator-run")
audit = load("ssh_hardening_audit", SSH_MODULE)


def key_line(seed, options="", comment=""):
    name = b"ssh-ed25519"
    raw = struct.pack(">I", len(name)) + name + struct.pack(">I", 32) + bytes([seed]) * 32
    return " ".join(part for part in (options, "ssh-ed25519", base64.b64encode(raw).decode(), comment) if part) + "\n"


def tree_hash(path):
    """A hash of names, types, modes, and contents under path (the check is read-only: the tree must be the same after a run)."""
    digest = hashlib.sha256()
    for current, dirs, files in os.walk(path):
        dirs.sort()
        for name in sorted(dirs + files):
            full = os.path.join(current, name)
            info = os.lstat(full)
            digest.update(f"{os.path.relpath(full, path)} {stat.S_IFMT(info.st_mode)} {stat.S_IMODE(info.st_mode)}\n".encode())
            if stat.S_ISREG(info.st_mode):
                digest.update(pathlib.Path(full).read_bytes())
    return digest.hexdigest()


class Machine:
    """An operator machine as the check sees it, in a temporary directory. Every attribute can be changed before check() is called."""

    def __init__(self, test):
        tmp = tempfile.TemporaryDirectory()
        test.addCleanup(tmp.cleanup)
        self.test = test
        self.base = pathlib.Path(tmp.name)
        self.root = self.base / "root"
        self.prefix = self.base / "prefix"
        self.state = self.base / "state"
        self.home = self.base / "home" / "op"
        self.admin_home = self.base / "home" / "opadm"
        self.proc = self.base / "proc"
        self.sudo = (1, "Sorry, user op may not run sudo on this machine.")
        self.packages = (0, "install ok installed")
        self.apt = 'APT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Unattended-Upgrade "1";\n'
        self.git = (0, "git version 2.47.3")
        self.sshd_direct = None
        self.environ = {"PATH": "/usr/bin"}
        self.groups = ["op"]
        for directory in (self.root / "etc" / "ssh" / "authorized_keys", self.root / "etc" / "ssh" / "sshd_config.d", self.root / "proc",
                          self.prefix / "operator" / "projects", self.state / "output", self.home, self.admin_home, self.proc):
            directory.mkdir(parents=True)
        for current, dirs, _ in os.walk(self.base):  # the umask of the test run must not make a directory group-writable
            for name in dirs:
                os.chmod(os.path.join(current, name), 0o755)
        os.chmod(self.base, 0o755)
        self.write(self.root / "etc" / "os-release", 'ID=debian\nVERSION_ID="13"\n')
        self.write(self.root / "proc" / "mounts", "overlay / overlay rw 0 0\nproc /proc proc rw 0 0\n")
        self.write(self.root / "etc" / "ssh" / "authorized_keys" / "op", key_line(1, "", "op"))
        self.write(self.root / "etc" / "ssh" / "authorized_keys" / "opadm", key_line(2, "", "adm"))
        self.write(self.root / "etc" / "ssh" / "sshd_config", "Include /etc/ssh/sshd_config.d/*.conf\nKbdInteractiveAuthentication no\n"
                   "UsePAM yes\nX11Forwarding yes\nPrintMotd no\nAcceptEnv LANG LC_*\nSubsystem sftp /usr/lib/openssh/sftp-server\n")
        self.write(self.root / "etc" / "ssh" / "sshd_config.d" / "00-ai-lab.conf",
                   "PubkeyAuthentication yes\nPasswordAuthentication no\nAllowUsers op opadm\nMACs -hmac-sha1*\n")
        self.write(self.prefix / "operator" / "operator.conf",
                   f"operator_user=op\nadmin_user=opadm\nrelease_tag=v1.2.3\nrelease_commit={COMMIT}\n")
        self.write(self.state / "run.lock", "", 0o600)
        self.add_project("platform")
        self.record_sshd()

    @staticmethod
    def write(path, text, mode=0o644):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        path.chmod(mode)

    def add_project(self, name, tag="v1.2.3", commit=COMMIT, contained="yes", output=True):
        directory = self.prefix / "operator" / "projects" / name
        (directory / "scripts" / "operator").mkdir(parents=True)
        for path in (directory, directory / "scripts", directory / "scripts" / "operator"):
            path.chmod(0o755)
        self.write(directory / "RELEASE", f"project={name}\nrelease_tag={tag}\nrelease_commit={commit}\ncontained_in_origin_main={contained}\n")
        self.write(directory / "scripts" / "operator" / "facts", "#!/bin/sh\nexit 0\n", 0o755)
        if output:
            (self.state / "output" / name).mkdir(parents=True)
            (self.state / "output" / name).chmod(0o700)
        return directory

    def sshd_text(self):
        keys = f"{self.root}/etc/ssh/authorized_keys/%u"
        return "\n".join(["pubkeyauthentication yes", "passwordauthentication no", "kbdinteractiveauthentication no",
                          "permitrootlogin no", "authenticationmethods publickey", f"authorizedkeysfile {keys}", "authorizedkeyscommand none",
                          "trustedusercakeys none", "authorizedprincipalsfile none", "allowagentforwarding no", "allowtcpforwarding no",
                          "x11forwarding no", "permittunnel no", "permituserrc no", "permituserenvironment no", "allowusers op",
                          "allowusers opadm", "kexalgorithms mlkem768x25519-sha256,curve25519-sha256",
                          f"macs hmac-sha2-256-etm{AT}openssh.com"]) + "\n"

    def record_sshd(self, text=None):
        path = self.root / "etc" / "ssh" / "ai-lab-sshd-effective.txt"
        path.unlink(missing_ok=True)
        ssh = str(self.root / "etc" / "ssh")
        audit.write_snapshot(str(path), text or self.sshd_text(), audit.config_digest(ssh), stat_digest=audit.config_stat_digest(ssh))

    def process(self, pid, names, command):
        directory = self.proc / str(pid)
        directory.mkdir(parents=True)
        (directory / "environ").write_bytes(b"\0".join(f"{name}=value".encode() for name in names) + b"\0")
        (directory / "cmdline").write_bytes(b"\0".join(part.encode() for part in command) + b"\0")

    def run(self, argv, env=None, cwd="/", timeout=0):
        command = os.path.basename(argv[0])
        if command == "git":
            return self.git
        if command == "sudo":
            return self.sudo
        if command == "dpkg-query":
            return self.packages
        if command == "apt-config":
            return 0, self.apt
        if command == "systemctl":
            return 0, "enabled\n"
        if command == "sshd":
            return self.sshd_direct if self.sshd_direct is not None else (1, "sshd: no hostkeys available -- exiting.")
        return 127, "unexpected command"

    @property
    def op(self):
        if not hasattr(self, "_op"):
            conf = operator_check.read_conf(str(self.prefix / "operator" / "operator.conf"))
            homes = {"op": str(self.home), "opadm": str(self.admin_home)}
            self._op = operator_check.Operator(audit, conf, "op", str(self.home), root=str(self.root), prefix=str(self.prefix),
                                               state=str(self.state), environ=self.environ, run=self.run, machine="x86_64",
                                               trusted_uids=(ME,), groups=self.groups, home_of=lambda name: homes[name],
                                               homes=lambda: dict(homes), systemd=False, proc=str(self.proc), own_pid=1)
        return self._op

    def check(self, item):
        return getattr(self.op, item.lower().replace("-", ""))()


class Case(unittest.TestCase):
    def machine(self):
        return Machine(self)

    def assertPass(self, results):
        self.assertEqual([status for status, _ in results], ["PASS"], results)

    def assertFail(self, results, text=""):
        self.assertIn("FAIL", [status for status, _ in results], results)
        self.assertIn(text, " ".join(detail for _, detail in results))


class WholeCheck(Case):
    ITEMS = {"OC-1", "OC-2", "OC-6", "OC-8", "OC-10", "OC-11", "OC-12", "PA-42", "PA-13"}

    def test_a_good_machine_passes_every_item_and_checks_no_declared_item(self):
        results = self.machine().op.check_all()
        self.assertEqual({status for status, _, _ in results}, {"PASS"}, results)
        self.assertEqual({item for _, item, _ in results}, self.ITEMS)
        for declared in ("OC-3", "OC-4", "OC-5", "OC-7", "OC-9"):
            self.assertNotIn(declared, self.ITEMS)

    def test_it_changes_nothing(self):
        """PA-A14: the tree hash before and after a run is equal."""
        machine = self.machine()
        before = tree_hash(machine.base)
        machine.op.check_all()
        self.assertEqual(tree_hash(machine.base), before)

    def test_a_broken_check_is_a_failure_never_a_pass(self):
        machine = self.machine()
        machine.op.oc8 = lambda: 1 / 0
        results = [r for r in machine.op.check_all() if r[1] == "OC-8"]
        self.assertEqual(results[0][0], "FAIL")

    def test_it_prints_no_secret(self):
        machine = self.machine()
        machine.environ = {"PATH": "/usr/bin", "GH_TOKEN": "canary-token-value"}
        text = " ".join(detail for _, _, detail in machine.op.check_all())
        self.assertNotIn("canary", text)
        self.assertIn("GH_TOKEN", text)


class PerItem(Case):
    def test_oc1_no_claude_directory_in_any_readable_home_and_no_shared_mount(self):
        machine = self.machine()
        self.assertPass(machine.check("OC-1"))
        (machine.home / ".claude").mkdir()
        self.assertFail(machine.check("OC-1"), "op has a ~/.claude/")
        (machine.home / ".claude").rmdir()
        (machine.admin_home / ".claude").mkdir()
        self.assertFail(machine.check("OC-1"), "opadm has a ~/.claude/")

    def test_oc1_a_private_home_is_a_warning_not_a_pass_for_that_home(self):
        machine = self.machine()
        machine.admin_home.chmod(0o000)
        self.addCleanup(machine.admin_home.chmod, 0o755)
        if os.access(machine.admin_home, os.R_OK | os.X_OK):
            self.skipTest("this account can read a mode 000 directory (root)")
        results = machine.check("OC-1")
        self.assertIn("WARN", [status for status, _ in results])
        self.assertNotIn("FAIL", [status for status, _ in results])

    def test_oc1_a_network_or_host_shared_mount_fails(self):
        for fstype in ("nfs4", "cifs", "9p", "virtiofs", "fuse.sshfs"):
            with self.subTest(fstype=fstype):
                machine = self.machine()
                machine.write(machine.root / "proc" / "mounts", f"share /mnt/x {fstype} rw 0 0\n")
                self.assertFail(machine.check("OC-1"), "mount")

    def test_oc2_an_installation_per_project_at_a_release_tag_contained_in_origin_main(self):
        machine = self.machine()
        self.assertPass(machine.check("OC-2"))
        self.assertIn("platform", machine.check("OC-2")[0][1])

    def test_oc2_two_projects_are_both_checked_pa_a30(self):
        machine = self.machine()
        machine.add_project("second-project", tag="v2.0.0")
        results = machine.check("OC-2")
        self.assertPass(results)
        self.assertIn("2 project(s)", results[0][1])
        machine.add_project("third", tag="nightly", output=False)
        self.assertFail(machine.check("OC-2"), "third: RELEASE names no release tag")

    def test_oc2_every_way_an_installation_can_be_wrong(self):
        cases = {
            "no project": (lambda m: [import_rmtree(m.prefix / "operator" / "projects" / "platform")], "no project is installed"),
            "a directory others can write": (lambda m: (m.prefix / "operator" / "projects" / "platform").chmod(0o777), "writable by others"),
            "a script others can write": (lambda m: (m.prefix / "operator" / "projects" / "platform" / "scripts" / "operator" / "facts")
                                          .chmod(0o777), "scripts/operator/facts is writable by others"),
            "no marker": (lambda m: (m.prefix / "operator" / "projects" / "platform" / "RELEASE").unlink(), "RELEASE does not exist"),
            "a marker of another project": (lambda m: m.write(m.prefix / "operator" / "projects" / "platform" / "RELEASE",
                                                              f"project=other\nrelease_tag=v1.0.0\nrelease_commit={COMMIT}\n"
                                                              "contained_in_origin_main=yes\n"), "names another project"),
            "a commit that is not a hash": (lambda m: m.write(m.prefix / "operator" / "projects" / "platform" / "RELEASE",
                                                              "project=platform\nrelease_tag=v1.0.0\nrelease_commit=abc\n"
                                                              "contained_in_origin_main=yes\n"), "names no commit"),
            "a release not contained in origin/main": (lambda m: m.write(m.prefix / "operator" / "projects" / "platform" / "RELEASE",
                                                                         f"project=platform\nrelease_tag=v1.0.0\nrelease_commit={COMMIT}\n"
                                                                         "contained_in_origin_main=no\n"), "not recorded as contained"),
            "owned by someone else": (lambda m: setattr(m.op, "trusted", (ME + 1,)), "not owned by root"),
        }
        for name, (change, text) in cases.items():
            with self.subTest(name=name):
                machine = self.machine()
                change(machine)
                self.assertFail(machine.check("OC-2"), text)

    def test_oc6_debian_13_on_x86_64_with_python_3_and_git(self):
        machine = self.machine()
        self.assertPass(machine.check("OC-6"))
        machine.op.machine = "aarch64"
        self.assertFail(machine.check("OC-6"), "x86_64")
        machine.op.machine = "x86_64"
        machine.write(machine.root / "etc" / "os-release", 'ID=ubuntu\nVERSION_ID="24.04"\n')
        self.assertFail(machine.check("OC-6"), "Debian 13")
        machine.write(machine.root / "etc" / "os-release", 'ID=debian\nVERSION_ID="13"\n')
        machine.git = (127, "FileNotFoundError")
        self.assertFail(machine.check("OC-6"), "git is not installed")

    def test_oc8_the_operator_user_has_no_sudo(self):
        machine = self.machine()
        self.assertPass(machine.check("OC-8"))
        machine.sudo = (0, "")
        self.assertFail(machine.check("OC-8"), "sudo -n true succeeds")

    def test_oc8_a_password_prompt_cannot_tell_a_rule_from_no_rule_so_it_is_a_warning(self):
        machine = self.machine()
        machine.sudo = (1, "sudo: a password is required")
        results = machine.check("OC-8")
        self.assertEqual([status for status, _ in results], ["WARN"], results)
        self.assertIn("sudo -l -U", results[0][1])
        machine.op.groups = ["op", "sudo"]
        self.assertFail(machine.check("OC-8"), "sudo")  # a root-equivalent group still fails whatever sudo answers

    def test_oc8_a_root_equivalent_group_fails(self):
        for group in ("sudo", "docker", "lxd", "disk", "adm" if False else "wheel"):
            with self.subTest(group=group):
                machine = self.machine()
                machine.op.groups = ["op", group]
                self.assertFail(machine.check("OC-8"), group)

    def test_oc10_the_lc13_settings_for_both_accounts(self):
        machine = self.machine()
        results = machine.check("OC-10")
        self.assertEqual([s for s, _ in results], ["PASS"], results)
        machine.write(machine.root / "etc" / "ssh" / "sshd_config.d" / "50-stray.conf", "ClientAliveInterval 5\n")
        self.assertFail(machine.check("OC-10"), "")  # a stray option, or a configuration that changed after the snapshot
        (machine.root / "etc" / "ssh" / "sshd_config.d" / "50-stray.conf").unlink()
        self.assertEqual([s for s, _ in machine.check("OC-10")], ["PASS"])

    @unittest.skipIf(os.geteuid() == 0, "root reads every file")
    def test_oc10_a_config_file_this_account_cannot_read_is_a_warning_and_never_a_crash(self):
        machine = self.machine()
        provider = machine.root / "etc" / "ssh" / "sshd_config.d" / "60-provider.conf"
        machine.write(provider, "# provider\n", 0o000)
        machine.record_sshd()
        results = machine.check("OC-10")
        self.assertEqual(sorted(status for status, _ in results), ["PASS", "WARN"], results)
        provider.chmod(0o600)
        provider.write_text("# provider\n# changed\n")
        provider.chmod(0o000)
        self.assertFail(machine.check("OC-10"), "changed after")
        provider.chmod(0o600)

    def test_oc10_sshd_reading_keys_from_anywhere_else_fails(self):
        machine = self.machine()
        text = machine.sshd_text().replace(f"authorizedkeysfile {machine.root}/etc/ssh/authorized_keys/%u",
                                           "authorizedkeysfile .ssh/authorized_keys")
        machine.sshd_direct = (0, text)
        self.assertFail(machine.check("OC-10"), "")
        machine.sshd_direct = (0, machine.sshd_text() + "authorizedkeyscommand /bin/true\n")
        self.assertFail(machine.check("OC-10"), "")

    def test_oc10_an_inert_authorized_keys_file_in_a_home_is_only_a_warning(self):
        machine = self.machine()
        (machine.home / ".ssh").mkdir()
        (machine.home / ".ssh" / "authorized_keys").write_text(key_line(1))
        results = machine.check("OC-10")
        self.assertEqual(sorted(s for s, _ in results), ["PASS", "WARN"], results)

    def test_oc11_different_keys(self):
        machine = self.machine()
        self.assertPass(machine.check("OC-11"))
        machine.write(machine.root / "etc" / "ssh" / "authorized_keys" / "opadm", key_line(1, "", "op"))
        self.assertFail(machine.check("OC-11"), "share one key")
        (machine.root / "etc" / "ssh" / "authorized_keys" / "opadm").unlink()
        self.assertFail(machine.check("OC-11"), "does not exist")

    def test_oc12_unattended_security_updates_are_configured(self):
        machine = self.machine()
        self.assertPass(machine.check("OC-12"))
        machine.packages = (1, "")
        self.assertFail(machine.check("OC-12"), "not installed")
        machine.packages = (0, "install ok installed")
        machine.apt = 'APT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Unattended-Upgrade "0";\n'
        self.assertFail(machine.check("OC-12"), "Unattended-Upgrade is not 1")
        machine.apt = ""
        self.assertFail(machine.check("OC-12"), "Update-Package-Lists is not 1")

    def test_pa42_one_output_directory_per_project_mode_0700_and_the_run_lock(self):
        machine = self.machine()
        self.assertPass(machine.check("PA-42"))
        machine.add_project("second-project")
        self.assertPass(machine.check("PA-42"))
        (machine.state / "output" / "second-project").chmod(0o755)
        self.assertFail(machine.check("PA-42"), "second-project: the output directory is not mode 0700")
        (machine.state / "output" / "second-project").chmod(0o700)
        (machine.state / "output" / "platform").rmdir()
        self.assertFail(machine.check("PA-42"), "platform: no output directory")

    def test_pa42_the_lock_file_must_exist_and_be_private(self):
        machine = self.machine()
        (machine.state / "run.lock").chmod(0o644)
        self.assertFail(machine.check("PA-42"), "accessible to others")
        (machine.state / "run.lock").unlink()
        self.assertFail(machine.check("PA-42"), "lock file is missing")


class Credentials(Case):
    """PA-A26: T2 and T3 live only inside script processes."""

    def test_a_token_in_this_environment_fails(self):
        machine = self.machine()
        machine.environ = {"PATH": "/usr/bin", "GITHUB_TOKEN": TOKEN}
        results = machine.check("PA-13")
        self.assertFail(results, "GITHUB_TOKEN")
        self.assertNotIn(TOKEN, " ".join(detail for _, detail in results))

    def test_a_token_in_a_file_of_an_output_directory_fails_and_is_not_printed(self):
        machine = self.machine()
        (machine.state / "output" / "platform" / "run.log").write_text(f"header\nAuthorization: {TOKEN}\n")
        results = machine.check("PA-13")
        self.assertFail(results, "hold a token")
        self.assertNotIn(TOKEN, " ".join(detail for _, detail in results))

    def test_a_token_that_is_not_there_passes_and_other_files_are_fine(self):
        machine = self.machine()
        (machine.state / "output" / "platform" / "facts.txt").write_text("git_present=yes\n")
        self.assertPass(machine.check("PA-13"))

    def test_a_persisted_credential_file_in_the_home_fails(self):
        for relative in (".git-credentials", ".netrc", ".config/gh/hosts.yml"):
            with self.subTest(relative=relative):
                machine = self.machine()
                (machine.home / relative).parent.mkdir(parents=True, exist_ok=True)
                (machine.home / relative).write_text("x\n")
                self.assertFail(machine.check("PA-13"), relative)

    def test_a_token_in_a_child_process_that_is_not_a_script_fails(self):
        machine = self.machine()
        machine.process(4242, ["PATH", "GH_TOKEN"], ["bash", "-c", "sleep 1"])
        self.assertFail(machine.check("PA-13"), "process 4242 outside a script")

    def test_a_token_in_a_script_process_is_where_it_belongs(self):
        machine = self.machine()
        script = str(machine.prefix / "operator" / "projects" / "platform" / "scripts" / "operator" / "facts")
        machine.process(4243, ["PATH", "GH_TOKEN"], ["/usr/bin/python3", script, "--apply"])
        machine.process(4244, ["PATH"], ["bash"])
        self.assertPass(machine.check("PA-13"))

    def test_the_check_itself_is_not_judged_by_its_own_process_entry(self):
        machine = self.machine()
        machine.process(1, ["GH_TOKEN"], ["operator-check"])  # own_pid is 1 in these fixtures
        self.assertPass(machine.check("PA-13"))


def import_rmtree(path):
    import shutil
    shutil.rmtree(path)


class Installation(Case):
    """PA-A14: the check refuses to run except from a root-owned release installation."""

    def prepare(self):
        machine = self.machine()
        return machine, str(machine.prefix), str(machine.prefix / "operator")

    def refusal(self, machine, here=None, **kw):
        return operator_check.require_installation(here or str(machine.prefix / "operator"), str(machine.prefix), (ME,), str(machine.base))

    def test_the_installation_of_the_configuration_is_accepted(self):
        machine = self.machine()
        self.assertIsNone(self.refusal(machine))

    def test_a_run_from_a_tree_the_user_owns_is_refused(self):
        machine = self.machine()
        other = machine.base / "clone" / "ansible" / "roles" / "operator_tools" / "files"
        other.mkdir(parents=True)
        self.assertIn("runs only from the installation", self.refusal(machine, str(other)))

    def test_a_directory_others_can_write_is_refused(self):
        machine = self.machine()
        (machine.prefix / "operator").chmod(0o777)
        self.assertIn("writable by others", self.refusal(machine))

    def test_a_chain_directory_that_is_not_root_owned_is_refused(self):
        machine = self.machine()
        self.assertIn("not owned by root", operator_check.require_installation(
            str(machine.prefix / "operator"), str(machine.prefix), (ME + 1,), str(machine.base)))

    def test_a_missing_or_foreign_conf_or_a_conf_without_a_release_tag_is_refused(self):
        machine = self.machine()
        conf = machine.prefix / "operator" / "operator.conf"
        conf.write_text("operator_user=op\nadmin_user=opadm\nrelease_tag=nightly\n")
        self.assertIn("release tag", self.refusal(machine))
        conf.chmod(0o666)
        self.assertIn("writable by others", self.refusal(machine))
        conf.unlink()
        self.assertIn("operator.conf", self.refusal(machine))

    def test_the_script_run_from_the_repository_is_refused_with_status_2(self):
        machine = self.machine()
        done = subprocess.run([sys.executable, "-I", "-B", str(TOOLS / "operator-check"), "--prefix", str(machine.prefix)],
                              capture_output=True, text=True, check=False)
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertIn("refused", done.stderr)
        self.assertEqual(done.stdout, "")

    def test_a_usage_error_is_status_2(self):
        for argv in (["--bogus"], ["--prefix"]):
            with self.subTest(argv=argv):
                self.assertEqual(operator_check.main(argv), 2)

    def test_the_wrong_account_is_refused_with_status_2(self):
        machine = self.machine()
        tools = machine.prefix / "operator"
        (tools / "ssh_hardening_audit.py").write_text(SSH_MODULE.read_text())
        done = operator_check.main(["--prefix", str(machine.prefix)], here=str(tools), trusted=(ME,), chain_top=str(machine.base))
        self.assertEqual(done, 2)  # operator.conf names "op", and this test does not run as that account


class Launcher(Case):
    """PA-A30: runs are one at a time; the script runs in the project's output directory with a clean environment."""

    def installed(self):
        machine = self.machine()
        tools = machine.prefix / "operator"
        for name in ("operator-check", "operator-run"):
            (tools / name).write_text((TOOLS / name).read_text())
            (tools / name).chmod(0o755)
        script = tools / "projects" / "platform" / "scripts" / "operator" / "show-environment"
        script.write_text('#!/bin/sh\nenv | sed "s/=.*//" | sort > "$OPERATOR_OUTPUT_DIR/names.txt"\npwd > "$OPERATOR_OUTPUT_DIR/cwd.txt"\nexit 7\n')
        script.chmod(0o755)
        return machine

    def run_launcher(self, machine, *argv):
        tools = str(machine.prefix / "operator")
        return operator_run.main(["--prefix", str(machine.prefix), *argv], here=tools, trusted=(ME,), chain_top=str(machine.base),
                                 state=str(machine.state))

    def test_the_script_runs_in_its_output_directory_with_a_clean_environment_and_its_status_is_returned(self):
        machine = self.installed()
        with mock.patch.dict(os.environ, {"GH_TOKEN": TOKEN, "SSH_AUTH_SOCK": "/tmp/agent", "OTHER": "x"}):
            code = self.run_launcher(machine, "platform", "scripts/operator/show-environment")
        self.assertEqual(code, 7)
        output = machine.state / "output" / "platform"
        names = (output / "names.txt").read_text().split()
        for forbidden in ("GH_TOKEN", "SSH_AUTH_SOCK", "OTHER"):
            self.assertNotIn(forbidden, names)
        for expected in ("OPERATOR_OUTPUT_DIR", "OPERATOR_PROJECT", "HOME", "PATH"):
            self.assertIn(expected, names)
        self.assertEqual((output / "cwd.txt").read_text().strip(), str(output.resolve()))

    def test_a_second_run_is_refused_while_the_first_is_in_progress(self):
        machine = self.installed()
        holder = os.open(machine.state / "run.lock", os.O_RDWR)
        self.addCleanup(os.close, holder)
        fcntl.flock(holder, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with mock.patch("sys.stderr") as err:
            code = self.run_launcher(machine, "platform", "scripts/operator/show-environment")
        self.assertEqual(code, 1)
        self.assertIn("another operator run is in progress", "".join(call.args[0] for call in err.write.call_args_list))
        self.assertFalse((machine.state / "output" / "platform" / "names.txt").exists(), "the script must not have started")
        fcntl.flock(holder, fcntl.LOCK_UN)
        self.assertEqual(self.run_launcher(machine, "platform", "scripts/operator/show-environment"), 7)
        self.assertEqual(self.run_launcher(machine, "platform", "scripts/operator/show-environment"), 7, "the lock is released after a run")

    def test_a_project_that_is_not_installed_or_a_bad_name_is_refused(self):
        machine = self.installed()
        for project in ("nothing", "../platform", "Platform", ""):
            with self.subTest(project=project):
                self.assertEqual(self.run_launcher(machine, project, "scripts/operator/show-environment"), 1)

    def test_a_script_outside_the_installation_or_not_root_owned_is_refused(self):
        machine = self.installed()
        project = machine.prefix / "operator" / "projects" / "platform"
        (project / "scripts" / "operator" / "loose").write_text("#!/bin/sh\nexit 0\n")
        (project / "scripts" / "operator" / "loose").chmod(0o775)
        (project / "scripts" / "operator" / "noexec").write_text("#!/bin/sh\nexit 0\n")
        (project / "scripts" / "operator" / "noexec").chmod(0o644)
        os.symlink("/bin/true", project / "scripts" / "operator" / "link")
        for script in ("../../../operator-check", "/bin/true", "scripts/operator/loose", "scripts/operator/noexec", "scripts/operator/link",
                       "scripts/operator/missing", "scripts/operator/with space", "scripts/../../x"):
            with self.subTest(script=script):
                self.assertEqual(self.run_launcher(machine, "platform", script), 1)

    def test_a_run_from_anywhere_but_the_installation_is_refused_with_status_2(self):
        machine = self.installed()
        code = operator_run.main(["--prefix", str(machine.prefix), "platform", "scripts/operator/show-environment"], here=str(TOOLS),
                                 trusted=(ME,), chain_top=str(machine.base), state=str(machine.state))
        self.assertEqual(code, 2)

    def test_a_usage_error_is_status_2(self):
        machine = self.installed()
        self.assertEqual(self.run_launcher(machine, "platform"), 2)


class Files(unittest.TestCase):
    def test_the_scripts_are_executable_python_without_bytecode(self):
        for name, first in (("operator-check", "#!/usr/bin/python3 -I\n"), ("operator-run", "#!/usr/bin/python3 -I\n")):
            self.assertTrue(os.access(TOOLS / name, os.X_OK), name)
            self.assertTrue((TOOLS / name).read_text().startswith(first), name)

    def test_nothing_in_the_tools_writes_a_file_or_runs_a_shell(self):
        for name in ("operator-check", "operator-run"):
            text = (TOOLS / name).read_text()
            for banned in ("shell=True", "os.system", "eval(", "exec(", "open(path, 'w'", 'open(path, "w"', "os.chmod", "os.chown", "os.remove",
                           "shutil", "os.mkdir", "os.makedirs", "os.rename"):
                self.assertNotIn(banned, text, f"{name}: {banned}")

    def test_the_check_has_one_method_per_item_and_the_ids_of_the_contract(self):
        ids = [item for item, _ in operator_check.Operator.ITEMS]
        self.assertEqual(ids, ["OC-1", "OC-2", "OC-6", "OC-8", "OC-10", "OC-11", "OC-12", "PA-42", "PA-13"])
        for _, method in operator_check.Operator.ITEMS:
            self.assertTrue(callable(getattr(operator_check.Operator, method)), method)


if __name__ == "__main__":
    unittest.main()
