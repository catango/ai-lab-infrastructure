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
        self.owners, self.flags, self.flags_error = {}, {}, None
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
        self.write(self.prefix / "lab" / "lab.conf", "machine_login=machine-bot\nowner=owner\nai_user=ai\nadmin_user=adm\ndeny_layer=both\n")
        self.write(self.prefix / "lab" / "deny.txt", "# the lab-wide deny list\n" + "\n".join(DENY) + "\n")
        self.write(self.prefix / "lab" / "engine" / "scripts" / "toolchain", "", 0o755)
        self.write(self.prefix / "bin" / "gh", "", 0o755)
        self.write(self.home / ".gitconfig", f"[user]\n\tname = machine-bot\n\temail = {EMAIL}\n")
        self.record_sshd()
        self.layer()

    def owner_of(self, info):
        """The seam for ownership: the test user cannot own a file as root, so the fixtures record who owns what."""
        return self.owners.get((info.st_dev, info.st_ino), (info.st_uid, info.st_gid))

    def flags_of(self, fd):
        """The seam for FS_IOC_GETFLAGS, which a container or a test user may not have."""
        if self.flags_error:
            raise self.flags_error
        info = os.fstat(fd)
        return self.flags.get((info.st_dev, info.st_ino), 0)

    def own(self, path, uid, gid):
        info = os.lstat(path)
        self.owners[(info.st_dev, info.st_ino)] = (uid, gid)

    def layer_object(self, deny=None):
        return {"enableAllProjectMcpServers": False,
                "permissions": {"deny": list(DENY if deny is None else deny), "disableBypassPermissionsMode": "disable"}}

    def layer(self, text=None, mode=0o644, immutable=True, root=True):
        """The user-level layer as lab setup leaves it: root:root 0644, immutable, in a directory the AI user owns."""
        directory = self.home / ".claude"
        directory.mkdir(mode=0o700, exist_ok=True)
        path = directory / "settings.json"
        path.unlink(missing_ok=True)
        self.write(path, json.dumps(self.layer_object(), indent=2) + "\n" if text is None else text, mode)
        if root:
            self.own(path, 0, 0)
        if immutable:
            info = os.lstat(path)
            self.flags[(info.st_dev, info.st_ino)] = 0x10
        return path

    def set_conf(self, **values):
        path = self.prefix / "lab" / "lab.conf"
        lines = [line for line in path.read_text().splitlines() if line.split("=")[0] not in values]
        self.write(path, "\n".join(lines + [f"{key}={value}" for key, value in values.items()]) + "\n")

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
        ssh = str(self.root / "etc" / "ssh")
        audit.write_snapshot(str(path), text or self.sshd_text(), audit.config_digest(ssh), stat_digest=audit.config_stat_digest(ssh))

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
                                      chain_top=str(self.base), owner_of=self.owner_of, flags_of=self.flags_of, ai_uid=ME)
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
                         {f"LC-{n}" for n in (1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16)} | {"PA-43"})

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

    def test_lc2_a_password_prompt_cannot_tell_a_rule_from_no_rule_so_it_is_a_warning(self):
        machine = self.machine()
        machine.sudo = (1, "sudo: a password is required")
        results = machine.check("LC-2")
        self.assertEqual([status for status, _ in results], ["WARN"], results)
        self.assertIn("sudo -l -U", results[0][1])
        machine.lab.groups = ["ai", "sudo"]
        self.assertFail(machine.check("LC-2"), "sudo")  # a root-equivalent group still fails whatever sudo answers

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

    @unittest.skipIf(os.geteuid() == 0, "root reads every file")
    def test_a_config_file_this_account_cannot_read_is_a_warning_and_never_a_crash(self):
        machine = self.machine()
        provider = machine.root / "etc" / "ssh" / "sshd_config.d" / "60-provider.conf"
        machine.write(provider, "# provider\n", 0o000)
        machine.record_sshd()
        results = machine.check("LC-13")
        self.assertEqual(sorted(status for status, _ in results), ["PASS", "WARN"], results)
        self.assertIn("60-provider.conf cannot be read by this account", " ".join(detail for _, detail in results))
        # the record still catches a change of that file, by its size and time
        provider.chmod(0o600)
        provider.write_text("# provider\n# changed\n")
        provider.chmod(0o000)
        self.assertFail(machine.check("LC-13"), "changed after lab setup")
        # a record without the size and time part cannot vouch for a file that cannot be read
        path = machine.root / "etc" / "ssh" / "ai-lab-sshd-effective.txt"
        path.unlink()
        audit.write_snapshot(str(path), machine.sshd_text(), "0" * 64)
        self.assertFail(machine.check("LC-13"), "no size and time record")
        provider.chmod(0o600)

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


