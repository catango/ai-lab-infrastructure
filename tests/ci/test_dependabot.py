"""CR-2 decision 9: .github/dependabot.yml covers github-actions and the pip lock directory, weekly, version updates only.

Text-level checks (the standard library has no YAML parser); yamllint validates the syntax in the gate.
"""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
CONFIG = ROOT / ".github" / "dependabot.yml"


def entries(text):
    """Each `- package-ecosystem:` block of the updates list as a dict of its simple scalar keys."""
    blocks = re.split(r"(?m)^  - (?=package-ecosystem:)", text)[1:]
    result = []
    for block in blocks:
        keys = {}
        for line in block.splitlines():
            match = re.match(r"^\s*([a-z-]+):\s*(\S.*?)\s*$", line)
            if match:
                keys[match.group(1)] = match.group(2).strip('"')
        result.append(keys)
    return result


class Dependabot(unittest.TestCase):
    def setUp(self):
        self.text = CONFIG.read_text()
        self.entries = entries(self.text)

    def test_version_2(self):
        self.assertRegex(self.text, r"(?m)^version: 2$")

    def test_exactly_the_two_planned_ecosystems(self):
        self.assertEqual(sorted(e["package-ecosystem"] for e in self.entries), ["github-actions", "pip"])

    def test_directories_exist(self):
        by_ecosystem = {e["package-ecosystem"]: e for e in self.entries}
        self.assertEqual(by_ecosystem["github-actions"]["directory"], "/")
        self.assertEqual(by_ecosystem["pip"]["directory"], "/toolchain/python")
        self.assertTrue((ROOT / "toolchain" / "python").is_dir())
        self.assertTrue((ROOT / ".github" / "workflows").is_dir())

    def test_weekly(self):
        self.assertEqual(len(re.findall(r"(?m)^\s+interval: weekly$", self.text)), len(self.entries))

    def test_version_updates_only_and_no_extra_reach(self):
        for banned in ("insecure-external-code-execution", "registries:", "allow:", "target-branch", "auto-merge", "automerge"):
            self.assertNotIn(banned, self.text)

    def test_pr_volume_is_limited(self):
        for entry in self.entries:
            self.assertLessEqual(int(entry["open-pull-requests-limit"]), 5)

    def test_pr_contract_allowlist_covers_the_lock_file(self):
        """PC-7 allows dependabot to change the lock file in this directory (design 6.2)."""
        rules = (ROOT / "scripts" / "pr_contract" / "rules.py").read_text()
        self.assertIn("toolchain/python/builder.lock", rules)

    def test_workflow_uses_are_pinned_so_dependabot_can_update_them(self):
        for workflow in (ROOT / ".github" / "workflows").glob("*.yml"):
            for line in workflow.read_text().splitlines():
                if re.match(r"\s*-?\s*uses:\s", line) and "./" not in line:
                    self.assertRegex(line, r"@[0-9a-f]{40} # v\d+\.\d+\.\d+$", f"{workflow.name}: {line.strip()}")


if __name__ == "__main__":
    unittest.main()
