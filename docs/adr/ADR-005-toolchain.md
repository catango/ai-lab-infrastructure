# ADR-005: Toolchain Manifest, Profiles, and Install Sources

| Field | Value |
|---|---|
| Status | **Accepted** (2026-11-17, by the merge of the CR-2 design PR #3 by the approver). Open questions were resolved by the approver before review; see CR-2 design section 9 |
| Date | 2026-11-17 |
| Repository | `ai-lab-infrastructure` |
| Change request | CR-2 (issue #2) |
| Amended by | ADR-011 decision 10 and CR-18 design section 5 (Accepted, 2026-11-18): adds the `operator` profile (decision 10 below). In effect since ADR-011 was accepted (2026-11-18, merge of PR #19) |
| Amended by (scope) | CR-39 (Proposed, design PR #40): decision 1 below applies to this platform's hosts only; the software template's CI manifest is separate (see decision 1). Takes effect when the CR-39 design PR is merged |
| Amended by (context) | CR-43 (design PR #44): ARM64 runners on private repositories. Takes effect when the CR-43 design PR is merged |
| Amended by (cross-build) | CR-55 (Proposed, design PR for issue #55): schema field `targets`, the cross-smoke at L2, and a context sentence on cross-building. Takes effect when the CR-55 design PR is merged |
| Scope | `builder` profile in full (Stage 1); `lab` profile structure only (completed in Stage 3); `operator` profile (CR-18) |
| Related | ADR-001 (D15 one toolchain, two profiles; D16 restore; section 5 guardrails), ADR-003 (PC rules), ADR-011 (operator tier), baseline sections 6 and 7 |

> This ADR records a decision. It does not install anything and does not authorize workflows or settings changes.
> Detail and rationale are in `docs/cr/CR-2/design.md`; this record keeps the decision itself.

---

## 1. Context

- D15 requires one toolchain codebase with `builder` (workspace, Debian 13, x86-64) and `lab` (lab VM, Ubuntu 24.04, ARM64) profiles.
- The platform repository is public, the home directory of the workspace is ephemeral (D16), and the workspace must be rebuilt by script within 15 minutes.
- The supply-chain rule is: pin versions, verify checksums or signatures, never `curl | sh`, and provide both architectures for every download.
- ARM64 behavior can be tested only on ARM64 hosts. GitHub provides `ubuntu-24.04-arm` runners for public repositories. GitHub also documents `ubuntu-24.04-arm` as a standard runner for private repositories that uses the account's included minutes and is then charged (read 2026-11-19; not verified by a run). This platform does not use it (ADR-009).

## 2. Decision

1. **One manifest.** `toolchain/manifest.toml` is the single source of truth for tools, versions, install sources, per-architecture URLs and SHA-256 checksums, profile membership, and smoke tests. *Scope (CR-39 amendment): ADR-005's manifest is the single source for this platform's hosts (`builder`, `lab`, `operator`). The software template's CI manifest is owned by the template, uses the same schema and rules (exact versions, both architectures, SHA-256), and is not a host profile.*
2. **Format: TOML.** It is parsed with the Python standard library (`tomllib`) on both target operating systems and allows comments.
3. **Three install sources.**
   - `download`: release artifact, exact version, SHA-256 mandatory for `amd64` and `arm64`, signature verified in addition where upstream publishes one.
   - `apt`: package from the target release's signed archive, minimum version recorded, installed version reported by verification.
   - `pip`: hash-locked requirements installed with `--require-hashes` into a venv under the install prefix.
4. **One install engine.** `scripts/toolchain` (Python 3, standard library) performs `check`, `list`, `install`, and `verify`. It verifies the checksum before extraction, hardens extraction, installs atomically and idempotently, and supports `--dry-run`. Ansible, CI, and verification all call it; none re-implements download or verification.
5. **Install layout.** `/opt/ai-lab/tools/<name>/<version>/`, symlinks in `/opt/ai-lab/bin`, venv in `/opt/ai-lab/venv`, `PATH` set by a profile snippet. CI uses a temporary prefix.
6. **Ansible provides structure, not logic.** `ansible/builder.yml`, `ansible/lab.yml`, and `ansible/operator.yml` select roles; tool membership comes from the manifest `profiles` field. The allowed profile names are `builder`, `lab`, and `operator`. Ansible is bootstrapped from the Debian archive by `workspace/restore.sh` on the workspace, and from the Ubuntu archive by `scripts/operator/setup` on the operator machines.
7. **Verification levels.** L1 static (manifest check, Ansible syntax check, quality gate); L2 executed on GitHub runners (install and smoke on amd64 and arm64, `builder` apply in a pinned `debian:13` container); L3 on the real host (workspace restore test; lab VM in Stage 3).
8. **Changes to the manifest** are toolchain PRs (ADR-003, branch `toolchain/`), each recording the checksum and signature verification evidence.
9. **Builder content.** `gh`, `yq`, `rg`, `fd`, `jq`, `shellcheck`, `actionlint`, OpenTofu, `yamllint`, `pymarkdownlnt`, Python 3, `ansible-core`, `git`, `curl`, and `tmux`. A container runtime is deferred until a project needs it (O-10). Claude Code is not installed by this profile.
10. **Operator profile** (ADR-011, CR-18). The `operator` profile targets Ubuntu 24.04 (minimal), x86-64, on both operator machines, and is sized for 1 GB of memory. It is the Ansible playbook `ansible/operator.yml` in the layout of decision 6, with tool membership from the manifest `profiles` field. The OCI CLI is installed through the `pip` source into a hash-locked venv from `toolchain/python/operator.lock`. The CR-2 manifest check rule is extended from `builder` and `lab` to `operator`. Every `download` entry still carries both architectures and checksums (decision 3), even though both operator machines are x86-64. Its content (apt package list, roles, hardening) is specified in CR-18 design section 5 and built by the `operator-profile` implementation PR.

## 3. Alternatives considered

| Alternative | Outcome |
|---|---|
| Ansible `get_url` and `unarchive` as the only mechanism | Rejected: cannot be reused by CI and verification; two code paths per architecture. |
| Tool managers (mise, asdf, aqua, Nix) | Rejected: additional trust surface and bootstrap dependency. |
| YAML manifest | Rejected: needs PyYAML or `yq` before the first install. |
| Exact pins for apt packages | Rejected: they break on every security update of the Debian archive. Apt uses a minimum version (documented exception to the pin rule). |
| Shell installer script | Rejected: safe archive extraction and manifest validation are easier to implement and test in Python. |

## 4. Consequences

**Positive:**
- Both architectures are verified in CI before the lab VM exists.
- Every download has a reviewed checksum; a changed upstream artifact fails closed.
- One code path for workstation, CI, and lab VM.

**Negative:**
- Each tool upgrade is a PR that records two checksums.
- Python 3 is a prerequisite on every target (already present on Debian 13 and Ubuntu 24.04).
- Apt packages are not exactly pinned (documented exception).

**Residual risks:**
- **RR-S1-2.** An upstream artifact can be replaced after its checksum is recorded. Mitigation: pinned checksums in reviewed PRs, fail-closed mismatch, signatures where available.
- **RR-S1-3.** Archive packages are not exactly pinned. Mitigation: signed archive, versions reported by verification.

## 5. Resolved and remaining items

| ID | Item | Outcome |
|---|---|---|
| O5-1 | APT pinning policy | Resolved: minimum version, installed version reported. |
| O5-2 | Manifest format | Resolved: TOML. |
| O5-3 | Markdown linter; OpenTofu or Terraform | Resolved: `pymarkdownlnt`; OpenTofu. |
| O5-4 | Container runtime in `builder` | Resolved: deferred until needed. |
| O5-5 | `lab` profile content, including ARM64 and Ubuntu specifics | Remaining: Stage 3, by an amendment or successor design. |
| O5-6 | `operator` profile content and its fit in 1 GB of memory | Decided in structure by ADR-011. Remaining: verification VO-7 (CR-18) before the CR-16 design PR, and the content in the `operator-profile` PR. |

## 6. Acceptance criteria (verified in the implementation PRs)

- AC5-1: Every `download` entry has amd64 and arm64 artifacts with checksums that match upstream (CI on both architectures).
- AC5-2: A tampered artifact is rejected and leaves nothing installed.
- AC5-3: A second install run makes no change and downloads nothing.
- AC5-4: The `builder` profile applies in a Debian 13 container and passes verification; the same engine passes smoke tests on an ARM64 runner.
- AC5-5: No tool is installed by `curl | sh` or from an unpinned source.
- AC5-6: The `operator` profile applies twice in a pinned minimal Ubuntu 24.04 container, the second run reports no change, and `scripts/operator/setup --apply` also passes as root without sudo (CR-18 acceptance P-8).