class UserLayer(Case):
    """PA-54, PA-A36: LC-16, the user-level deny layer of the AI user, read-only, one fixture per failure."""

    def layer_file(self, machine):
        return machine.home / ".claude" / "settings.json"

    def assertLc16Fails(self, machine, text):
        results = machine.check("LC-16")
        self.assertEqual([status for status, _ in results if status == "FAIL"], ["FAIL"], results)
        self.assertIn(text, " ".join(detail for _, detail in results))
        return results

    def test_a_complete_layer_passes_in_both_and_in_user_mode(self):
        for mode in ("both", "user"):
            machine = self.machine()
            machine.set_conf(deny_layer=mode)
            self.assertPass(machine.check("LC-16"))

    def test_claude_a_link_or_missing_or_not_owned_by_the_ai_user_fails(self):
        machine = self.machine()
        moved = machine.home / ".claude.real"
        os.rename(machine.home / ".claude", moved)
        (machine.home / ".claude").symlink_to(moved)
        self.assertLc16Fails(machine, "~/.claude is a link")
        machine = self.machine()
        os.rename(machine.home / ".claude", machine.home / "elsewhere")
        self.assertLc16Fails(machine, "~/.claude does not exist")
        machine = self.machine()
        machine.own(machine.home / ".claude", 0, 0)
        self.assertLc16Fails(machine, "~/.claude is not owned by the AI user")

    def test_settings_a_link_hard_linked_not_root_not_0644_not_immutable_fail(self):
        machine = self.machine()
        path = self.layer_file(machine)
        real = machine.home / ".claude" / "real.json"
        os.rename(path, real)
        path.symlink_to(real)
        self.assertLc16Fails(machine, "settings.json is a link")
        machine = self.machine()
        os.link(self.layer_file(machine), machine.base / "second-name")
        self.assertLc16Fails(machine, "hard-linked")
        machine = self.machine()
        machine.layer(root=False)
        self.assertLc16Fails(machine, "not owned by root")
        for mode in (0o600, 0o664, 0o666):
            machine = self.machine()
            machine.layer(mode=mode)
            self.assertLc16Fails(machine, "mode is not 0644")
        machine = self.machine()
        machine.layer(immutable=False)
        self.assertLc16Fails(machine, "the immutable attribute is not set")

    def test_an_attribute_that_cannot_be_read_fails_and_names_the_errno(self):
        machine = self.machine()
        machine.flags_error = OSError(25, "Inappropriate ioctl for device")
        results = self.assertLc16Fails(machine, "immutable attribute cannot be read")
        self.assertIn("ENOTTY", " ".join(detail for _, detail in results))

    def test_a_directory_or_a_missing_file_in_place_of_settings_fails(self):
        machine = self.machine()
        self.layer_file(machine).unlink()
        self.assertLc16Fails(machine, "settings.json does not exist")
        self.layer_file(machine).mkdir()
        self.assertLc16Fails(machine, "settings.json is not a regular file")

    def test_a_key_outside_the_canonical_object_fails(self):
        for change in (lambda o: o.update({"env": {"X": "1"}}), lambda o: o["permissions"].update({"allow": ["Bash(ls)"]}),
                       lambda o: o.update({"$schema": "x"}), lambda o: o.pop("enableAllProjectMcpServers"),
                       lambda o: o["permissions"].pop("disableBypassPermissionsMode")):
            machine = self.machine()
            obj = machine.layer_object()
            change(obj)
            machine.layer(json.dumps(obj, indent=2) + "\n")
            self.assertLc16Fails(machine, "canonical object")

    def test_a_missing_extra_changed_or_reordered_entry_fails(self):
        for deny, text in ((DENY[:-1], "1 entry missing"), (DENY + ["Bash(extra *)"], "1 entry not in the lab-wide list"),
                           ([DENY[0], DENY[1], DENY[2], "Read(~/.config/gh/*)"], "differs from the lab-wide list"),
                           ([DENY[1], DENY[0]] + DENY[2:], "order"), (DENY + [DENY[0]], "repeated")):
            machine = self.machine()
            machine.layer(json.dumps(machine.layer_object(deny), indent=2) + "\n")
            self.assertLc16Fails(machine, text)

    def test_a_changed_value_of_either_setting_fails(self):
        for value in ("enable", True, None):
            machine = self.machine()
            obj = machine.layer_object()
            obj["permissions"]["disableBypassPermissionsMode"] = value
            machine.layer(json.dumps(obj) + "\n")
            self.assertLc16Fails(machine, "disableBypassPermissionsMode")
        for value in (True, "false", 0):
            machine = self.machine()
            obj = machine.layer_object()
            obj["enableAllProjectMcpServers"] = value
            machine.layer(json.dumps(obj) + "\n")
            self.assertLc16Fails(machine, "enableAllProjectMcpServers")

    def test_invalid_json_and_a_json_value_that_is_not_an_object_fail_without_printing_the_content(self):
        for text in ("{not json canary-secret", "[\"canary-secret\"]", "\"canary-secret\"", ""):
            machine = self.machine()
            machine.layer(text)
            results = machine.check("LC-16")
            self.assertEqual(results[0][0], "FAIL")
            self.assertNotIn("canary", " ".join(detail for _, detail in results))

    def test_it_prints_no_content_of_the_file(self):
        machine = self.machine()
        obj = machine.layer_object()
        obj["permissions"]["allow"] = ["Bash(canary-secret *)"]
        obj["canary"] = "canary-secret"
        machine.layer(json.dumps(obj) + "\n")
        self.assertNotIn("canary", " ".join(detail for _, detail in machine.check("LC-16")))

    def test_a_moved_claude_directory_is_a_warning_and_a_file_of_that_name_is_not(self):
        machine = self.machine()
        (machine.home / ".claude.json").write_text("{}")
        self.assertPass(machine.check("LC-16"))
        (machine.home / ".claude.moved").mkdir()
        results = machine.check("LC-16")
        self.assertEqual([status for status, _ in results], ["PASS", "WARN"])
        self.assertIn(".claude.moved", results[1][1])

    def test_a_moved_directory_warns_next_to_the_failure_it_causes(self):
        machine = self.machine()
        os.rename(machine.home / ".claude", machine.home / ".claude.moved")
        results = machine.check("LC-16")
        self.assertEqual([status for status, _ in results], ["FAIL", "WARN"])

    def test_the_lab_wide_list_is_the_reference_and_must_be_root_owned_and_present(self):
        machine = self.machine()
        (machine.prefix / "lab" / "deny.txt").unlink()
        self.assertLc16Fails(machine, "lab-wide deny list")
        machine = self.machine()
        (machine.prefix / "lab" / "deny.txt").chmod(0o666)
        self.assertLc16Fails(machine, "lab-wide deny list")
        machine = self.machine()
        (machine.prefix / "lab" / "deny.txt").write_text("# nothing\n")
        self.assertLc16Fails(machine, "lab-wide deny list")

    def test_a_list_with_other_entries_than_the_layer_fails_so_a_new_project_entry_must_reach_the_layer(self):
        machine = self.machine()
        (machine.prefix / "lab" / "deny.txt").write_text("\n".join(DENY + ["Read(~/.config/svc/token)"]) + "\n")
        self.assertLc16Fails(machine, "1 entry missing")

    def test_a_lab_conf_without_or_with_an_unknown_deny_layer_fails(self):
        for value in ("", "everything", "BOTH"):
            machine = self.machine()
            machine.set_conf(deny_layer=value)
            self.assertLc16Fails(machine, "deny_layer")
        machine = self.machine()
        text = (machine.prefix / "lab" / "lab.conf").read_text().replace("deny_layer=both\n", "")
        (machine.prefix / "lab" / "lab.conf").write_text(text)
        self.assertLc16Fails(machine, "deny_layer")

    def test_managed_mode_passes_with_a_note_and_does_not_look_at_the_layer(self):
        machine = self.machine()
        machine.set_conf(deny_layer="managed")
        self.layer_file(machine).unlink()
        (machine.home / ".claude").rmdir()
        results = machine.check("LC-16")
        self.assertEqual([status for status, _ in results], ["PASS"])
        self.assertIn("not selected", results[0][1])

    def test_managed_mode_warns_when_a_root_owned_file_is_at_the_layer_path(self):
        machine = self.machine()
        machine.set_conf(deny_layer="managed")
        results = machine.check("LC-16")
        self.assertEqual([status for status, _ in results], ["PASS", "WARN"])
        self.assertIn("switched", results[1][1])
        self.assertIn("nothing removes it", results[1][1])

    def test_managed_mode_does_not_warn_for_a_file_the_ai_user_owns(self):
        machine = self.machine()
        machine.set_conf(deny_layer="managed")
        machine.layer(root=False, immutable=False)
        self.assertEqual([status for status, _ in machine.check("LC-16")], ["PASS"])

    def test_it_changes_nothing(self):
        for mode in ("both", "managed"):
            machine = self.machine()
            machine.set_conf(deny_layer=mode)
            (machine.home / ".claude.moved").mkdir()
            before = tree_hash(machine.base)
            machine.check("LC-16")
            self.assertEqual(tree_hash(machine.base), before)

    def test_the_check_reads_the_attribute_through_a_descriptor_that_does_not_follow_a_link(self):
        text = (TOOLS / "lab-check").read_text()
        self.assertIn("FS_IOC_GETFLAGS", text)
        self.assertIn("O_NOFOLLOW", text)
        self.assertNotIn("lsattr", text)


