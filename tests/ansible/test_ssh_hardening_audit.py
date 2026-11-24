"""CR-57 PA-16, PA-A18, PA-A29: the key rules and the sshd audit of the shared SSH hardening role.

The logic of the role's module is in plain functions, so these tests run without Ansible, root, or sshd: they build a small fake
machine (account homes in a temporary directory) and call the functions. The PA-28 job runs the same rules for real in a Debian
13 container (tests/ansible/pa28-lab.sh).
"""
import base64
import importlib.util
import os
import pathlib
import stat
import struct
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE = ROOT / "ansible" / "roles" / "ssh_hardening" / "library" / "ssh_hardening_audit.py"
spec = importlib.util.spec_from_file_location("ssh_hardening_audit", MODULE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

ME = os.getuid()


def key_line(seed, options="", comment="", key_type="ssh-ed25519"):
    """A well-formed public key line built from a seed (not a real key pair)."""
    name = key_type.encode()
    raw = struct.pack(">I", len(name)) + name + struct.pack(">I", 32) + bytes([seed]) * 32
    blob = base64.b64encode(raw).decode()
    return " ".join(part for part in (options, key_type, blob, comment) if part) + "\n"


class Machine:
    """Accounts with homes in a temporary directory, and a keys directory standing in for the root-owned location."""

    def __init__(self, test):
        self.tmp = tempfile.TemporaryDirectory()
        test.addCleanup(self.tmp.cleanup)
        self.base = pathlib.Path(self.tmp.name)
        self.keys_dir = self.base / "authorized_keys.d"
        self.entries = []

    def account(self, name, keys=None):
        home = self.base / "home" / name
        home.mkdir(parents=True)
        self.entries.append((name, str(home)))
        if keys is not None:
            (home / ".ssh").mkdir()
            (home / ".ssh" / "authorized_keys").write_text("".join(keys))
        return home

    def run(self, accounts=("ai", "adm"), private=("ai",), options=None):
        return audit.audit_keys(self.entries, list(accounts), list(private), str(self.keys_dir), options, trusted_uids=(ME,))


def good_machine(test):
    machine = Machine(test)
    machine.account("ai", [key_line(1, comment="ai")])
    machine.account("adm", [key_line(2, comment="adm")])
    machine.account("root", None)
    machine.account("daemon", None)
    return machine


class Parse(unittest.TestCase):
    def test_plain_key_with_comment(self):
        key = audit.parse_key_line(key_line(1, comment="some comment"))
        self.assertEqual((key.options, key.type, key.comment), ("", "ssh-ed25519", "some comment"))

    def test_options_with_quotes_and_spaces_are_kept_together(self):
        key = audit.parse_key_line(key_line(1, options='from="a b,c",verify-required'))
        self.assertEqual(key.options, 'from="a b,c",verify-required')
        self.assertEqual(key.type, "ssh-ed25519")

    def test_security_key_type(self):
        key = audit.parse_key_line(key_line(3, key_type="sk-ssh-ed25519@openssh.com", options="verify-required"))
        self.assertEqual(key.type, "sk-ssh-ed25519@openssh.com")

    def test_blank_and_comment_lines_are_not_keys(self):
        for line in ("", "   \n", "# a comment\n"):
            self.assertIsNone(audit.parse_key_line(line))

    def test_malformed_lines_raise(self):
        bad = ["ssh-ed25519\n", "ssh-ed25519 !!!notbase64\n", "garbage words here\n", 'opt="unterminated ssh-ed25519 AAAA\n',
               key_line(1, key_type="ssh-dss"), "ssh-rsa " + key_line(1).split()[1] + "\n"]
        for line in bad:
            with self.subTest(line=line[:20]):
                with self.assertRaises(ValueError):
                    audit.parse_key_line(line)


class KeyRules(unittest.TestCase):
    def test_one_key_each_passes_and_renders_the_files(self):
        result = good_machine(self).run(options={"ai": "restrict,pty"})
        self.assertEqual(result["problems"], [])
        self.assertTrue(result["files"]["ai"].startswith("restrict,pty ssh-ed25519 "))
        self.assertTrue(result["files"]["adm"].startswith("ssh-ed25519 "))
        self.assertTrue(result["files"]["adm"].endswith(" adm\n"))

    def test_options_of_the_provisioned_key_stay_in_front_of_the_forced_ones(self):
        machine = Machine(self)
        machine.account("ai", [key_line(1, options="verify-required")])
        machine.account("adm", [key_line(2)])
        result = machine.run(options={"ai": "restrict,pty"})
        self.assertTrue(result["files"]["ai"].startswith("verify-required,restrict,pty ssh-ed25519 "))

    def assert_refused(self, machine, fragment, **kwargs):
        problems = machine.run(**kwargs)["problems"]
        self.assertTrue(any(fragment in problem for problem in problems), problems)

    def test_a_missing_key_fails(self):
        machine = Machine(self)
        machine.account("ai", [key_line(1)])
        machine.account("adm", None)
        self.assert_refused(machine, "adm: has no key")

    def test_an_empty_key_file_fails(self):
        machine = Machine(self)
        machine.account("ai", [key_line(1)])
        machine.account("adm", ["# nothing here\n"])
        self.assert_refused(machine, "adm: has no key")

    def test_a_second_key_fails(self):
        machine = Machine(self)
        machine.account("ai", [key_line(1), key_line(9)])
        machine.account("adm", [key_line(2)])
        self.assert_refused(machine, "ai: has more than one key")

    def test_a_shared_key_fails_even_with_other_comments_and_options(self):
        machine = Machine(self)
        machine.account("ai", [key_line(1, comment="one")])
        machine.account("adm", [key_line(1, options="verify-required", comment="two")])
        self.assert_refused(machine, "adm and ai: share one key")

    def test_a_key_for_root_or_another_account_fails(self):
        for other in ("root", "daemon"):
            for name in ("authorized_keys", "authorized_keys2"):
                with self.subTest(account=other, file=name):
                    machine = good_machine(self)
                    home = pathlib.Path(dict(machine.entries)[other])
                    (home / ".ssh").mkdir(exist_ok=True)
                    (home / ".ssh" / name).write_text(key_line(7))
                    self.assert_refused(machine, f"{other}: is not a managed account")

    def test_a_comment_only_file_of_another_account_is_not_a_key(self):
        machine = good_machine(self)
        home = pathlib.Path(dict(machine.entries)["root"])
        (home / ".ssh").mkdir()
        (home / ".ssh" / "authorized_keys").write_text("# empty\n\n")
        self.assertEqual(machine.run()["problems"], [])

    def test_a_key_file_of_another_account_in_the_root_owned_location_fails(self):
        machine = good_machine(self)
        machine.keys_dir.mkdir()
        (machine.keys_dir / "stranger").write_text(key_line(5))
        self.assert_refused(machine, "stranger: is not a managed account and has a key in the root-owned location")

    def test_a_private_key_in_the_ai_users_ssh_directory_fails(self):
        marker = "-" * 5 + "BEGIN OPENSSH " + "PRIVATE KEY" + "-" * 5
        for filename, content in (("id_ed25519", "x\n"), ("anything", marker + "\n")):
            with self.subTest(file=filename):
                machine = good_machine(self)
                (pathlib.Path(dict(machine.entries)["ai"]) / ".ssh" / filename).write_text(content)
                self.assert_refused(machine, "ai: ~/.ssh holds a private key")

    def test_a_public_key_file_is_not_a_private_key(self):
        machine = good_machine(self)
        (pathlib.Path(dict(machine.entries)["ai"]) / ".ssh" / "id_ed25519.pub").write_text(key_line(1))
        self.assertEqual(machine.run()["problems"], [])

    def test_the_private_key_rule_covers_only_the_listed_accounts(self):
        machine = good_machine(self)
        (pathlib.Path(dict(machine.entries)["adm"]) / ".ssh" / "id_ed25519").write_text("x\n")
        self.assertEqual(machine.run(private=("ai",))["problems"], [])
        self.assert_refused(machine, "adm: ~/.ssh holds a private key", private=("ai", "adm"))

    def test_a_symbolic_link_is_never_followed(self):
        machine = good_machine(self)
        ai = pathlib.Path(dict(machine.entries)["ai"])
        target = machine.base / "elsewhere"
        target.write_text(key_line(1))
        (ai / ".ssh" / "authorized_keys").unlink()
        (ai / ".ssh" / "authorized_keys").symlink_to(target)
        self.assert_refused(machine, "ai: its authorized_keys is a link")
        self.assertEqual(target.read_text(), key_line(1))

    def test_a_linked_ssh_directory_fails(self):
        machine = Machine(self)
        ai = machine.account("ai", None)
        real = machine.base / "real-ssh"
        real.mkdir()
        (real / "authorized_keys").write_text(key_line(1))
        (ai / ".ssh").symlink_to(real)
        machine.account("adm", [key_line(2)])
        self.assert_refused(machine, "ai: ~/.ssh is a link")

    def test_a_missing_account_fails(self):
        machine = Machine(self)
        machine.account("ai", [key_line(1)])
        self.assert_refused(machine, "adm: the account does not exist")

    def test_the_root_owned_copy_wins_so_a_later_edit_of_the_home_file_is_inert(self):
        machine = good_machine(self)
        first = machine.run(options={"ai": "restrict,pty"})
        audit.install_files(first["files"], str(machine.keys_dir))
        ai_file = pathlib.Path(dict(machine.entries)["ai"]) / ".ssh" / "authorized_keys"
        ai_file.write_text(key_line(1) + key_line(8))
        again = machine.run(options={"ai": "restrict,pty"})
        self.assertEqual(again["problems"], [])
        self.assertEqual(again["files"], first["files"])

    def test_a_root_owned_copy_that_is_not_owned_by_a_trusted_user_fails(self):
        machine = good_machine(self)
        audit.install_files(machine.run()["files"], str(machine.keys_dir))
        problems = audit.audit_keys(machine.entries, ["ai", "adm"], ["ai"], str(machine.keys_dir), None, trusted_uids=(ME + 1,))["problems"]
        self.assertTrue(any("not owned by root" in problem for problem in problems), problems)

    @unittest.skipIf(os.getuid() == 0, "root can read everything")
    def test_a_home_that_cannot_be_read_is_a_finding_not_a_crash(self):
        machine = good_machine(self)
        locked = pathlib.Path(dict(machine.entries)["daemon"])
        (locked / ".ssh").mkdir()
        (locked / ".ssh" / "authorized_keys").write_text(key_line(6))
        locked.chmod(0)
        self.addCleanup(locked.chmod, 0o755)
        self.assert_refused(machine, "daemon: its key files cannot be read")

    def test_findings_never_contain_key_material(self):
        machine = Machine(self)
        machine.account("ai", [key_line(1), key_line(9)])
        machine.account("adm", [key_line(1)])
        text = " ".join(machine.run()["problems"])
        for seed in (1, 9):
            self.assertNotIn(key_line(seed).split()[1], text)


class Install(unittest.TestCase):
    def test_writes_root_owned_style_files_once_and_changes_nothing_the_second_time(self):
        machine = good_machine(self)
        files = machine.run()["files"]
        self.assertTrue(audit.install_files(files, str(machine.keys_dir)))
        for name in files:
            self.assertEqual(stat.S_IMODE((machine.keys_dir / name).stat().st_mode), 0o644)
            self.assertEqual((machine.keys_dir / name).read_text(), files[name])
        self.assertFalse(audit.install_files(files, str(machine.keys_dir)))

    def test_check_mode_writes_nothing(self):
        machine = good_machine(self)
        self.assertTrue(audit.install_files(machine.run()["files"], str(machine.keys_dir), check_mode=True))
        self.assertFalse(machine.keys_dir.exists())

    def test_a_changed_key_is_replaced_and_no_temporary_file_stays(self):
        machine = good_machine(self)
        files = machine.run()["files"]
        audit.install_files(files, str(machine.keys_dir))
        files["adm"] = key_line(4)
        self.assertTrue(audit.install_files(files, str(machine.keys_dir)))
        self.assertEqual(sorted(path.name for path in machine.keys_dir.iterdir()), ["adm", "ai"])

    def test_nothing_is_written_into_a_home(self):
        machine = good_machine(self)
        before = sorted(str(path.relative_to(machine.base)) for path in (machine.base / "home").rglob("*"))
        audit.install_files(machine.run()["files"], str(machine.keys_dir))
        after = sorted(str(path.relative_to(machine.base)) for path in (machine.base / "home").rglob("*"))
        self.assertEqual(before, after)


SSHD_BEFORE = "port 22\nauthorizedkeyscommand none\ntrustedusercakeys none\nauthorizedprincipalsfile none\nauthorizedkeysfile .ssh/authorized_keys\n"
SSHD_AFTER = (SSHD_BEFORE.replace(".ssh/authorized_keys", "/etc/ssh/authorized_keys/%u")
              + "pubkeyauthentication yes\npasswordauthentication no\nkbdinteractiveauthentication no\npermitrootlogin no\n"
              "authenticationmethods publickey\nallowagentforwarding no\nallowtcpforwarding no\nx11forwarding no\npermittunnel no\n"
              "permituserrc no\npermituserenvironment no\nallowusers ai adm\n")


class Sshd(unittest.TestCase):
    def test_unset_settings_pass(self):
        self.assertEqual(audit.audit_sshd(SSHD_BEFORE, "sshd_before"), [])

    def test_each_of_the_three_authentication_settings_fails_when_set(self):
        for keyword in audit.AUTH_SETTINGS:
            with self.subTest(keyword=keyword):
                text = SSHD_BEFORE.replace(f"{keyword} none", f"{keyword} /some/path")
                self.assertEqual(audit.audit_sshd(text, "sshd_before"), [f"sshd: {keyword} is set"])

    def test_empty_output_fails(self):
        self.assertEqual(audit.audit_sshd("", "sshd_before"), ["sshd -T printed nothing"])

    def test_the_hardened_output_passes(self):
        self.assertEqual(audit.audit_sshd(SSHD_AFTER, "sshd_after", ["ai", "adm"]), [])

    def test_keys_read_from_anywhere_else_fail_after_the_switch(self):
        text = SSHD_AFTER.replace("authorizedkeysfile /etc/ssh/authorized_keys/%u", "authorizedkeysfile /etc/ssh/authorized_keys/%u .ssh/authorized_keys")
        self.assertIn("sshd: authorized keys are not read from the root-owned location only", audit.audit_sshd(text, "sshd_after", ["ai", "adm"]))

    def test_a_relaxed_setting_fails_after_the_switch(self):
        for keyword in audit.EXPECTED_AFTER:
            with self.subTest(keyword=keyword):
                wanted = audit.EXPECTED_AFTER[keyword]
                other = "no" if wanted != "no" else "yes"
                text = SSHD_AFTER.replace(f"{keyword} {wanted}", f"{keyword} {other}")
                self.assertEqual(audit.audit_sshd(text, "sshd_after", ["ai", "adm"]), [f"sshd: {keyword} is not {wanted}"])

    def test_allowusers_must_be_exactly_the_managed_accounts(self):
        problems = audit.audit_sshd(SSHD_AFTER.replace("allowusers ai adm", "allowusers ai adm other"), "sshd_after", ["ai", "adm"])
        self.assertEqual(problems, ["sshd: AllowUsers is not exactly the managed accounts"])


if __name__ == "__main__":
    unittest.main()
