# Documentation index

Open only the document and section relevant to the task. Decision status is tracked in the
[decision index](architecture/baseline-v0.2.md#4-decision-index) of the baseline; the status cells here are short.

This repository was named `ai-lab-infrastructure` before the rename to `ai-lab-platform`. Accepted ADRs, approved CR records and
baseline v0.1 keep the old name as history; GitHub redirects the old URLs.

## Architecture

| Document | Purpose | Status |
|---|---|---|
| [Architecture baseline v0.2](architecture/baseline-v0.2.md) | Constraints, component map (AI labs, operator machine, lab host), decision index, build sequence | Accepted (CR-57, 2026-11-23) |
| [Architecture baseline v0.1](architecture/baseline-v0.1.md) | Earlier component map and decision index | Superseded by baseline v0.2; kept so links survive |

## Architecture decision records

| Document | Purpose | Status |
|---|---|---|
| [ADR-001](adr/ADR-001-trust-model-and-execution.md) | Trust model, execution hosts, credential placement, guardrails | Accepted; amended by ADR-011, CR-57 (ADR-012, lab setup and the token step), and CR-57 follow-up R-2 (user-level deny layer) |
| [ADR-002](adr/ADR-002-infrastructure-deployment-pipeline.md) | Infrastructure deployment pipeline | Superseded by CR-57 |
| [ADR-003](adr/ADR-003-pr-centric-workflow.md) | PR-centric workflow, change classes, `pr-contract` | Accepted; PC-8 reads `operator_paths` (CR-57 follow-up R-1) |
| [ADR-005](adr/ADR-005-toolchain.md) | Toolchain manifest, profiles, install sources | Accepted; `lab` and `operator` profiles on Debian 13, amd64 only (CR-57) |
| [ADR-008](adr/ADR-008-software-template.md) | Software template: structure, `CLAUDE.md`, rules, Skills, template-sync, template gate | Accepted (CR-39) |
| [ADR-009](adr/ADR-009-security-and-ci-baseline.md) | Security and CI baseline: required checks, Actions hardening, rulesets, check catalogue | Accepted (CR-43) |
| [ADR-010](adr/ADR-010-token-optimisation-and-metrics.md) | Token optimisation and metrics: size budgets, loading order, checkpoint format, metrics tiers | Accepted (CR-45) |
| [ADR-011](adr/ADR-011-operator-tier.md) | Operator tier: rules for credentialed and extended-permission scripts | Accepted; amended by CR-57 (the lab operator machine, cloud provisioning, and the Ubuntu profile dropped) |
| [ADR-012](adr/ADR-012-host-model.md) | Host model: AI lab, operator machine, lab host; credentials, accounts and keys, LC-1 to LC-16, OC-1 to OC-12, lab setup, token step, project toolchains | Accepted (CR-57); decision 14 and LC-16 by follow-up R-2 |

ADR-004, ADR-006, and ADR-007 were listed in baseline v0.1 and never written; baseline v0.2 withdraws them.

## Change requests

| CR | Summary | Status |
|---|---|---|
| [CR-2](cr/CR-2/README.md) | Stage 1 foundation: toolchain, quality gate, `pr-contract`, CI | Implemented; the timed reset test (AC1-7) is the approver's |
| [CR-18](cr/CR-18/README.md) | Operator tier: reviewed scripts for credentialed tasks (facts, GitHub setup) | PRs 1 to 5 and 7a merged; the rest is carried by ADR-012 and ADR-011; to be closed by the approver (CR-57 step U-1) |
| [CR-21](cr/CR-21/README.md) | ADR-003 rule PC-8: operator script review section | Implemented |
| [CR-39](cr/CR-39/README.md) | Software template design (ADR-008) | Design merged |
| [CR-43](cr/CR-43/README.md) | Security and CI baseline design (ADR-009) | Design merged; nothing implemented |
| [CR-45](cr/CR-45/README.md) | Token optimisation and metrics design (ADR-010) | Design merged; nothing implemented |
| [CR-57](cr/CR-57/README.md) | Platform-agnostic AI workflow platform: per-project AI labs reached through Claude Desktop SSH sessions, a separate operator machine, no cloud provisioning | Design merged (PR 58); implementation PRs 0 to 10 and 4a merged (PR 10 is #76; issue #57 closed), rename follow-up merged (#77, #78) |

## Operations

| Document | Purpose | Status |
|---|---|---|
| [AI host](operations/ai-host.md) | Hosts the AI user needs, the lab and operator contracts, the user-level deny layer (LC-16), the manual probe | Active |
| [AI lab runbook](operations/lab.md) | Lab setup, token step, lab check, project toolchains, what the PA-A38 check showed, pre-disposal | Active |
| [New project](operations/new-project.md) | Repository, AI lab, token step, `initialize-project`, operator scripts, allowlist audit, the two-prompt probe | Active |
| [Operator machine](operations/operator.md) | Operator configuration, projects, tokens T2 and T3, separation test, rollback | Active |
| [GitHub setup](operations/github-setup.md) | Stage 0 runbook: accounts, repositories, rulesets, token; scripted parts point at `github-setup`, replaced manual steps are in Appendix A | Executed; shortened by CR-18 |

## Configuration, workflow, and tooling

| Path | Purpose |
|---|---|
| [CLAUDE.md](../CLAUDE.md) | Instructions for Claude Code in this repository |
| [config/project.yaml](../config/project.yaml) | Logins, `architectures`, `operator_paths`, `operator_endpoints`; read by scripts and by `pr-contract` from the base commit |
| [.claude/settings.json](../.claude/settings.json) | Claude Code project guardrails (ADR-001 section 5) |
| [docs/PLATFORM.md](PLATFORM.md), [.claude/deny.platform.txt](../.claude/deny.platform.txt), [config/preset.yaml](../config/preset.yaml) | This platform's preset for the template (ADR-008 decision 14): the seeded platform rules, the seeded platform deny rules, and the preset configuration; Claude Code does not load them in this repository |
| [.github/PULL_REQUEST_TEMPLATE/](../.github/PULL_REQUEST_TEMPLATE/), [.github/ISSUE_TEMPLATE/cr.md](../.github/ISSUE_TEMPLATE/cr.md) | PR templates per type (ADR-003 PC-1); change request intake |
| [scripts/quality-gate.sh](../scripts/quality-gate.sh) | Quality gate: the checks in `scripts/checks/` (same entry point locally and in CI) |
| [scripts/pr-contract](../scripts/pr-contract), [scripts/pr-body](../scripts/pr-body) | PR rules PC-1 to PC-9; PR body skeleton from a template |
| [scripts/gate-evidence](../scripts/gate-evidence) | Prints the evidence line for an architecture with no runner (rule PC-9) |
| [scripts/toolchain](../scripts/toolchain), [toolchain/manifest.toml](../toolchain/manifest.toml) | Install engine (`check`, `list`, `install`, `verify`); tools, exact versions, URLs, checksums (ADR-005) |
| [ansible/](../ansible/) | The `lab` and `operator` profiles (Debian 13, x86-64), the shared SSH hardening role, the release check, managed settings, the deny layer, project toolchains |
| [workspace/claude-user/](../workspace/claude-user/) | User-level settings (the source of the managed settings), the required deny list, user-level instructions |
| [scripts/operator/](../scripts/operator/) | Operator scripts (`facts`, `github-setup`) and `machine-profiles.toml` (sizes of the operator machine, no identifiers) |
| [.github/workflows/](../.github/workflows/), [.github/dependabot.yml](../.github/dependabot.yml) | `ci.yml` and `pr-contract.yml`; weekly updates for the pinned Actions and the Python lock |