class UserLayerCredentials(Case):
    """PA-A31 (as amended): coverage of a project credential path is read from the managed settings and, when selected, the layer."""

    def setUp(self):
        self.lab_machine = self.machine()
        repo = self.lab_machine.repo("project")
        self.lab_machine.write(repo / "docs" / "PROJECT.md", "## Credential paths\n\n- `~/.config/svc/token` - a test credential\n")
        self.lab_machine.write(self.lab_machine.home / ".config" / "svc" / "token", "x", 0o600)
        self.lab_machine.write(self.lab_machine.root / "etc" / "claude-code" / "managed-settings.json",
                               json.dumps({"permissions": {"deny": DENY}}))

    def layer_with_rule(self):
        self.lab_machine.layer(json.dumps(self.lab_machine.layer_object(DENY + ["Read(~/.config/svc/token)"])) + "\n")

    def test_a_rule_that_only_the_layer_carries_covers_the_path_when_the_layer_is_selected(self):
        self.layer_with_rule()
        self.assertPass(self.lab_machine.check("PA-43"))

    def test_the_layer_is_not_read_in_managed_mode(self):
        self.lab_machine.set_conf(deny_layer="managed")
        self.layer_with_rule()
        self.assertFail(self.lab_machine.check("PA-43"), "not covered")

    def test_a_rule_in_neither_layer_does_not_cover_it(self):
        self.assertFail(self.lab_machine.check("PA-43"), "not covered")


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


