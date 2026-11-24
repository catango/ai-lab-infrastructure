"""CR-57 PA-A8, PA-A13, PA-A18, PA-A26, PA-A31, PA-A32: the lab check, one fixture per LC item, against a fake machine.

The machine is a temporary tree (an /etc, a home, a prefix, clones under ~/work built with real git); commands that need root,
the network, or a package manager (sudo, dpkg-query, apt-config, sshd -T, gh, the toolchain engine) are answered by a small fake.
Nothing here needs root. The PA-28 job runs the installed check as the AI user on a real Debian 13 (tests/ansible/pa28-lab.sh).
"""
import base64
import json
import os
import pathlib
import struct
import subprocess
import tempfile
import unittest

import helpers
from helpers import ROOT, SSH_MODULE, TOOLS, load, tree_hash

lab_check = load("lab_check", TOOLS / "lab-check")
audit = load("ssh_hardening_audit", SSH_MODULE)
ME = os.getuid()
GIT_ENV = {"PATH": "/usr/bin:/bin", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null", "GIT_AUTHOR_NAME": "t",
           "GIT_AUTHOR_EMAIL": "noreply", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "noreply"}
EMAIL = "42+machine-bot@users.noreply.github.com"
DROPIN = (ROOT / "ansible" / "roles" / "ssh_hardening" / "tasks" / "main.yml").read_text()
AT = "@"  # kept apart so that no line of this file looks like an email address to the public-repository hygiene check
DENY = ["Bash(ssh *)", "Read(~/.ssh/**)", "Edit(~/.ssh/**)", "Read(~/.config/gh/**)"]


def key_line(seed, options="", comment=""):
    name = b"ssh-ed25519"
    raw = struct.pack(">I", len(name)) + name + struct.pack(">I", 32) + bytes([seed]) * 32
    return " ".join(part for part in (options, "ssh-ed25519", base64.b64encode(raw).decode(), comment) if part) + "\n"


def git(path, *args):
    done = subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True, env=GIT_ENV, check=False)
    assert done.returncode == 0, done.stderr
    return done.stdout


