# AI Engineering Platform: Architecture Baseline v0.1

> **Superseded by [baseline v0.2](baseline-v0.2.md)** (CR-57, Proposed; takes effect when the CR-57 design PR is merged). This file is kept as history so that existing links survive. Its OCI components, decisions D2 to D7, D12, and CHG-002, ADR-004, ADR-006, ADR-007, and Stages 2 to 4 are superseded or withdrawn; read v0.2 for the current component map, decision index, and build sequence.

| Field | Value |
|---|---|
| Status | **Proposed**. Approved by your review and merge of the seed PR in `ai-lab-infrastructure` (ADR-003 approval rule). Superseded by baseline v0.2 (CR-57, Proposed) |
| Date | 2026-11-17 |
| Approval mode | P1 = Option 1: baseline approval, then incremental design PRs per component |
| Target location | `ai-lab-infrastructure/docs/architecture/baseline-v0.1.md` |
| Governs | `ai-lab-infrastructure`, `ai-software-template`, all application repositories created from the template |

## 1. What approving this baseline means

- **Accepted ADRs and decisions (Section 4) become binding** for all implementation work.
- **Components marked *Designed* (Section 3) may be implemented** through ADR-003 implementation PRs.
- **Components marked *Pending design* must first pass an approved design PR** (ADR-003, Class 3) before implementation starts.
- **Approval does not authorize consequential actions.** Creating OCI resources, IAM changes, creating repositories, changing visibility, installing software on a host, credential changes, and destructive resets each still need explicit authorization at the time (master prompt Section 20).

## 2. Mission and fixed constraints (unchanged)

- **Who and what.** One engineer builds a secure, reproducible, AI-assisted engineering platform. Claude Enterprise is used for architecture, Claude Code for implementation, and all development runs on remote Linux.
- **Zero cost.** OCI Always Free only (home region `uk-london-1`). GitHub Free only. No paid fallback.
- **No unsupported Claude access.** No Anthropic API key, no SSO automation, no session-token extraction, and no unattended or event-driven Claude execution (CHG-003).
- **No developer tools on Windows** (CHG-001). Exception: the OS-bundled OpenSSH client.
- **MCP only when useful**, under the admission policy (D11).
- **Human control.** You approve architecture, infrastructure changes, and merges. Auto-merge is never used.

## 3. Component map

| Component | Location | Responsibility | Governing record | Status |
|---|---|---|---|---|
| Windows client | Corporate laptop | Claude Desktop (chat with read-only GitHub Integration, Code tab), browser, OpenSSH keys and `~/.ssh/config` with `ProxyJump` | ADR-001 | Designed |
| Platform workspace | Corporate-assigned, x86-64 Debian 13, ephemeral home | Builds platform repos; `builder` toolchain profile; restore by script | ADR-001 (D15, D16) | Designed |
| OCI lab VM | `uk-london-1`, A1 2 OCPU / 12 GB, Ubuntu 24.04 ARM64 | Engineering lab for application projects; `lab` toolchain profile | ADR-001; ADR-004 | Pending design (ADR-004) |
| OCI bootstrap stack (Tier 0) | Resource Manager, started by you | Compartment, quotas, budget, IAM, dynamic group, Vault secret, federation trust | ADR-002; ADR-004 | Pending design (ADR-004) |
| OCI lab stack | Resource Manager | VCN, subnet, NSG, A1 instance, block volume, backup bucket | ADR-002; ADR-004 | Pending design (ADR-004) |
| Infrastructure pipeline | GitHub Actions (public infra repo) → OIDC → Resource Manager | Plan and apply with two human gates; private plans and state | ADR-002 | Designed, conditional on S2 |
| Toolchain manifest + Ansible roles | `ai-lab-infrastructure` | Pinned, verified tools for `builder` and `lab` profiles | ADR-001 (D15); ADR-005 | Pending design (ADR-005) |
| Workspace restore | `ai-lab-infrastructure/workspace/` | Rebuild the workspace after a home reset in about 15 minutes | ADR-001 (D16) | Designed |
| `labctl` | Lab VM (local commands) + Cloud Shell / Resource Manager (rebuild) | status, verify, backup, restore, reset workspace, reset toolchain, rebuild | ADR-006 | Pending design |
| Backup and DR | restic → Object Storage; boot-volume backups (≤ 5) | Protect sensitive and uncommitted data; tested recovery | ADR-007 | Pending design |
| PR workflow + `pr-contract` | All repositories | PR as unit of work, approval, and audit trail | ADR-003 | Designed |
| Software template | `ai-software-template` | CLAUDE.md, rules, Skills, CR and ADR templates, workflows, quality gate | ADR-008 | Pending design |
| Security and CI baseline | All repositories | Public-repo security features, Actions hardening, quality gates | ADR-009 | Pending design |
| Token optimization and metrics | Template + Skills | Context loading strategy, checkpoints, measurable metrics | ADR-010 | Pending design |
| GitHub configuration | Your account, machine account, two repos | Identities, settings, rulesets, token, chat GitHub Integration | ADR-001, ADR-003; `GITHUB-SETUP.md` | **Done** (Stage 0 completed) |