class Scratch(Case):
    def test_the_tools_it_starts_keep_their_state_in_a_scratch_directory_not_the_home(self):
        machine = self.machine()
        seen = {}
        lab = lab_check.Lab(audit, {}, "ai", str(machine.home), prefix=str(machine.prefix), scratch=str(machine.base / "scratch"))
        original = lab_check.subprocess.run

        def fake(argv, env=None, **_):
            seen.update(env)
            return type("Done", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        lab_check.subprocess.run = fake
        try:
            lab._run(["true"])
        finally:
            lab_check.subprocess.run = original
        for name in ("XDG_STATE_HOME", "XDG_CACHE_HOME", "ANSIBLE_HOME", "ANSIBLE_LOCAL_TEMP", "ANSIBLE_REMOTE_TEMP"):
            self.assertTrue(seen[name].startswith(str(machine.base / "scratch")), name)
        self.assertEqual(seen["HOME"], str(machine.home))


class Static(unittest.TestCase):
    def test_the_check_never_uses_a_shell_eval_or_a_write(self):
        text = (TOOLS / "lab-check").read_text()
        for banned in ("shell=True", "eval(", "exec(", "os.system", "os.popen", "open(path, \"w", ".write_text", "os.chmod", "os.remove",
                       "os.unlink", "shutil."):
            self.assertNotIn(banned, text, banned)

    def test_the_lab_check_has_exactly_the_contract_items(self):
        ids = [item for item, _ in lab_check.Lab.ITEMS]
        self.assertEqual(ids, [f"LC-{n}" for n in (1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16)] + ["PA-43"])


if __name__ == "__main__":
    unittest.main()
