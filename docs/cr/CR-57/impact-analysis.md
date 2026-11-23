# CR-57 Impact analysis

## 1. What changes

In this design PR, under `docs/` only (PC-4):

- The CR-57 files are added.
- Four accepted records get a header entry marked Proposed, effective when this PR is merged: ADR-001 and ADR-005 (amended), ADR-002 and ADR-011 (superseded). Their bodies change only after the approver's decisions arrive as a review on this PR (design section 5).
- `docs/README.md` gets a CR-57 row and the amended statuses.

Nothing else. No code, workflow, setting, ruleset, secret, label, or tag changes, and the template repository is not touched.

Later, in implementation PRs (see the plan): removal of the operator and lab code, one gate profile of the manifest, `scripts/bootstrap`, the host contract document, the rewritten `CLAUDE.md`, and baseline v0.2.

## 2. Affected components and records

| Item | Effect |
|---|---|
| ADR-001 | Amended: two named hosts become AI hosts, OCI and operator zones and rows removed, restore becomes bootstrap, rule PA-3 added. The GitHub model (T1, machine account, rulesets, D17, RR-9, RR-10) is unchanged |
| ADR-002, ADR-011, CR-18 | Superseded in full / withdrawn. Issue #16 and PR #17 closed when the design merges (Q6) |
| ADR-005 | Amended: Ansible, builder content, operator profile, and the `lab` profile go; one gate profile stays |
| ADR-003, ADR-008, ADR-009, ADR-010 | Not edited. PC-8 and `operator-contract` stay generic and inactive (Q2) |
| `scripts/operator/`, `tests/operator/`, `ansible/`, `docs/operations/operator.md`, `gate-0-audit.md` | Later: removed |
| `workspace/restore.sh`, `verify.sh`, `workspace-restore.md` | Later: replaced by `scripts/bootstrap` and a host document; `workspace/claude-user/` stays |
| `toolchain/manifest.toml`, `toolchain/python/operator.lock` | Later: one profile; the operator-only entries and lock go |
| `ci.yml` | Later: the jobs `operator-profile`, `operator-limits`, `builder-profile` go; the aggregate `quality-gate` needs the rest; required check names unchanged |
| `scripts/pr_contract/rules.py` | Later: `OPERATOR_PATHS` becomes configuration with an empty value |
| `CLAUDE.md` of this repository | Later: rewritten, in the PR that removes the matching code |
| CR-43 | PR 5 (parity) unaffected; PR 6 (settings docs and desired state) re-scoped to documentation only (Q1) |
| CR-39, CR-45, `ai-software-template` | Unaffected; the preset change PR drops OCI and operator content from `docs/PLATFORM.md` |

## 3. Security and privacy

- The GitHub trust model is unchanged: machine account, T1 entered by the user in a plain SSH terminal, rulesets, deny rules, `forbidden-api`, and the approver as the only one who approves and merges.
- The attack surface shrinks: no OCI credential, no operator machine, no Terraform path, no scripted settings changes.
- It grows in one place: AI hosts are no longer provisioned by the platform, so guardrail strength depends on the host owner (RR-P2). The host contract and the read-only bootstrap checks mitigate it.
- PA-3 keeps Claude Code from opening onward SSH and from reading `~/.ssh/`.
- No host, address, user, or key appears in any file (public repository rules).

## 4. Operational impact on the approver

- Reviews the design and answers Q1 to Q6 as a review by the approver account on the PR.
- Closes or approves closing issue #16 and PR #17 after the merge.
- Keeps the GitHub settings list manual (ADR-009 decision 13) once the scripted path is retired.
- Provides AI hosts and keys; the platform no longer does.

## 5. Dependencies and assumptions

- CR-55 is withdrawn (PR 56 and issue 55 closed).
- CR-43 PR 4 is merged. CR-43 PR 5 and CR-39 and CR-45 continue unchanged.
- Whether tests and CI jobs outside the listed paths refer to operator or lab content is not verified; the first removal PR inventories it.

## 6. Cost and capacity

No cost. The OCI plans (Always Free account, quotas, budget alert) were Proposed, never accepted, and fall away. The zero-cost rule of ADR-009 decision 12 stays for GitHub.

## 7. Rollback

Before implementation, revert the design PR (a revert removes the four header entries). After implementation, each PR is a normal revert; removed code stays in history. The removal order keeps the gate green after every PR.

## 8. Alternatives considered

See design section 6.
