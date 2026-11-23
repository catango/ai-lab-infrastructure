# CR-55 Implementation plan

Starts only after the design PR is merged (ADR-003 section 4). Each PR runs in its own session, in `ai-lab-infrastructure` unless stated, branch `impl/CR-55-<slug>`, and declares `Implements: #55` and `Design:` with the design PR number. Slugs and order are proposals.

**Order constraint.** The generic code is seeded into the template from this repository at a recorded commit (CR-39 PR 2), so PRs 1 to 3 merge before that seed, or the same changes are made in the template by its own PR.

## 1. The PRs

| # | Repository, branch slug | Content | Needs | Criteria |
|---|---|---|---|---|
| 1 | here, `cross-manifest` | Manifest field `targets`, its check and fixtures, and the cross-smoke in `scripts/toolchain verify` with a stub-compiler fixture | Design merged | XB-A1, XB-A2 |
| 2 | here, `cross-config` | Strict reader of `cross_builds` (base commit), the config comment block, fixtures and the comparison with `yq` | Design merged | XB-A4 |
| 3 | here, `cross-build-script` | `scripts/cross-build` with `--dry-run`, fixtures, and the check `no-emulation` with its catalogue entry | PRs 1 and 2 | XB-A3, XB-A8 |
| T | template, inside the CR-39 PRs | The job `cross-build-<target>`, the seeded script and check, the configuration key, the aggregate fixtures, the matrix and `not run` behaviour for private repositories | PR 3; CR-39 PRs that own the CI | XB-A5, XB-A6, XB-A7 |
| 4 | here, `cross-docs` | Runbook note for the user-run toolchain install and the `docs/README.md` status line. No ADR is edited in an implementation PR | PRs 1 to 3 | XB-A10 |

XB-A9 is verified in the design PR itself (the amendment text is committed there after the approver's review). Approver checks only: XB-A10 (diff review) and the first real cross-build run in an application repository.

## 2. Preconditions and user-only steps

- Q1 to Q8 answered by a review of the approver account on the design PR.
- A first project must choose a cross toolchain that exists as a download with checksums for both host architectures; if none does, that project's toolchain PR records the exception or uses `apt` (XB-3). Claude Code installs nothing: the user runs the install command that the PR prints.
- CR-43 PR 5 is not a precondition and is not started by this CR.

## 3. Checklist (each PR keeps its own)

- [ ] Draft PR opened with the implementation template, `Implements:` and `Design:` filled in
- [ ] Fixtures and tests written first for the PR's criteria
- [ ] Implementation done
- [ ] `./scripts/quality-gate.sh` passes; any skipped check is reported
- [ ] CI green
- [ ] Marked ready for review