## 4. Decision index

| ID | Decision | Status | Record |
|---|---|---|---|
| CHG-001 | No developer tools on Windows; MCP when useful; GitHub via plugin (GitHub part superseded by D17) | Accepted | Discussion log |
| CHG-002 | Static OCI key fallback if federation is unavailable | Accepted, conditional | ADR-002 §7 |
| CHG-003 | PR-centric workflow; no automatic Claude responses | Accepted | ADR-003 |
| D1 | Claude Code via Claude Desktop SSH sessions; CLI in `tmux` as fallback | Accepted | ADR-001 |
| D2 | Terraform via OCI Resource Manager (HCL kept OpenTofu-compatible) | Accepted | ADR-002 |
| D3 | Ansible runs locally on each host | **Proposed** | ADR-005 |
| D4 | SSH from the last corporate hop's egress IP only; key-only; Bastion as break-glass | **Proposed**, pending O-9 | ADR-004 |
| D5 | 50 GB boot + ~100 GB block volume for `/srv/work` | **Proposed** | ADR-004 |
| D6 | Always-Free-only account + compartment quotas + plan allowlist + budget alert | **Proposed** | ADR-004 |
| D7 | Level-3 rebuild by boot-volume replacement | Pending design | ADR-006 |
| D8/D13 | Machine account for all AI GitHub access; you only approve and merge | Accepted | ADR-001 |
| D9 | Approval = your approving review + merge; design PR merge commit as evidence | Accepted | ADR-003 |
| D10 | Design artifacts committed to design branches by Claude Code (revised by D17) | Accepted | ADR-003, ADR-001 |
| D11 | MCP admission policy; v1 inventory = none | Accepted on seed PR merge | ADR-001 §5 |
| D12 | Control plane = GitHub Actions + Resource Manager; pipeline never manages IAM | Accepted | ADR-002 |
| D14 | Repositories under your personal account; machine account as collaborator | Accepted | ADR-001 |
| D15 | One toolchain codebase; `builder` and `lab` profiles; three test levels | Accepted | ADR-001 |
| D16 | Ephemeral workspace home; restore script; token re-entered by you | Accepted | ADR-001 |
| D17 | GitHub access per surface: chat = read-only GitHub Integration; Claude Code = `gh`; no Claude GitHub App; no GitHub MCP in v1 | Accepted on seed PR merge | ADR-001 |

## 5. Trust boundaries (summary of ADR-001)

- **B1.** AI-operated hosts cannot approve or merge, change repository settings, or change OCI infrastructure.
- **B3.** Only you, in the browser, approve, merge, apply infrastructure, change settings, or change IAM.
- **B2** (host-to-host isolation) is intentionally not provided. This is accepted risk RR-9.

## 6. Build sequence

Each stage starts only when its entry criteria are met. Work inside a stage follows ADR-003.

