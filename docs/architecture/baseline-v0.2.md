# AI Engineering Platform: Architecture Baseline v0.2

| Field | Value |
|---|---|
| Status | **Proposed**. Approved by the approver's review and merge of CR-57 design PR 58 (ADR-003 approval rule) |
| Date | 2026-11-23 |
| Replaces | [Baseline v0.1](baseline-v0.1.md), which stays as history with a "superseded by v0.2" banner so that existing links survive |
| Change request | CR-57 (issue #57), PA-38, PA-40 |
| Governs | `ai-lab-infrastructure`, `ai-software-template`, all application repositories created from the template |

## 1. What approving this baseline means

- **Accepted ADRs and decisions (section 4) become binding** for all implementation work.
- **Components marked *Designed* (section 3) may be implemented** through ADR-003 implementation PRs, in the order of the CR-57 plan.
- **Approval does not authorize consequential actions.** Creating repositories, changing visibility, installing software on a host, credential changes, and destructive resets each still need explicit authorization at the time.

## 2. Mission and fixed constraints

- **Who and what.** One engineer builds a secure, reproducible, AI-assisted engineering platform. Claude Enterprise is used for architecture, Claude Code for implementation, and all development runs on remote Linux.
- **Zero cost.** GitHub Free only. No paid fallback. No payment method on the personal account and budgets at $0 with usage stopped (ADR-009 decision 12). Machines are provided outside the platform (the AI labs, the operator machine, and the lab host).
- **No unsupported Claude access.** No Anthropic API key, no SSO automation, no session-token extraction, and no unattended or event-driven Claude execution (CHG-003).
- **No developer tools on Windows** (CHG-001). Exception: the OS-bundled OpenSSH client, which is outside the platform (ADR-012).
- **MCP only when useful**, under the admission policy (D11).
- **Human control.** You approve architecture, infrastructure changes, and merges. Auto-merge is never used.
- **Platform agnostic.** The platform is preconfigured AI and integrated GitHub workflows. Everything technology-specific belongs to the project (CR-57 PA-8).

## 3. Component map

| Component | Location | Responsibility | Governing record | Status |
|---|---|---|---|---|
| Windows client | Corporate laptop, outside the platform | Claude Desktop (chat with read-only GitHub Integration, Code tab, SSH sessions), browser, OpenSSH keys and `~/.ssh/config` with `ProxyJump` | ADR-001, ADR-012 | Designed |
| AI lab (one per project) | Disposable Debian 13 x86-64 VM on the lab host; AI user and lab admin | Develops one project's repositories; lab profile; managed settings; token step; lab check | ADR-001, ADR-012 | Designed (CR-57) |
| Operator machine | Long-lived Debian 13 x86-64 VM; operator user and operator admin | Runs reviewed operator scripts (`github-setup`, `facts`) per project from release tags; holds T2, T3, production credentials only during runs | ADR-011, ADR-012 | Designed (CR-57) |
| Lab host | Jump host and hypervisor of the AI labs, outside the platform | Carries the AI lab; full control of it | ADR-012 (zone Z8) | Outside the platform |
| Toolchain manifest and Ansible profiles | `ai-lab-infrastructure` | Pinned, verified tools; `lab` and `operator` profiles; amd64 only | ADR-005 (amended) | Designed (CR-57) |
| PR workflow and `pr-contract` | All repositories | PR as unit of work, approval, and audit trail | ADR-003 | Designed |
| Software template | `ai-software-template` | CLAUDE.md, rules, Skills, CR and ADR templates, workflows, quality gate | ADR-008 | Designed (implementation pending) |
| Security and CI baseline | All repositories | Public-repo security features, Actions hardening, quality gates | ADR-009 | Designed |
| Token optimisation and metrics | Template and Skills | Context loading, checkpoints, measurable metrics | ADR-010 | Proposed (CR-45) |
| GitHub configuration | Your account, machine account, repositories | Identities, settings, rulesets, token, chat GitHub Integration | ADR-001, ADR-003 | **Done** (Stage 0) |
| Anthropic | Claude Enterprise | Chat; inference for Claude Code sessions | ADR-001 | External |

## 4. Decision index

| ID | Decision | Status | Record |
|---|---|---|---|
| CHG-001 | No developer tools on Windows; MCP when useful; GitHub via plugin (GitHub part superseded by D17) | Accepted | Discussion log |
| CHG-002 | Static OCI key fallback if federation is unavailable | **Superseded** (CR-57) | ADR-002 section 7 |
| CHG-003 | PR-centric workflow; no automatic Claude responses | Accepted | ADR-003 |
| D1 | Claude Code via Claude Desktop SSH sessions; CLI in `tmux` as fallback | Accepted | ADR-001 |
| D2 | Terraform via OCI Resource Manager | **Superseded** (CR-57) | ADR-002 |
| D3 | Ansible runs locally on each host | **Reduced** (CR-57): the lab and operator profiles, run by the admin users | ADR-005 (amended), ADR-012 |
| D4 | SSH from the last corporate hop's egress IP only; Bastion as break-glass | **Superseded** (CR-57): egress is another project's; SSH hardening is ADR-012 | ADR-012 |
| D5 | 50 GB boot and ~100 GB block volume | **Superseded** (CR-57) | — |
| D6 | Always-Free-only account, quotas, allowlist, budget alert | **Superseded** (CR-57) | — |
| D7 | Level-3 rebuild by boot-volume replacement | **Superseded** (CR-57): an AI lab is rebuilt as a fresh VM | ADR-012 |
| D8/D13 | Machine account for all AI GitHub access; you only approve and merge | Accepted | ADR-001 |
| D9 | Approval = your approving review plus merge; design PR merge commit as evidence | Accepted | ADR-003 |
| D10 | Design artifacts committed to design branches by Claude Code (revised by D17) | Accepted | ADR-003, ADR-001 |
| D11 | MCP admission policy; v1 inventory = none | Accepted | ADR-001 section 5 |
| D12 | Control plane = GitHub Actions and Resource Manager | **Superseded** (CR-57) | ADR-002 |
| D14 | Repositories under your personal account; machine account as collaborator | Accepted | ADR-001 |
| D15 | One toolchain codebase; profiles; three test levels | **Reduced** (CR-57): `lab` and `operator` profiles, Debian 13, amd64 only | ADR-005 (amended) |
| D16 | Disposable home; restore script; token re-entered by you | **Reduced** (CR-57): lab setup, token step, lab check | ADR-001 (amended), ADR-012 |
| D17 | GitHub access per surface | Accepted | ADR-001 |
| ADR-012 | Host model: AI lab, operator machine, lab host (Z8), contracts | **Proposed** (CR-57; accepted by merge) | ADR-012 |

ADR-004, ADR-006, and ADR-007 are **withdrawn** in this baseline (PA-38); their numbers are not reused. ADR-002 is superseded and ADR-011 is amended (CR-57).

## 5. Trust boundaries (summary of ADR-001 and ADR-012)

- **B1.** AI hosts cannot approve, merge, change repository settings, or change infrastructure.
- **B3.** Only you, in the browser, approve, merge, and change settings; production and infrastructure changes happen only through reviewed operator scripts that you run on the operator machine.
- **B2** (lab-to-lab isolation) is intentionally not provided. This is accepted risk RR-9.

## 6. Build sequence

Each stage starts only when its entry criteria are met. Work inside a stage follows ADR-003.

| Stage | Content | Entry criteria | Exit criteria |
|---|---|---|---|
| 0. GitHub foundation (**done**) | Accounts, repos, settings, rulesets, token, chat GitHub Integration | Baseline v0.1 approved | `GITHUB-SETUP.md` verification passed |
| 1. Platform foundation (CR-2) | `CLAUDE.md`, quality gate, `pr-contract`, CI skeleton | Stage 0 done | Implemented in six PRs (CR-2); its restore part is replaced by CR-57 |
| CR-57 implementation | Steps 0 to 10 of `docs/cr/CR-57/implementation-plan.md`, in strict order, then the repository rename (the approver's, Q3) | CR-57 design merged | Plan checklist complete; amd64-only gate green; lab setup on a fresh VM ends with a working lab |
| 5. Software template | Template structure, Skills, CR lifecycle, workflows; the real run with this platform's preset | ADR-008, ADR-009, ADR-010 approved; CR-57 implemented; repository renamed | Template validated by a dry run and one real run (ADR-008 decision 12) |
| 6. First project on its own lab VM | A real small project end to end on its own AI lab | Stage 5 done; an AI lab provided | Full Class 3 CR completed under ADR-003 |
| 7. Timed rebuild test and metrics | A timed rebuild of an AI lab (AC1-7) and the metrics baseline (ADR-010) | Stage 6 done | Two separate items: a documented timed rebuild (AC1-7), and the metrics baseline recorded |

Stages 2 to 4 of baseline v0.1 (OCI seed, lab VM, pipeline) are dropped with ADR-002, ADR-004, ADR-006, and ADR-007.

## 7. Records

| ADR | Topic | Status |
|---|---|---|
| ADR-001 | Trust model, GitHub model, guardrails | Accepted; amended by CR-57 |
| ADR-002 | Infrastructure deployment pipeline | Superseded (CR-57) |
| ADR-003 | PR-centric workflow | Accepted |
| ADR-004, ADR-006, ADR-007 | OCI baseline, `labctl`, backup and disaster recovery | Withdrawn (PA-38) |
| ADR-005 | Toolchain | Accepted; amended by CR-57 |
| ADR-008 | Software template | Accepted |
| ADR-009 | Security and CI baseline | Accepted (its status line still reads Proposed; the follow-up design PR R-1 corrects it, `docs/cr/CR-57/design.md` O-12) |
| ADR-010 | Token optimisation and metrics | Proposed (CR-45) |
| ADR-011 | Rules for operator scripts | Accepted; amended by CR-57 |
| ADR-012 | Host model | Proposed (CR-57) |
