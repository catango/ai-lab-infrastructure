# CR-18 Impact analysis

## 1. What changes

- A new ADR (ADR-011) that amends ADR-001's credential placement for the operator user.
- A new directory `scripts/operator/` with a shared library, a setup script for the operator workspace, and three first use-case scripts, built in later implementation PRs.
- A new runbook `docs/operations/operator.md` (how the approver sets up and uses the operator clone).
- The manual runbooks `docs/operations/gate-0-audit.md` and `docs/operations/github-setup.md` are shortened to the parts that stay manual, and point at the scripts, once the scripts exist.
- The lab build (CR-16) gains an optional operator login (design section 7).

Nothing in this design PR creates a user, a token, a script, or an OCI or GitHub change.

## 2. Affected components and records

| Item | Effect |
|---|---|
| ADR-001 decision 5, section 4 matrix, B1 | Amended by ADR-011 decision 7. A pointer row is added to ADR-001 by this PR. The matrix wording is updated by the PR that adds the first script |
| ADR-002 | Unchanged. Operator scripts never change infrastructure (ADR-011 decision 5) |
| ADR-003 | Operator scripts are code, so they follow the PR workflow and the quality gate |
| ADR-005 | The OCI CLI and other non-Debian tools for the operator are installed by the `setup` script from pinned sources with checksums for both architectures. Whether that is a manifest entry or a profile is confirmed in the implementation PR (VO-6) |
| CR-16 | Needs a design change for the lab login and its acceptance criteria. That change goes through a new design PR after both CR-16 and CR-18 are merged. CR-16 is not edited by this PR |
| `workspace/verify.sh` V-4 | Unchanged. It checks the invoking user's home, and it runs as the AI user |
| `docs/operations/gate-0-audit.md`, `github-setup.md` | Shortened by the implementation PRs, not by this PR |

## 3. Security and privacy

- This is a trust-boundary change: credentials exist on the workspace for the first time, under a user the AI cannot read.
- The separation rests on file permissions and sudo, not on a host boundary. The AI user is in the `sudo` group (RR-OP-2).
- The operator may use sudo to install packages (approver's decision of 2026-11-18). The operator can therefore become root, so AI-written code that the operator runs could reach root (RR-OP-8). Only the `setup` script may call sudo, and a gate check rejects it elsewhere.
- AI-written code runs with credentials the AI never sees (RR-OP-1). The controls are review and merge before use, a merged-commit check, a fixed operation list, short-lived credentials, and sanitised output.
- The repository is public. Scripts contain no identifier. Their output to the approver is a summary without OCIDs, addresses, or names.

## 4. Operational impact on the approver

The approver, not Claude, performs these.

- Test the separation before the first credentialed run (acceptance U-1).
- Run `setup` once as the operator (and again after a reset), entering the operator's sudo password.
- Run the scripts as the operator user, in dry-run mode first.
- Create and revoke the token T2 for each GitHub configuration run, and choose the OCI authentication method (Q3).
- Review operator scripts with extra care: they are the code that runs with credentials.

## 5. Dependencies and assumptions

- CR-16 is merged first if possible, because the acceptance runner and the lab login build on it. The audit and GitHub scripts do not depend on it.
- The operator user already exists on the workspace. Its name is never written in the repository.
- Outbound internet access works for the operator user, and the OCI CLI can be installed there (VO-1, VO-2, `setup`).

## 6. Cost and capacity

No cost. No OCI resource is created.

## 7. Rollback

Delete the scripts through a PR, revoke T2 and any OCI session, remove the operator's sudo right, uninstall the tools `setup` added, and revert ADR-011 and the ADR-001 pointer. The manual runbooks stay valid throughout, so rollback loses no capability.

## 8. Alternatives considered

See ADR-011 section 3.