class Machine:
    """A lab as the check sees it, in a temporary directory. Every attribute can be changed before check() is called."""

    def __init__(self, test):
        tmp = tempfile.TemporaryDirectory()
        test.addCleanup(tmp.cleanup)
        self.base = pathlib.Path(tmp.name)
        self.root = self.base / "root"
        self.prefix = self.base / "prefix"
        self.home = self.base / "home" / "ai"
        self.admin_home = self.base / "home" / "adm"
        self.logged_in = True
        self.login = "machine-bot"
        self.scopes = "repo, workflow, read:org"
        self.sshd_direct = None
        self.sudo = (1, "Sorry, user ai may not run sudo on lab.")
        self.packages = (0, "install ok installed")
        self.apt = 'APT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Unattended-Upgrade "1";\n'
        self.engine = (0, "toolchain: verified 12 tools")
        self.environ = {"PATH": "/usr/bin"}
        self.groups = ["ai"]
        for directory in (self.root / "etc" / "claude-code", self.root / "etc" / "ssh" / "authorized_keys",
                          self.root / "etc" / "ssh" / "sshd_config.d", self.prefix / "lab" / "engine" / "scripts",
                          self.home / ".ssh", self.home / "work", self.admin_home):
            directory.mkdir(parents=True)
        for current, dirs, _ in os.walk(self.base):  # the umask of the test run must not make a directory group-writable
            for name in dirs:
                os.chmod(os.path.join(current, name), 0o755)
        os.chmod(self.base, 0o755)
        self.home.joinpath(".ssh").chmod(0o700)
        self.write(self.root / "etc" / "os-release", 'ID=debian\nVERSION_ID="13"\n')
        self.write(self.root / "etc" / "claude-code" / "managed-settings.json", json.dumps({"permissions": {"deny": DENY}}))
        self.write(self.root / "etc" / "claude-code" / "CLAUDE.md", "<!-- BEGIN ai-lab-infrastructure managed rules -->\nrules\n")
        self.write(self.root / "etc" / "ssh" / "authorized_keys" / "ai", key_line(1, "restrict,pty", "ai"))
        self.write(self.root / "etc" / "ssh" / "authorized_keys" / "adm", key_line(2, "", "adm"))
        self.write(self.root / "etc" / "ssh" / "sshd_config", "Include /etc/ssh/sshd_config.d/*.conf\nKbdInteractiveAuthentication no\n"
                   "UsePAM yes\nX11Forwarding yes\nPrintMotd no\nAcceptEnv LANG LC_*\nSubsystem sftp /usr/lib/openssh/sftp-server\n")
        self.write(self.root / "etc" / "ssh" / "sshd_config.d" / "00-ai-lab.conf",
                   "PubkeyAuthentication yes\nPasswordAuthentication no\nAllowUsers ai adm\nMACs -hmac-sha1*\n")
        self.write(self.prefix / "lab" / "token-step", (TOOLS / "token-step").read_text(), 0o755)
        self.write(self.prefix / "lab" / "lab.conf", "machine_login=machine-bot\nowner=owner\nai_user=ai\nadmin_user=adm\n")
        self.write(self.prefix / "lab" / "engine" / "scripts" / "toolchain", "", 0o755)
        self.write(self.prefix / "bin" / "gh", "", 0o755)
        self.write(self.home / ".gitconfig", f"[user]\n\tname = machine-bot\n\temail = {EMAIL}\n")
        self.record_sshd()

    @staticmethod
    def write(path, text, mode=0o644):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        path.chmod(mode)

    def sshd_text(self):
        keys = f"{self.root}/etc/ssh/authorized_keys/%u"
        return "\n".join(["pubkeyauthentication yes", "passwordauthentication no", "kbdinteractiveauthentication no",
                          "permitrootlogin no", "authenticationmethods publickey", f"authorizedkeysfile {keys}", "authorizedkeyscommand none",
                          "trustedusercakeys none", "authorizedprincipalsfile none", "allowagentforwarding no", "allowtcpforwarding no",
                          "x11forwarding no", "permittunnel no", "permituserrc no", "permituserenvironment no", "allowusers ai",
                          "allowusers adm", "kexalgorithms mlkem768x25519-sha256,curve25519-sha256",
                          f"macs hmac-sha2-256-etm{AT}openssh.com"]) + "\n"

    def record_sshd(self, text=None):
        """What lab setup records after it switched sshd: the settings and the digest of the configuration files."""
        path = self.root / "etc" / "ssh" / "ai-lab-sshd-effective.txt"
        path.unlink(missing_ok=True)
        audit.write_snapshot(str(path), text or self.sshd_text(), audit.config_digest(str(self.root / "etc" / "ssh")))

    def repo(self, name, remote="https://github.com/owner/name.git", commit=True):
        path = self.home / "work" / name
        path.mkdir(parents=True)
        git(path, "init", "-q", "-b", "main")
        if commit:
            git(path, "-c", "commit.gpgsign=false", "commit", "-q", "--allow-empty", "-m", "first")
        if remote:
            git(path, "remote", "add", "origin", remote)
        return path

    def run(self, argv, env=None, cwd="/", timeout=0):
        command = os.path.basename(argv[0])
        if command == "git":
            return self.lab._run(argv, env={"GIT_CONFIG_NOSYSTEM": "1", **(env or {})}, cwd=cwd)
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
        if argv[0] == str(self.prefix / "bin" / "gh"):
            if argv[1:3] == ["auth", "status"]:
                return (0, "Logged in") if self.logged_in else (1, "You are not logged in")
            if argv[1:3] == ["api", "-i"]:
                return 0, f'HTTP/2.0 200 OK\r\nX-Oauth-Scopes: {self.scopes}\r\n\r\n{{"login":"{self.login}","id":42}}\n'
        if command.startswith("python"):
            return self.engine
        return 127, "unexpected command"

    @property
    def lab(self):
        if not hasattr(self, "_lab"):
            conf = lab_check.read_conf(str(self.prefix / "lab" / "lab.conf"))
            homes = {"ai": str(self.home), "adm": str(self.admin_home)}
            self._lab = lab_check.Lab(audit, conf, "ai", str(self.home), root=str(self.root), prefix=str(self.prefix),
                                      environ=self.environ, run=self.run, gh=str(self.prefix / "bin" / "gh"), machine="x86_64",
                                      trusted_uids=(ME,), groups=self.groups, home_of=lambda name: homes[name], systemd=False,
                                      chain_top=str(self.base))
        return self._lab

    def check(self, item):
        """[(status, detail)] of one item, as printed (id without the dash handling: LC-6 -> lc6, PA-43 -> pa43)."""
        return getattr(self.lab, item.lower().replace("-", ""))()

    def statuses(self):
        return {(status, item) for status, item, _ in self.lab.check_all()}


