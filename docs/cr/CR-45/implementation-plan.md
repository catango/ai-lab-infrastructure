# CR-45 Implementation plan

Starts only after the design PR is merged (ADR-003 section 4) **and** the entry criteria of baseline Stage 5 are met: ADR-008, ADR-009, and ADR-010 approved. Each PR runs in its own session. The PRs are in `ai-software-template`, branch `impl/CR-45-<slug>`, and declare `Implements: catango/ai-lab-infrastructure#45` and `Design: catango/ai-lab-infrastructure#<design PR>` (qualified references, ADR-003 PC-3 as amended). The template's own `pr-contract` exists after CR-39 PR 3; until then the references are in the body by hand. The slugs and the order are proposals; the approver confirms them when the design merges.

These PRs add to the template content of CR-39 and so follow its PRs. The CR-39 PR numbers below are those of its [plan](../CR-39/implementation-plan.md).

## 1. The PRs

| # | PR (branch slug) | Content | Needs | Acceptance criteria |
|---|---|---|---|---|
| 1 | `budgets` | `.template/budgets.toml` with the values of design section 4 (the real always-loaded set measured first), `size-budget` extended (classes, description characters, the always-loaded group), tests; V-1 and V-2 checked and recorded | CR-39 PR 4 (`CLAUDE.md`, rules, `claude-md`) and PR 2 (`size-budget`); ADR-009 assumption X-1 still valid | M-1, M-2, M-17 (part) |
| 2 | `ci-output` | Finding cap at 200 characters, annotations under Actions (gate and `pr-contract`) with the escaping rule, the summary-line rule, check `output-budget` and the `[outputs]` values for the scripts that exist, tests; V-3 checked on a test PR | PR 1; CR-39 PR 2 (`size-budget`, gate) and PR 3 (`pr-contract`) | M-4 (part), M-5, M-17 (part) |
| 3 | `loading` | Skill headings and check `skill-layout`; `pr-checkpoint` validation and `show`; `cr-context` outline; `review-threads` paging; the context-discipline numbers in the template's `CLAUDE.md` text; `[outputs]` for all scripts | PR 2; CR-39 PR 7 (all Skills and their scripts exist) | M-3, M-4, M-6, M-7, M-8, M-9, M-10 |
| 4 | `metrics` | `scripts/metrics` (`static`, `prs`, `snapshot`, `compare`), the snapshot schema, the `--dir` option (default `docs/metrics/`, created by the project and not in the payload manifest; the template's own snapshots under `template-dev/docs/metrics/`), the static baseline `baseline-static`, the constraints checklist | PR 3; CR-39 PR 9 (the dry run exists, so the baseline covers a generated repository) | M-11, M-12, M-13, M-14, M-15, M-16 (a) |

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
| Before PR 1 | Approve ADR-008, ADR-009, and ADR-010 (Stage 5 entry) |
| After ADR-010 is accepted | Review the change PR that adds the context-discipline numbers to this repository's `CLAUDE.md` (Q7); Claude Code proposes it after ADR-010 is accepted |
| PR 2 | Nothing. If the annotation channel does not work (V-3), the filtered log through `pr-checkpoint show` becomes the primary channel without a new design PR; the result is recorded in the PR |
| Optional, at Stage 7 | Commit usage figures for tier C only if you choose to: type them in a session you start with `metrics snapshot --usage <pr>:<key>=<int>`; otherwise keep your own notes outside any host (Q14) |
| Stage 7 | Ask for `metrics snapshot --label baseline` in a session you start, review the baseline PR, and re-confirm the soft thresholds (M-16 (b)) |

## 4. What this plan does not do

- No change to ADR-009, and no decision that belongs to it.
- No change to repository settings, rulesets, labels, secrets, collaborators, or tags by Claude Code.
- No change to ADR-003 or ADR-008 beyond what the approver decided in Q12 and Q13 (applied in the design PR); no change to an approved design file.
- No telemetry, scheduled or event-driven run, workflow that invokes Claude, new credential, or MCP server. No analysis of session transcripts.
- No lab VM, OCI, or operator-machine work. The full baseline waits for Stage 7.
