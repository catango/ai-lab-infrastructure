# Documentation index

Open only the document and section relevant to the task. Decision status is tracked in the
[decision index](architecture/baseline-v0.2.md#4-decision-index) of the baseline; it is not repeated here.

## Architecture

| Document | Purpose | Status |
|---|---|---|
| [Architecture baseline v0.2](architecture/baseline-v0.2.md) | Constraints without OCI, component map (AI labs, operator machine, lab host), decision index, build sequence | Proposed (CR-57, approved by merge of design PR 58) |
| [Architecture baseline v0.1](architecture/baseline-v0.1.md) | Component map, decision index, build sequence, designs still to write | Superseded by baseline v0.2 (CR-57, Proposed); kept as history so links survive |

## Architecture decision records

| Document | Purpose | Status |
|---|---|---|
| [ADR-001](adr/ADR-001-trust-model-and-execution.md) | Trust model, execution hosts, credential placement, workspace restore, guardrails | Accepted; amended by ADR-011 (zones Z6 and Z7, credential rows); amended by CR-57 (Proposed): AI labs and the operator machine (ADR-012), zones Z1, Z6, Z8, lab setup and the token step replace the restore |
| [ADR-002](adr/ADR-002-infrastructure-deployment-pipeline.md) | Infrastructure deployment pipeline | Accepted, conditional on Spike S2; superseded by CR-57 (Proposed, effective on merge) |
| [ADR-003](adr/ADR-003-pr-centric-workflow.md) | PR-centric workflow, change classes, `pr-contract` | Accepted; rule PC-8 (CR-21) in force; amended by CR-39 (Proposed): application-repository contract, init PR, qualified references; amended by CR-57 follow-up R-1 (Proposed): PC-8 refers to the `operator_paths` key, AI lab wording, ADR-002 citations |
| [ADR-005](adr/ADR-005-toolchain.md) | Toolchain manifest, profiles, install sources | Accepted; amended by ADR-011 (the `operator` profile); scope amended by CR-39 (Proposed): the template's CI manifest is not a host profile; amended by CR-57 (Proposed): `lab` and `operator` profiles on Debian 13, amd64 only |
| [ADR-011](adr/ADR-011-operator-tier.md) | Operator tier: rules for credentialed and extended-permission scripts (dry run by default, release tags, prompted credentials, sanitised output, standard-library Python) | Accepted (2026-11-18, merge of the CR-18 design PR); amended by CR-57 (Proposed): the lab operator machine, OCI, alarms, lab access, and the Ubuntu profile dropped; ADR-012 describes the operator machine |
| [ADR-012](adr/ADR-012-host-model.md) | Host model: AI lab, operator machine, lab host (zones Z1, Z6, Z8); credential placement, accounts and keys, lab contract, operator contract, lab setup, token step, project toolchains | Proposed (CR-57; accepted by merge of design PR 58) |
| [ADR-008](adr/ADR-008-software-template.md) | Software template: structure, `CLAUDE.md`, rules, Skills, CR and ADR templates, template-sync, template gate and CI | Accepted (2026-11-19, merge of the CR-39 design PR #40) |
| [ADR-009](adr/ADR-009-security-and-ci-baseline.md) | Security and CI baseline: required checks, Actions hardening, repository security features on GitHub Free, fork PRs, evidence line, printed rulesets, gate-check catalogue | Accepted (2026-11-20, merge of the CR-43 design PR #44); amended ADR-001, ADR-003, ADR-005, and ADR-008; amended by CR-57 follow-up R-1 (Proposed): status line, decision 11 wording, `operator_endpoints` in decision 14, Related row |
| [ADR-010](adr/ADR-010-token-optimisation-and-metrics.md) | Token optimisation and metrics: size budgets and loading order, checkpoint format, concise CI output, review-loop cost, metrics tiers, baseline and regression | Accepted (2026-11-20, merge of the CR-45 design PR #46, decisions Q1 to Q15 applied; amends ADR-003 section 7 and ADR-008); status line corrected to Accepted by CR-57 follow-up R-1 (Proposed) |

ADR-004, ADR-006, and ADR-007 were listed in baseline v0.1 section 7 and were never written; baseline v0.2 withdraws them (CR-57, PA-38) and their numbers are not reused.

## Change requests

| CR | Summary | Status |
|---|---|---|
| [CR-2](cr/CR-2/README.md) | Stage 1 workspace foundation: toolchain, restore, quality gate, `pr-contract`, CI | Implemented in six PRs; closes with the last one. The timed reset test (AC1-7) is run by the approver |
| [CR-18](cr/CR-18/README.md) | Operator tier: two dedicated machines run reviewed scripts for credentialed and extended-permission tasks (facts, GitHub setup, acceptance tests) | Design approved (ADR-011 Accepted). PRs 1 to 5 merged (release v0.4.4); PR 7a (runbook and evidence table, #38) merged 2026-11-19. The lab operator VM, PR 6 (`acceptance`), and PR 7b wait for the OCI VMs, which are postponed (approver, 2026-11-19). Open until PR 7b merges. CR-57 (Proposed): to be closed by PR comment after the CR-57 design merges (Q6); its generic parts are carried by ADR-012 (operator contract) and the amended ADR-011 |
| [CR-21](cr/CR-21/README.md) | ADR-003 rule PC-8: operator script review section required for changes to operator code | Implemented (design PR #22 and implementation PR #24 merged, 2026-11-18) |
| [CR-39](cr/CR-39/README.md) | Software template design (ADR-008): structure, `CLAUDE.md`, rules, Skills, template-sync, template gate and CI, Stage 5 dry run | Design merged (PR #40, 2026-11-19) with the approver's decisions Q1 to Q14 applied. Also amends ADR-003 and ADR-005 |
| [CR-43](cr/CR-43/README.md) | Security and CI baseline design (ADR-009): required checks, Actions hardening, GitHub Free feature matrix, fork PRs, evidence line, rulesets, check catalogue, rule sharing | Design merged (PR #44, 2026-11-20); also amended ADR-001, ADR-003, ADR-005, and ADR-008. Nothing is implemented |
| [CR-45](cr/CR-45/README.md) | Token optimisation and metrics design (ADR-010): budgets, loading order, checkpoint format, CI output, review-loop cost, metrics tiers, baseline and regression | Design merged (PR #46, 2026-11-20) with the approver's decisions Q1 to Q15 applied. Also amends ADR-003 and ADR-008. Nothing is implemented |
| [CR-57](cr/CR-57/README.md) | Platform-agnostic AI workflow platform: preconfigured AI and integrated GitHub workflows, per-project AI labs reached through Claude Desktop SSH sessions, a separate operator machine, OCI discarded | Design revised with the approver's decisions of 2026-11-23 (rounds 1 to 5), for the architecture discussion. Adds ADR-012 and baseline v0.2, supersedes ADR-002, amends ADR-001, ADR-005, and ADR-011 (Proposed). The follow-up design PR R-1 (Proposed) carries the corrections of ADR-003, ADR-009, and ADR-010 that this design left unedited. Nothing is implemented |

## Operations

| Document | Purpose | Status |
|---|---|---|
| [Operator machines](operations/operator.md) | Runbook for the operator machine: platform operator VM, tokens T2 and T3, rollback | Platform operator VM sections active. Break-glass section not written |
| [GitHub setup](operations/github-setup.md) | Stage 0 runbook: accounts, repositories, rulesets, token; the scripted parts point at `github-setup`, the manual steps they replaced are in Appendix A | Executed (Stage 0 complete); shortened by CR-18 |
| [Workspace restore](operations/workspace-restore.md) | Runbook: rebuild the workspace after a home reset, token T1, verification, reset test | Active |

## Configuration and workflow files

| File | Purpose | Status |
|---|---|---|
| [CLAUDE.md](../CLAUDE.md) | Instructions for Claude Code in this repository | Active |
| [config/project.yaml](../config/project.yaml) | Approver and machine account logins, and the `architectures` with their runner labels (read from the base commit by rule PC-9), read by scripts | Active |
| [.claude/settings.json](../.claude/settings.json) | Claude Code project guardrails (ADR-001 section 5) | Active |
| [.github/PULL_REQUEST_TEMPLATE/](../.github/PULL_REQUEST_TEMPLATE/) | PR templates per type (ADR-003 rule PC-1) | Active |
| [.github/ISSUE_TEMPLATE/cr.md](../.github/ISSUE_TEMPLATE/cr.md) | Change request intake | Active |

## Tooling and automation (Stage 1)

| Path | Purpose | Status |
|---|---|---|
| [scripts/quality-gate.sh](../scripts/quality-gate.sh) | Quality gate: the checks in `scripts/checks/` (same entry point locally and in CI) | Active |
| [scripts/pr-contract](../scripts/pr-contract), [scripts/pr-body](../scripts/pr-body) | PR rules PC-1 to PC-9 (run from the base checkout in CI); PR body skeleton from a template | Active |
| [scripts/gate-evidence](../scripts/gate-evidence) | Runs the quality gate on a host and prints the one evidence line for an architecture with no runner (rule PC-9) | Active |
| [scripts/toolchain](../scripts/toolchain) | Install engine for the toolchain manifest: `check`, `list`, `install`, `verify` | Active |
| [toolchain/manifest.toml](../toolchain/manifest.toml) | Tools, exact versions, per-architecture URLs and checksums (ADR-005) | Active |
| [ansible/](../ansible/) | `lab` profile (Debian 13, x86-64; CR-57, called `builder` before), the shared SSH hardening role, the release check, and the managed settings; `builder.yml` is a legacy playbook for `workspace/restore.sh` until CR-57 PR 7 | Active |
| [workspace/](../workspace/) | `restore.sh`, `verify.sh`, repositories, user-level Claude Code configuration | Active |
| [scripts/operator/machine-profiles.toml](../scripts/operator/machine-profiles.toml) | Architecture, OS, memory, CPU, disk, and bandwidth of the operator machine, no identifiers (CR-18; created by the `operator-lib` PR) | Active. The platform operator VM entry holds architecture and OS only (its measured memory, CPU, and disk are not in the file yet) |
| [.github/workflows/](../.github/workflows/) | `ci.yml` (`quality-gate`, `toolchain-amd64`, `toolchain-arm64`, `host-profiles`, `operator-profile`) and `pr-contract.yml` | Active |
| [.github/dependabot.yml](../.github/dependabot.yml) | Weekly version updates for the pinned Actions and the Python lock | Active |
