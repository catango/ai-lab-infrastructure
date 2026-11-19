# CR-43 Implementation plan

Starts only after the design PR is merged (ADR-003 section 4) and the approver's decisions on design section 15 are applied. Each PR runs in its own session. The PRs here are in `ai-lab-infrastructure`, branch `impl/CR-43-<slug>`, and declare `Implements: #43` and `Design: #<design PR>`. The slugs and the order are proposals; the approver confirms them when the design merges. The template-side items are not separate PRs: they are carried by the CR-39 implementation PRs (Q22), which add a body section "Also verifies CR-43 criteria" listing the S-ids.

**Order constraint.** The generic code is seeded into the template from this repository at a recorded commit (CR-39 PR 2). PRs 1 to 3 below therefore merge **before** CR-39 PR 2, so that the seed carries the new rules, or the same changes are made in the template and the parity script (PR 5) is run afterwards.

## 1. The PRs

| # | Repository, PR (branch slug) | Content | Needs | Criteria |
|---|---|---|---|---|
| 1 | here, `check-classes` | The `# class:` header on every check, `quality-gate.sh --list` prints it, the gate fails on a missing or unknown class, the catalogue test | Design merged | S-14 |
| 2 | here, `workflow-policy` | WP-1 to WP-14 with `allowed_action_owners` and `runner_labels` read from `config/project.yaml`, a fixture per rule, the existing workflows kept green | PR 1 | S-1, S-7 (static part), S-8 (gate part) |
| 3 | here, `dependabot-config` | Gate check `dependabot-config`, and a root `SECURITY.md` for this repository (generic text, no contact data) | PR 1; Q12 and Q13 decided | S-6, S-18 (this repository) |
| 4 | here, `evidence` | `scripts/gate-evidence`, rule PC-9 in `scripts/pr_contract/`, the section "Architecture evidence" in the change and implementation PR templates, config keys `architectures` (with `runner` and `runner_private`). May be folded into the preset change PR of CR-39 section 14 if the approver prefers | ADR-003 amendment A1 accepted | S-9 |
| 5 | here, `parity` | `scripts/checks-parity`, its fixtures, and the check that no workflow calls it | PR 3 | S-15 |
| 6 | here, `settings-docs` | A runbook section for application repositories with the ordered list of design section 12 and the read-only checks; if Q20 says so, the application profile of `github-setup`'s desired state (operator code: PC-8 section, run by the approver only) | Design merged; Q20 decided | S-4, S-5, S-17, S-19 (docs part) |
| T | template, inside CR-39 PRs 1, 2, 3, 4, 8, and 9 | PR 1: `initialize-project` printing (S-10), seeded `SECURITY.md` (S-18). PR 2: the aggregate job and matrix names (S-2), `forbidden-api` (S-11), `dependabot-config` and `workflow-policy` seeded (S-6, S-1). PR 3: PC-9 and the evidence section (S-9). PR 4: `operator-contract` (S-12) and the private-repository checklist in the PR templates (S-16). PR 8: `owned-drift` (S-13). PR 9: the dry run checks the printed rulesets and the job names, and records S-19 with the real run | CR-39 plan preconditions; ADR-009 and ADR-010 approved | S-1, S-2, S-6, S-9 to S-13, S-16, S-18, S-19 |

Criteria that are approver checks only: S-3, S-4 (application repositories), S-5, S-17.

## 2. Checklist (each PR keeps its own)

- [ ] Draft PR opened with the implementation template, `Implements:` and `Design:` filled in
- [ ] Fixtures and tests written first for the PR's criteria
- [ ] Implementation done
- [ ] `./scripts/quality-gate.sh` passes; any skipped check is reported
- [ ] CI green
- [ ] Marked ready for review

## 3. User-only actions

| When | Action |
|---|---|
| Before PR 1 | Decide the questions of design section 15 (the architecture discussion, then the review). Approve ADR-010 separately before Stage 5 |
| Now, for this repository and the template (design section 12, U-A1) | Run the `github-setup` dry run and `facts --scope github` on the platform operator VM and compare with design sections 3, 4.2, and 5; confirm that `pr-contract` and `quality-gate` are required on both repositories; confirm the CodeQL state (S-3 to S-5) |
| U-0 | Set the Actions spending limit or budget of the personal account to zero (S-17) |
| Before PR 4 | Merge amendment A1 (with this design PR) so that PC-9 is part of ADR-003 |
| After the CR-39 PRs 1 and 2 | In the throwaway repository of CR-39 T-16 (b): the steps U-1 to U-8 of design section 12, in order, with the checks recorded (S-3, S-19) |
| For each new third-party Action | Add the allowlist entry after reading the PR, before the merge (U-10) |
| For each fork PR | Read the workflow diff before approving the run (U-11) |
| After PR 6 | Review the runbook section and, if added, run the `github-setup` dry run for an application repository |

## 4. What this plan does not do

- No decision that belongs to ADR-010, and no change to an accepted record before the approver decides the amendments.
- No change by Claude Code to repository settings, rulesets, secrets, variables, labels, collaborators, or tags. `github-setup` and every operator script are run by the approver only.
- No lab VM, OCI, or operator-machine work.
- No Scorecard, dependency review, or artifact attestation (later; the Scorecard is baseline Stage 7).
- No change to `ai-software-template` outside the CR-39 PRs.
