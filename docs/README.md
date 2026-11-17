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
| [ADR-001](adr/ADR-001-trust-model-and-execution.md) | Trust model, execution hosts, credential placement, workspace restore, guardrails | Accepted |
| [ADR-002](adr/ADR-002-infrastructure-deployment-pipeline.md) | Infrastructure deployment pipeline | Accepted, conditional on Spike S2 |
| [ADR-003](adr/ADR-003-pr-centric-workflow.md) | PR-centric workflow, change classes, `pr-contract` | Accepted |
| [ADR-005](adr/ADR-005-toolchain.md) | Toolchain manifest, profiles, install sources | Accepted by the merge of the CR-2 design PR (the file's own status line still reads Proposed; it changes only through a design PR) |

ADR-004 and ADR-006 to ADR-010 are listed in baseline section 7 and are written as design PRs.

## Change requests

| CR | Summary | Status |
|---|---|---|
| [CR-2](cr/CR-2/README.md) | Stage 1 workspace foundation: toolchain, restore, quality gate, `pr-contract`, CI | Implemented in six PRs; closes with the last one. The timed reset test (AC1-7) is run by the approver |

## Operations

| Document | Purpose | Status |
|---|---|---|
| [GitHub setup](operations/github-setup.md) | Stage 0 runbook: accounts, repositories, rulesets, token | Executed (Stage 0 complete) |
| [Workspace restore](operations/workspace-restore.md) | Runbook: rebuild the workspace after a home reset, token T1, verification, reset test | Active |
| [Gate 0 audit](operations/gate-0-audit.md) | Pre-architecture audit checklist for the OCI tenancy | Ready for execution |

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
| [scripts/pr-contract](../scripts/pr-contract), [scripts/pr-body](../scripts/pr-body) | PR rules PC-1 to PC-7 (run from the base checkout in CI); PR body skeleton from a template | Active |
| [scripts/toolchain](../scripts/toolchain) | Install engine for the toolchain manifest: `check`, `list`, `install`, `verify` | Active |
| [toolchain/manifest.toml](../toolchain/manifest.toml) | Tools, exact versions, per-architecture URLs and checksums (ADR-005) | Active |
| [ansible/](../ansible/) | `builder` profile (Debian 13, x86-64) and the `lab` placeholder (Stage 3) | Active |
| [workspace/](../workspace/) | `restore.sh`, `verify.sh`, repositories, user-level Claude Code configuration | Active |
| [.github/workflows/](../.github/workflows/) | `ci.yml` (`quality-gate`, `toolchain-amd64`, `toolchain-arm64`, `builder-profile`) and `pr-contract.yml` | Active |
| [.github/dependabot.yml](../.github/dependabot.yml) | Weekly version updates for the pinned Actions and the Python lock | Active |
