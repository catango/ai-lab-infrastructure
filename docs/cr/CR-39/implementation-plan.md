# CR-39 Implementation plan

Starts only after the design PR is merged (ADR-003 section 4) **and** the entry criteria of baseline Stage 5 are met: ADR-009 and ADR-010 are approved too. Each PR runs in its own session. The PRs are in `ai-software-template`, branch `impl/CR-39-<slug>`, and declare `Implements: catango/ai-lab-infrastructure#39` and `Design: catango/ai-lab-infrastructure#40` (qualified references, ADR-003 PC-3 as amended). Until the template has its own `pr-contract` (PR 3) its PRs carry the references in the body by hand. The slugs and the order are proposals; the approver confirms them when the design merges.

**Outside CR-39:** this platform's preset is a change PR in `ai-lab-infrastructure` (identities, `deny.platform.txt`, `docs/PLATFORM.md`, architectures and runner labels, post-init actions, the RR-10 note), together with the check that the core deny list plus the platform list equals ADR-001 section 5, and the follow-through of this repository to ADR-003 as amended (`approver_id`, `design_repos`, `operator_paths`, qualified PC-3 references, the new PR types). Claude Code proposes it; the approver decides the form. It is a prerequisite of the real run in PR 9.

## 1. The PRs

| # | PR (branch slug) | Content | Needs | Acceptance criteria |
|---|---|---|---|---|
| 1 | `skeleton` | Layout, `.template/manifest.toml` with the three classes, the neutral configuration schema, `scripts/initialize-project --config`, `template-dev/` with its own records, the `manifest` and `leak` tests | Design merged; ADR-009 and ADR-010 approved | T-1, T-2 (generation part), T-15, T-21 (scan part) |
| 2 | `gate` | `scripts/quality-gate.sh`, generic checks seeded from `ai-lab-infrastructure` at a commit recorded in the template-only file `template-dev/provenance.toml` (history only), the install engine and the template's CI manifest, checks `forbidden-api` and `size-budget`, `ci.yml` as a matrix | PR 1; ADR-009 assumptions D9-1, D9-2, D9-8 still valid | T-3, T-14 (gate part), T-19 |
| 3 | `pr-contract` | `scripts/pr_contract/` and `scripts/pr-body`, data-driven by the configuration; PC-1 to PC-8, TC-1, TC-2; the five PR templates; `pr-contract.yml` | PR 2; ADR-003 amendment merged (this design PR) | T-8, T-20 (rule part) |
| 4 | `instructions` | `CLAUDE.md`, `docs/PLATFORM.md` and `docs/PROJECT.md` seeds, `settings.json`, `required-deny.txt`, the rules, `operator.md`, `operator_guard.py`, checks `claude-md`, `deny-list`, `operator-contract` | PR 3; ADR-010 budgets; import behaviour verified | T-4, T-5, T-6, T-22 |
| 5 | `cr-templates` | `docs/cr/_template/`, `docs/adr/_template.md`, `scripts/new-cr`, `cr-layout`, the `docs/README.md` seed | PR 4 | T-7 |
| 6 | `skills-core` | `prepare-cr-context`, `implement-approved-cr`, `review-implementation`, `resume-work`, `initialize-project`, `start-cr`, and the scripts `cr-context`, `cr-criteria`, `pr-checkpoint` | PR 5 | T-12, T-13 |
| 7 | `review-feedback` | `address-review-feedback` and `scripts/review-threads` | PR 6; GitHub semantics for edited comments verified | T-11 |
| 8 | `template-sync` | `scripts/template-sync`, `sync-template`, `overrides.toml` and `state.toml` handling, check `owned-drift`, the `sync` test; `.claude/settings.json` regenerated on overwrite from the core list plus the seeded `deny.platform.txt` (design section 4, step 3) | PR 7; the `owned-drift` reading for `uses:` changes confirmed | T-9, T-10, T-17 |
| 9 | `dry-run` | `template-dev/dry-run.sh`, the `generate`, `sync`, `skills` jobs on both architectures with two configurations, the dry-run report, the design section 11 check, the release checklist | PR 8 | T-2, T-3, T-14, T-16 (a), T-21 |

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
| Before the first template tag | Apply the **tag ruleset** on `ai-software-template` (only the approver creates `v*` tags) |
| After PR 3 | Make `pr-contract` and the gate jobs (`quality-gate-<arch>` for each configured architecture) required checks on `ai-software-template`, if ADR-009 says so |
| Preset | Review and merge the preset change PR in `ai-lab-infrastructure` |
| After PR 9 | Create the first template tag, and a second tag for the sync test. Then the real run of design section 12 (b): create a throwaway public repository with "Use this template", add the machine account as collaborator and update the AC1-1 allowlist for the run, apply the printed branch and tag rulesets before the init PR merges, and drive the five steps of T-16 (b). Afterwards delete the repository, remove the collaborator, restore the allowlist, and record the PR links in the last implementation PR |
| After PR 9 | Review the dry-run report; with the real run this closes the Stage 5 exit criterion |

## 4. What this plan does not do

- No change to ADR-009 or ADR-010, and no decision that belongs to them.
- No change to repository settings, rulesets, labels, secrets, collaborators, or tags by Claude Code.
- No change to this repository's code in CR-39. The ADR-003 and ADR-005 amendments are docs changes in the design PR; the preset and the follow-through to ADR-003 as amended are a separate change PR.
- No lab VM, OCI, or operator-machine work. The lab VM checks (T-12 on the lab VM, ARM64 on the real host) move to Stage 6.
- No adoption of the template's generic code by `ai-lab-infrastructure` (a later CR, after Stage 5).
