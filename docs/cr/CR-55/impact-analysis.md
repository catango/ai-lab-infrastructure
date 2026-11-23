# CR-55 Impact analysis

## 1. What changes

In this design PR, under `docs/` only (PC-4):

- The CR-55 files are added.
- Two accepted records get an "Amended by (CR-55, Proposed)" header entry, effective when this PR is merged: ADR-008 and ADR-009. Their bodies change only after the approver's decisions arrive as a review on this PR (design section 5). ADR-005 is not amended unless Q1 is accepted.
- `docs/README.md` gets a CR-55 row.

Nothing else. No code, workflow, setting, ruleset, secret, variable, collaborator, label, or tag changes. CR-43 PR 5 is not started.

Later, in implementation PRs (see the plan): `scripts/cross-build`, the check `no-emulation`, and in the template the extra step of the matrix job for an architecture without a runner.

## 2. Affected components and records

| Item | Effect |
|---|---|
| ADR-008 | Amended: decision 8 (seeded generic code) and decision 9 (the matrix job without a runner also cross-builds) |
| ADR-009 | Amended: decision 7 (one sentence), decision 10 (catalogue entry). Decision 7 and Q14 are amended further only if Q1 is accepted |
| ADR-001, ADR-003, ADR-005 | Not amended. PC-9, the evidence line, `gate-evidence`, the manifest, and the profiles are unchanged |
| `config/project.yaml` | Unchanged: no new key. `architectures` already carries `runner_private` |
| `toolchain/manifest.toml`, `scripts/toolchain`, `builder` profile | Unchanged. Cross toolchains live in the project repository |
| `ai-software-template` | Later, inside CR-39 PRs: the seeded script and check, and the matrix job step |

## 3. Security and privacy

- No new execution surface: nothing built for a foreign architecture is run on the workspace or the runner (XB-4), and no system setting is touched.
- No third-party Action, artifact, or cache (WP-14 stays). The platform downloads nothing new.
- The cross toolchain is the project's supply-chain surface and is out of scope here (XB-5).
- The lab VM and operator machines are not reached and nothing is deployed to them (XB-10).
- The cross-build summary is a file count and a hash; no host name, path, user, or address.
- Residual risks RR-X1 and RR-X2 (design section 8).

## 4. Operational impact on the approver

- Reviews the design and answers Q1 to Q4 as a review by the approver account on the PR.
- For a private repository without an ARM64 runner, keeps accepting or rejecting the PC-9 evidence line per PR, as today.
- If Q1 is accepted, confirms on the account that the $0 budget stops usage of included minutes.

## 5. Dependencies and assumptions

- CR-43 PR 4 (#54) is merged in `main` (read at `85360e8`). CR-43 PR 5 is a separate session and is not touched.
- GitHub runner labels, private-repository availability of arm64 runners, and the billing model were read on 2026-11-23 through search summaries of GitHub's pages; not verified by a run.

## 6. Cost and capacity

No OCI cost and no metered runner unless Q1 is accepted. Public repositories use free native runners. A private repository without an ARM64 runner adds an amd64 step inside an existing job (included minutes, not measured). The $0 budget with usage stopped (ADR-009 decision 12) means exhaustion stops CI and never bills.

## 7. Rollback

Before implementation, revert the design PR (a revert removes the two header entries). After implementation, each PR is a normal revert. Without a build entry point in a project, `scripts/cross-build` does nothing.

## 8. Alternatives considered

See design section 6. The main ones: cross-build everything, emulation, platform-provided toolchains, a new configuration key, a separate required job, an artifact handoff, native Windows and macOS targets now, native arm64 on private repositories by default.
