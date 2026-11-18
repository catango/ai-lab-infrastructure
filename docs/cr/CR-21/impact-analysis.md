# CR-21 Impact analysis

## 1. What changes

- ADR-003 section 6 gains rule PC-8, and section 11 gains AC3-7. The ADR header gains an "Amended by" row. Both are edited in this design PR.
- Later, in one implementation PR: `scripts/pr_contract/` implements PC-8, its tests are added, and the PR templates gain a hint comment like the one for PC-6.

Nothing in this design PR changes `pr-contract`, a template, a workflow, or a setting.

## 2. Affected components and records

| Item | Effect |
|---|---|
| ADR-003 | Rule PC-8 and AC3-7 added. PC-1 to PC-7 are unchanged |
| ADR-011 / CR-18 | Relies on PC-8. Its implementation PRs carry the section once PC-8 is enforced; until then the section is added by hand |
| `scripts/pr_contract/` | New rule, in the implementation PR |
| `.github/PULL_REQUEST_TEMPLATE/` | A hint comment in the implementation, change, toolchain, and infra templates. No new required section, so PC-1 is unchanged |
| Dependabot PRs | Exempt from PC-8 (Q3) |

## 3. Security and privacy

- The rule adds a review prompt, not a technical barrier. The approver's review and the release tag (ADR-011 decision 3) remain the controls.
- Like the other rules, `pr-contract` treats the PR body as untrusted input and reads changed paths from the API with a read-only token. No secret is added.
- The section text is public. The template tells the author to give no identifier, address, or name.

## 4. Operational impact on the approver

The approver reads the "Operator script review" section in each operator PR. No new user-only action, except merging the implementation PR.

## 5. Dependencies and assumptions

- The path list matches the layout that CR-18 designs. If CR-18 changes the layout, the list changes with a new design PR.
- The rule becomes enforceable once the implementation PR is merged. Operator PRs before that carry the section voluntarily.

## 6. Cost and capacity

None.

## 7. Rollback

Revert the implementation PR and the ADR-003 rows. Operator PRs then lose only the automatic check.

## 8. Alternatives considered

| Alternative | Outcome | Reason |
|---|---|---|
| A CODEOWNERS entry for operator paths | Rejected | The approver already reviews every PR. CODEOWNERS does not make the reviewer's checklist visible |
| A checklist in the implementation template for every PR | Rejected | PC-1 requires every template section non-empty, so it would burden PRs that do not touch operator code |
| Put the check in the quality gate | Rejected | The gate sees files, not the PR body. `pr-contract` already reads both |