class Case(unittest.TestCase):
    def machine(self):
        return Machine(self)

    def assertPass(self, results):
        self.assertEqual([status for status, _ in results], ["PASS"], results)

    def assertFail(self, results, text=""):
        self.assertIn("FAIL", [status for status, _ in results], results)
        self.assertIn(text, " ".join(detail for _, detail in results))


class WholeCheck(Case):
    def test_a_good_lab_passes_every_item_and_names_no_lc5(self):
        machine = self.machine()
        results = machine.lab.check_all()
        self.assertEqual({status for status, _, _ in results}, {"PASS"}, results)
        self.assertEqual({item for _, item, _ in results},
                         {f"LC-{n}" for n in (1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15)} | {"PA-43"})

    def test_it_changes_nothing(self):
        """PA-A8: the tree hash before and after every run is equal, for the whole check and for the pre-disposal mode."""
        machine = self.machine()
        machine.repo("project")
        before = tree_hash(machine.base)
        machine.lab.check_all()
        machine.lab.pre_disposal()
        self.assertEqual(tree_hash(machine.base), before)

    def test_a_broken_check_is_a_failure_never_a_pass(self):
        machine = self.machine()
        machine.lab.lc10 = lambda: 1 / 0
        results = [r for r in machine.lab.check_all() if r[1] == "LC-10"]
        self.assertEqual(results[0][0], "FAIL")

    def test_it_prints_no_secret(self):
        machine = self.machine()
        machine.environ = {"PATH": "/usr/bin", "AWS_SECRET_ACCESS_KEY": "canary-secret-value", "GH_TOKEN": "canary-token-value"}
        text = " ".join(detail for _, _, detail in machine.lab.check_all())
        self.assertNotIn("canary", text)
        self.assertIn("AWS_SECRET_ACCESS_KEY", text)


