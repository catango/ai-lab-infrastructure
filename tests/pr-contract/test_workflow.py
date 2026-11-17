"""P-10: the workflow passes only --repo and --pr, from a base checkout, with least privilege."""
import re
import unittest

import helpers

WORKFLOW = helpers.ROOT / ".github" / "workflows" / "pr-contract.yml"


class Workflow(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text()
        self.lines = self.text.splitlines()

    def test_top_level_permissions_are_empty_and_job_is_read_only(self):
        self.assertIn("\npermissions: {}\n", self.text)
        self.assertRegex(self.text, r"permissions:\n      contents: read\n      pull-requests: read\n      issues: read\n")
        self.assertNotRegex(self.text, r"(write|admin)")

    def test_triggers(self):
        self.assertIn("pull_request:", self.text)
        self.assertIn("types: [opened, edited, synchronize, reopened, ready_for_review, converted_to_draft]", self.text)
        for banned in ("pull_request_target", "workflow_run", "schedule:", "secrets.", "paths:", "paths-ignore:"):
            self.assertNotIn(banned, self.text)

    def test_checkout_is_the_base_commit_without_credentials(self):
        self.assertIn("ref: ${{ github.event.pull_request.base.sha }}", self.text)
        self.assertIn("persist-credentials: false", self.text)
        self.assertRegex(self.text, r"uses: actions/checkout@[0-9a-f]{40} # v\d+\.\d+\.\d+")

    def test_script_arguments_are_exactly_repo_and_pr_from_env(self):
        invocations = [line.strip() for line in self.lines if "scripts/pr-contract" in line and "[" not in line]
        self.assertEqual(invocations, ['python3 -I scripts/pr-contract --repo "$REPO" --pr "$PR_NUMBER"'])
        self.assertIn("REPO: ${{ github.repository }}", self.text)
        self.assertIn("PR_NUMBER: ${{ github.event.pull_request.number }}", self.text)

    def test_no_expression_inside_run_blocks(self):
        inside = False
        for line in self.lines:
            if re.match(r"\s+run: [|>]", line):
                inside = True
                continue
            if inside and line.strip() and not line.startswith("          "):
                inside = False
            if inside:
                self.assertNotIn("${{", line)

    def test_bootstrap_skip_is_explicit(self):
        self.assertIn("skipped: bootstrap", self.text)

    def test_timeout_and_concurrency(self):
        self.assertIn("timeout-minutes:", self.text)
        self.assertIn("cancel-in-progress: true", self.text)

    def test_runner_is_pinned(self):
        self.assertIn("runs-on: ubuntu-24.04", self.text)
        self.assertNotIn("latest", self.text)


if __name__ == "__main__":
    unittest.main()
