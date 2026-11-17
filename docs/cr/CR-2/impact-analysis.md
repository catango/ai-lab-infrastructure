# CR-2 Impact analysis

## 1. What changes

| Area | Change | When |
|---|---|---|
| `docs/cr/CR-2/`, `docs/adr/ADR-005-toolchain.md` | Added by this design PR (documents only) | Design PR |
| `toolchain/`, `scripts/toolchain` | New manifest and install engine | Implementation |
| `ansible/` | New `builder` playbook and roles; `lab` placeholder | Implementation |
| `workspace/` | New `restore.sh`, `verify.sh`, `repos.txt`, `claude-user/`, helpers | Implementation |
| `scripts/quality-gate.sh`, `scripts/checks/` | New | Implementation |
| `scripts/pr-contract`, `tests/` | New | Implementation |
| `.github/workflows/`, `.github/dependabot.yml` | New CI skeleton | Implementation |
| `docs/operations/workspace-restore.md` | New runbook | Implementation |
| `CLAUDE.md` | Wording change for `gh pr create --template` (design question 10) and the `fd` and `quality-gate` notes, in a separate change PR | After approval |

Nothing in the repository changes in the design PR other than files under `docs/` (PC-4).

## 2. Affected components and records

| Item | Effect |
|---|---|
| ADR-001 section 4a | Implemented as written. Two interpretations are flagged: local tracking branches instead of checkouts (question 13); the noreply email built at run time. |
| ADR-001 section 5 | Guardrail list becomes a machine-checked list (`required-deny.txt`). Workspace managed settings stay opt-in. |
| ADR-003 sections 6 and 7 | `pr-contract` implemented. Verification item V3-1 finding: `gh pr create --template` does not work without a terminal. |
| Baseline section 6, stage 1 | Entry criterion "ADR-005 approved (builder part)" is met by merging this design PR, which carries ADR-005. |
| Baseline section 7 | ADR-005 moves from "to be written" to "Proposed". |
| `.claude/settings.json` | Unchanged. The `fd` allow rule needs `fd` installed (the builder profile provides it). |

## 3. Security and privacy

- The repository is public. The design uses placeholders only. The `public-repo-hygiene` check enforces this for later PRs.
- Supply chain: all downloads are checksum-pinned for two architectures; extraction is hardened; apt is the one documented exception (question 1).
- Token T1 handling follows ADR-001 D16. The script never receives the token through argv, environment, or files. It refuses to run inside a Claude Code session.
- CI adds no secrets and no Claude invocation. All jobs run with least-privilege tokens. Residual risk RR-S1-1 (workflow editable by the PR) is mitigated by PC-6 and the approver's review.

## 4. Operational impact on the user

- Manual actions the implementation will need from the user (Claude does not run these): `sudo` commands for `restore.sh` and for apt bootstrap; creating a release tag; configuring required checks in the ruleset; creating the `class:3` label if wanted; running the reset test for AC1-7.
- Each is listed with the exact command in the runbook and in the PR that needs it.
- Each implementation PR is small (see the implementation plan) so that reviews stay short.

## 5. Dependencies and assumptions

- Stage 0 is done (ADR-003 and the seed PR are merged).
- GitHub-hosted `ubuntu-24.04-arm` runners are available for this public repository (to confirm in implementation).
- The workspace has network access to GitHub and to the Debian archive. Corporate proxies or TLS interception are not known to exist; if they do, downloads may need a CA bundle (to confirm in the reset test).
- Python 3.12 or later exists on every target (Debian 13 and Ubuntu 24.04 ship it).
- Linters not present on the workspace today (`yamllint`, Markdown linter, `terraform` or `tofu`, `ansible`, `fd`) arrive with the builder profile. Until then they are reported as not run.

## 6. Cost and capacity

- GitHub-hosted runners for public repositories are free, including the ARM64 label (to confirm).
- No OCI resources are created or changed. No OCI credentials are involved.
- The A1 capacity of the lab VM is not affected.

## 7. Rollback

- Design PR: revert the merge commit.
- Implementation PRs: each is independent and revertible. `restore.sh` and the toolchain only add files under `/opt/ai-lab` and `~/.claude/` (with backups). Removing `/opt/ai-lab` and its `PATH` snippet fully reverses the toolchain install.
- Required checks are added by the user; removing them from the ruleset removes the CI dependency.

## 8. Alternatives considered

| Alternative | Why not chosen |
|---|---|
| Ansible `get_url` and `unarchive` as the install mechanism | Cannot be reused by CI and verification; arm64 and amd64 paths would be maintained twice. |
| Nix, mise, asdf, or aqua as the tool manager | New trust surface and bootstrap dependency; the manifest plus a small installer is easier to audit. |
| `pr-contract` as a bash script with `jq` | Parsing untrusted Markdown and API JSON safely and testing it with fixtures is clearer and safer in Python. |
| `pull_request_target` for `pr-contract` | Gives untrusted PRs a privileged context; unnecessary because a read-only token suffices. |
| Embedding PR text in workflow expressions | Script-injection risk (ADR-003 section 6, security requirement). |