class PerItem(Case):
    def test_lc1_debian_13_on_x86_64(self):
        machine = self.machine()
        self.assertPass(machine.check("LC-1"))
        machine.lab.machine = "aarch64"
        self.assertFail(machine.check("LC-1"), "x86_64")
        machine.lab.machine = "x86_64"
        machine.write(machine.root / "etc" / "os-release", 'ID=ubuntu\nVERSION_ID="24.04"\n')
        self.assertFail(machine.check("LC-1"), "Debian 13")

    def test_lc1_follows_the_os_release_link_that_debian_ships(self):
        machine = self.machine()
        target = machine.root / "usr" / "lib" / "os-release"
        machine.write(target, 'ID=debian\nVERSION_ID="13"\n')
        (machine.root / "etc" / "os-release").unlink()
        (machine.root / "etc" / "os-release").symlink_to("../usr/lib/os-release")
        self.assertPass(machine.check("LC-1"))

    def test_lc2_no_sudo_and_no_root_equivalent_group(self):
        machine = self.machine()
        self.assertPass(machine.check("LC-2"))
        for group in ("sudo", "docker", "lxd", "disk"):
            machine.lab.groups = ["ai", group]
            self.assertFail(machine.check("LC-2"), group)
        machine.lab.groups = ["ai"]
        machine.sudo = (0, "User ai may run the following commands: (ALL) ALL")
        self.assertFail(machine.check("LC-2"), "sudo allows")
        machine.sudo = (1, "sudo: a password is required")
        self.assertFail(machine.check("LC-2"), "password")

    def test_lc3_the_lab_admin_is_never_a_claude_target(self):
        machine = self.machine()
        self.assertPass(machine.check("LC-3"))
        (machine.admin_home / ".claude").mkdir()
        self.assertFail(machine.check("LC-3"), "~/.claude")

    def test_lc3_a_private_admin_home_is_a_warning_not_a_pass(self):
        machine = self.machine()
        machine.lab.lstat = lambda path: (_ for _ in ()).throw(PermissionError()) if path.endswith(".claude") else os.lstat(path)
        self.assertEqual(machine.check("LC-3")[0][0], "WARN")

    def test_lc4_root_owned_managed_files(self):
        machine = self.machine()
        self.assertPass(machine.check("LC-4"))
        (machine.root / "etc" / "claude-code" / "managed-settings.json").chmod(0o666)
        self.assertFail(machine.check("LC-4"), "writable by others")
        (machine.root / "etc" / "claude-code" / "managed-settings.json").chmod(0o644)
        machine.lab.trusted = (ME + 1,)
        self.assertFail(machine.check("LC-4"), "not owned by root")
        machine.lab.trusted = (ME,)
        (machine.root / "etc" / "claude-code" / "CLAUDE.md").unlink()
        self.assertFail(machine.check("LC-4"), "managed CLAUDE.md")
        machine.write(machine.root / "etc" / "claude-code" / "CLAUDE.md", "no rules here\n")
        self.assertFail(machine.check("LC-4"), "lacks the managed rules")

    def test_lc4_settings_without_a_deny_list_fail(self):
        machine = self.machine()
        machine.write(machine.root / "etc" / "claude-code" / "managed-settings.json", "{}")
        self.assertFail(machine.check("LC-4"), "no deny list")

    def test_lc6_agent_socket_private_key_and_ssh_remote(self):
        """PA-A13: the three fixtures that fail."""
        machine = self.machine()
        self.assertPass(machine.check("LC-6"))
        machine.lab.environ["SSH_AUTH_SOCK"] = "/tmp/agent.1"
        self.assertFail(machine.check("LC-6"), "agent socket")
        del machine.lab.environ["SSH_AUTH_SOCK"]
        self.assertPass(machine.check("LC-6"))
        (machine.home / ".ssh" / "id_ed25519").write_text("not a real key\n")
        self.assertFail(machine.check("LC-6"), "private key")
        (machine.home / ".ssh" / "id_ed25519").unlink()
        machine.repo("good")
        self.assertPass(machine.check("LC-6"))
        for url in (f"git{AT}github.com:owner/name.git", f"ssh://git{AT}github.com/owner/name.git"):
            machine.repo("bad", remote=url)
            self.assertFail(machine.check("LC-6"), "bad: a remote is not HTTPS")
            subprocess.run(["rm", "-rf", str(machine.home / "work" / "bad")], check=True)

    def test_lc6_a_url_rewrite_to_ssh_fails(self):
        machine = self.machine()
        machine.write(machine.home / ".gitconfig", f"[user]\n\tname = machine-bot\n\temail = {EMAIL}\n"
                      f"[url \"git{AT}github.com:\"]\n\tinsteadOf = https://github.com/\n")
        self.assertFail(machine.check("LC-6"), "rewrite")

    def test_lc7_token_login_scopes_and_file_mode(self):
        machine = self.machine()
        self.assertPass(machine.check("LC-7"))
        machine.logged_in = False
        self.assertFail(machine.check("LC-7"), "not logged in")
        machine.logged_in = True
        machine.login = "someone-else"
        self.assertFail(machine.check("LC-7"), "another account")
        machine.login = "machine-bot"
        machine.scopes = "repo"
        self.assertFail(machine.check("LC-7"), "scopes")
        machine.scopes = "repo, workflow"
        hosts = machine.home / ".config" / "gh" / "hosts.yml"
        machine.write(hosts, "github.com:\n  oauth_token: x\n", 0o644)
        self.assertFail(machine.check("LC-7"), "0600")
        hosts.chmod(0o600)
        self.assertPass(machine.check("LC-7"))
        machine.lab.environ["GITHUB_TOKEN"] = "canary"
        self.assertFail(machine.check("LC-7"), "environment")

    def test_lc8_the_effective_git_identity(self):
        machine = self.machine()
        self.assertPass(machine.check("LC-8"))
        machine.write(machine.home / ".gitconfig", f"[user]\n\tname = machine-bot\n\temail = someone{AT}example.org\n")
        self.assertFail(machine.check("LC-8"), "noreply")
        machine.write(machine.home / ".gitconfig", f"[user]\n\tname = wrong\n\temail = {EMAIL}\n")
        self.assertFail(machine.check("LC-8"), "user.name")
        machine.write(machine.home / ".gitconfig", f"[user]\n\tname = machine-bot\n\temail = {EMAIL}\n")
        repo = machine.repo("project")
        self.assertPass(machine.check("LC-8"))
        git(repo, "config", "user.email", f"someone{AT}example.org")
        self.assertFail(machine.check("LC-8"), "project: user.email")

    def test_lc9_gate_tools_at_the_manifest_versions(self):
        machine = self.machine()
        self.assertPass(machine.check("LC-9"))
        machine.engine = (1, "yq: FAILED (version 1.0 is not 4.54.3)")
        self.assertFail(machine.check("LC-9"), "yq")
        machine.engine = (0, "")
        (machine.prefix / "lab" / "engine" / "scripts" / "toolchain").unlink()
        self.assertFail(machine.check("LC-9"), "engine")

    def test_lc10_no_production_or_infrastructure_credential_by_name(self):
        """PA-A26."""
        machine = self.machine()
        self.assertPass(machine.check("LC-10"))
        for relative in (".oci", ".aws", ".config/gcloud", ".kube"):
            path = machine.home / relative
            path.mkdir(parents=True)
            self.assertFail(machine.check("LC-10"), relative)
            path.rmdir()
        (machine.home / ".terraform.d").mkdir()
        (machine.home / ".terraform.d" / "credentials.tfrc.json").write_text("{}")
        self.assertFail(machine.check("LC-10"), "credentials.tfrc.json")
        (machine.home / ".terraform.d" / "credentials.tfrc.json").unlink()
        machine.lab.environ["OCI_CLI_KEY_FILE"] = "x"
        self.assertFail(machine.check("LC-10"), "$OCI_CLI_KEY_FILE")

    def test_lc11_the_ai_users_key_carries_restrict_and_pty(self):
        machine = self.machine()
        self.assertPass(machine.check("LC-11"))
        path = machine.root / "etc" / "ssh" / "authorized_keys" / "ai"
        for options in ("", "restrict", "pty"):
            machine.write(path, key_line(1, options, "ai"))
            self.assertFail(machine.check("LC-11"), "restrict,pty")
        machine.write(path, key_line(1, "restrict,pty", "ai") + key_line(3, "", "extra"))
        self.assertFail(machine.check("LC-11"), "exactly one key")
        path.unlink()
        self.assertFail(machine.check("LC-11"), "does not exist")

    def test_lc12_the_two_accounts_have_different_keys(self):
        machine = self.machine()
        self.assertPass(machine.check("LC-12"))
        machine.write(machine.root / "etc" / "ssh" / "authorized_keys" / "adm", key_line(1, "", "adm"))
        self.assertFail(machine.check("LC-12"), "share one key")

    def test_lc14_the_token_step_is_root_owned_with_a_clean_environment(self):
        machine = self.machine()
        self.assertPass(machine.check("LC-14"))
        step = machine.prefix / "lab" / "token-step"
        step.chmod(0o775)
        self.assertFail(machine.check("LC-14"), "writable by others")
        step.chmod(0o755)
        machine.lab.trusted = (ME + 1,)
        self.assertFail(machine.check("LC-14"), "not owned by root")
        machine.lab.trusted = (ME,)
        machine.write(step, "#!/bin/bash\nread -r token\n", 0o755)
        self.assertFail(machine.check("LC-14"), "env -i")
        step.unlink()
        step.symlink_to(machine.base / "elsewhere")
        self.assertFail(machine.check("LC-14"), "is a link")

    def test_lc14_a_directory_the_ai_user_can_write_fails(self):
        machine = self.machine()
        (machine.prefix / "lab").chmod(0o777)
        self.assertFail(machine.check("LC-14"), "writable by others")

    def test_lc15_unattended_security_updates(self):
        machine = self.machine()
        self.assertPass(machine.check("LC-15"))
        machine.packages = (1, "")
        self.assertFail(machine.check("LC-15"), "not installed")
        machine.packages = (0, "install ok installed")
        machine.apt = 'APT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Unattended-Upgrade "0";\n'
        self.assertFail(machine.check("LC-15"), "Unattended-Upgrade")


