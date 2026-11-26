"""CR-57 PA-A13, PA-A10: the PA-19(a) deny entries are in the three copies of the deny list, and the three copies do not drift.

The drift checks of the old workspace restore tests (deleted in plan PR 7), re-created for the three copies and the new entries.
The managed settings take their deny list from workspace/claude-user/settings.json (roles/claude_managed_settings), so the third
copy is also the managed list; the PA-28 job compares the installed managed settings with required-deny.txt.
"""
import json
import pathlib
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


if __name__ == "__main__":
    unittest.main()
