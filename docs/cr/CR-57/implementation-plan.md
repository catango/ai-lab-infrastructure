# CR-57 Implementation plan

Starts only after the design PR is merged (ADR-003 section 4). Each PR runs in its own session, in `ai-lab-infrastructure` unless stated, branch `impl/CR-57-<slug>`, and declares `Implements: #57` and `Design:` with the design PR number. Slugs and order are proposals. No ADR is edited in an implementation PR.

## 1. Removal order

The repository `CLAUDE.md` keeps a rule until the PR that removes its subject (PA-11), and the gate is green after every PR. Operator code goes before Ansible because the operator playbook and lock are part of both; the toolchain profile change goes after Ansible because the builder-profile CI job applies the playbook.

## 2. The PRs

| # | Branch slug | Content | Needs | Criteria |
|---|---|---|---|---|
| 1 | `remove-operator` | Inventory of operator and lab references in tests and CI (reported first); remove `scripts/operator/`, `tests/operator/`, `docs/operations/operator.md`, the `operator-profile` and `operator-limits` jobs, `ansible/operator.yml`, the operator manifest entries and `toolchain/python/operator.lock`; `OPERATOR_PATHS` becomes configuration (empty); fixtures; the operator lines of `CLAUDE.md` | Design merged; Q1, Q2 | PA-A1, PA-A5, PA-A6 |
| 2 | `remove-lab-ansible` | Remove `ansible/` (builder, lab, roles, inventory), `tests/ansible/`, the `builder-profile` job, `docs/operations/gate-0-audit.md`, the OCI and lab lines of `CLAUDE.md` | PR 1 | PA-A1, PA-A4, PA-A5 |
| 3 | `gate-profile` | One manifest profile for the gate tools, `scripts/toolchain` and its manifest check updated, `toolchain-<arch>` jobs unchanged in effect | PR 2 | PA-A7 |
| 4 | `bootstrap` | `scripts/bootstrap` (replaces `workspace/restore.sh` and `verify.sh`), fixtures, `workspace-restore.md` replaced; `workspace/claude-user/` stays | PR 3 | PA-A8 |
| 5 | `host-contract` | `docs/operations/ai-host.md` (HC-1 to HC-6), `CLAUDE.md` rewrite with PA-3, the user-level `CLAUDE.md` of `claude-user/` | PR 4 | PA-A3, PA-A4 |
| 6 | `baseline-v0.2` | Baseline v0.2 (short), `docs/README.md`, CR-18 status; issue #16 and PR #17 closed on the approver's word | PR 5; Q4, Q6 | PA-A2 |
| 7 | `preset` | The preset for the template: `docs/PLATFORM.md` and the deny list source without OCI or operator content (ADR-008 decision 14) | PR 5 | PA-A9 |

PA-A10 is checked in every PR by the existing tests. CR-43 PR 5 (parity) is not affected and is not started by this CR; CR-43 PR 6 is re-scoped to documentation only after Q1.

## 3. Preconditions and user-only steps

- Q1 to Q6 answered by a review of the approver account on the design PR.
- The approver closes issue #16 and PR #17, or tells the session to, after the design merges. Any OCI or operator VM resources that exist are the approver's to keep or delete outside this repository; nothing here touches them.
- The approver provides the AI hosts and their keys; Claude Code installs nothing and runs no `sudo`.
- A rename of the repository, if wanted, is a setting the approver changes (Q3).

## 4. Checklist (each PR keeps its own)

- [ ] Draft PR opened with the implementation template, `Implements:` and `Design:` filled in
- [ ] Fixtures and tests written first for the PR's criteria
- [ ] Implementation done
- [ ] `./scripts/quality-gate.sh` passes; any skipped check is reported
- [ ] CI green
- [ ] Marked ready for review