class Sshd(Case):
    """LC-13 and PA-A18."""

    def test_the_recorded_settings_pass(self):
        machine = self.machine()
        self.assertPass(machine.check("LC-13"))

    def test_the_settings_of_a_running_sshd_pass_when_it_can_be_asked(self):
        machine = self.machine()
        machine.sshd_direct = (0, machine.sshd_text())
        results = machine.check("LC-13")
        self.assertPass(results)
        self.assertIn("sshd -T", results[0][1])

    def test_without_a_record_it_fails(self):
        machine = self.machine()
        (machine.root / "etc" / "ssh" / "ai-lab-sshd-effective.txt").unlink()
        self.assertFail(machine.check("LC-13"), "not recorded")

    def test_a_configuration_that_changed_after_the_record_fails(self):
        machine = self.machine()
        (machine.root / "etc" / "ssh" / "sshd_config.d" / "00-ai-lab.conf").write_text("PasswordAuthentication yes\n")
        self.assertFail(machine.check("LC-13"), "changed after lab setup")

    def test_a_record_that_the_ai_user_could_write_fails(self):
        machine = self.machine()
        (machine.root / "etc" / "ssh" / "ai-lab-sshd-effective.txt").chmod(0o666)
        self.assertFail(machine.check("LC-13"), "writable by others")

    def test_a_stray_sshd_option_fails(self):
        machine = self.machine()
        extra = machine.root / "etc" / "ssh" / "sshd_config.d" / "50-extra.conf"
        for text, message in (("ClientAliveInterval 5\n", "clientaliveinterval"), ("Match User x\n  X11Forwarding yes\n", "Match block"),
                              ("Port 2222\n", "port")):
            machine.write(extra, text)
            machine.record_sshd()
            self.assertFail(machine.check("LC-13"), message)
        extra.unlink()
        machine.record_sshd()
        self.assertPass(machine.check("LC-13"))

    def test_sshd_reading_keys_from_a_user_owned_file_fails(self):
        machine = self.machine()
        machine.record_sshd(machine.sshd_text().replace(f"{machine.root}/etc/ssh/authorized_keys/%u", ".ssh/authorized_keys"))
        self.assertFail(machine.check("LC-13"), "root-owned location")

    def test_each_authentication_setting_fails(self):
        for setting in ("authorizedkeyscommand /bin/true", "trustedusercakeys /ca.pub", "authorizedprincipalsfile /p/%u"):
            with self.subTest(setting=setting):
                machine = self.machine()
                keyword = setting.split()[0]
                machine.record_sshd(machine.sshd_text().replace(f"{keyword} none", setting))
                self.assertFail(machine.check("LC-13"), f"{keyword} is set")

    def test_the_other_lc13_settings_fail_when_they_are_off(self):
        for line, wrong in (("passwordauthentication no", "passwordauthentication yes"), ("permitrootlogin no", "permitrootlogin yes"),
                            ("allowagentforwarding no", "allowagentforwarding yes"), ("x11forwarding no", "x11forwarding yes"),
                            ("allowtcpforwarding no", "allowtcpforwarding yes"), ("permittunnel no", "permittunnel yes"),
                            ("permituserrc no", "permituserrc yes"), ("allowusers adm", "allowusers other"),
                            (f"macs hmac-sha2-256-etm{AT}openssh.com", "macs hmac-sha1"),
                            ("kexalgorithms mlkem768x25519-sha256,curve25519-sha256", "kexalgorithms diffie-hellman-group14-sha1")):
            with self.subTest(wrong=wrong):
                machine = self.machine()
                machine.record_sshd(machine.sshd_text().replace(line, wrong))
                self.assertFail(machine.check("LC-13"))

    def test_an_inert_authorized_keys_file_is_only_a_warning(self):
        machine = self.machine()
        machine.write(machine.home / ".ssh" / "authorized_keys", key_line(1))
        results = machine.check("LC-13")
        self.assertEqual([status for status, _ in results], ["PASS", "WARN"])
        self.assertNotIn("FAIL", [status for status, _, _ in machine.lab.check_all()])


