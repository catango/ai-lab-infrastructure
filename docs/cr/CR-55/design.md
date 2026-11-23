# CR-55 Design: cross-platform architectures and cross-builds

Status: proposal for the architecture discussion. Design only: nothing is implemented, no setting changes. Decisions are named XB-1 to XB-14; the questions for the approver are Q1 to Q8 (section 6).

## 1. Requirement and the decisions already taken

Requirement (user, 2026-11-23): "the lab should also be able to develop cross-platform architectures and cross-builds". In the intake discussion the user fixed four inputs, which are not re-opened here:

| Input | Decision |
|---|---|
| Target architectures | `amd64` and `arm64` only. A third architecture is a later CR |
| What a cross-build delivers | **Build only.** Tests run on GitHub runners of the specific architecture, natively |
| Mechanism | **Cross-compilers.** No emulation |
| Where it runs | The x86-64 workspace and CI (hosted amd64 runner). Not the lab VM |

Definitions. *Host*: the machine the build runs on. *Target*: the architecture the artifact is for. A *cross-build* has host != target. A *native* run has host == target.

## 2. Facts this design rests on

Read in `main` at commit `85360e8` (which contains CR-43 PR 4, #54) and in the accepted records; none was verified by a run unless stated.

- `scripts/gate-evidence <arch>` refuses an architecture that is not `uname -m` of the host. PC-9 (`scripts/pr_contract/rules.py`) asks for an evidence line only for an architecture without a runner for the repository (`config/project.yaml` key `architectures`, read from the base commit, SC-20).
- The reader of `architectures` (`scripts/pr_contract/config.py`) is strict: any key inside an entry other than `name`, `runner`, `runner_private` is an error, and any other top-level key is skipped. A new field on `architectures` would therefore break PC-9; a new top-level key does not.
- `ci.yml` already runs the toolchain job per architecture (`ubuntu-24.04`, `ubuntu-24.04-arm`). The free ARM64 runner is for public repositories only; no metered ARM64 runner is used (ADR-005 context, ADR-009 decision 7 and Q14; the GitHub fact was read on 2026-11-19 and not verified by a run).
- WP-14 forbids `actions/cache`, `actions/upload-artifact`, and `actions/download-artifact`; WP-4 allows `actions/checkout` only. A job cannot hand a file to another job.
- ADR-005: every `download` has `amd64` and `arm64` checksums, for the host architecture of the tool. ADR-008 decision 8: the template has its own CI manifest with the same schema; it is not a host profile.
- CLAUDE.md: Claude Code installs no software, never reaches the lab VM or an operator machine, and runs no `sudo`.

I did not read the `ai-software-template` repository. Statements about it come from ADR-008 and CR-39.

## 3. Decisions

**XB-1 Scope.** Targets are `amd64` and `arm64`. v1 direction: host `amd64`, target `arm64` (workspace and hosted amd64 runner). The reverse direction has no requirement and is not designed (Q5).

**XB-2 Build only, no emulation.** A cross-build never executes a target binary on a host of another architecture. Forbidden: qemu-user, `binfmt_misc`, a foreign-architecture container (`--platform`), `dpkg --add-architecture`. A cross-build job builds and checks the artifact, nothing else.

**XB-3 Mechanism: pinned cross-compilers.** A cross toolchain is a manifest tool. Preferred source `download`: exact version and SHA-256 for **both host architectures** (ADR-005 decision 3 unchanged, as for the operator profile in ADR-005 decision 10). `apt` only when no download exists, with the minimum-version exception of ADR-005. Reason for the preference: the workspace is Debian 13 and the runner is Ubuntu 24.04, so distro cross packages give two different compilers for the same commit (RR-X2). A language's own cross support (a pinned Go, or a pinned Rust with a target and linker) is a manifest tool of the same kind.

**XB-4 Manifest field `targets`.** A tool may carry `targets = ["arm64"]`: the architectures it builds for. Valid values are `amd64` and `arm64`; a third name is an error (ADR-005 decisions 1 and 3 stay two-architecture). A tool with `targets` also has a *cross-smoke* in `scripts/toolchain verify`: it compiles a fixed trivial source and reads the ELF header of the result with a pure reader, checking that the machine field is the target's. The result is never executed. CI runs it in the existing `toolchain-amd64` job.

**XB-5 Configuration key `cross_builds`.** A new top-level key of `config/project.yaml`: a list of `{host, target}`, absent by default (no cross-builds). Both names must be entries of `architectures`, `host != target`, and v1 accepts only `host: amd64, target: arm64`. A strict reader of the same style as `config.py` reads it from the **base commit** (SC-20), so a PR cannot add a cross-build target to judge itself. PC-9 and `architectures` are unchanged.

**XB-6 The script `scripts/cross-build <target>`.** Generic code, seeded into the template (ADR-008 decision 8). It refuses a target equal to the host, refuses a target not configured for this host, runs the project's build entry point for the target with the cross toolchain, and then checks every ELF file in the output for the target's machine field. It prints the file count and a SHA-256 of the sorted list of file hashes; no host name, user, or absolute path. It supports `--dry-run` and never executes a built file. The entry point (`scripts/build --target <arch>`, project-owned) and the output directory are proposals (Q7).

**XB-7 CI job `cross-build-<target>`.** In the generated `ci.yml`, a job on the hosted runner of the host, using only `actions/checkout`. It installs the cross toolchain with `scripts/toolchain install` from the manifest, runs `scripts/cross-build`, and writes `cross-built: <target> (build only)` to its summary. The aggregate `quality-gate` already needs every other job (ADR-009 decision 1), so a failed, skipped, or cancelled cross-build blocks the merge on a public repository. It runs for private repositories too (amd64 runner).

**XB-8 Native tests are unchanged.** `quality-gate-arm64` runs natively on the free ARM64 runner for a public repository (ADR-008 decision 9). For a private repository there is no ARM64 runner: the job writes `not run: arm64` and PC-9 asks for the evidence line from an arm64 host (ADR-009 decision 7). This CR adds nothing to PC-9 and nothing to `gate-evidence`.

**XB-9 What is and is not tested.** The native job tests a native build of the same commit. The cross-built artifact itself is built and architecture-checked but is not executed anywhere automatically, because WP-14 forbids handing it to another job. This is residual risk RR-X1 (Q1 lists the alternative).

**XB-10 No evidence from the workspace.** A cross-build on the workspace is not evidence for a PR and has no evidence-line kind: the proof that the arm64 build works is the CI job `cross-build-arm64`. `gate-evidence arm64` keeps refusing on an x86-64 host.

**XB-11 Installing on the workspace.** The user installs the cross toolchain (restore, or the `scripts/toolchain install` command that the PR proposes); Claude Code does not. Where the pins live is Q2. The recommendation keeps the `builder` profile unchanged.

**XB-12 Gate check `no-emulation`** (class generic, catalogue of ADR-009 decision 10). A line scan of workflows, scripts, and the manifest for the XB-2 patterns, with fixtures. It is advisory like the other static checks (ADR-009 decision 2, SC-19): the approver's review of the workflow diff stays the authority.

**XB-13 Lab VM and operator machines are untouched.** No script deploys, copies, or runs an artifact on the lab VM or an operator machine. Running a cross-built artifact on the lab VM, and its deployment, are separate work for the approver and the operator tier (ADR-002, ADR-011), after the OCI VMs exist.

**XB-14 Cost.** No metered runner label. The cross-build job adds amd64 runner minutes: free on a public repository; on a private one it uses the included minutes, and the $0 budget with usage stopped (ADR-009 decision 12) means exhaustion stops CI and never bills. The amount is not measured (no run exists).

## 4. Amendments to accepted records (the process of this PR)

CR-43 and CR-39 define the process, and this PR follows it: an accepted record is changed only by an "Amended by" header entry that takes effect when the design PR is merged. This PR adds that header entry to the three records below, marked Proposed. The **body text** in the table is committed to each record in this PR only after the approver's decisions arrive as a review on this PR, as CR-43 did with Q21. Until then the table is the intended text and the records' bodies are unchanged. ADR-001 and ADR-003 are not amended (PC-9 and the trust model are unchanged); no approved `design.md` is edited.

| Record | Intended amendment |
|---|---|
| A1: [ADR-005](../../adr/ADR-005-toolchain.md) | Decision 1: the schema gains the optional `targets` field (XB-4). Decision 7: L2 gains the cross-smoke on amd64 for target arm64. Context: one sentence, "cross-building needs no ARM64 host; running does; emulation is not used" |
| A2: [ADR-008](../../adr/ADR-008-software-template.md) | Decision 8: the seeded generic code gains `scripts/cross-build` and the check `no-emulation`. Decision 9: the matrix gains the job `cross-build-<target>`. Decision 14: the configuration gains `cross_builds` |
| A3: [ADR-009](../../adr/ADR-009-security-and-ci-baseline.md) | Decision 14: `cross_builds` is a policy input read from the base commit. Decision 7: one sentence that a cross-built target has no host evidence (XB-10). Decision 10: the catalogue gains `no-emulation` |

## 5. Alternatives considered

| Alternative | Outcome | Reason |
|---|---|---|
| qemu-user and `binfmt_misc` to run and test arm64 on amd64 | Rejected (user) | Weaker evidence than a native runner, needs system changes that Claude Code cannot make, and a new execution surface |
| Foreign-architecture containers | Rejected | Needs the container runtime that ADR-005 O-10 deferred, and emulation underneath |
| Distro cross packages as the default | Not chosen | Debian 13 and Ubuntu 24.04 give different compilers (RR-X2); a download is pinned and checksummed |
| A new field inside `architectures` | Rejected | The strict PC-9 reader would fail (section 2) |
| Cross-build evidence from the workspace as an evidence line | Rejected | It would be a second host-reported kind of unverifiable prose; the CI job is automated |
| Pass the cross-built artifact to the native job | Deferred (Q1) | Needs the artifact actions, which WP-14 and WP-4 forbid in v1 |
| A third architecture now (armv7, riscv64) | Out of scope (user) | Amends ADR-005 decisions 1 and 3 and adds checksums per tool |
| A metered ARM64 runner for private repositories | Rejected | ADR-009 Q14 and the zero-cost constraint |

## 6. Questions for the approver

Each has a recommended default, which the criteria and the plan assume until the review says otherwise.

| ID | Question | Recommended default |
|---|---|---|
| Q1 | Must the cross-built artifact itself be tested on the native runner? | No (RR-X1). The alternative amends WP-14 and the allowlist for the GitHub-owned artifact actions with the ADR-009 decision 4 steps, and publishes the artifact on a public repository |
| Q2 | Where are the cross toolchain pins? | The project's own manifest in the application repository (same schema, template-owned engine, ADR-008 decision 8), so the workspace and CI use the same pin; the `builder` profile stays unchanged. The alternative adds them to the `builder` profile (amends ADR-005 decision 9) |
| Q3 | Target libraries (an arm64 `libssl`, for example)? | None in v1: static linking, vendored code, or a checksummed sysroot as a manifest download. The alternative, multiarch apt, needs `dpkg --add-architecture` on the workspace by the user |
| Q4 | A private repository has no ARM64 runner. Is "built by CI, not tested natively, PC-9 evidence from an arm64 host" acceptable? | Yes, accepted per PR by the approver, as PC-9 already works. Until the lab VM exists there is no arm64 host for the evidence line |
| Q5 | Is the reverse direction (host arm64, target amd64) needed? | No; a later CR |
| Q6 | Is the ELF machine check enough for the artifact check? | Yes for v1 (Linux C, C++, Go, Rust). Other formats are out of scope |
| Q7 | The project build entry point and output directory? | `scripts/build --target <arch>` writing under `build/<arch>/`, project-owned, seeded |
| Q8 | The key name `cross_builds`? | Yes |

## 7. Risks and what stays open

- **RR-X1.** The tested arm64 binary is a native build; the cross-built binary is not executed. A miscompile that only the cross toolchain causes would pass CI. Mitigation: the ELF check, a pinned toolchain, and Q1.
- **RR-X2.** A distro cross compiler on the workspace and on the runner can differ. Mitigation: `download` preferred (XB-3).
- **RR-X3.** The static `no-emulation` scan cannot see a script that builds the command at run time. Mitigation: review, as for every static gate rule (SC-19).
- Not verified: which cross toolchain a first project uses (none is chosen here); the CI minutes of a cross-build job; the template repository's current files; that every cross toolchain exists as a download for both host architectures. The implementation plan names a precondition for the last item.
