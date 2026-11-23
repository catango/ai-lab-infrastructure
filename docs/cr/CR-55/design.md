# CR-55 Design: cross-platform architectures and cross-builds

Status: proposal for the architecture discussion. Design only: nothing is implemented, no setting changes. Decisions are XB-1 to XB-12; the questions for the approver are Q1 to Q4 (section 7).

## 1. Requirement and the inputs already given

Requirement (user, 2026-11-23): "the lab should also be able to develop cross-platform architectures and cross-builds". The user fixed these inputs (intake discussion and a follow-up in the session of this PR); they are not re-opened here, and the approver's review confirms them:

| Input | Decision |
|---|---|
| Architectures | `amd64` and `arm64`. `amd64` (x86-64) is the standard architecture. No third architecture |
| Direction | amd64 host to arm64 target only. **No reverse cross-build** |
| Build and test | **Prefer native build and test** on any GitHub-hosted runner that has the target. A cross-build is the fallback, and it is build only |
| Mechanism | Cross-compilers, no emulation |
| Cross toolchains | **They live in the project repository.** The platform does not provision, pin, or smoke-test them |
| Where | The x86-64 workspace and CI |

Definitions. *Host*: where the build runs. *Target*: the architecture of the artifact. *Native*: host equals target. *Cross-build*: host differs from target.

## 2. Facts this design rests on

Read in `main` at `85360e8` (contains CR-43 PR 4) and in the accepted records, and on GitHub's pages on 2026-11-23 through a search that returned summaries. Nothing was verified by a run.

- `scripts/gate-evidence <arch>` refuses an architecture that is not the host's. PC-9 asks for an evidence line only for an architecture without a runner for the repository, from `architectures` in the base commit (SC-20). `architectures` entries carry `name`, `runner` (public repository), `runner_private`; the reader (`scripts/pr_contract/config.py`) rejects any other key inside an entry.
- ADR-008 decision 9: the CI matrix has one job per configured architecture. Where no runner exists, the job runs on a base runner and writes `not run: <arch>`; a required job is never skipped (ADR-009 decision 1). The private flag is read from `github.event.repository.private` (ADR-008 decision 10).
- ADR-009 decision 7 and Q14: no metered ARM64 runner is used; decision 12: no payment method and $0 budgets with usage stopped. WP-14 forbids cache and artifact actions, so one job cannot hand a file to another.
- CLAUDE.md: Claude Code installs no software and never reaches the lab VM or an operator machine.
- The hosted runner picture (section 3).

I did not read the `ai-software-template` repository; statements about it come from ADR-008 and CR-39.

## 3. Hosted runners considered

Standard GitHub-hosted runners, as summarized from GitHub's runner reference and changelog. Labels change over time; the allowed set stays the configured `runner_labels` list (WP-13).

| Platform | Public repository | Private repository |
|---|---|---|
| Linux x64 (`ubuntu-24.04`) | Free | Included minutes |
| Linux arm64 (`ubuntu-24.04-arm`) | Free, 4 CPU | Available since January 2026 (changelog of 2026-01-29), 2 CPU, counts against included usage; **this platform does not use it by default** (ADR-009 Q14) |
| Windows arm64 (`windows-11-arm`), Windows x64 | Free | Arm64 as Linux arm64; Windows x64 uses included minutes (multiplier not verified) |
| macOS Apple silicon (`macos-15`, `macos-latest`) and Intel (`macos-15-intel`) | Free | Included minutes; multipliers and the current Free-plan allowance not verified (GitHub moved the allowance toward a dollar amount) |

Result. Every row has a native runner. **A cross-build is therefore needed only where the policy forbids the native runner:** the workspace (x86-64), and a private repository whose `runner_private` for arm64 is empty (the platform default). Non-Linux platforms are not a v1 target (Q2).

## 4. Decisions

**XB-1 Scope.** Linux, `amd64` standard, `arm64` target. The only cross direction is amd64 host to arm64 target. No reverse direction, no third architecture.

**XB-2 Native first.** For every architecture of `architectures`, CI builds and tests natively on the hosted runner configured for the repository's visibility (`runner` or `runner_private`), as ADR-008 decision 9 already says. Nothing in this CR changes that path. This CR adds no new key, job, or manifest field.

**XB-3 Cross-build only as the fallback.** An architecture with no runner for the repository's visibility already runs its matrix job on a base (amd64) runner and writes `not run: <arch>`. That job also runs `scripts/cross-build <arch>` and writes `cross-built: <arch> (build only)`. So no new required job and no job-level skip exist, and the aggregate `quality-gate` fails if the cross-build fails. On the workspace the same script is the local cross-build.

**XB-4 Build only, no emulation.** A cross-build never executes a target binary on a host of another architecture. Forbidden: qemu-user, `binfmt_misc`, a foreign-architecture container (`--platform`), `dpkg --add-architecture`.

**XB-5 The project owns its cross toolchain and build.** Compilers, linkers, sysroots, and target libraries live in the project repository and follow that repository's own supply-chain rules. The platform changes no manifest, no `builder` profile, and no toolchain engine. The one contract is a project-owned build entry point `scripts/build --target <arch>` that writes under `build/<arch>/` (Q3).

**XB-6 The script `scripts/cross-build <target>`.** Generic code, seeded into the template (ADR-008 decision 8). It refuses a target equal to the host, refuses a name not in `architectures`, runs the entry point, checks every ELF file in the output for the target's machine field, and prints the file count and one SHA-256 of the sorted file hashes; no host name, user, or absolute path. It supports `--dry-run` and never executes a built file.

