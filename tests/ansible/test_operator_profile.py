"""The operator profile (CR-18 design section 5.5; acceptance P-3 and the static part of P-4 to P-7).

Static checks over the playbook and roles, plus one real playbook run that must be refused before any task runs. The profile is
applied for real only by `setup --apply` (CI container, approver); nothing here changes this machine.
"""
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
ANSIBLE = ROOT / "ansible"
ROLES = ("operator_user", "operator_sudo", "operator_ssh", "operator_system", "operator_firewall", "operator_checks", "operator_lock")
HAVE_ANSIBLE = shutil.which("ansible-playbook") is not None


def tasks(role):
    return (ANSIBLE / "roles" / role / "tasks" / "main.yml").read_text()


def everything():
    return {p.relative_to(ANSIBLE).as_posix(): p.read_text() for p in ANSIBLE.rglob("*.yml") if "operator" in p.as_posix()}


class Structure(unittest.TestCase):
    def test_layout(self):
        self.assertTrue((ANSIBLE / "operator.yml").is_file())
        for role in ROLES:
            self.assertTrue((ANSIBLE / "roles" / role / "tasks" / "main.yml").is_file(), role)

    def test_role_names_match_the_pc8_path_rule(self):
        for role in ROLES:
            self.assertTrue(role.startswith("operator_"))

    def test_the_first_play_applies_the_roles_in_a_fixed_order(self):
        text = (ANSIBLE / "operator.yml").read_text()
        first = text.split("\n- name:")[0] if "\n- name:" in text else text
        order = ["apt_base", "toolchain", "python_tools", "shell_env", "operator_system", "operator_user", "operator_sudo",
                 "operator_ssh", "operator_firewall", "operator_checks", "verify"]
        positions = [first.index(f"- {role}") for role in order]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("operator_lock", first)

    def test_the_toolchain_profile_is_operator(self):
        self.assertIn("toolchain_profile: operator", (ANSIBLE / "operator.yml").read_text())

    def test_the_apply_guard_is_the_first_task_and_runs_before_anything_else(self):
        text = (ANSIBLE / "operator.yml").read_text()
        first_task = text.index("- name:", text.index("pre_tasks:"))
        self.assertIn("operator_apply", text[first_task:first_task + 600])
        self.assertIn("ansible_check_mode", text[first_task:first_task + 600])
        self.assertIn("always", text[first_task:first_task + 600])
        self.assertIn("operator_apply: false", (ANSIBLE / "group_vars" / "all.yml").read_text())

    def test_the_lock_play_is_separate_tagged_and_never_runs_by_default(self):
        text = (ANSIBLE / "operator.yml").read_text()
        play = text[text.index("Lock the initial"):]
        self.assertIn("operator_lock", play)
        self.assertRegex(play, r"tags:\s*\[[^\]]*never[^\]]*\]")
        for variable in ("operator_initial_account", "operator_login_confirmed"):
            self.assertIn(variable, tasks("operator_lock"))
        self.assertIn("DenyUsers", tasks("operator_lock"))

    def test_the_preflight_names_the_one_supported_platform(self):
        group = (ANSIBLE / "group_vars" / "all.yml").read_text()
        for line in ("operator_expected_os: Ubuntu", 'operator_expected_major: "24"', "operator_expected_arch: x86_64"):
            self.assertIn(line, group)


class Privilege(unittest.TestCase):
    def test_become_goes_through_the_root_check_and_is_never_blanket(self):
        for name, text in everything().items():
            self.assertNotIn("become: true", text, name)
            for match in re.finditer(r"become:\s*(.+)", text):
                self.assertIn(match.group(1).strip().strip('"'), ("{{ ai_lab_become }}", "false"), name)

    def test_no_shell_raw_download_or_remote_code_in_the_operator_files(self):
        for name, text in everything().items():
            for banned in ("ansible.builtin.shell", "ansible.builtin.raw", "get_url", "ansible.builtin.uri", "unarchive", "curl ", "wget ", "| sh", "| bash", "eval "):
                self.assertNotIn(banned, text, f"{name}: {banned}")

    def test_no_nopasswd_rule_is_ever_written(self):
        for name, text in everything().items():
            for line in text.splitlines():
                if "NOPASSWD" in line and "ALL=" in line:
                    self.fail(f"{name}: a sudoers rule with NOPASSWD: {line.strip()}")

    def test_sudo_asks_for_the_password_every_time(self):
        text = tasks("operator_sudo")
        self.assertIn("timestamp_timeout=0", text)
        self.assertIn("visudo", text)
        self.assertRegex(text, r"ALL=\(ALL:ALL\) ALL")
        self.assertIn("/etc/sudoers.d/", text)

    def test_other_files_lose_their_nopasswd_option(self):
        text = tasks("operator_sudo")
        self.assertIn("NOPASSWD", text)
        self.assertIn("ansible.builtin.replace", text)
        self.assertIn("ansible.builtin.find", text)


