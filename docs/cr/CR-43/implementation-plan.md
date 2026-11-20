# CR-43 Implementation plan

Starts only after the design PR is merged (ADR-003 section 4). Each PR runs in its own session. The PRs here are in `ai-lab-infrastructure`, branch `impl/CR-43-<slug>`, and declare `Implements: #43` and `Design: #44`. The slugs and the order are proposals; the approver confirms them when the design merges. The template-side items are not separate PRs: they ride in the CR-39 implementation PRs (Q22), which add a body section "Also verifies CR-43 criteria" listing the S-ids.

**Order constraint.** The generic code is seeded into the template from this repository at a recorded commit (CR-39 PR 2). PRs 1, 2a, 2b, and 3 below therefore merge **before** CR-39 PR 2, so that the seed carries the new rules, or the same changes are made in the template and the parity script (PR 5) is run afterwards.

## 1. The PRs

| # | Repository, PR (branch slug) | Content | Needs | Criteria |
|---|---|---|---|---|
| 1 | here, `check-classes` | The `# class:` header on every check, `quality-gate.sh --list` prints it, the gate fails on a missing or unknown class, the catalogue test | Design merged | S-14 (class part) |
| 2a | here, `workflow-policy` | WP-1 to WP-16 on a parsed form of the workflow (`yq -o=json` and Python `json`) plus the line scan for text patterns; config keys `allowed_actions` and `runner_labels` read from the base commit; one fixture per rule; the existing workflows kept green | PR 1 | S-1, S-8 (gate part), S-22 |
| 2b | here, `required-aggregate` | `ci.yml`: the current job renamed `gate`, the aggregate `quality-gate` needing every other job; `pr-contract.yml`: the policy checks run from the base checkout against a read-only head checkout, the bootstrap skip removed; policy inputs from the base commit (SC-20); a PC-6 "Workflow change justification" section | PR 2a | S-2 (this repository), S-7, S-20, S-21, S-23 |
| 3 | here, `codeowners` | Check `codeowners` (class template), generic check `dependabot-config` (including `open-pull-requests-limit: 0`), `public-repo-hygiene` accepting the one `CODEOWNERS` line, and for this repository a root `SECURITY.md` and `.github/CODEOWNERS` | PR 1 | S-6, S-14 (`codeowners`), S-18 (this repository) |
| 4 | here, `evidence` | `scripts/gate-evidence`, rule PC-9 in `scripts/pr_contract/` reading `architectures` from the base commit, the section "Architecture evidence" in the change and implementation PR templates, config key `architectures` (with `runner` and `runner_private`). May be folded into the preset change PR of CR-39 section 14 if the approver prefers | Design merged (A1 is applied there) | S-9, S-20 (`architectures`) |
| 5 | here, `parity` | `scripts/checks-parity` (hashes the generic checks and their fixtures, prints the template tag compared), its fixtures, and the check that no workflow calls it | PR 3 | S-15 |
| 6 | here, `settings-docs` | A runbook section for application repositories with the ordered list of design section 12 and the read-only checks; the platform desired state gets `required_status_checks` (source GitHub Actions), `require_code_owner_review = true`, and `allow_update_branch = false` (operator code: PC-8 section, run by the approver only). This is the last PR of this repository: it lists the template PRs as `<owner>/ai-software-template#<n>` and uses `Closes #43` only after they merge | PRs 2b and 3; the template PRs | S-3, S-4, S-5, S-17, S-19 (docs part) |
| T | template, inside CR-39 PRs 1, 2, 3, 4, 8, and 9 | PR 1: `initialize-project` printing with `release_tags` default true and code-owner review (S-10), seeded `SECURITY.md` and `CODEOWNERS` (S-18). PR 2: the aggregate `quality-gate` and matrix names, `template-ci`, the not-run summary (S-2), `forbidden-api` (S-11), `workflow-policy`, `dependabot-config`, and the seeded checks (S-1, S-6). PR 3: PC-9 and the evidence section (S-9), the policy checks from the base in `pr-contract.yml` (S-20, S-21). PR 4: `operator-contract` (S-12), `codeowners` (S-14), the private-repository checklist in the PR templates (S-16). PR 8: `owned-drift` (S-13). PR 9: the dry run checks the printed rulesets and the job names, and records S-19 with the real run | CR-39 plan preconditions; ADR-009 and ADR-010 approved | S-1, S-2, S-6, S-9 to S-14, S-16, S-18 to S-22, S-19 |

Criteria that are approver checks only: S-3, S-4 (application repositories), S-5, S-17.

## 2. Checklist (each PR keeps its own)

- [ ] Draft PR opened with the implementation template, `Implements:` and `Design:` filled in
- [ ] Fixtures and tests written first for the PR's criteria
- [ ] Implementation done
- [ ] `./scripts/quality-gate.sh` passes; any skipped check is reported
- [ ] CI green
- [ ] Marked ready for review

## 3. User-only actions

Design section 12 is the full ordered list. For the platform repositories:

| When | Action |
|---|---|
| Now, before PR 1 | U-A1: run the `github-setup` dry run and `facts --scope github` on the platform operator VM and read by hand the required checks and their source. U-A2: turn "Always suggest updating pull request branches" off in both repositories. U-A3: enable CodeQL default setup on both. U-0: re-read runbook Parts 1.2 and 1.3 |
| After PR 2b's first green run | U-7a: confirm that the required checks are exactly `pr-contract` and `quality-gate` from GitHub Actions; remove any separately required platform names |
| After PR 3 merges | U-7b: turn on "Require review from Code Owners" in `main-protection` |
| After PR 6 merges | U-A4: run the `github-setup` dry run again |
| Before the first template tag | Apply the `release-tags` ruleset on `ai-software-template` (CR-39 plan) |
| In the real run of CR-39 T-16 (b) | The steps U-1 to U-8 of design section 12, in order, with the checks recorded (S-3, S-19) |
| For each new third-party Action | The steps of design section 6, ending with the allowlist entry after reading the source (U-10) |
| For each outside PR | Close it without a run, or read the diff of every file a workflow executes before approving the run (U-11) |
| Before PR 1 | Approve ADR-010 separately before Stage 5 |

## 4. What this plan does not do

- No decision that belongs to ADR-010.
- No change by Claude Code to repository settings, rulesets, secrets, variables, labels, collaborators, or tags. `github-setup` and every operator script are run by the approver only.
- No lab VM, OCI, or operator-machine work.
- No Scorecard, dependency review, or artifact attestation (later; the Scorecard is baseline Stage 7).
- No change to `ai-software-template` outside the CR-39 PRs.