| Stage | Content | Entry criteria | Exit criteria |
|---|---|---|---|
| 0. GitHub foundation (**done**) | Accounts, repos, settings, rulesets, token, chat GitHub Integration | Baseline v0.1 approved | `GITHUB-SETUP.md` verification passed |
| 1. Workspace foundation | `CLAUDE.md` and `.claude/` for the infra repo; `workspace/restore.sh`; `builder` profile; quality-gate script; `pr-contract`; CI skeleton incl. ARM64 runner job | Stage 0 done; ADR-005 approved (builder part) | Workspace restorable (AC1-7); CI green on a test PR |
| 2. OCI seed | ADR-004; bootstrap stack; lab stack; cloud-init | Gate 0 Part 2.3 passed; O-9 known; D3–D6 approved | VM running in `uk-london-1`; SSH via `ProxyJump` works |
| 3. Lab VM | `lab` profile; managed settings; Spike S1; `labctl` status, verify, backup | Stage 2 done; ADR-006/007 approved for these parts | S1 passed; `labctl verify` green; first restic backup restored in a test |
| 4. Pipeline | Spike S2; ADR-002 workflows and environments | Stage 3 done | ADR-002 AC-1 to AC-7 passed |
| 5. Software template | Template structure, Skills, CR lifecycle, workflows | ADR-008/009/010 approved | Template validated by generating a throwaway repo in a dry run |
| 6. First application project | A real small project end-to-end on the lab VM | Stage 5 done | Full Class 3 CR completed under ADR-003 |
| 7. Resilience | `labctl` reset levels and rebuild, DR test, Scorecard, metrics review | Stage 6 done | Documented recovery test; metrics baseline recorded |

**Postponed (2026-11-19, approver).** Stages 2 to 4 (OCI seed, Lab VM, Pipeline) are postponed, and with them the CR-16 design (issue #16, PR #17), because no Oracle Always Free resources are available. Stage 5 (software template) proceeds first, on the platform workspace; its entry criteria are unchanged (ADR-008/009/010 approved). Stage 6 needs the lab VM and waits for Stages 2 to 4, and so does Stage 7. Work that needs a lab VM or the lab operator VM, such as CR-18 PR 6 (`acceptance`), waits until OCI resources are available again. Nothing already decided changes.

## 7. Designs still to be written (each as a design PR)

| ADR | Topic | Needed by stage |
|---|---|---|
| ADR-004 | OCI baseline: network, NSG, storage, quotas, budget, bootstrap and lab stack contents, Always Free eligibility checks | 2 |
| ADR-005 | Toolchain: manifest format, profiles, install sources, verification, smoke tests | 1 (builder), 3 (lab) |
| ADR-006 | `labctl` and the three reset levels, including rebuild under A1 capacity limits | 3 / 7 |
| ADR-007 | Backup and DR: data classes, restic design, retention, restore tests | 3 |
| ADR-008 | Software template: structure, CLAUDE.md, rules, Skills (incl. `address-review-feedback`), CR templates | 5 |
| ADR-009 | GitHub public-repo security matrix, Actions hardening, quality gates | 1 (CI skeleton), 5 |
| ADR-010 | Token optimization strategy and measurable metrics | 5 |

## 8. Master prompt deliverables (Section 18): coverage

| # | Deliverable | Covered by |
|---|---|---|
| 1–3 | Executive summary; requirements and constraints; decision log | This baseline §2–§4 |
| 4–6 | OCI architecture; Always Free and cost control; network and security | ADR-002, ADR-004 |
| 7 | Linux toolchain | ADR-001 (D15), ADR-005 |
| 8–9 | Repository structures | ADR-005/006 (infra), ADR-008 (template) |
| 10–11 | Claude Enterprise and Claude Code workflows | ADR-001, ADR-003 |
| 12 | Skills architecture | ADR-003 §8, ADR-008 |
| 13–15 | Governance; security matrix; Actions and quality gates | ADR-003, ADR-009 |
| 16 | Class 3 CR lifecycle | ADR-003 |
| 17 | Token optimization | ADR-010 |
| 18–19 | Lab reset; backup and DR | ADR-006, ADR-007 |
| 20–21 | Provisioning sequence; implementation roadmap | This baseline §6; ADR-004 |
| 22 | Acceptance criteria | Each ADR's acceptance criteria |
| 23–24 | Risks and assumptions; unresolved decisions | ADR residual-risk and open-item sections; §4 "Proposed" rows |
| 25 | Claude Code implementation hand-off | Stage 1 hand-off package (next deliverable) |

## 9. Open inputs

| ID | Item | Blocks |
|---|---|---|
| Gate 0 §2.3 | Current A1 usage (urgent over-allowance check) | Stage 2 |
| O-9 | Egress IP(s) of the last corporate hop and their stability | Stage 2 (D4) |
| O-4 | Spike S1 (ARM64 host, `ProxyJump`, passphrase key) | Stage 3 |
| O-8 | Minimum classic token scopes accepted by `gh` | Stage 0 |
| S2 | OIDC federation on Always Free | Stage 4 |