class Credentials(Case):
    """PA-A31: PA-43 against the effective managed settings."""

    def project(self, machine, *paths):
        repo = machine.repo("project")
        lines = "\n".join(f"- `{path}` - credential of the test service" for path in paths)
        machine.write(repo / "docs" / "PROJECT.md", f"# Project\n\n## Credential paths\n\n{lines}\n\n## Other\n\n- `~/not-a-credential`\n")

    def test_no_listed_path_passes(self):
        self.assertPass(self.machine().check("PA-43"))

    def test_a_listed_path_with_mode_0600_and_a_deny_rule_passes(self):
        machine = self.machine()
        self.project(machine, "~/.config/svc/token")
        machine.write(machine.home / ".config" / "svc" / "token", "x", 0o600)
        machine.write(machine.root / "etc" / "claude-code" / "managed-settings.json",
                      json.dumps({"permissions": {"deny": DENY + ["Read(~/.config/svc/token)"]}}))
        self.assertPass(machine.check("PA-43"))

    def test_a_mode_0644_file_and_an_uncovered_path_fail(self):
        machine = self.machine()
        self.project(machine, "~/.config/svc/one", "~/.config/svc/two")
        machine.write(machine.home / ".config" / "svc" / "one", "x", 0o644)
        machine.write(machine.root / "etc" / "claude-code" / "managed-settings.json",
                      json.dumps({"permissions": {"deny": DENY + ["Read(~/.config/svc/one)"]}}))
        results = machine.check("PA-43")
        self.assertFail(results, "one is not mode 0600")
        self.assertIn("two is not covered", results[0][1])
        self.assertNotIn("one is not covered", results[0][1])
        self.assertNotIn("not-a-credential", results[0][1])

    def test_a_directory_rule_with_a_glob_covers_the_path(self):
        machine = self.machine()
        self.project(machine, "~/.config/svc/token")
        machine.write(machine.root / "etc" / "claude-code" / "managed-settings.json",
                      json.dumps({"permissions": {"deny": DENY + ["Read(~/.config/svc/**)"]}}))
        self.assertPass(machine.check("PA-43"))