**XB-7 What is tested.** With a native runner, the native build is built and tested: the whole artifact path is exercised. In the fallback case the cross-built artifact is built and architecture-checked but not executed anywhere automatically (RR-X1). PC-9 is unchanged: the "tested" evidence for such an architecture is the host-reported line from an arm64 host, and a workspace cross-build is not evidence (`gate-evidence arm64` keeps refusing on x86-64).

**XB-8 Gate check `no-emulation`** (class generic, catalogue of ADR-009 decision 10). A line scan of workflows and scripts for the XB-4 patterns, with fixtures. It is advisory like the other static checks (SC-19); the approver's review stays the authority.

**XB-9 Private repositories.** Default: unchanged policy, so arm64 is cross-built (XB-3) and tested through the PC-9 evidence line. Option: a repository sets `runner_private: ubuntu-24.04-arm` in its configuration and gets native arm64 build and test on included minutes, with the $0 budget and usage stopped (ADR-009 decision 12) so exhaustion stops CI and never bills. The `architectures` key already supports it. It contradicts "no metered ARM64 runner is used" (ADR-009 decision 7 and Q14), so it is **not decided here** (Q1).

**XB-10 Lab VM and operator machines are untouched.** No script deploys, copies, or runs an artifact on them. Deployment is separate work (ADR-002, ADR-011).

**XB-11 Cost.** No metered label unless Q1 is accepted. The fallback adds an amd64 base-runner step inside an existing job: free on a public repository (where the native runner is used instead), included minutes on a private one. Not measured.

**XB-12 Workspace.** Local cross-builds run `scripts/cross-build` with the project's own cross toolchain, which the user installs (Claude Code installs nothing).

## 5. Amendments to accepted records (the process of this PR)

An accepted record changes only by an "Amended by" header entry that takes effect when this design PR is merged (CR-39 and CR-43 process). This PR adds that entry, marked Proposed, to the two records below. The **body text** is committed in this PR only after the approver's decisions arrive as a review by the approver account, as CR-43 did with Q21; until then the table is the intended text. ADR-001, ADR-003, and ADR-005 are not amended, and no approved `design.md` is edited. If Q1 is accepted, the same step also amends ADR-009 decision 7 and the ADR-005 context line on private ARM64 runners.

| Record | Intended amendment |
|---|---|
| A1: [ADR-008](../../adr/ADR-008-software-template.md) | Decision 8: the seeded generic code gains `scripts/cross-build` and the check `no-emulation`. Decision 9: the matrix job of an architecture with no runner also cross-builds and writes `cross-built: <arch> (build only)` |
| A2: [ADR-009](../../adr/ADR-009-security-and-ci-baseline.md) | Decision 7: one sentence that a cross-built architecture has no host evidence and that the line is still required. Decision 10: the catalogue gains `no-emulation` |

## 6. Alternatives considered

| Alternative | Outcome | Reason |
|---|---|---|
| Cross-build everything from x86 | Rejected | A native runner gives stronger evidence and exists for every platform (section 3) |
| qemu-user and `binfmt_misc` | Rejected (user) | Weaker than native, system changes Claude Code cannot make, a new execution surface |
| Foreign-architecture containers | Rejected | Needs the container runtime ADR-005 O-10 deferred, and emulation underneath |
| The platform provisions cross toolchains (manifest `targets`, builder profile) | Rejected (user) | They live in the project repository |
| A new `cross_builds` key | Dropped | The fallback follows from `architectures` and the private flag |
| A separate `cross-build-<arch>` required job | Dropped | The matrix job of the architecture without a runner already exists and cannot be skipped |
| Hand the cross-built artifact to a native test job | Dropped | WP-14 forbids it, and native first makes it unnecessary |
| Windows and macOS native targets now | Deferred (Q2) | Evidence line, install engine, and `gate-evidence` assume Linux |
| Native arm64 on private repositories by default | Not chosen (Q1) | ADR-009 decision 7 and Q14 |

## 7. Questions for the approver

Each has a recommended default that the criteria and the plan assume until the review says otherwise.

| ID | Question | Recommended default |
|---|---|---|
| Q1 | May a private repository use the hosted ARM64 runner (opt-in `runner_private`) for native build and test? It amends ADR-009 decision 7 and Q14 and adds one ADR-005 context line | Keep the platform default (no metered ARM64 runner), and allow the opt-in per repository only on the approver's explicit decision, with the $0 budget in force. The user's preference for native testing argues for yes once the budget stop is confirmed on the account |
| Q2 | Are Windows and macOS runners targets of this CR? | No: a later CR, because the evidence line, the install engine, and `gate-evidence` are Linux-only |
| Q3 | The project build entry point and output directory | `scripts/build --target <arch>` writing `build/<arch>/`, project-owned, seeded |
| Q4 | Is the ELF machine check enough? | Yes for Linux C, C++, Go, Rust; other formats are out of scope |

## 8. Risks and what stays open

- **RR-X1.** In the fallback case a miscompile caused only by the cross toolchain passes CI, because the cross-built binary is never executed. Mitigation: the ELF check, the project's pinned toolchain, the PC-9 evidence line for the target, and Q1.
- **RR-X2.** The `no-emulation` scan cannot see a command built at run time. Mitigation: review (SC-19).
- Not verified: GitHub's current labels, private-repository multipliers, and the Free-plan allowance; whether the $0 budget stops usage of included minutes as ADR-009 decision 12 assumes (Q1 depends on it); the CI minutes of the fallback step; the template repository's files.
