"""CR-57 plan PR 4, the two extensions of the user and the shared roles: the system-wide git identity (LC-8), unattended security updates
(LC-15, OC-12), and the PA-18 switches of the managed settings.

Real runs of what can run as the current user (the assertions of the git identity role, the merge expression of the managed settings
role) and static checks of the rest. The tasks that set `owner: root` need root: they run in the PA-28 job, in a Debian container
(tests/ansible/pa28-lab.sh and pa28-operator.sh). Nothing here touches the machine.
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
ANSIBLE = ROOT / "ansible"
HAVE_ANSIBLE = shutil.which("ansible-playbook") is not None
# The names of the PA-18 switches, as read in the Claude Code documentation (pull request body, "PA-18"). A rename is a visible diff.
PA18_KEYS = {"disableClaudeAiConnectors": True, "enableArtifact": False}


def play(test, tasks, extra, check=False):
    """Run `tasks` (YAML text) of a one-play playbook against the local machine; return (exit code, output)."""
    tmp = tempfile.TemporaryDirectory()
    test.addCleanup(tmp.cleanup)
    base = pathlib.Path(tmp.name)
    (base / "play.yml").write_text("- hosts: all\n  connection: local\n  gather_facts: false\n" + tasks)
    env = {"PATH": os.environ["PATH"], "HOME": str(base), "ANSIBLE_HOME": str(base), "ANSIBLE_LOCAL_TEMP": str(base),
           "ANSIBLE_ROLES_PATH": str(ANSIBLE / "roles"), "ANSIBLE_NOCOLOR": "1", "LC_ALL": "C.UTF-8"}
    argv = ["ansible-playbook", "-i", str(ANSIBLE / "inventory" / "localhost.yml"), str(base / "play.yml"),
            "-e", f"repo_root={ROOT}", "-e", "ai_lab_become=false"]
    if check:
        argv.append("--check")
    for key, value in extra.items():
        argv += ["-e", f"{key}={value}"]
    done = subprocess.run(argv, capture_output=True, text=True, env=env, cwd=base, timeout=180, check=False, stdin=subprocess.DEVNULL)
    return done.returncode, done.stdout + done.stderr


def role(name, tasks_from=None):
    if tasks_from:
        return f"  tasks:\n    - ansible.builtin.import_role: {{name: {name}, tasks_from: {tasks_from}}}\n"
    return f"  roles:\n    - {name}\n"


def unchanged(output):
    return re.search(r"changed=0 +unreachable=0 +failed=0", output) is not None


@unittest.skipUnless(HAVE_ANSIBLE, "ansible-playbook is not installed")
class GitIdentity(unittest.TestCase):
    def config(self, text):
        path = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, path)
        (path / "project.yaml").write_text(text)
        return path / "project.yaml", path / "gitconfig"

    def test_the_id_must_be_a_positive_integer_and_the_login_plain(self):
        for name, text in (("empty", "github:\n  machine_login: bot\n  machine_user_id:\n"),
                           ("text", "github:\n  machine_login: bot\n  machine_user_id: guess\n"),
                           ("zero", "github:\n  machine_login: bot\n  machine_user_id: 0\n"),
                           ("negative", "github:\n  machine_login: bot\n  machine_user_id: -3\n"),
                           ("missing key", "github:\n  machine_login: bot\n"),
                           ("no login", "github:\n  machine_user_id: 42\n"),
                           ("a login with a space", "github:\n  machine_login: 'a b'\n  machine_user_id: 42\n")):
            with self.subTest(case=name):
                conf, _ = self.config(text)
                code, out = play(self, role("git_identity", "assert"), {"git_identity_project_config": conf})
                self.assertNotEqual(code, 0, out)
                self.assertIn("numeric GitHub id", out)

    def test_a_good_configuration_passes_the_assertion(self):
        conf, _ = self.config("github:\n  machine_login: bot-1\n  machine_user_id: 42\n")
        code, out = play(self, role("git_identity", "assert"), {"git_identity_project_config": conf})
        self.assertEqual(code, 0, out)

    def test_the_identity_goes_into_a_marked_block_of_the_root_owned_file_so_foreign_lines_stay(self):
        """The real run (a foreign line kept, the block there once, a second run quiet) is the PA-28 job: it needs root."""
        text = (ANSIBLE / "roles" / "git_identity" / "tasks" / "main.yml").read_text()
        self.assertIn("ansible.builtin.blockinfile", text)
        self.assertIn('marker: "# {mark} ai-lab-infrastructure machine identity"', text)
        self.assertIn("create: true", text)
        self.assertIn("name = {{ git_identity_github.machine_login }}", text)
        self.assertIn("email = {{ git_identity_github.machine_user_id }}+{{ git_identity_github.machine_login }}"
                      "@{{ git_identity_noreply_domain }}", text)
        self.assertIn("users.noreply.github.com", (ANSIBLE / "roles" / "git_identity" / "defaults" / "main.yml").read_text())

    def test_the_role_writes_the_system_file_only_and_nothing_into_a_home(self):
        text = (ANSIBLE / "roles" / "git_identity" / "tasks" / "main.yml").read_text()
        self.assertIn("/etc/gitconfig", (ANSIBLE / "roles" / "git_identity" / "defaults" / "main.yml").read_text())
        self.assertNotRegex(text, r"~|/home/|\.gitconfig|ansible.builtin.uri|ansible.builtin.shell|ansible.builtin.command")
        self.assertIn("owner: root", text)

    def test_the_real_configuration_has_the_key_and_the_form_is_the_one_the_lab_check_reads(self):
        text = (ROOT / "config" / "project.yaml").read_text()
        self.assertRegex(text, r"(?m)^  machine_user_id:")
        check = (ANSIBLE / "roles" / "lab_tools" / "files" / "lab-check").read_text()
        self.assertIn(r'[0-9]+\+', check)
        self.assertIn(r"users\.noreply\.github\.com", check)


@unittest.skipUnless(HAVE_ANSIBLE, "ansible-playbook is not installed")
class UnattendedUpgrades(unittest.TestCase):
    TEXT = (ANSIBLE / "roles" / "unattended_upgrades" / "tasks" / "main.yml").read_text()

    def test_the_package_comes_from_the_archive_through_the_apt_module_and_not_the_manifest(self):
        self.assertIn("ansible.builtin.apt:", self.TEXT)
        self.assertIn("name: unattended-upgrades", self.TEXT)
        manifest = (ROOT / "toolchain" / "manifest.toml").read_text()
        self.assertNotIn("unattended-upgrades", manifest, "the operator profile takes manifest membership for Python 3 and git only (O-15)")
        for banned in ("apt_repository", "apt_key", "get_url", "deb822", "sources.list"):
            self.assertNotIn(banned, self.TEXT)

    def test_the_two_periodic_settings_that_the_checks_read_are_set_to_one(self):
        self.assertIn('APT::Periodic::Update-Package-Lists "1";', self.TEXT)
        self.assertIn('APT::Periodic::Unattended-Upgrade "1";', self.TEXT)
        self.assertIn("/etc/apt/apt.conf.d/20auto-upgrades", (ANSIBLE / "roles" / "unattended_upgrades" / "defaults" / "main.yml").read_text())
        for check in ("lab-check", "operator-check"):
            path = next(ANSIBLE.rglob(check), None)
            if path:
                self.assertIn("APT::Periodic::Update-Package-Lists", path.read_text())

    def test_no_reboot_is_scheduled_by_the_role_and_the_units_are_left_alone_without_systemd(self):
        self.assertNotIn("Automatic-Reboot", self.TEXT)
        self.assertIn("service_mgr'] == 'systemd'", self.TEXT)
        self.assertIn("apt-daily-upgrade.timer", (ANSIBLE / "roles" / "unattended_upgrades" / "defaults" / "main.yml").read_text())

    def test_both_profiles_use_the_one_role(self):
        for playbook in ("lab.yml", "operator.yml"):
            text = (ANSIBLE / playbook).read_text()
            self.assertRegex(text, r"- role: unattended_upgrades", playbook)
        self.assertEqual(sorted(p.name for p in (ANSIBLE / "roles" / "unattended_upgrades").rglob("*") if p.is_dir()), ["defaults", "tasks"])


@unittest.skipUnless(HAVE_ANSIBLE, "ansible-playbook is not installed")
class ManagedSettingsPA18(unittest.TestCase):
    """PA-18: the role owns the switches, merged over what is there (never a replacement), and a rename is a visible diff."""

    def defaults(self):
        return (ANSIBLE / "roles" / "claude_managed_settings" / "defaults" / "main.yml").read_text()

    def test_the_names_are_pinned(self):
        text = self.defaults()
        self.assertIn("claude_managed_role_settings:\n  disableClaudeAiConnectors: true\n  enableArtifact: false\n", text)
        keys = re.search(r"claude_managed_role_settings:\n((?:  .+\n)+)", text).group(1)
        self.assertEqual(sorted(re.findall(r"^  (\w+):", keys, re.M)), sorted(PA18_KEYS))

    def test_the_open_switch_is_not_set(self):
        self.assertNotIn("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC:", self.defaults().replace("# Open, not set here: CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", ""))
        self.assertNotIn('"env"', (ANSIBLE / "roles" / "claude_managed_settings" / "tasks" / "main.yml").read_text())

    def test_the_user_level_settings_file_is_not_edited_for_them(self):
        settings = json.loads((ROOT / "workspace" / "claude-user" / "settings.json").read_text())
        for key in PA18_KEYS:
            self.assertNotIn(key, settings, "workspace/claude-user/settings.json is restored to existing workspaces until PR 7")

    def merge(self, existing):
        """Evaluate the content expression of the role's task, as written, over `existing`; return the file text it would write."""
        tasks = (ANSIBLE / "roles" / "claude_managed_settings" / "tasks" / "main.yml").read_text()
        expression = re.search(r'content: "(\{\{ claude_managed_existing.*?\}\})\\n"', tasks).group(1)
        tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        (tmp / "existing.json").write_text(json.dumps(existing))
        out = tmp / "out.json"
        text = ("  vars_files:\n    - " + str(ANSIBLE / "roles" / "claude_managed_settings" / "defaults" / "main.yml") + "\n"
                "  vars:\n"
                f"    claude_managed_existing: \"{{{{ lookup('ansible.builtin.file', '{tmp}/existing.json') | from_json }}}}\"\n"
                "    claude_managed_ours: \"{{ lookup('ansible.builtin.file', claude_managed_settings_source) | from_json }}\"\n"
                "  tasks:\n    - ansible.builtin.copy:\n"
                f"        dest: {out}\n        content: \"{expression}\\n\"\n")
        code, output = play(self, text, {})
        self.assertEqual(code, 0, output)
        return out.read_text()

    def test_a_merge_keeps_foreign_settings_enforces_the_switches_and_a_second_pass_changes_nothing(self):
        existing = {"foreignSetting": True, "enableArtifact": True, "permissions": {"deny": ["Bash(foreign *)"]}}
        text = self.merge(existing)
        merged = json.loads(text)
        self.assertIs(merged["foreignSetting"], True)
        self.assertIn("Bash(foreign *)", merged["permissions"]["deny"])
        self.assertIn("Bash(sudo *)", merged["permissions"]["deny"])
        for key, value in PA18_KEYS.items():
            self.assertIs(merged[key], value, key)
        self.assertEqual(self.merge(merged), text)

    def test_an_empty_start_gets_the_switches_too(self):
        merged = json.loads(self.merge({}))
        for key, value in PA18_KEYS.items():
            self.assertIs(merged[key], value, key)

    def test_no_deny_rule_is_removed_or_weakened(self):
        """PA-A10: the switches add keys; the deny list of the managed file is still the core list."""
        settings = json.loads((ROOT / "workspace" / "claude-user" / "settings.json").read_text())
        required = [l for l in (ROOT / "workspace" / "claude-user" / "required-deny.txt").read_text().splitlines() if l and not l.startswith("#")]
        self.assertEqual(sorted(settings["permissions"]["deny"]), sorted(required))


if __name__ == "__main__":
    unittest.main()
