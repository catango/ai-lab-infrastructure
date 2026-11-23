# CR-55 Implementation plan

Starts only after the design PR is merged (ADR-003 section 4). Each PR runs in its own session, in `ai-lab-infrastructure` unless stated, branch `impl/CR-55-<slug>`, and declares `Implements: #55` and `Design:` with the design PR number. Slugs and order are proposals.

**Order constraint.** The generic code is seeded into the template from this repository at a recorded commit (CR-39 PR 2), so PR 1 merges before that seed, or the same change is made in the template by its own PR.

## 1. The PRs

| # | Repository, branch slug | Content | Needs | Criteria |
|---|---|---|---|---|
| 1 | here, `cross-build-script` | `scripts/cross-build` with `--dry-run` and fixtures, and the check `no-emulation` with its catalogue entry | Design merged | XB-A1, XB-A4, XB-A5 |
| T | template, inside the CR-39 PRs that own the CI | The extra step in the matrix job of an architecture without a runner, the seeded script and check, the aggregate fixtures | PR 1; the CR-39 CI PRs | XB-A2, XB-A3, XB-A6 |
| 2 | here, `cross-docs` | Runbook note for local cross-builds on the workspace and the `docs/README.md` status line. No ADR is edited in an implementation PR | PR 1 | XB-A8 |

XB-A7 is verified in the design PR itself (the amendment text is committed there after the approver's review). Approver checks only: XB-A8 (diff review) and the first real cross-build in an application repository.

## 2. Preconditions and user-only steps

- Q1 to Q4 answered by a review of the approver account on the design PR.
- A project that cross-builds supplies its own cross toolchain and `scripts/build`; Claude Code installs nothing, and the user runs any install command that the project documents.
- If Q1 is accepted: the approver confirms the $0 budget with usage stopped on the account, and sets `runner_private` for the repository through its configuration PR.
- CR-43 PR 5 is not a precondition and is not started by this CR.

## 3. Checklist (each PR keeps its own)

- [ ] Draft PR opened with the implementation template, `Implements:` and `Design:` filled in
- [ ] Fixtures and tests written first for the PR's criteria
- [ ] Implementation done
- [ ] `./scripts/quality-gate.sh` passes; any skipped check is reported
- [ ] CI green
- [ ] Marked ready for review
