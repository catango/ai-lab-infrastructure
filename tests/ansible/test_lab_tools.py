"""CR-57 plan PR 3: the lab_tools role (the root-owned token step and lab check, LC-14), the sshd snapshot, and the PC-8 path.

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

    def test_the_new_role_is_an_operator_path_for_the_next_pr(self):
        """PC-8 reads the base commit, so this PR states the path in its body; the file lists it for every PR after this one."""
        config = (ROOT / "config" / "project.yaml").read_text()
        self.assertIn("  - ansible/roles/lab_tools/\n", config)

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
            body = role[role.index("content: |") + len("content: |\n"):role.index("      notify: Reload ssh")]
            (ssh / "sshd_config.d" / "00-ai-lab.conf").write_text("\n".join(line[10:] for line in body.splitlines()) + "\n")
            self.assertEqual(audit.audit_sshd_files(str(ssh)), [])
            (ssh / "sshd_config.d" / "99.conf").write_text("Banner /etc/issue\nMatch All\n")
            problems = audit.audit_sshd_files(str(ssh))
            self.assertIn("sshd: banner in sshd_config.d/99.conf is outside LC-13", problems)
            self.assertIn("sshd: a Match block in sshd_config.d/99.conf hides settings from the audit", problems)


if __name__ == "__main__":
    unittest.main()
