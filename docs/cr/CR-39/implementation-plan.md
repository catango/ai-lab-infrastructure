# CR-39 Implementation plan

Starts only after the design PR is merged (ADR-003 section 4) **and** the entry criteria of baseline Stage 5 are met: ADR-009 and ADR-010 are approved too. Each PR runs in its own session. The PRs are in `ai-software-template`, branch `impl/CR-39-<slug>`, and declare `Implements:` and `Design:` for issue #39 and this design PR. How a cross-repository reference passes `pr-contract` is part of Q8; until the template has its own `pr-contract` (PR 3), its PRs carry the references in the body by hand. The slugs and the order are proposals; the approver confirms them with the design.

## 1. The PRs

| # | PR (branch slug) | Content | Needs | Acceptance criteria |
|---|---|---|---|---|
| 1 | `skeleton` | Directory layout, `.template/manifest.toml` with classes, `config/project.yaml` placeholders, `scripts/initialize-project`, `template-dev/` with the `manifest` and `leak` tests | Design merged; ADR-009 and ADR-010 approved; Q1, Q9, Q12 decided | T-1, T-15 |
| 2 | `gate` | `scripts/quality-gate.sh`, generic checks copied from `ai-lab-infrastructure` at a recorded commit, the template checks `claude-md`, `deny-list`, `cr-layout`, `size-budget`, `ci.yml` with the ARM64 job | PR 1; Q5, Q7 decided; ADR-009 assumptions D9-1 and D9-2 still valid | T-3 (job part), T-14 (gate part) |
| 3 | `pr-contract` | `scripts/pr_contract/` and `scripts/pr-body` for application repositories, the four PR templates, `pr-contract.yml` | PR 2; the ADR-003 amendment of Q8 merged | T-8 |
| 4 | `instructions` | `CLAUDE.md` with zones, `.claude/settings.json`, `required-deny.txt`, the rules | PR 3; Q4 decided; ADR-010 budgets | T-4, T-5, T-6 |
| 5 | `cr-templates` | `docs/cr/_template/`, `docs/adr/_template.md`, `scripts/new-cr`, `docs/README.md` seed | PR 4; Q12 | T-7 |
| 6 | `skills-core` | `prepare-cr-context`, `implement-approved-cr`, `review-implementation`, `resume-work`, `initialize-project`, `start-cr` (if Q6) and the scripts `cr-context`, `cr-criteria`, `pr-checkpoint` | PR 5; Q6 | T-12, T-13 |
| 7 | `review-feedback` | `address-review-feedback` and `scripts/review-threads` | PR 6 | T-11 |
| 8 | `template-sync` | `scripts/template-sync`, `sync-template` Skill (if Q6), `template-sync.md` PR template, the `sync` test | PR 7; Q2, Q3 decided | T-9, T-10 |
| 9 | `dry-run` | `template-dev/dry-run.sh`, the `generate`, `sync`, `skills` jobs on both architectures, the dry-run report, the section 11 check | PR 8 | T-2, T-3, T-13 (jobs), T-14, T-16 |

## 2. Checklist (each PR keeps its own)

- [ ] Draft PR opened with the implementation template, `Implements:` and `Design:` filled in
- [ ] Fixtures and tests written first for the PR's criteria
- [ ] Implementation done
- [ ] `./scripts/quality-gate.sh` passes in the template; any skipped check is reported
- [ ] CI green
- [ ] Marked ready for review

## 3. User-only actions

| When | Action |
|---|---|
| Before PR 1 | Approve ADR-009 and ADR-010 (Stage 5 entry). Check that the ruleset on `ai-software-template` does not require a status check that does not exist yet |
| After PR 3 | Make `quality-gate` and `pr-contract` required checks on `ai-software-template`, if ADR-009 says so (settings stay with the approver) |
| After PR 9 | Create the first template release tag (approver only). Optionally (Q11) run "Use this template" once in a throwaway repository and delete it afterwards |
| After PR 9 | Review the dry-run report; this closes the Stage 5 exit criterion |

## 4. What this plan does not do

- No change to ADR-009 or ADR-010, and no decision that belongs to them.
- No change to repository settings, rulesets, labels, secrets, or tags by Claude Code.
- No change to this repository's code, except the ADR-003 amendment of Q8 (a docs change in a design PR) and the docs index.
- No lab VM, OCI, or operator-machine work. The lab VM checks (T-12 on the lab VM, ARM64 on the real host) move to Stage 6.
- No adoption of the template by `ai-lab-infrastructure` (Q7).
