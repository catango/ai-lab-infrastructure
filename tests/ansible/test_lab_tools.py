"""CR-57 plan PR 3 and PR 4: the lab_tools role (the root-owned token step and lab check, LC-14), the sshd snapshot, and the PC-8 paths.

Nothing here needs root. The role is read in text and run in check mode against a temporary prefix; what needs root (ownership,
the links in /usr/local/bin, the AI user unable to write) is the PA-28 job (tests/ansible/pa28-lab.sh, job `host-profiles`).
"""
import importlib.util
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
ROLE = ROOT / "ansible" / "roles" / "lab_tools"
MODULE = ROOT / "ansible" / "roles" / "ssh_hardening" / "library" / "ssh_hardening_audit.py"
spec = importlib.util.spec_from_file_location("ssh_hardening_audit", MODULE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class Role(unittest.TestCase):
    def test_layout_and_executable_scripts(self):
        for rel in ("tasks/main.yml", "defaults/main.yml", "files/token-step", "files/lab-check"):
            self.assertTrue((ROLE / rel).is_file(), rel)
        for rel in ("files/token-step", "files/lab-check"):
            self.assertTrue(os.access(ROLE / rel, os.X_OK), rel)
        self.assertTrue((ROLE / "files" / "token-step").read_text().startswith("#!/bin/bash -p\n"))
        self.assertTrue((ROLE / "files" / "lab-check").read_text().startswith("#!/usr/bin/python3 -I\n"))

    def test_every_install_task_is_root_owned_and_uses_the_root_check(self):
        text = (ROLE / "tasks" / "main.yml").read_text()
        tasks = re.split(r"^- name: ", text, flags=re.M)[1:]
        self.assertGreaterEqual(len(tasks), 5)
        for task in tasks:
            self.assertIn("owner: root", task, task.splitlines()[0])
            self.assertIn('become: "{{ ai_lab_become }}"', task, task.splitlines()[0])
        for mode in re.findall(r'^\s+mode: "(\d+)"', text, re.M):
            self.assertEqual(int(mode, 8) & 0o022, 0, f"mode {mode} is writable by others")

    def test_nothing_is_written_into_a_users_home(self):
        text = (ROLE / "tasks" / "main.yml").read_text() + (ROLE / "defaults" / "main.yml").read_text()
        self.assertNotRegex(text, r"/home/|~/|ansible_env|lab_ai_user }}/|ansible_user_dir")

    def test_the_lab_profile_applies_it_before_sshd(self):
        text = (ROOT / "ansible" / "lab.yml").read_text()
        roles = re.findall(r"^    - (?:role: )?([a-z_]+)$", text[text.index("  roles:"):], re.M)
        self.assertLess(roles.index("lab_tools"), roles.index("ssh_hardening"))
        self.assertEqual(roles[-1], "ssh_hardening")

    def test_lab_setup_applies_what_lc8_and_lc15_read_so_only_lc7_is_left_to_the_user(self):
        """Plan PR 4, first extension: the git identity and the unattended updates are part of lab setup (they had no owner before)."""
        text = (ROOT / "ansible" / "lab.yml").read_text()
        roles = re.findall(r"^    - (?:role: )?([a-z_]+)$", text[text.index("  roles:"):], re.M)
        for role in ("git_identity", "unattended_upgrades"):
            self.assertLess(roles.index(role), roles.index("ssh_hardening"), role)
        check = (ROLE / "files" / "lab-check").read_text()
        self.assertIn("APT::Periodic::Unattended-Upgrade", check)
        self.assertIn("def lc8", check)

    def test_the_roles_are_operator_paths(self):
        """PC-8 reads the base commit, so a PR that adds a path states it in its body; the file lists it for every PR after that."""
        config = (ROOT / "config" / "project.yaml").read_text()
        for path in ("lab_tools", "git_identity", "unattended_upgrades", "ssh_hardening", "release_check", "claude_managed_settings",
                     "claude_user_deny"):
            self.assertIn(f"  - ansible/roles/{path}/\n", config, path)
        self.assertIn("  - ansible/roles/operator_*/\n", config)

    def test_a_check_mode_run_renders_the_lab_configuration_from_the_project_configuration(self):
        if shutil.which("ansible-playbook") is None:
            self.skipTest("ansible-playbook is not installed")
        with tempfile.TemporaryDirectory() as tmp:
            play = pathlib.Path(tmp) / "play.yml"
            play.write_text("- hosts: all\n  connection: local\n  gather_facts: false\n  vars_files: [" + str(ROOT / "ansible" / "group_vars" / "all.yml")
                            + "]\n  roles: [lab_tools]\n")
            env = {"PATH": os.environ["PATH"], "HOME": tmp, "ANSIBLE_HOME": tmp, "ANSIBLE_LOCAL_TEMP": tmp, "ANSIBLE_NOCOLOR": "1",
                   "ANSIBLE_ROLES_PATH": str(ROOT / "ansible" / "roles"), "LC_ALL": "C.UTF-8"}
            done = subprocess.run(
                ["ansible-playbook", "-i", str(ROOT / "ansible" / "inventory" / "localhost.yml"), str(play), "--check", "--diff",
                 "-e", f"repo_root={ROOT}", "-e", f"toolchain_prefix={tmp}/opt", "-e", f"lab_tools_link_dir={tmp}/bin",
                 "-e", "ai_lab_become=false", "-e", "lab_ai_user=ai", "-e", "lab_admin_user=adm"],
                capture_output=True, text=True, env=env, cwd=tmp, timeout=120, check=False)
            out = done.stdout + done.stderr
            self.assertEqual(done.returncode, 0, out[-1500:])
            self.assertRegex(out, r"failed=0 ")
            self.assertIn("machine_login=", out)
            self.assertIn("ai_user=ai", out)
            self.assertIn("admin_user=adm", out)
            self.assertFalse((pathlib.Path(tmp) / "opt").exists(), "a check-mode run wrote")


class DenyLayerRole(unittest.TestCase):
    """CR-57 plan PR 4a (PA-47, PA-50 to PA-52, PA-54): the variable, deny.txt, the role, and the probe, read in text."""

    role = ROOT / "ansible" / "roles" / "claude_user_deny"

    def test_the_default_is_both_and_it_is_written_to_lab_conf(self):
        variables = (ROOT / "ansible" / "group_vars" / "all.yml").read_text()
        self.assertRegex(variables, r"(?m)^lab_deny_layer: both$")
        tasks = (ROLE / "tasks" / "main.yml").read_text()
        self.assertIn("deny_layer={{ lab_deny_layer }}", tasks)

    def test_lab_setup_installs_the_lab_wide_list_root_owned_beside_lab_conf_from_the_merged_list(self):
        """Plan PR 4a installed a byte copy of the core list; plan PR 8 installs the core list followed by a project's entries (the
        text is the core list byte for byte when no project is selected, see tests/lab/test_project_input.py)."""
        tasks = (ROLE / "tasks" / "main.yml").read_text()
        block = tasks[tasks.index("- name: Install the lab-wide deny list"):]
        block = block[:block.index("\n- name:", 1)] if "\n- name:" in block[1:] else block
        for needle in ("ansible.builtin.copy", 'content: "{{ lab_deny_text }}"', 'dest: "{{ lab_tools_dir }}/deny.txt"', "owner: root",
                       'mode: "0644"', 'become: "{{ ai_lab_become }}"'):
            self.assertIn(needle, block, needle)

    def test_the_variable_is_checked_before_anything_changes_and_the_probe_is_a_pre_task(self):
        text = (ROOT / "ansible" / "lab.yml").read_text()
        pre = text[text.index("  pre_tasks:"):text.index("  roles:")]
        self.assertIn("lab_deny_layer in ['both', 'user', 'managed']", pre)
        self.assertIn("tasks_from: probe", pre)
        self.assertIn("lab_deny_layer in ['both', 'user']", pre)
        self.assertLess(pre.index("Deny layer variable"), pre.index("Attribute probe"))
        self.assertLess(pre.index("Key audit"), pre.index("Attribute probe"))

    def test_the_role_runs_only_for_both_and_user_and_only_the_module_touches_the_home(self):
        text = (self.role / "tasks" / "main.yml").read_text()
        self.assertIn("lab_deny_layer in ['both', 'user']", text)
        self.assertIn("claude_user_deny:", text)
        for banned in ("ansible.builtin.file", "ansible.builtin.copy", "lineinfile", "blockinfile", "template", "ansible.builtin.command",
                       "ansible.builtin.shell", "chattr"):
            self.assertNotIn(banned, text, banned)
        probe = (self.role / "tasks" / "probe.yml").read_text()
        self.assertIn("action: probe", probe)
        self.assertIn("check_mode: false", probe)
        self.assertNotIn("ansible.builtin.copy", probe)

    def test_the_operator_profile_knows_nothing_of_the_layer(self):
        for path in (ROOT / "ansible").rglob("*.yml"):
            if path.name == "operator.yml" or "operator_" in str(path):
                self.assertNotRegex(path.read_text(), r"claude_user_deny|lab_deny_layer|deny_layer", str(path))

    def test_the_probe_can_be_skipped_only_by_naming_its_tag_which_the_fixtures_use_for_the_refusals(self):
        text = (ROOT / "ansible" / "lab.yml").read_text()
        block = text[text.index("- name: Attribute probe"):]
        self.assertIn("claude_user_deny_probe", block.split("\n\n")[0])


class Snapshot(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.ssh = pathlib.Path(tmp.name)
        (self.ssh / "sshd_config.d").mkdir()
        (self.ssh / "sshd_config").write_text("Include /etc/ssh/sshd_config.d/*.conf\nUsePAM yes\n")
        (self.ssh / "sshd_config.d" / "00-ai-lab.conf").write_text("PasswordAuthentication no\n")
        self.path = self.ssh / "snapshot.txt"
        self.uid = os.getuid()

    def write(self, text="passwordauthentication no\n"):
        return audit.write_snapshot(str(self.path), text, audit.config_digest(str(self.ssh)))

    def test_write_once_and_a_second_write_changes_nothing(self):
        self.assertTrue(self.write())
        self.assertFalse(self.write())
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o644)

    def test_check_mode_writes_nothing(self):
        self.assertTrue(audit.write_snapshot(str(self.path), "x\n", audit.config_digest(str(self.ssh)), check_mode=True))
        self.assertFalse(self.path.exists())

    def test_read_returns_the_text_while_the_configuration_is_unchanged(self):
        self.write("passwordauthentication no\n")
        text, problems = audit.read_snapshot(str(self.path), str(self.ssh), (self.uid,))
        self.assertEqual(problems, [])
        self.assertIn("passwordauthentication no", text)

    def test_read_refuses_after_any_configuration_file_changes(self):
        self.write()
        for name in ("sshd_config", "sshd_config.d/00-ai-lab.conf", "sshd_config.d/10-new.conf"):
            with self.subTest(changed=name):
                self.write()
                target = self.ssh / name
                original = target.read_text() if target.exists() else None
                target.write_text((original or "") + "# changed\n")
                _, problems = audit.read_snapshot(str(self.path), str(self.ssh), (self.uid,))
                self.assertTrue(any("changed after lab setup" in problem for problem in problems), problems)
                if original is None:
                    target.unlink()
                else:
                    target.write_text(original)

    def test_read_refuses_a_missing_foreign_or_writable_record(self):
        _, problems = audit.read_snapshot(str(self.path), str(self.ssh), (self.uid,))
        self.assertTrue(any("not recorded" in problem for problem in problems))
        self.write()
        _, problems = audit.read_snapshot(str(self.path), str(self.ssh), (self.uid + 1,))
        self.assertTrue(any("not owned by root" in problem for problem in problems))
        self.path.chmod(0o666)
        _, problems = audit.read_snapshot(str(self.path), str(self.ssh), (self.uid,))
        self.assertTrue(any("writable by others" in problem for problem in problems))

    @unittest.skipIf(os.geteuid() == 0, "root reads every file")
    def test_an_unreadable_file_gives_no_content_digest_and_the_stat_record_stands_in(self):
        provider = self.ssh / "sshd_config.d" / "60-provider.conf"
        provider.write_text("# provider\n")
        provider.chmod(0o000)
        self.assertIsNone(audit.config_digest(str(self.ssh)))
        self.assertEqual(audit.unreadable_config_files(str(self.ssh)), ["sshd_config.d/60-provider.conf"])
        # recorded as root would: the content digest is the one of a reader that can see every file
        provider.chmod(0o600)
        content_digest = audit.config_digest(str(self.ssh))
        provider.chmod(0o000)
        audit.write_snapshot(str(self.path), "passwordauthentication no\n", content_digest, stat_digest=audit.config_stat_digest(str(self.ssh)))
        text, problems = audit.read_snapshot(str(self.path), str(self.ssh), (self.uid,))
        self.assertEqual(problems, [])
        self.assertIn("passwordauthentication no", text)
        provider.chmod(0o600)
        provider.write_text("# provider\n# edited\n")
        provider.chmod(0o000)
        _, problems = audit.read_snapshot(str(self.path), str(self.ssh), (self.uid,))
        self.assertTrue(any("changed after lab setup" in problem for problem in problems), problems)
        self.assertEqual(audit.audit_sshd_files(str(self.ssh)), ["sshd: sshd_config.d/60-provider.conf cannot be read"])
        self.assertEqual(audit.audit_sshd_files(str(self.ssh), skip_unreadable=True), [])
        provider.chmod(0o600)

    def test_the_stat_record_changes_with_a_new_file_or_a_new_size_and_a_record_without_it_still_reads_while_all_files_are_readable(self):
        before = audit.config_stat_digest(str(self.ssh))
        (self.ssh / "sshd_config.d" / "10-new.conf").write_text("# x\n")
        self.assertNotEqual(audit.config_stat_digest(str(self.ssh)), before)
        (self.ssh / "sshd_config.d" / "10-new.conf").unlink()
        self.assertEqual(audit.config_stat_digest(str(self.ssh)), before)
        audit.write_snapshot(str(self.path), "passwordauthentication no\n", audit.config_digest(str(self.ssh)))
        _, problems = audit.read_snapshot(str(self.path), str(self.ssh), (self.uid,))
        self.assertEqual(problems, [])

    def test_the_module_records_the_stat_digest_with_the_snapshot(self):
        text = (ROOT / "ansible" / "roles" / "ssh_hardening" / "library" / "ssh_hardening_audit.py").read_text()
        self.assertIn("config_stat_digest(params[\"ssh_dir\"])", text)

    def test_the_role_records_the_snapshot_only_after_the_audit_of_the_switched_settings(self):
        text = (ROOT / "ansible" / "roles" / "ssh_hardening" / "tasks" / "main.yml").read_text()
        self.assertLess(text.index("mode: sshd_after"), text.index("mode: snapshot"))
        self.assertLess(text.index("mode: snapshot"), text.index("rescue:"))


class StrayOptions(unittest.TestCase):
    def test_the_managed_drop_in_and_the_debian_defaults_are_the_only_settings_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            ssh = pathlib.Path(tmp)
            (ssh / "sshd_config.d").mkdir()
            (ssh / "sshd_config").write_text("# default\nInclude /etc/ssh/sshd_config.d/*.conf\nX11Forwarding yes\nUsePAM=yes\n")
            role = (ROOT / "ansible" / "roles" / "ssh_hardening" / "tasks" / "main.yml").read_text()
            body = role[role.index("content: |") + len("content: |\n"):role.index("      become:", role.index("content: |"))]
            (ssh / "sshd_config.d" / "00-ai-lab.conf").write_text("\n".join(line[10:] for line in body.splitlines()) + "\n")
            self.assertEqual(audit.audit_sshd_files(str(ssh)), [])
            (ssh / "sshd_config.d" / "99.conf").write_text("Banner /etc/issue\nMatch All\n")
            problems = audit.audit_sshd_files(str(ssh))
            self.assertIn("sshd: banner in sshd_config.d/99.conf is outside LC-13", problems)
            self.assertIn("sshd: a Match block in sshd_config.d/99.conf hides settings from the audit", problems)


if __name__ == "__main__":
    unittest.main()
