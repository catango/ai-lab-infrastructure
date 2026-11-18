"""facts, GitHub scope (acceptance F-3): GET only, unauthenticated by default, T3 only on request, counts and yes/no only."""
import importlib.machinery
import importlib.util
import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr

import helpers
import fakes
import fakes_github as gh
from operator_lib import exitcodes, hostfacts

SCRIPT = helpers.OPERATOR_DIR / "facts"
T3 = helpers.PAT + "T3CANARYVALUE12345"


def load_facts():
    loader = importlib.machinery.SourceFileLoader("operator_facts_github_tests", str(SCRIPT))
    spec = importlib.util.spec_from_loader("operator_facts_github_tests", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


facts = load_facts()
BASE = ["--scope", "github", "--owner", gh.OWNER, "--repo", "ai-lab-infrastructure", "--repo", "ai-software-template"]


class Base(unittest.TestCase):
    def setUp(self):
        self.api = gh.FakeGitHub()
        self.lines = []
        self.prompts = []
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def getpass(self, prompt):
        self.prompts.append(prompt)
        return T3

    def run_facts(self, *argv):
        self.lines = []
        return facts.main(list(argv), system=fakes.FakeSystem(), environ={"HOME": self.tmp.name}, out=self.lines.append,
                          require_release=lambda repo, out=print: None, runner=fakes.FakeRunner(), opener=self.api, getpass_fn=self.getpass)

    @property
    def text(self):
        return "\n".join(self.lines)

    def section(self, repo):
        start = self.lines.index(f"== facts (github): {repo} ==")
        values = {}
        for line in self.lines[start + 1:]:
            if line.startswith("=="):
                break
            if ": " in line:
                key, value = line.split(": ", 1)
                values[key] = value
        return values


class DryRun(Base):
    def test_a_dry_run_lists_the_get_paths_and_sends_nothing(self):
        self.assertEqual(self.run_facts(*BASE), exitcodes.OK)
        self.assertEqual((self.api.requests, self.prompts), ([], []))
        self.assertIn(f"GET /repos/{gh.OWNER}/ai-lab-infrastructure", self.text)
        self.assertIn("/rulesets", self.text)
        self.assertNotIn("--apply", " ".join(l for l in self.lines if l.startswith("GET")))

    def test_the_scope_needs_an_owner_and_a_repository(self):
        for argv in (["--scope", "github"], ["--scope", "github", "--owner", gh.OWNER], ["--scope", "github", "--repo", "x"],
                     ["--scope", "github", "--owner", "bad owner", "--repo", "x"], ["--scope", "github", "--owner", gh.OWNER, "--repo", "a/b"],
                     ["--owner", gh.OWNER, "--repo", "x"]):
            with self.subTest(argv=argv), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                self.run_facts(*argv)
            self.assertEqual(caught.exception.code, exitcodes.USAGE)
        self.assertEqual(self.api.requests, [])


class Unauthenticated(Base):
    def test_by_default_no_token_is_asked_for_or_sent_and_every_call_is_a_get(self):
        self.assertEqual(self.run_facts(*BASE, "--apply"), exitcodes.OK)
        self.assertEqual(self.prompts, [])
        self.assertEqual({r["method"] for r in self.api.requests}, {"GET"})
        self.assertEqual(self.api.tokens(), {None})

    def test_public_facts_are_reported_as_yes_no_and_counts(self):
        self.run_facts(*BASE, "--apply")
        v = self.section("ai-lab-infrastructure")
        expected = {"merge_commits_allowed": "no", "squash_allowed": "yes", "rebase_allowed": "no", "auto_merge_allowed": "no", "wiki_enabled": "no",
                    "issues_enabled": "yes", "projects_enabled": "no", "is_template": "no", "rulesets": "2", "branch_ruleset_active": "yes",
                    "tag_ruleset_active": "yes", "private_vulnerability_reporting": "yes", "environments": "0"}
        for key, value in expected.items():
            self.assertEqual(v.get(key), value, key)
        self.assertEqual(self.section("ai-software-template")["is_template"], "yes")

    def test_values_that_need_a_token_are_unknown_without_one(self):
        self.run_facts(*BASE, "--apply")
        v = self.section("ai-lab-infrastructure")
        for key in ("secret_scanning", "secret_scanning_push_protection", "vulnerability_alerts", "dependabot_security_updates",
                    "actions_selected_only", "sha_pinning_required", "workflow_permissions_read_only", "collaborators"):
            self.assertEqual(v.get(key), "unknown", key)

    def test_the_r3_tag_ruleset_is_reported(self):
        self.api.repos["ai-lab-infrastructure"]["rulesets"] = [r for r in self.api.repos["ai-lab-infrastructure"]["rulesets"] if r["target"] != "tag"]
        self.run_facts(*BASE, "--apply")
        self.assertEqual(self.section("ai-lab-infrastructure")["tag_ruleset_active"], "no")
        self.assertEqual(self.section("ai-software-template")["tag_ruleset_active"], "yes")

    def test_a_weak_tag_ruleset_does_not_count(self):
        weak = self.api.repos["ai-lab-infrastructure"]["rulesets"][1]
        weak["rules"] = [r for r in weak["rules"] if r["type"] != "deletion"]
        self.run_facts(*BASE, "--apply")
        self.assertEqual(self.section("ai-lab-infrastructure")["tag_ruleset_active"], "no")
        weak2 = self.api.repos["ai-software-template"]["rulesets"][1]
        weak2["enforcement"] = "disabled"
        self.run_facts(*BASE, "--apply")
        self.assertEqual(self.section("ai-software-template")["tag_ruleset_active"], "no")

    def test_an_unknown_repository_is_reported_not_raised(self):
        self.assertEqual(self.run_facts("--scope", "github", "--owner", gh.OWNER, "--repo", "no-such-repo", "--apply"), exitcodes.OK)
        self.assertEqual(self.section("no-such-repo")["reachable"], "no")


class WithToken(Base):
    def test_use_token_asks_once_for_t3_and_sends_it_on_every_request(self):
        self.run_facts(*BASE, "--apply", "--use-token")
        self.assertEqual(len(self.prompts), 1)
        self.assertIn("T3", self.prompts[0])
        self.assertEqual(self.api.tokens(), {"Bearer " + T3})
        self.assertEqual({r["method"] for r in self.api.requests}, {"GET"})

    def test_the_admin_only_facts_are_then_known(self):
        self.run_facts(*BASE, "--apply", "--use-token")
        v = self.section("ai-lab-infrastructure")
        expected = {"secret_scanning": "yes", "secret_scanning_push_protection": "yes", "vulnerability_alerts": "yes", "dependabot_security_updates": "yes",
                    "actions_selected_only": "yes", "sha_pinning_required": "yes", "workflow_permissions_read_only": "yes", "collaborators": "1"}
        for key, value in expected.items():
            self.assertEqual(v.get(key), value, key)

    def test_a_refused_read_is_unknown(self):
        self.api.deny_admin_reads = True
        self.run_facts(*BASE, "--apply", "--use-token")
        self.assertEqual(self.section("ai-lab-infrastructure")["vulnerability_alerts"], "unknown")

    def test_the_token_and_the_repository_text_never_reach_the_output_or_the_disk(self):
        self.run_facts(*BASE, "--apply", "--use-token")
        self.assertNotIn(T3, self.text)
        self.assertNotIn(gh.CANARY, self.text)
        self.assertNotIn(gh.OWNER, "\n".join(l for l in self.lines if not l.startswith("GET")))
        self.assertEqual(os.listdir(self.tmp.name), [])

    def test_the_token_is_not_asked_for_in_a_dry_run(self):
        self.run_facts(*BASE, "--use-token")
        self.assertEqual(self.prompts, [])

    def test_a_refused_token_stops_before_any_request(self):
        facts_lines = []
        code = facts.main(BASE + ["--apply", "--use-token"], system=fakes.FakeSystem(), environ={"HOME": self.tmp.name}, out=facts_lines.append,
                          require_release=lambda repo, out=print: None, runner=fakes.FakeRunner(), opener=self.api, getpass_fn=lambda p: "bad")
        self.assertEqual(code, exitcodes.FAILED)
        self.assertEqual(self.api.requests, [])


class Script(unittest.TestCase):
    def test_the_github_scope_uses_a_read_only_client_and_no_write_path(self):
        text = (helpers.OPERATOR_DIR / "lib" / "operator_lib" / "githubfacts.py").read_text()
        self.assertIn("read_only=True", text)
        for banned in ('"POST"', '"PUT"', '"PATCH"', '"DELETE"', "subprocess"):
            self.assertNotIn(banned, text)

    def test_the_hostfacts_state_is_not_touched_by_the_github_scope(self):
        self.assertTrue(hasattr(hostfacts, "State"))


if __name__ == "__main__":
    unittest.main()
