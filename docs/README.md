# Documentation index

Open only the document and section relevant to the task. Decision status is tracked in the
[decision index](architecture/baseline-v0.1.md#4-decision-index) of the baseline; it is not repeated here.

## Architecture

| Document | Purpose | Status |
|---|---|---|
| [Architecture baseline v0.1](architecture/baseline-v0.1.md) | Component map, decision index, build sequence, designs still to write | Proposed (approved by merge of the seed PR) |

## Architecture decision records

| Document | Purpose | Status |
|---|---|---|
| [ADR-001](adr/ADR-001-trust-model-and-execution.md) | Trust model, execution hosts, credential placement, workspace restore, guardrails | Accepted; amended by ADR-011 (zones Z6 and Z7, credential rows) |
| [ADR-002](adr/ADR-002-infrastructure-deployment-pipeline.md) | Infrastructure deployment pipeline | Accepted, conditional on Spike S2 |
| [ADR-003](adr/ADR-003-pr-centric-workflow.md) | PR-centric workflow, change classes, `pr-contract` | Accepted; rule PC-8 (CR-21) in force; amended by CR-39 (Proposed): application-repository contract, init PR, qualified references |
| [ADR-005](adr/ADR-005-toolchain.md) | Toolchain manifest, profiles, install sources | Accepted; amended by ADR-011 (the `operator` profile); scope amended by CR-39 (Proposed): the template's CI manifest is not a host profile |
| [ADR-011](adr/ADR-011-operator-tier.md) | Operator tier: two dedicated machines (platform operator VM, lab operator VM) for credentialed and extended-permission scripts; amends ADR-001 credential placement | Accepted (2026-11-18, merge of the CR-18 design PR) |
| [ADR-008](adr/ADR-008-software-template.md) | Software template: structure, `CLAUDE.md`, rules, Skills, CR and ADR templates, template-sync, template gate and CI | Proposed (CR-39 design PR #40, decisions Q1 to Q14 applied, in review) |

ADR-004, ADR-006, ADR-007, ADR-009, and ADR-010 are listed in baseline section 7 and are written as design PRs.

## Change requests

| CR | Summary | Status |
|---|---|---|
| [CR-2](cr/CR-2/README.md) | Stage 1 workspace foundation: toolchain, restore, quality gate, `pr-contract`, CI | Implemented in six PRs; closes with the last one. The timed reset test (AC1-7) is run by the approver |
| [CR-18](cr/CR-18/README.md) | Operator tier: two dedicated machines run reviewed scripts for credentialed and extended-permission tasks (facts, GitHub setup, acceptance tests) | Design approved (ADR-011 Accepted). PRs 1 to 5 merged (release v0.4.4); PR 7a (runbook and evidence table) in review. The lab operator VM, PR 6 (`acceptance`), and PR 7b wait for the OCI VMs, which are postponed (approver, 2026-11-19). Open until PR 7b merges |
| [CR-21](cr/CR-21/README.md) | ADR-003 rule PC-8: operator script review section required for changes to operator code | Implemented (design PR #22 and implementation PR #24 merged, 2026-11-18) |
| [CR-39](cr/CR-39/README.md) | Software template design (ADR-008): structure, `CLAUDE.md`, rules, Skills, template-sync, template gate and CI, Stage 5 dry run | Design in review with the approver's decisions Q1 to Q14 applied. Also amends ADR-003 and ADR-005 |

## Operations

| Document | Purpose | Status |
|---|---|---|
| [Operator machines](operations/operator.md) | Runbook for the operator machines: platform operator VM, tokens T2 and T3, rollback | Platform operator VM sections active. Lab operator VM, `ssh` templates, and break-glass sections not written (PR 7b, OCI postponed) |
| [GitHub setup](operations/github-setup.md) | Stage 0 runbook: accounts, repositories, rulesets, token; the scripted parts point at `github-setup`, the manual steps they replaced are in Appendix A | Executed (Stage 0 complete); shortened by CR-18 |
| [Workspace restore](operations/workspace-restore.md) | Runbook: rebuild the workspace after a home reset, token T1, verification, reset test | Active |
| [Gate 0 audit](operations/gate-0-audit.md) | Pre-architecture audit checklist for the OCI tenancy; the OCI part is `facts --scope oci`, the manual steps it replaced are in Appendix A | Ready for execution; shortened by CR-18 |

## Configuration and workflow files

| File | Purpose | Status |
|---|---|---|
| [CLAUDE.md](../CLAUDE.md) | Instructions for Claude Code in this repository | Active |
| [config/project.yaml](../config/project.yaml) | Approver and machine account logins read by scripts | Active |
| [.claude/settings.json](../.claude/settings.json) | Claude Code project guardrails (ADR-001 section 5) | Active |
| [.github/PULL_REQUEST_TEMPLATE/](../.github/PULL_REQUEST_TEMPLATE/) | PR templates per type (ADR-003 rule PC-1) | Active |
| [.github/ISSUE_TEMPLATE/cr.md](../.github/ISSUE_TEMPLATE/cr.md) | Change request intake | Active |

## Tooling and automation (Stage 1)

| Path | Purpose | Status |
|---|---|---|
| [scripts/quality-gate.sh](../scripts/quality-gate.sh) | Quality gate: the checks in `scripts/checks/` (same entry point locally and in CI) | Active |
| [scripts/pr-contract](../scripts/pr-contract), [scripts/pr-body](../scripts/pr-body) | PR rules PC-1 to PC-8 (run from the base checkout in CI); PR body skeleton from a template | Active |
| [scripts/toolchain](../scripts/toolchain) | Install engine for the toolchain manifest: `check`, `list`, `install`, `verify` | Active |
| [toolchain/manifest.toml](../toolchain/manifest.toml) | Tools, exact versions, per-architecture URLs and checksums (ADR-005) | Active |
| [ansible/](../ansible/) | `builder` profile (Debian 13, x86-64) and the `lab` placeholder (Stage 3) | Active |
| [workspace/](../workspace/) | `restore.sh`, `verify.sh`, repositories, user-level Claude Code configuration | Active |
| [scripts/operator/machine-profiles.toml](../scripts/operator/machine-profiles.toml) | Architecture, OS, memory, CPU, disk, and bandwidth per operator machine, no identifiers (CR-18; created by the `operator-lib` PR) | Active. The platform operator VM entry holds architecture and OS only (its measured memory, CPU, and disk are not in the file yet); the lab operator VM entry holds design inputs and waits for the VM (OCI postponed) |
| [.github/workflows/](../.github/workflows/) | `ci.yml` (`quality-gate`, `toolchain-amd64`, `toolchain-arm64`, `builder-profile`) and `pr-contract.yml` | Active |
| [.github/dependabot.yml](../.github/dependabot.yml) | Weekly version updates for the pinned Actions and the Python lock | Active |
