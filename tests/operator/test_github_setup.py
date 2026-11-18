"""github-setup (acceptance G-2 and G-3): run against an in-memory GitHub API with a fake token prompt. Nothing leaves the process."""
import copy
import importlib.machinery
import importlib.util
import io
import os
import pathlib
import tempfile
import unittest
from contextlib import redirect_stderr

import helpers
import fakes_github as gh
from operator_lib import exitcodes, release

SCRIPT = helpers.OPERATOR_DIR / "github-setup"
T2 = helpers.PAT + "T2CANARYVALUE12345"
T3 = helpers.PAT + "T3CANARYVALUE12345"


def load_script():
    loader = importlib.machinery.SourceFileLoader("operator_github_setup_script", str(SCRIPT))
    spec = importlib.util.spec_from_loader("operator_github_setup_script", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


script = load_script()
ARGS = ["--owner", gh.OWNER, "--collaborator", gh.COLLABORATOR]


class Base(unittest.TestCase):
    def setUp(self):
        self.api = gh.FakeGitHub()
        self.lines = []
        self.prompts = []
        self.asked = []

    def getpass(self, prompt):
        self.prompts.append(prompt)
        return T2 if "T2" in prompt else T3

    def run_script(self, *argv, confirm=True):
        self.lines = []
        return script.main(list(argv) + ARGS if "--owner" not in argv else list(argv), opener=self.api, getpass_fn=self.getpass,
                           out=self.lines.append, require_release=lambda repo, out=print: None,
                           confirm_fn=lambda question: self.asked.append(question) or confirm)

    @property
    def text(self):
        return "\n".join(self.lines)

    def set_drifted(self, *names):
        for name in names or gh.REPOS:
            self.api.repos[name] = gh.drifted_repo(name == "ai-software-template")


class DryRun(Base):
    def test_a_dry_run_reads_with_t3_and_never_writes(self):
        self.set_drifted()
        self.assertEqual(self.run_script(), exitcodes.OK)
        self.assertEqual(self.api.writes(), [])
        self.assertEqual(len(self.prompts), 1)
        self.assertIn("T3", self.prompts[0])
        self.assertEqual(self.api.tokens(), {"Bearer " + T3})

    def test_it_shows_the_differences_and_lists_the_writes_it_would_make(self):
        self.set_drifted()
        self.run_script()
        for fragment in ("allow_merge_commit: yes -> no", "has_wiki: yes -> no", "secret_scanning: disabled -> enabled",
                         "vulnerability_alerts: no -> yes", "default_workflow_permissions: write -> read", "main-protection", "release-tags",
                         "would: PATCH settings", "would: PUT vulnerability-alerts", "would: create ruleset main-protection", "would: invite the collaborator"):
            self.assertIn(fragment, self.text)

    def test_an_explicit_dry_run_flag_is_the_same_and_nothing_is_confirmed(self):
        self.set_drifted()
        self.run_script("--dry-run")
        self.assertEqual((self.api.writes(), self.asked), ([], []))

    def test_a_repository_in_the_wanted_state_has_nothing_to_do(self):
        self.assertEqual(self.run_script(), exitcodes.OK)
        self.assertNotIn("would:", self.text)
        self.assertIn("changes: 0", self.text)

    def test_the_environments_are_listed_as_deferred_and_never_touched(self):
        self.run_script()
        self.assertIn("deferred", self.text)
        self.assertFalse([r for r in self.api.requests if "environments" in r["path"]])

    def test_manual_items_are_named(self):
        self.run_script()
        for word in ("grouped", "discussions"):
            self.assertIn(word, self.text)

    def test_the_token_is_never_printed_and_nothing_is_written_to_disk(self):
        self.set_drifted()
        with tempfile.TemporaryDirectory() as tmp:
            before = os.listdir(tmp)
            self.run_script()
            self.assertEqual(os.listdir(tmp), before)
        for secret in (T2, T3, gh.CANARY):
            self.assertNotIn(secret, self.text)

    def test_it_ends_with_the_reminder_to_revoke_the_token(self):
        self.run_script()
        self.assertIn("Revoke", self.lines[-1])


class Apply(Base):
    def test_apply_uses_t2_and_brings_both_repositories_to_the_wanted_state(self):
        self.set_drifted()
        self.assertEqual(self.run_script("--apply"), exitcodes.OK)
        self.assertEqual(len(self.prompts), 1)
        self.assertIn("T2", self.prompts[0])
        self.assertEqual(self.api.tokens(), {"Bearer " + T2})
        for name in gh.REPOS:
            self.assertEqual(self.api.repos[name]["settings"], gh.DESIRED_SETTINGS, name)
            self.assertEqual(self.api.repos[name]["is_template"], name == "ai-software-template")
            self.assertEqual(self.api.repos[name]["security_and_analysis"]["secret_scanning"]["status"], "enabled")
            self.assertTrue(self.api.repos[name]["vulnerability_alerts"] and self.api.repos[name]["automated_security_fixes"])
            self.assertEqual(self.api.repos[name]["actions"], gh.good_repo()["actions"])
            self.assertEqual(self.api.repos[name]["workflow"], gh.good_repo()["workflow"])
            self.assertEqual(self.api.repos[name]["retention"]["days"], 30)
            self.assertEqual({r["name"] for r in self.api.repos[name]["rulesets"]}, {"main-protection", "release-tags"})
            self.assertEqual(self.api.repos[name]["invitations"], {gh.COLLABORATOR})

    def test_a_second_apply_changes_nothing(self):
        self.set_drifted()
        self.run_script("--apply")
        self.api.requests.clear()
        self.assertEqual(self.run_script("--apply"), exitcodes.OK)
        self.assertEqual(self.api.writes(), [])
        self.assertIn("changes: 0", self.text)

    def test_only_what_differs_is_written(self):
        self.api.repos["ai-lab-infrastructure"]["settings"]["has_wiki"] = True
        self.run_script("--apply")
        writes = self.api.writes()
        self.assertEqual([(w["method"], w["path"].rsplit("/", 1)[-1], w["body"]) for w in writes],
                         [("PATCH", "ai-lab-infrastructure", {"has_wiki": False})])

    def test_updating_a_ruleset_asks_first_and_keeps_rule_types_it_does_not_manage(self):
        repo = self.api.repos["ai-lab-infrastructure"]
        main = repo["rulesets"][0]
        main["rules"].append({"type": "required_status_checks", "parameters": {"required_status_checks": [{"context": "quality-gate"}]}})
        main["rules"][3]["parameters"]["required_approving_review_count"] = 2
        self.assertEqual(self.run_script("--apply", confirm=False), exitcodes.OK)
        self.assertEqual(self.api.writes(), [])
        self.assertEqual(len(self.asked), 1)
        self.run_script("--apply", confirm=True)
        types = [rule["type"] for rule in repo["rulesets"][0]["rules"]]
        self.assertIn("required_status_checks", types)
        params = next(r for r in repo["rulesets"][0]["rules"] if r["type"] == "pull_request")["parameters"]
        self.assertEqual(params["required_approving_review_count"], 1)

    def test_creating_a_ruleset_needs_no_confirmation(self):
        self.api.repos["ai-lab-infrastructure"]["rulesets"] = []
        self.run_script("--apply", confirm=False)
        self.assertEqual(self.asked, [])
        self.assertEqual(len(self.api.repos["ai-lab-infrastructure"]["rulesets"]), 2)

    def test_a_pending_invitation_is_not_repeated(self):
        repo = self.api.repos["ai-lab-infrastructure"]
        repo["collaborators"], repo["invitations"] = set(), {gh.COLLABORATOR}
        self.run_script("--apply")
        self.assertFalse([w for w in self.api.writes() if "collaborators" in w["path"]])
        self.assertIn("pending", self.text)

    def test_an_unreadable_value_is_reported_and_not_written(self):
        self.api.deny_admin_reads = True
        self.api.repos["ai-lab-infrastructure"]["actions"]["allowed_actions"] = "all"
        code = self.run_script("--apply")
        self.assertEqual(code, exitcodes.FAILED)
        self.assertIn("unknown", self.text)
        self.assertFalse([w for w in self.api.writes() if "/actions/" in w["path"]])

    def test_the_apply_summary_and_revoke_reminder(self):
        self.set_drifted()
        self.run_script("--apply")
        self.assertIn("changes:", self.text)
        self.assertIn("Revoke", self.lines[-1])
        for secret in (T2, T3, gh.CANARY):
            self.assertNotIn(secret, self.text)

    def test_only_one_repository_when_asked(self):
        self.set_drifted()
        self.run_script("--apply", "--repo", "ai-software-template")
        self.assertEqual(self.api.repos["ai-lab-infrastructure"]["settings"], gh.DRIFTED_SETTINGS)
        self.assertEqual(self.api.repos["ai-software-template"]["settings"], gh.DESIRED_SETTINGS)


class Usage(Base):
    def assertUsage(self, *argv):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            script.main(list(argv), opener=self.api, getpass_fn=self.getpass, out=self.lines.append, require_release=lambda repo, out=print: None)
        self.assertEqual(caught.exception.code, exitcodes.USAGE)
        self.assertEqual((self.api.requests, self.prompts), ([], []))

    def test_both_flags_and_bad_arguments_are_usage_errors_before_anything_runs(self):
        self.assertUsage("--dry-run", "--apply", *ARGS)
        self.assertUsage(*ARGS, "--bogus")
        self.assertUsage("--owner", gh.OWNER)
        self.assertUsage("--collaborator", gh.COLLABORATOR)
        for bad in ("", "a b", "x/y", "-lead", "a" * 40, "ev;il", "$(x)"):
            self.assertUsage("--owner", bad, "--collaborator", gh.COLLABORATOR)
            self.assertUsage("--owner", gh.OWNER, "--collaborator", bad)
        self.assertUsage(*ARGS, "--repo", "not-in-the-desired-state")

    def test_the_release_check_runs_first(self):
        def refuse(repo, out=print):
            raise SystemExit(exitcodes.FAILED)
        with self.assertRaises(SystemExit) as caught:
            script.main(list(ARGS), opener=self.api, getpass_fn=self.getpass, out=self.lines.append, require_release=refuse)
        self.assertEqual(caught.exception.code, 1)
        self.assertEqual((self.api.requests, self.prompts), ([], []))

    def test_a_refused_token_stops_the_run_before_any_request(self):
        def refuse(prompt):
            return "bad"
        code = script.main(list(ARGS), opener=self.api, getpass_fn=refuse, out=self.lines.append, require_release=lambda repo, out=print: None)
        self.assertEqual(code, exitcodes.FAILED)
        self.assertEqual(self.api.requests, [])
        self.assertNotIn("bad", self.text)


class Script(unittest.TestCase):
    def test_it_is_executable_and_uses_the_shared_library(self):
        self.assertTrue(os.access(SCRIPT, os.X_OK))
        text = SCRIPT.read_text()
        for word in ("parse_mode", "require_release_commit", "prompt_token", "HttpClient"):
            self.assertIn(word, text)

    def test_it_starts_no_subprocess_and_does_not_read_the_environment_for_tokens(self):
        text = SCRIPT.read_text()
        for banned in ("subprocess", "os.environ", "os.getenv", "GH_TOKEN", "GITHUB_TOKEN", "gh auth"):
            self.assertNotIn(banned, text)

    def test_the_dry_run_client_is_read_only_and_the_apply_client_is_not(self):
        text = SCRIPT.read_text()
        self.assertIn("read_only=mode.dry_run", text)


if __name__ == "__main__":
    unittest.main()
