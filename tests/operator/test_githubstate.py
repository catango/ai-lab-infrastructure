import pathlib
import tempfile
import unittest

import helpers
from operator_lib import githubstate

DESIRED = helpers.OPERATOR_DIR / "github-desired-state.toml"


def load(text):
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "state.toml"
        path.write_text(text)
        return githubstate.load_desired(path)


class RepositoryFile(unittest.TestCase):
    def setUp(self):
        self.text = DESIRED.read_text()

    def test_the_repository_file_is_valid(self):
        desired = githubstate.load_desired(DESIRED)
        self.assertEqual(set(desired["repositories"]), {"ai-lab-infrastructure", "ai-software-template"})
        self.assertEqual({r["name"] for r in desired["rulesets"]}, {"main-protection", "release-tags"})
        self.assertEqual(desired["environments"], [])

    def test_it_holds_no_login_address_or_token(self):
        import re
        for pattern in (r"@", r"\b\d{1,3}(\.\d{1,3}){3}\b", r"ghp_|github_pat_", r"ocid1"):
            self.assertIsNone(re.search(pattern, self.text), pattern)

    def test_the_wanted_values_follow_the_runbook(self):
        d = githubstate.load_desired(DESIRED)
        self.assertEqual((d["settings"]["allow_merge_commit"], d["settings"]["allow_squash_merge"], d["settings"]["allow_rebase_merge"],
                          d["settings"]["allow_auto_merge"]), (False, True, False, False))
        self.assertEqual(d["actions"]["default_workflow_permissions"], "read")
        self.assertFalse(d["actions"]["can_approve_pull_request_reviews"])
        main = next(r for r in d["rulesets"] if r["name"] == "main-protection")
        self.assertEqual(main["bypass_actors"], [])
        pull = next(r for r in main["rules"] if r["type"] == "pull_request")["parameters"]
        self.assertEqual((pull["required_approving_review_count"], pull["allowed_merge_methods"]), (1, ["squash"]))
        tags = next(r for r in d["rulesets"] if r["name"] == "release-tags")
        self.assertEqual({r["type"] for r in tags["rules"]}, {"creation", "update", "deletion", "non_fast_forward"})

    def test_invalid_files_are_refused_with_a_message_that_has_no_value(self):
        bad = {
            "schema": self.text.replace("schema_version = 1", "schema_version = 2"),
            "unknown top-level key": self.text + "\n[extra]\nx = 1\n",
            "unknown setting": self.text.replace("has_wiki = false", "has_wiki = false\nnot_a_setting = true"),
            "wrong type": self.text.replace("has_wiki = false", 'has_wiki = "no"'),
            "security cannot be switched off": self.text.replace("vulnerability_alerts = true", "vulnerability_alerts = false"),
            "bad enforcement": self.text.replace('enforcement = "active"', 'enforcement = "maybe"', 1),
            "bad repository name": self.text.replace("[repositories.ai-lab-infrastructure]", "[repositories.\"a b\"]"),
            "environment not deferred": self.text + '\n[[environments]]\nname = "example"\ndeferred = false\n',
            "not toml": "this is [not toml",
        }
        for label, text in bad.items():
            with self.subTest(label), self.assertRaises(githubstate.StateError) as caught:
                load(text)
            self.assertNotIn("SECRETVALUE", str(caught.exception))

    def test_a_missing_file_is_an_error(self):
        with self.assertRaises(githubstate.StateError):
            githubstate.load_desired("/nonexistent/state.toml")


class Show(unittest.TestCase):
    def test_only_safe_values_are_shown(self):
        self.assertEqual([githubstate.show(v) for v in (True, False, 3, ["a", "b"], None, "PR_TITLE", "selected")],
                         ["yes", "no", "3", "2 items", "not set", "PR_TITLE", "selected"])
        for value in ("some free text", "alice", -1, 10**9, {"a": 1}):
            self.assertEqual(githubstate.show(value), "<redacted>")


if __name__ == "__main__":
    unittest.main()
