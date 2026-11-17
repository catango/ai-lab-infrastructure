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

ADR-004 to ADR-010 are listed in baseline section 7 and are written as design PRs.

## Operations

| Document | Purpose | Status |
|---|---|---|
| [GitHub setup](operations/github-setup.md) | Stage 0 runbook: accounts, repositories, rulesets, token | Executed (Stage 0 complete) |
| [Gate 0 audit](operations/gate-0-audit.md) | Pre-architecture audit checklist for the OCI tenancy | Ready for execution |

## Configuration and workflow files

| File | Purpose | Status |
|---|---|---|
| [CLAUDE.md](../CLAUDE.md) | Instructions for Claude Code in this repository | Active |
| [config/project.yaml](../config/project.yaml) | Approver and machine account logins read by scripts | Active |
| [.claude/settings.json](../.claude/settings.json) | Claude Code project guardrails (ADR-001 section 5) | Active |
| [.github/PULL_REQUEST_TEMPLATE/](../.github/PULL_REQUEST_TEMPLATE/) | PR templates per type (ADR-003 rule PC-1) | Active |
| [.github/ISSUE_TEMPLATE/cr.md](../.github/ISSUE_TEMPLATE/cr.md) | Change request intake | Active |
