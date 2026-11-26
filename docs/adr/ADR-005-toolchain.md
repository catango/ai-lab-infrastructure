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
| Amended by (CR-57) | CR-57 (design PR 58 for issue #57, merged 2026-11-23; approver's decisions of 2026-11-23, PA-24, PA-30, PA-31): decisions 6 and 10 describe the Ansible `lab` and `operator` profiles on Debian 13, run by the admin users (ADR-012); decision 3 requires artifacts for exactly the architectures listed in `config/project.yaml` (this repository: amd64 only; an artifact for an unlisted architecture is an error); decision 5 stays; decisions 1 (scope note), 7, 9 (as far as PA-31 needs), section 1, the consequences, AC5-1, AC5-4, and AC5-6 are updated. In effect since the merge of the CR-57 design PR (PR 58, 2026-11-23) |
| Scope | The `lab` profile (the CR-2 `builder` profile renamed, PA-31) and the `operator` profile (CR-18, retargeted to Debian 13), both installed by Ansible on Debian 13, x86-64, with one shared SSH hardening role |
| Related | ADR-001 (D15 one toolchain; D16; section 5 guardrails), ADR-003 (PC rules), ADR-011 (operator script rules), ADR-012 (host model), baseline v0.2 |

> This ADR records a decision. It does not install anything and does not authorize workflows or settings changes.
> Detail and rationale are in `docs/cr/CR-2/design.md`; this record keeps the decision itself.

---

## 1. Context

- D15 requires one toolchain codebase. Amended by CR-57: it has a `lab` profile (the AI lab, Debian 13, x86-64) and an `operator` profile (the operator machine, Debian 13, x86-64), both applied by Ansible and run by the admin users (ADR-012). This repository supports amd64 only (PA-30).
- The platform repository is public, an AI lab is disposable (D16), and lab setup, the token step, and the lab check must bring a fresh VM to a working lab within 15 minutes, excluding the time to type T1.
- The supply-chain rule is: pin versions, verify checksums or signatures, never `curl | sh`, and provide artifacts and checksums for exactly the architectures listed in `config/project.yaml`.
- The install engine and the manifest schema stay architecture-generic (ADR-008 decision 8); the engine's arm64 path is tested only by the template's CI (residual risk of PA-30). GitHub documents `ubuntu-24.04-arm` as a standard runner for private repositories that uses the account's included minutes and is then charged (read 2026-11-19; not verified by a run). This platform does not use it (ADR-009).

## 2. Decision

1. **One manifest.** `toolchain/manifest.toml` is the single source of truth for tools, versions, install sources, per-architecture URLs and SHA-256 checksums, profile membership, and smoke tests. *Scope (CR-39 amendment, updated by CR-57): ADR-005's manifest is the single source for this platform's hosts (`lab`, `operator`). The software template's CI manifest is owned by the template, uses the same schema and rules (exact versions, an artifact and SHA-256 per architecture), and is not a host profile.*
2. **Format: TOML.** It is parsed with the Python standard library (`tomllib`) on both target operating systems and allows comments.
3. **Three install sources.**
   - `download`: release artifact, exact version, SHA-256 mandatory for exactly the architectures listed in `config/project.yaml` (amended by CR-57; this repository: `amd64`; an artifact for an unlisted architecture is an error), signature verified in addition where upstream publishes one.
   - `apt`: package from the target release's signed archive, minimum version recorded, installed version reported by verification.
   - `pip`: hash-locked requirements installed with `--require-hashes` into a venv under the install prefix.
4. **One install engine.** `scripts/toolchain` (Python 3, standard library) performs `check`, `list`, `install`, and `verify`. It verifies the checksum before extraction, hardens extraction, installs atomically and idempotently, and supports `--dry-run`. Ansible, CI, and verification all call it; none re-implements download or verification.
5. **Install layout.** `/opt/ai-lab/tools/<name>/<version>/`, symlinks in `/opt/ai-lab/bin`, venv in `/opt/ai-lab/venv`, `PATH` set by a profile snippet. CI uses a temporary prefix.
6. **Ansible provides structure, not logic** (amended by CR-57). The lab profile and the operator profile select roles; tool membership comes from the manifest `profiles` field. The allowed profile names are `lab` and `operator`. Both profiles use one shared SSH hardening role (PA-31). Each is run by the matching admin user (the lab admin, the operator admin) from a clone the admin owns at a release tag, in check mode with diff by default (ADR-012 decisions 5 and 7). Ansible is bootstrapped from the Debian archive by the admin. The files `ansible/lab.yml` and `ansible/operator.yml` are the entry points; the CR-2 `builder` profile becomes the lab profile.
7. **Verification levels.** L1 static (manifest check, Ansible syntax check, quality gate); L2 executed on GitHub runners (install and smoke on amd64; CI applies the lab and operator profiles twice, the second run changing nothing, and once in dry run, the tree hash unchanged, then runs the token step fixtures and both checks, in a pinned `debian:13` container started with the two users and one key each, PA-28); L3 on the real host (lab setup on a fresh VM, then the timed run of AC1-7).
8. **Changes to the manifest** are toolchain PRs (ADR-003, branch `toolchain/`), each recording the checksum and signature verification evidence.
9. **Gate tools and base content** (the former "builder content", amended by CR-57 only as far as PA-31 and the removal of Terraform need): `gh`, `yq`, `rg`, `fd`, `jq`, `shellcheck`, `actionlint`, `yamllint`, `pymarkdownlnt`, Python 3, `ansible-core`, `git`, `curl`, and `tmux`; OpenTofu is removed. The full content of the lab profile is set by the lab profile PR. Claude Code is not installed by this profile.
10. **Operator profile** (ADR-011, CR-18; amended by CR-57). The `operator` profile targets Debian 13, x86-64, on the operator machine, within the limits of its machine-profile file. It is the Ansible playbook `ansible/operator.yml` in the layout of decision 6, with tool membership from the manifest `profiles` field and the shared SSH hardening role. The OCI CLI and its lock are removed. It configures the operator user without sudo, the output directories, and the per-project installation of operator scripts (ADR-012 decisions 7 and 12). The operator profile takes manifest membership for Python 3 and git only (OC-6) and installs no gate tools; the gate tools are the lab profile's. The manifest check rule applies to `lab` and `operator`.

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
- The architectures listed in `config/project.yaml` are verified in CI.
- Every download has a reviewed checksum; a changed upstream artifact fails closed.
- One code path for the AI lab, the operator machine, and CI.

**Negative:**
- Each tool upgrade is a PR that records a checksum per listed architecture.
- Python 3 is a prerequisite on every target (already present on Debian 13).
- Apt packages are not exactly pinned (documented exception).

**Residual risks:**
- **RR-S1-2.** An upstream artifact can be replaced after its checksum is recorded. Mitigation: pinned checksums in reviewed PRs, fail-closed mismatch, signatures where available.
- **RR-S1-3.** Archive packages are not exactly pinned. Mitigation: signed archive, versions reported by verification.

## 5. Resolved and remaining items

| ID | Item | Outcome |
|---|---|---|
| O5-1 | APT pinning policy | Resolved: minimum version, installed version reported. |
| O5-2 | Manifest format | Resolved: TOML. |
| O5-3 | Markdown linter; OpenTofu or Terraform | Resolved: `pymarkdownlnt`; OpenTofu. The OpenTofu choice is superseded by CR-57 (OpenTofu is removed from the manifest). |
| O5-4 | Container runtime in `builder` | Resolved: deferred until needed. |
| O5-5 | `lab` profile content | Resolved by CR-57 (PA-31): the CR-2 builder profile becomes the lab profile; its content is set by the lab profile PR. ARM64 and Ubuntu specifics are dropped. |
| O5-6 | `operator` profile content | Decided by CR-57 (PA-20, PA-31): Debian 13, shared SSH hardening role; content built by the operator profile PR. |

## 6. Acceptance criteria (verified in the implementation PRs)

- AC5-1: Every `download` entry has an artifact with a checksum that matches upstream for exactly the architectures listed in `config/project.yaml`, and none for an unlisted architecture (CI on the listed architectures).
- AC5-2: A tampered artifact is rejected and leaves nothing installed.
- AC5-3: A second install run makes no change and downloads nothing.
- AC5-4: The `lab` profile applies in a pinned Debian 13 container and passes verification (PA-28).
- AC5-5: No tool is installed by `curl | sh` or from an unpinned source.
- AC5-6: The `operator` profile applies twice in a pinned Debian 13 container, the second run reports no change, and the operator check passes afterwards (PA-28, PA-A21).
