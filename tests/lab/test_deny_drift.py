"""CR-57 PA-A13, PA-A10: the PA-19(a) deny entries are in the three copies of the deny list, and the three copies do not drift.

The drift checks of the old workspace restore tests (deleted in plan PR 7), re-created for the three copies and the new entries.
The managed settings take their deny list from workspace/claude-user/settings.json (roles/claude_managed_settings), so the third
copy is also the managed list; the PA-28 job compares the installed managed settings with required-deny.txt.
"""
import importlib.machinery
import importlib.util
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
PA19_ENTRIES = [
    "Bash(ssh *)", "Bash(scp *)", "Bash(sftp *)", "Bash(rsync *)", "Bash(ssh-keygen *)", "Bash(ssh-add *)", "Bash(ssh-agent *)",
    "Read(~/.ssh/**)", "Edit(~/.ssh/**)",
]


def deny(path):
    return json.loads((ROOT / path).read_text())["permissions"]["deny"]


def required():
    lines = (ROOT / "workspace" / "claude-user" / "required-deny.txt").read_text().splitlines()
    return [line for line in lines if line.strip() and not line.lstrip().startswith("#")]


class Drift(unittest.TestCase):
    def test_required_deny_equals_the_repository_settings(self):
        self.assertEqual(sorted(required()), sorted(deny(".claude/settings.json")))

    def test_the_user_level_settings_carry_the_same_deny_rules(self):
        self.assertEqual(sorted(deny("workspace/claude-user/settings.json")), sorted(required()))

    def test_no_copy_lists_a_rule_twice(self):
        for name, rules in (("settings", deny(".claude/settings.json")), ("user", deny("workspace/claude-user/settings.json")),
                            ("required", required())):
            self.assertEqual(len(rules), len(set(rules)), name)


class Pa19(unittest.TestCase):
    def test_the_ssh_client_family_and_the_ssh_directory_are_denied_in_every_copy(self):
        for name, rules in (("settings", deny(".claude/settings.json")), ("user", deny("workspace/claude-user/settings.json")),
                            ("required", required())):
            for entry in PA19_ENTRIES:
                self.assertIn(entry, rules, f"{name}: {entry}")

    def test_the_managed_settings_source_is_the_user_level_file(self):
        defaults = (ROOT / "ansible" / "roles" / "claude_managed_settings" / "defaults" / "main.yml").read_text()
        self.assertIn("workspace/claude-user/settings.json", defaults)


MODULE = ROOT / "ansible" / "roles" / "claude_user_deny" / "library" / "claude_user_deny.py"


def load_helper():
    path = ROOT / "ansible" / "roles" / "lab_project" / "files" / "lab-project-input"
    loader = importlib.machinery.SourceFileLoader("lab_project_input", str(path))
    spec = importlib.util.spec_from_loader("lab_project_input", loader)
    module = importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode = True
    loader.exec_module(module)
    return module


def layer_module():
    spec = importlib.util.spec_from_file_location("claude_user_deny", MODULE)
    module = importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode = True
    spec.loader.exec_module(module)
    return module


class UserLayerDrift(unittest.TestCase):
    """CR-57 PA-55, PA-A36 (plan PR 4a): the user-level layer is generated from required-deny.txt and equals each of the three copies."""

    def generated(self):
        module = layer_module()
        text = (ROOT / "workspace" / "claude-user" / "required-deny.txt").read_text()
        return json.loads(module.canonical_content(module.parse_deny_list(text)))

    def test_the_role_takes_its_list_from_required_deny_txt(self):
        """Plan PR 8: the layer, the managed settings, and deny.txt read one list, `lab_deny_entries`, which is the core list of
        required-deny.txt (`lab_deny_list_source`) plus a project's deny.platform.txt entries; with no project it is the core list."""
        variables = (ROOT / "ansible" / "group_vars" / "all.yml").read_text()
        self.assertIn('lab_deny_list_source: "{{ repo_root }}/workspace/claude-user/required-deny.txt"', variables)
        self.assertIn("lookup('ansible.builtin.file', lab_deny_list_source, rstrip=False)", variables)
        for role, task, needle in (("claude_user_deny", "main.yml", "lab_deny_entries"), ("lab_tools", "main.yml", "lab_deny_text")):
            text = (ROOT / "ansible" / "roles" / role / "tasks" / task).read_text()
            self.assertIn(needle, text, f"{role}/{task}")
            self.assertNotIn("claude-user/settings.json", text, f"{role}/{task}")
        project = (ROOT / "ansible" / "roles" / "lab_project" / "tasks" / "input.yml").read_text()
        self.assertIn("lab_deny_list_source", project)

    def test_the_merge_keeps_the_core_list_first_and_adds_only(self):
        helper = load_helper()
        text = (ROOT / "workspace" / "claude-user" / "required-deny.txt").read_text()
        merged, entries, added = helper.merge_deny(text, "Read(~/.config/svc/**)\n", "owner/project", "c" * 40)
        self.assertEqual(entries[:90], required())
        self.assertEqual(added, ["Read(~/.config/svc/**)"])
        self.assertEqual(len(entries), len(set(entries)))
        self.assertTrue(merged.startswith(text))

    def test_the_generated_layer_has_the_entries_and_the_count_of_each_of_the_three_copies(self):
        generated = self.generated()["permissions"]["deny"]
        self.assertEqual(len(generated), 90)
        self.assertEqual(generated, required(), "the same entries in the same order as the source")
        for name, rules in (("settings", deny(".claude/settings.json")), ("user", deny("workspace/claude-user/settings.json")),
                            ("required", required())):
            self.assertEqual(len(generated), len(rules), name)
            self.assertEqual(sorted(generated), sorted(rules), name)

    def test_no_entry_is_listed_twice(self):
        generated = self.generated()["permissions"]["deny"]
        self.assertEqual(len(generated), len(set(generated)))

    def test_the_two_other_keys_equal_those_of_the_user_level_settings_of_the_workspace(self):
        user = json.loads((ROOT / "workspace" / "claude-user" / "settings.json").read_text())
        generated = self.generated()
        self.assertEqual(generated["enableAllProjectMcpServers"], user["enableAllProjectMcpServers"])
        self.assertEqual(generated["permissions"]["disableBypassPermissionsMode"], user["permissions"]["disableBypassPermissionsMode"])
        self.assertEqual(sorted(generated), ["enableAllProjectMcpServers", "permissions"])
        self.assertEqual(sorted(generated["permissions"]), ["deny", "disableBypassPermissionsMode"])


if __name__ == "__main__":
    unittest.main()
