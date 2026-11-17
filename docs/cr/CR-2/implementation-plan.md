# CR-2 Implementation plan

Starts only after the design PR is merged (ADR-003 section 4). Each implementation PR uses branch `impl/CR-2-<slug>`, declares `Implements: #2` and `Design: #<design PR>`, and keeps its own checkpoint list. The last PR uses `Closes #2`. Implementation PRs do not edit this CR's `design.md` or `acceptance-criteria.md` (PC-5); a needed design change is a new design PR.

## 1. Order and dependencies

| # | PR (branch slug) | Content | Needs | Acceptance criteria |
|---|---|---|---|---|
| 1 | `quality-gate` | `scripts/quality-gate.sh`, `scripts/checks/`, fixtures and tests; minimal `ci.yml` with the `quality-gate` job (using the runner's tools until the toolchain exists) | Design merged | Q-1 to Q-9, part of C-1, C-2, C-6, C-7 |
| 2 | `pr-contract` | `scripts/pr-contract`, `tests/pr-contract/`, `.github/workflows/pr-contract.yml`, bootstrap handling for the first PR | PR 1 (gate runs its tests) | P-1 to P-11, rest of C-1, C-2 |
| 3 | `toolchain` | `toolchain/manifest.toml`, `toolchain/python/builder.lock`, `scripts/toolchain`, tests; real versions, URLs, checksums for both architectures; `toolchain-amd64` and `toolchain-arm64` matrix job | PR 1; design merged (ADR-005 accepted by that merge) | T-1 to T-7, T-10, C-3 |
| 4 | `builder-profile` | `ansible/` with `builder.yml`, roles, `lab.yml` placeholder; `builder-profile` container job | PR 3 | T-8, T-9, T-4 |
| 5 | `restore` | `workspace/` (`restore.sh`, `verify.sh`, `repos.txt`, `claude-user/`, helpers), runbook `docs/operations/workspace-restore.md` | PR 4 | R-1 to R-9, D-1 |
| 6 | `ci-finish` | `.github/dependabot.yml` (if approved), `docs/README.md` updates, CI summary polish, AC evidence table in the PR body; `Closes #2` | PRs 1 to 5 | C-4, C-5, D-2, D-3 |

PRs 1 and 2 can be reviewed in either order, but PR 2 depends on the quality gate to run its tests. PRs 3 and 4 follow the toolchain before restore because restore applies the profile.

## 2. Checklist per PR

Each PR body carries the checkpoint list below (adapted per PR). Commit and push after each item.

- [ ] Draft PR opened with the implementation template, `Implements:` and `Design:` filled in
- [ ] Tests or fixtures written first for the criteria in the table above
- [ ] Implementation complete
- [ ] `./scripts/quality-gate.sh` passes (once PR 1 is merged); before that, available linters run and the rest are reported
- [ ] CI green
- [ ] Acceptance criteria evidence recorded in the PR body
- [ ] Marked ready for review

## 3. Work detail by PR

### PR 1: quality gate

1. Dispatcher with the interface and exit codes in design section 5.
2. Checks in this order: `bash-hygiene`, `shellcheck`, `public-repo-hygiene`, `workflow-policy`, `no-claude-in-workflows`, `links`, `yaml`, `markdown`, `actionlint`; later PRs add `python`, `toolchain`, `ansible`, `terraform` checks together with the code they check.
3. Fixture-driven tests, one failing and one passing fixture per check, run by a test script that the gate itself invokes.
4. `ci.yml` with the `quality-gate` job, `permissions: {}` at the top, pinned `actions/checkout`.

### PR 2: pr-contract

1. Offline mode and fixtures first, then the API client.
2. Rules PC-1 to PC-7 as in design section 6.2; hostile-input fixtures (design section 6.3).
3. Workflow runs the script from a base checkout; the bootstrap case (no script on the base branch) reports "skipped: bootstrap" for that PR only.
4. One live test: a throwaway draft PR from a branch with a known violation, to confirm the check fails and passes with a read-only token (V3-4).

### PR 3: toolchain

1. Choose versions; record each upstream checksum and signature verification result in the PR body (never in chat).
2. Build the manifest for both architectures; the check job downloads every artifact and compares.
3. Engine hardening tests (T-2, T-3).
4. Hash-locked pip file generated with a universal resolution so both architectures are covered.

### PR 4: builder profile

1. Roles in the order `apt_base`, `toolchain`, `python_tools`, `shell_env`, `rootless_podman`, `verify`.
2. Container job on a `debian:13` image pinned by digest; applies the playbook twice to prove idempotence.
3. `lab.yml` placeholder with the Stage 3 failure message and syntax-check coverage.

### PR 5: restore

1. Helpers and `verify.sh` first, with negative tests using a temporary `HOME`.
2. `restore.sh` with dry-run and preflight; step-by-step tests against a temporary `HOME` and stubbed `sudo`, `gh`, and `ansible-playbook`.
3. Runbook with the exact commands the user runs.
4. Hand-off for the user-run reset test (R-4); evidence recorded in the PR.

### PR 6: finish

1. Fill in the acceptance evidence table in the PR body.
2. Link the green test PR for C-5.

## 4. Actions that only the user can perform

| Action | Needed for | Notes |
|---|---|---|
| Run `sudo` commands and `restore.sh` | PR 4 manual check, PR 5 | Claude proposes exact commands (CLAUDE.md: never `sudo`) |
| Create the first release tag | Restore bootstrap | Question 7 |
| Require checks in the ruleset | After PR 1, 2, 3, 4 are green | Names in design section 7.4 |
| Create the `class:3` label | Optional | Question 12 |
| Run the home reset and time it | R-4 (AC1-7) | After PR 5 merges |
| Review, approve, merge every PR | All | |

## 5. Definition of done for CR-2

- All acceptance criteria in `acceptance-criteria.md` have recorded evidence in the implementation PRs.
- Stage 1 exit criteria: workspace restorable (AC1-7), CI green on a test PR.
- ADR-005 was accepted by the merge of the design PR.
- The final implementation PR is merged by the user and closes issue #2.
