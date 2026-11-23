# CR-55 Impact analysis

## 1. What changes

In this design PR, under `docs/` only (PC-4):

- The CR-55 files are added.
- Three accepted records get an "Amended by (CR-55, Proposed)" header entry, effective when this PR is merged: ADR-005, ADR-008, ADR-009. Their bodies change only after the approver's decisions arrive as a review on this PR (design section 4).
- `docs/README.md` gets a CR-55 row and the amended statuses.

Nothing else. No code, workflow, setting, ruleset, secret, variable, collaborator, label, or tag changes. CR-43 PR 5 is not started.

Later, in implementation PRs (see the plan): the manifest field `targets` and the cross-smoke, the configuration key `cross_builds`, `scripts/cross-build`, the check `no-emulation`, and in the template the job `cross-build-<target>`.

## 2. Affected components and records

| Item | Effect |
|---|---|
| ADR-005 | Amended: schema field `targets`, L2 cross-smoke, one context sentence |
| ADR-008 | Amended: seeded generic code, the matrix job, the configuration key |
| ADR-009 | Amended: `cross_builds` as a base-commit policy input, one sentence in decision 7, one catalogue entry |
| ADR-001, ADR-003 | Not amended. PC-9, the evidence line, and `gate-evidence` are unchanged |
| `config/project.yaml` | Later: optional key `cross_builds`; `architectures` is not touched |
| `toolchain/manifest.toml`, `scripts/toolchain` | Later: optional field `targets` and the cross-smoke. No tool is added by this CR |
| `ci.yml` here | Later: the cross-smoke runs inside the existing `toolchain-amd64` job; no new job here |
| `ai-software-template` | Later, inside CR-39 PRs: the job, the script, the check, and the configuration key |

## 3. Security and privacy

- No new execution surface: nothing built for a foreign architecture is ever run on the workspace or the runner (XB-2), and no system setting (binfmt, multiarch) is touched.
- Supply chain: each cross toolchain is a pinned, checksummed download for both host architectures, extracted by the existing hardened engine. No third-party Action, no artifact, no cache (WP-14 stays).
- A PR cannot add a cross-build target to the policy that judges it (`cross_builds` from the base commit, SC-20). The static `no-emulation` check is advisory; review stays the authority (SC-19).
- The lab VM and the operator machines are not reached and nothing is deployed to them (XB-13).
- The cross-build summary is a file count and a hash; no host name, path, user, or address. Public repository rules apply.
- Residual risks RR-X1 to RR-X3 (design section 7).

## 4. Operational impact on the approver

- Reviews the design and answers Q1 to Q8 as a review by the approver account on the PR.
- Installs a cross toolchain on the workspace, or has the restore do it (Claude Code does not).
- For a private repository, accepts or rejects "not tested natively on arm64" per PR (Q4).

## 5. Dependencies and assumptions

- CR-43 PR 4 (#54) is merged in `main` (read at `85360e8`). CR-43 PR 5 is a separate session and is not touched.
- The free ARM64 runner for public repositories is as documented on 2026-11-19; not verified by a run.
- Whether a suitable cross toolchain exists as a download for both host architectures is not verified; no toolchain is chosen here.

## 6. Cost and capacity

No OCI cost and no metered runner. One extra amd64 job per PR in a repository with a cross-build: free on a public repository, included minutes on a private one, and the $0 budget with usage stopped means exhaustion stops CI and never bills (ADR-009 decision 12). The minutes are not measured.

## 7. Rollback

Before implementation, revert the design PR (a revert restores the three header entries). After implementation, each PR is a normal revert. A repository without the `cross_builds` key runs no cross-build, so the feature is off by default.

## 8. Alternatives considered

See design section 5. The main ones: emulation, foreign-architecture containers, distro cross packages as default, a field inside `architectures`, evidence from the workspace, an artifact handoff to the native job, a third architecture, a metered ARM64 runner.
