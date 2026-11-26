"""CR-57 plan PR 8 (PA-34, PA-A23, PA-A31, O-18, O-22, I-7, R-2): the lab_project role and its place in lab setup.

Nothing here needs root. The role is read in text, and a play that runs the project input and the role in check mode runs against a
temporary prefix and a local clone (the supplied-SHA channel with no account change). What needs root and a second account (the AI
user cannot modify the tools, the smoke test runs as that user, the apply of a package list) is the PA-28 job
(tests/ansible/pa28-lab.sh, step `project`).
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
ROLE = ROOT / "ansible" / "roles" / "lab_project"
ANSIBLE = ROOT / "ansible"
GIT_ENV = {"PATH": os.environ["PATH"], "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null", "GIT_AUTHOR_NAME": "t",
           "GIT_AUTHOR_EMAIL": "noreply", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "noreply"}
MANIFEST = ('schema_version = 1\n[tools.demo]\nversion = "1.0.0"\nprofiles = ["lab"]\nsource = "download"\nformat = "binary"\n'
            'binaries = ["demo"]\nsmoke = ["demo"]\nsmoke_match = "1.0.0"\n[tools.demo.artifacts.amd64]\n'
            'url = "https://example.org/demo-1.0.0"\nsha256 = "' + "0" * 64 + '"\n')


def tasks_of(path):
    return re.split(r"^- name: ", path.read_text(), flags=re.M)[1:]


class Layout(unittest.TestCase):
    def test_the_role_has_its_files(self):
        for rel in ("tasks/main.yml", "tasks/input.yml", "defaults/main.yml", "files/lab-project-input"):
            self.assertTrue((ROLE / rel).is_file(), rel)
        self.assertTrue(os.access(ROLE / "files" / "lab-project-input", os.X_OK))

    def test_lab_setup_reads_the_project_before_the_probe_and_applies_it_after_lab_tools(self):
        text = (ANSIBLE / "lab.yml").read_text()
        pre = text[text.index("  pre_tasks:"):text.index("  roles:")]
        self.assertLess(pre.index("name: Project input"), pre.index("name: Attribute probe"))
        self.assertLess(pre.index("name: Deny layer variable"), pre.index("name: Project input"))
        block = pre[pre.index("name: Project input") - 20:pre.index("name: Attribute probe")]
        self.assertIn("tags: [always]", block)
        self.assertIn("tasks_from: input", block)
        roles = re.findall(r"^    - (?:role: )?([a-z_]+)$", text[text.index("  roles:"):], re.M)
        self.assertLess(roles.index("lab_tools"), roles.index("lab_project"))
        self.assertLess(roles.index("lab_project"), roles.index("claude_user_deny"))
        self.assertLess(roles.index("lab_project"), roles.index("ssh_hardening"))

    def test_the_operator_profile_has_no_project_toolchain(self):
        self.assertNotIn("lab_project", (ANSIBLE / "operator.yml").read_text())

    def test_the_role_is_an_operator_path_from_the_next_pr_on(self):
        config = (ROOT / "config" / "project.yaml").read_text()
        self.assertIn("  - ansible/roles/lab_project/\n", config)


class Defaults(unittest.TestCase):
    text = (ROLE / "defaults" / "main.yml").read_text()

    def test_the_tools_go_to_opt_ai_lab_project_and_amd64_only(self):
        self.assertRegex(self.text, r'(?m)^lab_project_prefix: "\{\{ toolchain_prefix \}\}/project"$')
        self.assertRegex(self.text, r"(?m)^lab_project_arch: amd64$")

    def test_no_project_is_selected_by_default_and_nothing_is_reviewed_by_default(self):
        for name in ("lab_project_repo", "lab_project_ref", "lab_project_sha", "lab_project_clone", "lab_project_packages_reviewed"):
            self.assertRegex(self.text, rf"(?m)^{name}: ''$", name)

    def test_the_account_that_reads_the_supplied_clone_is_the_ai_user(self):
        self.assertRegex(self.text, r"""(?m)^lab_project_git_user: "\{\{ lab_ai_user \| default\(''\) \}\}"$""")

    def test_the_lab_wide_list_defaults_to_the_core_list(self):
        variables = (ANSIBLE / "group_vars" / "all.yml").read_text()
        self.assertIn("lab_deny_text: \"{{ lookup('ansible.builtin.file', lab_deny_list_source, rstrip=False) }}\"", variables)
        self.assertIn("lab_deny_entries:", variables)


class Tasks(unittest.TestCase):
    main = (ROLE / "tasks" / "main.yml").read_text()
    stage = (ROLE / "tasks" / "input.yml").read_text()

    def test_every_task_that_changes_the_machine_is_root_owned_and_goes_through_the_root_check(self):
        for task in tasks_of(ROLE / "tasks" / "main.yml"):
            title = task.splitlines()[0]
            if "ansible.builtin.debug" in task or "ansible.builtin.assert" in task:
                continue
            self.assertIn('become: "{{ ai_lab_become }}"', task, title)
            if "ansible.builtin.copy" in task or "ansible.builtin.file" in task:
                self.assertIn("owner: root", task, title)
        for mode in re.findall(r'^\s+mode: "(\d+)"', self.main, re.M):
            self.assertEqual(int(mode, 8) & 0o022, 0, f"mode {mode} is writable by others")

    def test_the_platform_engine_installs_and_the_project_copy_is_never_named(self):
        """PA-34: the root-owned scripts/toolchain of the release clone runs; nothing runs a file of the project."""
        self.assertIn("{{ toolchain_engine }}", self.main)
        self.assertIn("- -I", self.main)
        for text in (self.main, self.stage):
            self.assertNotRegex(text, r"lab_project_stage\s*}}/scripts|/scripts/toolchain\"|project[^\n]*scripts/toolchain")
        for text in (self.main, self.stage):
            self.assertNotIn("ansible.builtin.shell", text)
            self.assertNotIn("ansible.builtin.script", text)
        self.assertIn("--manifest", self.main)
        self.assertIn("--source", self.main)
        self.assertIn("- download", self.main)

    def test_amd64_only_with_the_checksum_rules_of_the_engine_and_a_dry_run_in_check_mode(self):
        self.assertIn("{{ lab_project_arch }}", self.main)
        self.assertIn("--dry-run", self.main)
        self.assertIn("ansible_check_mode", self.main)
        for banned in ("get_url", "ansible.builtin.uri", "unarchive", "curl ", "wget "):
            self.assertNotIn(banned, self.main)

    def test_the_smoke_tests_run_as_the_ai_user_with_the_installed_engine_and_never_in_check_mode(self):
        task = self.main[self.main.index("Smoke"):]
        task = task[:task.index("\n- name:", 1)] if "\n- name:" in task[1:] else task
        self.assertIn("runuser", task)
        self.assertIn("- -u", task)
        self.assertIn("{{ lab_ai_user }}", task)
        self.assertIn("verify", task)
        self.assertIn("{{ lab_project_engine }}", task)
        self.assertIn("not ansible_check_mode", task)
        self.assertNotIn("{{ toolchain_engine }}", task, "the clone of the lab admin is not readable by the AI user; the installed copy runs")

    def test_a_package_list_is_applied_only_with_the_digest_of_the_dry_run_and_the_dry_run_is_shown(self):
        self.assertIn("--reviewed", self.main)
        self.assertIn("{{ lab_project_packages_reviewed }}", self.main)
        self.assertIn("--apply", self.main)
        self.assertIn("ansible.builtin.debug", self.main)
        self.assertIn("lab_project_packages_plan.stdout_lines", self.main)
        self.assertLess(self.main.index("lab_project_packages_plan.stdout_lines"), self.main.index("--apply"),
                        "the plan is shown before anything is installed")

    def test_the_project_files_are_recorded_root_owned_beside_the_lab_tools(self):
        for name in ("manifest.toml", "packages.txt", "deny.platform.txt", "SOURCE"):
            self.assertIn(name, self.main, name)
        self.assertIn("{{ lab_project_record_dir }}", self.main)

    def test_the_path_snippet_puts_the_project_tools_after_everything_else(self):
        self.assertIn("/etc/profile.d/ai-lab-project.sh", self.main)
        self.assertRegex(self.main, r'PATH="\$\{PATH\}:\{\{ lab_project_prefix \}\}/bin"')

    def test_the_input_runs_in_check_mode_too_and_changes_nothing(self):
        self.assertIn("check_mode: false", self.stage)
        self.assertIn("changed_when: false", self.stage)
        self.assertIn("ansible.builtin.tempfile", self.stage)
        self.assertIn("lab_deny_text", self.stage)
        self.assertIn("lab_deny_entries", self.stage)
        self.assertIn("--as-user", self.stage)
        self.assertIn("python3", self.stage)
        self.assertIn("- -I", self.stage)

    def test_nothing_is_written_into_a_users_home(self):
        text = self.main + self.stage + (ROLE / "defaults" / "main.yml").read_text()
        self.assertNotRegex(text, r"/home/|~/|ansible_env|ansible_user_dir")


class DenyThroughTheSameChannel(unittest.TestCase):
    """I-7, R-2: one list feeds deny.txt, the managed settings, and the user-level layer."""

    def test_the_three_consumers_read_the_merged_list(self):
        tools = (ANSIBLE / "roles" / "lab_tools" / "tasks" / "main.yml").read_text()
        block = tools[tools.index("- name: Install the lab-wide deny list"):]
        block = block[:block.index("\n- name:", 1)]
        self.assertIn('content: "{{ lab_deny_text }}"', block)
        self.assertNotIn("src:", block)
        for needle in ("owner: root", 'mode: "0644"', 'dest: "{{ lab_tools_dir }}/deny.txt"', 'become: "{{ ai_lab_become }}"'):
            self.assertIn(needle, block)
        managed = (ANSIBLE / "roles" / "claude_managed_settings" / "defaults" / "main.yml").read_text()
        self.assertIn("claude_managed_lab_wide_deny:", managed)
        self.assertIn('deny: "{{ lab_deny_entries }}"', managed)
        layer = (ANSIBLE / "roles" / "claude_user_deny" / "tasks" / "main.yml").read_text()
        self.assertIn('deny_entries: "{{ lab_deny_entries }}"', layer)
        self.assertNotIn("deny_list:", layer)

    def test_the_source_of_the_core_list_stays_required_deny_txt(self):
        variables = (ANSIBLE / "group_vars" / "all.yml").read_text()
        self.assertIn('lab_deny_list_source: "{{ repo_root }}/workspace/claude-user/required-deny.txt"', variables)


@unittest.skipUnless(shutil.which("ansible-playbook") and shutil.which("git"), "ansible-playbook and git are needed")
class CheckModeRun(unittest.TestCase):
    """A play of the project input and the role in check mode, against a local clone and a temporary prefix."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        self.repo = self.tmp / "project"
        (self.repo / "toolchain").mkdir(parents=True)
        (self.repo / ".claude").mkdir()
        (self.repo / "toolchain" / "manifest.toml").write_text(MANIFEST)
        (self.repo / ".claude" / "deny.platform.txt").write_text("# seeded\nRead(~/.config/svc/**)\n")
        self.git("init", "-q", "-b", "main")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "A")
        self.sha = self.git("rev-parse", "HEAD").strip()

    def git(self, *args):
        done = subprocess.run(["git", "-C", str(self.repo), *args], capture_output=True, text=True, env=GIT_ENV, check=False)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout

    def play(self, *extra, roles=True):
        play = self.tmp / "play.yml"
        play.write_text(
            "- hosts: all\n  connection: local\n  gather_facts: false\n  vars_files: [" + str(ANSIBLE / "group_vars" / "all.yml") + "]\n"
            "  pre_tasks:\n    - ansible.builtin.import_role: {name: lab_project, tasks_from: input}\n"
            "    - ansible.builtin.debug: {msg: 'ENTRIES={{ lab_deny_entries | to_json }}'}\n"
            + ("  roles: [lab_project]\n" if roles else ""))
        env = {"PATH": os.environ["PATH"], "HOME": str(self.tmp), "ANSIBLE_HOME": str(self.tmp), "ANSIBLE_LOCAL_TEMP": str(self.tmp),
               "ANSIBLE_NOCOLOR": "1", "ANSIBLE_ROLES_PATH": str(ANSIBLE / "roles"), "LC_ALL": "C.UTF-8"}
        argv = ["ansible-playbook", "-i", str(ANSIBLE / "inventory" / "localhost.yml"), str(play), "--check", "--diff",
                "-e", f"repo_root={ROOT}", "-e", f"toolchain_prefix={self.tmp}/opt", "-e", "ai_lab_become=false", "-e", "lab_ai_user=ai",
                "-e", "lab_project_git_user=", "-e", f"ansible_python_interpreter={shutil.which('python3')}", *extra]
        done = subprocess.run(argv, capture_output=True, text=True, env=env, cwd=self.tmp, timeout=180, check=False)
        return done.returncode, done.stdout + done.stderr

    def entries(self, out):
        match = re.search(r'ENTRIES=(\[.*?\])"', out.replace('\\"', '"'))
        self.assertIsNotNone(match, out[-1500:])
        return json.loads(match.group(1))

    def test_without_a_project_the_list_is_the_core_list_and_the_role_does_nothing(self):
        code, out = self.play()
        self.assertEqual(code, 0, out[-2000:])
        core = [l for l in (ROOT / "workspace" / "claude-user" / "required-deny.txt").read_text().splitlines() if l and not l.startswith("#")]
        self.assertEqual(self.entries(out), core)
        self.assertFalse((self.tmp / "opt").exists())

    def test_a_supplied_sha_adds_the_project_entries_after_the_core_and_a_dry_run_writes_nothing(self):
        code, out = self.play("-e", f"lab_project_clone={self.repo}", "-e", f"lab_project_sha={self.sha}")
        self.assertEqual(code, 0, out[-2500:])
        entries = self.entries(out)
        self.assertEqual(entries[-1], "Read(~/.config/svc/**)")
        self.assertEqual(len(entries), 91)
        self.assertIn("would install", out)
        self.assertIn("demo 1.0.0", out)
        self.assertFalse((self.tmp / "opt").exists(), "a check-mode run wrote")

    def test_an_unmerged_or_malformed_choice_stops_the_play_before_anything_else(self):
        code, out = self.play("-e", f"lab_project_clone={self.repo}", "-e", "lab_project_sha=main")
        self.assertNotEqual(code, 0)
        code, out = self.play("-e", "lab_project_repo=https://github.com/o/p")
        self.assertNotEqual(code, 0)
        self.assertFalse((self.tmp / "opt").exists())


if __name__ == "__main__":
    unittest.main()