class Ssh(unittest.TestCase):
    def test_the_drop_in_is_key_only_and_wins_over_later_files(self):
        text = tasks("operator_ssh")
        self.assertIn("/etc/ssh/sshd_config.d/10-operator.conf", text)
        for line in ("PasswordAuthentication no", "KbdInteractiveAuthentication no", "PermitRootLogin no", "PubkeyAuthentication yes",
                     "X11Forwarding no", "AllowAgentForwarding no", "MaxAuthTries 3"):
            self.assertIn(line, text)

    def test_the_config_is_validated_before_it_is_kept(self):
        self.assertIn("sshd -t", tasks("operator_ssh"))

    def test_the_operator_user_has_a_private_home_and_ssh_directory(self):
        text = tasks("operator_user")
        self.assertIn('mode: "0700"', text)
        self.assertIn("authorized_keys", text)
        self.assertNotRegex(text, r"groups:\s*\S*(sudo|adm|docker|lxd|disk)")


class Firewall(unittest.TestCase):
    def test_the_ruleset_is_its_own_table_with_a_default_drop_and_an_optional_ssh_allowlist(self):
        text = tasks("operator_firewall")
        self.assertIn("table inet operator", text)
        self.assertIn("policy drop", text)
        self.assertIn("tcp dport 22", text)
        self.assertNotIn("flush ruleset", text.split("operator.nft", 1)[-1].split("nftables.conf")[0])
        self.assertIn("ssh-allowlist", text)

    def test_the_change_is_checked_and_reverts_unless_confirmed(self):
        text = tasks("operator_firewall")
        self.assertIn("nft -c -f %s", text)
        self.assertIn("systemd-run", text)
        self.assertIn("operator-firewall-revert", text)
        self.assertIn("ansible.builtin.pause", text)

    def test_it_is_skipped_where_it_cannot_work(self):
        text = tasks("operator_firewall")
        self.assertIn("service_mgr", text)
        self.assertIn("virtualization_type", text)


class Checks(unittest.TestCase):
    def test_the_separation_checks_cover_the_design_list(self):
        text = tasks("operator_checks")
        for needle in (".claude/remote", "findmnt", "NOPASSWD", "-nG", "check_mode: false"):
            self.assertIn(needle, text)


@unittest.skipUnless(HAVE_ANSIBLE, "ansible-playbook is not installed")
class Guard(unittest.TestCase):
    def test_a_real_run_without_the_apply_variable_is_refused_before_any_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {"PATH": os.environ["PATH"], "HOME": tmp, "ANSIBLE_HOME": tmp, "ANSIBLE_LOCAL_TEMP": tmp,
                   "ANSIBLE_CONFIG": str(ANSIBLE / "ansible.cfg"), "ANSIBLE_NOCOLOR": "1", "LC_ALL": "C.UTF-8"}
            done = subprocess.run(["ansible-playbook", "-i", str(ANSIBLE / "inventory" / "localhost.yml"), str(ANSIBLE / "operator.yml")],
                                  capture_output=True, text=True, env=env, cwd=ROOT, timeout=120, check=False, stdin=subprocess.DEVNULL)
        output = done.stdout + done.stderr
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("operator_apply", output)
        self.assertNotIn("TASK [apt_base", output)
        self.assertNotIn("TASK [operator_", output)

    def test_the_playbook_passes_the_syntax_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {"PATH": os.environ["PATH"], "HOME": tmp, "ANSIBLE_HOME": tmp, "ANSIBLE_LOCAL_TEMP": tmp, "ANSIBLE_NOCOLOR": "1", "LC_ALL": "C.UTF-8"}
            done = subprocess.run(["ansible-playbook", "-i", "localhost,", "--syntax-check", str(ANSIBLE / "operator.yml")],
                                  capture_output=True, text=True, env=env, cwd=ROOT, timeout=120, check=False)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)


if __name__ == "__main__":
    unittest.main()