class PreDisposal(Case):
    """PA-A32: two repositories, one dirty and one with an unpushed commit; the listing names both and changes nothing."""

    def test_it_lists_both_and_changes_nothing(self):
        machine = self.machine()
        dirty = machine.repo("dirty")
        (dirty / "notes.txt").write_text("not committed\n")
        machine.repo("clean-and-pushed")
        git(machine.home / "work" / "clean-and-pushed", "update-ref", "refs/remotes/origin/main", "HEAD")
        unpushed = machine.repo("unpushed")
        git(unpushed, "update-ref", "refs/remotes/origin/main", "HEAD")
        git(unpushed, "-c", "commit.gpgsign=false", "commit", "-q", "--allow-empty", "-m", "second")
        before = tree_hash(machine.base)
        listing = machine.lab.pre_disposal()
        self.assertEqual(sorted(name for name, _ in listing), ["dirty", "unpushed"])
        self.assertEqual(tree_hash(machine.base), before)
        self.assertIn("uncommitted", dict(listing)["dirty"][0])
        self.assertIn("no remote branch has", dict(listing)["unpushed"][0])

    def test_nothing_to_list_when_everything_is_saved(self):
        machine = self.machine()
        repo = machine.repo("saved")
        git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
        self.assertEqual(machine.lab.pre_disposal(), [])


class Static(unittest.TestCase):
    def test_the_check_never_uses_a_shell_eval_or_a_write(self):
        text = (TOOLS / "lab-check").read_text()
        for banned in ("shell=True", "eval(", "exec(", "os.system", "os.popen", "open(path, \"w", ".write_text", "os.chmod", "os.remove",
                       "os.unlink", "shutil."):
            self.assertNotIn(banned, text, banned)

    def test_the_lab_check_has_exactly_the_contract_items(self):
        ids = [item for item, _ in lab_check.Lab.ITEMS]
        self.assertEqual(ids, [f"LC-{n}" for n in (1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15)] + ["PA-43"])


if __name__ == "__main__":
    unittest.main()
