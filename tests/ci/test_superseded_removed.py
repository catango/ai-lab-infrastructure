"""CR-57 plan PR 7 (`remove-superseded`): what the workspace restore, the CR-2 legacy playbook, the Ubuntu operator profile, and the
`builder` alias left behind is gone, and nothing points at it (PA-A5, PA-A16).

Text and file-tree checks over this repository only. They fail while any removed path exists or any workflow, document, or manifest
still names the alias. The profiles of the two supported machines are covered by tests/ansible and tests/toolchain.
"""
import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from toolchain_engine import manifest  # noqa: E402

REMOVED_PATHS = (
    "workspace/restore.sh", "workspace/verify.sh", "workspace/lib", "workspace/repos.txt", "tests/workspace",
    "docs/operations/workspace-restore.md", "ansible/builder.yml",
    "ansible/roles/operator_firewall", "ansible/roles/operator_lock", "ansible/roles/operator_sudo", "ansible/roles/operator_system",
    "ansible/roles/operator_ssh", "tests/ansible/opt-in-role-test.sh",
)
KEPT_PATHS = ("workspace/claude-user/settings.json", "workspace/claude-user/required-deny.txt", "workspace/claude-user/CLAUDE.md")
# Documents that may name a removed file: records of history and the plan itself.
RECORDS = ("docs/adr/", "docs/cr/", "docs/architecture/")
STALE = re.compile(r"workspace/restore\.sh|workspace/verify\.sh|workspace/lib|workspace/repos\.txt|tests/workspace|workspace-restore\.md"
                   r"|ansible/builder\.yml|opt-in-role-test")


def tracked_text_files():
    for path in sorted(ROOT.rglob("*")):
        rel = path.relative_to(ROOT).as_posix()
        if not path.is_file() or rel.startswith((".git/", "tests/pr-contract/fixtures/recorded/")) or rel.startswith(RECORDS):
            continue
        if "__pycache__" in rel or rel == "tests/ci/test_superseded_removed.py":
            continue
        try:
            yield rel, path.read_text()
        except UnicodeDecodeError:
            continue


class RemovedPaths(unittest.TestCase):
    def test_the_removed_paths_are_gone(self):
        for rel in REMOVED_PATHS:
            self.assertFalse((ROOT / rel).exists(), rel)

    def test_the_user_level_files_the_lab_profile_reads_stay(self):
        for rel in KEPT_PATHS:
            self.assertTrue((ROOT / rel).is_file(), rel)

    def test_no_file_names_a_removed_path(self):
        hits = [f"{rel}: {m.group(0)}" for rel, text in tracked_text_files() for m in STALE.finditer(text)]
        self.assertEqual(hits, [])

    def test_every_role_on_disk_is_applied_by_a_playbook_or_imported_by_one(self):
        roles = sorted(p.name for p in (ROOT / "ansible" / "roles").iterdir() if p.is_dir())
        text = "\n".join((ROOT / "ansible" / name).read_text() for name in ("lab.yml", "operator.yml"))
        text += "\n".join(p.read_text() for p in (ROOT / "ansible" / "roles").rglob("*.yml"))
        unused = [role for role in roles if not re.search(rf"(^|\s)(role:\s*|name:\s*|-\s+){role}\s*$", text, re.M)]
        self.assertEqual(unused, [])

    def test_the_variables_of_the_removed_roles_are_gone(self):
        text = (ROOT / "ansible" / "group_vars" / "all.yml").read_text()
        for name in ("operator_user_name", "operator_authorized_keys_file", "operator_firewall_enabled", "operator_firewall_revert_seconds",
                     "CR-18 Ubuntu profile"):
            self.assertNotIn(name, text)

    def test_the_documents_index_names_no_removed_file(self):
        text = (ROOT / "docs" / "README.md").read_text()
        self.assertNotIn("workspace-restore", text)
        self.assertNotIn("Workspace restore", text)
        self.assertNotIn("legacy playbook", text)
        self.assertIn("workspace/claude-user", text)


class BuilderAlias(unittest.TestCase):
    """O-19: PR 2 kept `builder` accepted so that its own pr-contract run read a base manifest that still had the name; PR 7 removes it."""

    def test_the_profiles_are_lab_and_operator(self):
        self.assertEqual(manifest.PROFILES, ("lab", "operator"))
        self.assertFalse(hasattr(manifest, "ALIASES"))
        self.assertFalse(hasattr(manifest, "canonical_profile"))

    def test_no_workflow_asks_for_the_builder_profile(self):
        for name in ("ci.yml", "pr-contract.yml"):
            text = (ROOT / ".github" / "workflows" / name).read_text()
            self.assertNotIn("--profile builder", text, name)
            self.assertIn("--profile lab", text, name)

    def test_the_ci_installs_and_verifies_the_lab_profile_in_every_place_it_used_the_alias(self):
        text = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
        self.assertEqual(len(re.findall(r"--profile lab\b", text)), 5)
        self.assertEqual(len(re.findall(r"--profile\s+(?!lab\b|operator\b)\S+", text)), 0)
        self.assertEqual(len(re.findall(r"--profile\s+\S+", (ROOT / ".github" / "workflows" / "pr-contract.yml").read_text())), 1)

    def test_the_manifest_and_the_engine_no_longer_name_the_alias(self):
        for rel in ("toolchain/manifest.toml", "scripts/toolchain_engine/manifest.py"):
            self.assertNotRegex((ROOT / rel).read_text(), r'"builder"|alias', rel)

    def test_no_tool_of_the_manifest_lists_builder(self):
        import tomllib
        tools = tomllib.loads((ROOT / "toolchain" / "manifest.toml").read_text())["tools"]
        for name, entry in tools.items():
            self.assertTrue(set(entry["profiles"]) <= {"lab", "operator"}, name)


if __name__ == "__main__":
    unittest.main()
