# CR-57 Design: a platform-agnostic AI workflow platform

Status: proposal for the architecture discussion. Design only: nothing is implemented, no setting changes. Decisions are PA-1 to PA-12; the questions for the approver are Q1 to Q6 (section 7).

## 1. Requirement and the decisions already taken

Requirement (user, 2026-11-23): simplify; discard all platform-related requirements; the project is platform agnostic and focuses on **preconfigured AI** and **integrated GitHub workflows**; it uses Claude Code and connects to any AI lab environment over SSH; everything technology-specific belongs to the project that the platform drives; **discard all OCI configuration and lab setup**.

Decided with the user in this session (2026-11-23):

| Input | Decision |
|---|---|
| SSH model | **Claude Desktop SSH sessions** (ADR-001 decision 2, baseline D1). The host and its key stay with the user. Claude Code does not open SSH to another host |
| CR-55 (cross-builds) | Withdrawn; cross-builds are project-owned. PR 56 and issue 55 are closed |
| OCI and operator work | Superseded through the amendment process of this PR (section 5) |
| Scoping | The defaults of the session's last message: ADR-002 and ADR-011 superseded in full; ADR-001 and ADR-005 amended in part; ADR-003, ADR-008, ADR-009, ADR-010 stay; merged code removed by implementation PRs after this design merges; this repository's `CLAUDE.md` rewritten |

## 2. Facts this design rests on

Read in `main` at `85360e8` and in the accepted records. Nothing was verified by a run.

- ADR-001 already says Claude Code runs only through Claude Desktop SSH sessions to hosts (decision 2) and fixes the GitHub model: machine account, one classic token T1 entered by the user in a plain SSH terminal, rulesets, deny rules (decisions 3, 4, 8, section 5, B1, B3, RR-9, RR-10). These do not depend on OCI.
- What is OCI- or lab-specific: ADR-001 decisions 1 and 5, zones Z2, Z4, Z6, Z7, the OCI rows of section 4, section 4a and decision 7 (workspace restore, D16); all of ADR-002 (Resource Manager pipeline) and ADR-011 (operator tier, CR-18); ADR-005 decisions 6, 9, 10 (Ansible, builder content, operator profile) and the `lab` and `operator` profiles. Baseline D2 to D7, D12, D15, and Stages 2 to 4 are OCI plans.
- ADR-003, ADR-008, ADR-009, and ADR-010 name no OCI resource. ADR-008 already makes the template platform-neutral, with platform values in a preset (`docs/PLATFORM.md`, `.claude/deny.platform.txt`, decision 14).
- Merged code and docs that belong to the discarded setup: `scripts/operator/` (22 files, including `github-setup` and `facts`), `tests/operator/`, `ansible/` (playbooks `builder`, `lab`, `operator`, roles, inventory), `docs/operations/operator.md` and `gate-0-audit.md`, the manifest entries of the `operator` profile and `toolchain/python/operator.lock`, the `operator-profile`, `operator-limits`, and `builder-profile` CI jobs, and `OPERATOR_PATHS` in `scripts/pr_contract/rules.py`, which is hardcoded to the two operator paths.
- `workspace/` holds `restore.sh`, `verify.sh`, `repos.txt`, `lib/`, and `claude-user/` (user-level `CLAUDE.md`, `settings.json`, `required-deny.txt`): the last is preconfigured AI and survives.
- The repository is public, so no host, address, user, or key appears in any file (CLAUDE.md conventions).

## 3. Decisions

**PA-1 Purpose.** The platform is two things: **preconfigured AI** (user-level and project Claude Code settings, rules, Skills, guardrails, the instruction-trust rule) and **integrated GitHub workflows** (the PR-centric workflow and `pr-contract`, the CI and security baseline, the software template, the machine-account model). It provisions no infrastructure and prescribes no technology stack.

**PA-2 An AI host is any SSH-reachable Linux machine the user provides.** The user owns the host, its address, and its key; the platform names none. The platform states only a **host contract** (section 4) in `docs/operations/ai-host.md`. A project's lab is one such host or a set of them; how a project reaches its own lab is documented in that project.

**PA-3 No onward SSH, no key access.** Claude Code runs on the host of its Desktop SSH session. It never opens SSH to another host, never reads `~/.ssh/`, and never handles a host credential. This replaces the repository rule "never try to reach the lab VM or an operator machine", which is removed together with those machines (nothing is left to name).

**PA-4 Trust model after the change.** Zones: the client (Z0), AI hosts (Z1, replacing the workspace and the lab VM), GitHub (Z3), Anthropic (Z5). Z2 (OCI lab VM), Z4 (OCI control plane), Z6 and Z7 (operator VMs) are removed. B1 (an AI host cannot approve, merge, or change settings) and B3 (only the approver can) stay without the OCI clauses. Machine account, token T1, rulesets, D17, RR-9, and RR-10 stay unchanged.

**PA-5 Guardrails.** ADR-001 section 5 stays, except the rows about `terraform`, `tofu`, and mutating `oci` verbs. Technology-specific deny rules move to the project's seeded `.claude/deny.platform.txt` (ADR-008 decision 6); the owned core list `.claude/required-deny.txt` stays technology-free. Placement of settings stays as in section 5 and RR-8.

**PA-6 Host bootstrap replaces the workspace restore.** D16 keeps its two rules: nothing durable lives only on a host (work is committed and pushed to its PR branch), and Claude Code configuration lives in repositories. The 15-minute rebuild of a whole workspace by Ansible is dropped. A script `scripts/bootstrap` installs the user-level Claude Code configuration (from `workspace/claude-user/`) and checks the host contract read-only; it installs no technology, has `--dry-run`, uses no `sudo`, and never prints a credential. Token T1 is still entered by the user in a plain SSH terminal (AC1-8).

**PA-7 Toolchain reduced to the gate.** ADR-005 stays for the tools this repository's own gate and CI need (shellcheck, yq, actionlint, pymarkdown, and so on): one manifest, three install sources, one install engine, both architectures with SHA-256 for every download (an AI host can be x86-64 or ARM64). The profiles `builder`, `lab`, `operator`, Ansible, and the container-based profile check go; the gate tools form one profile installed by `scripts/toolchain` into a user prefix. Project toolchains, cross-compilers, and runtimes belong to the project (CR-55 withdrawn).

**PA-8 Everything technology-specific is the project's.** Toolchain pins, build and deploy commands, runners and architectures, lab connection notes, and technology deny rules live in the project repository, through the template's existing seams: `docs/PROJECT.md`, `docs/PLATFORM.md`, `.claude/deny.platform.txt`, the CI manifest, and `config/project.yaml` (ADR-008 decisions 1, 6, 8, 14). This repository's preset for itself loses its OCI and operator content.

**PA-9 ADR-002 and ADR-011 are superseded in full; CR-18 is withdrawn.** ADR-011's amendments of ADR-001 and ADR-005 fall with it and are replaced by PA-4 to PA-7. The OCI seed (issue #16, PR #17) is closed when this design merges (Q6). Baseline v0.1 is replaced by v0.2 (Q4): the decision index marks D2 to D7, D12, D15 (profiles), and D16 (restore) superseded or reduced, and Stages 2 to 4 are dropped; Stage 5 (the template) is the next stage.

**PA-10 Rules that stay generic.** ADR-003 is unchanged, including PC-8 (review section for operator-class code) and the template's `operator-contract`: with no operator paths they are inactive, and a project with credentialed scripts can use them (ADR-008 decision 11). The hardcoded `OPERATOR_PATHS` of this repository becomes the configured, empty value in the removal PR (Q2).

**PA-11 Order of removal.** The repository `CLAUDE.md` keeps its operator and OCI rules until the PR that removes the matching code, so no rule is dropped before its subject is gone (the removal order of the plan). Required check names (`pr-contract`, `quality-gate`) do not change, so no ruleset edit is needed.

**PA-12 Name and role.** The repository keeps its name and role as the source of the platform's records, `pr-contract`, the generic gate checks (seeded into the template), and the user-level AI configuration. The template stays a separate repository. A rename is a repository setting for the approver (Q3); no file hardcodes the name, because values come from `config/project.yaml`.

## 4. The host contract (PA-2)

The platform asks of an AI host only this; every item is checked read-only by `scripts/bootstrap`.

| ID | Requirement |
|---|---|
| HC-1 | Linux, reachable by Claude Desktop over SSH, which deploys the Claude Code engine under the user's home (ADR-001 context) |
| HC-2 | `git`, `gh`, `bash`, and Python 3 (standard library only for the platform's scripts) |
| HC-3 | Network access to GitHub and Anthropic; nothing else is required by the platform |
| HC-4 | The machine-account token T1 is entered by the user in a plain SSH terminal, never in a Claude session |
| HC-5 | The Claude Code guardrails of ADR-001 section 5 are present (managed settings if the host owner allows them, else user and project settings) |
| HC-6 | No cloud or infrastructure credential is needed by the platform; a project that needs one documents it itself |

## 5. Amendments and supersession (the process of this PR)

An accepted record changes only by a header entry that takes effect when this design PR is merged (CR-39, CR-43 process). This PR adds that entry, marked Proposed, to ADR-001, ADR-002, ADR-005, and ADR-011. The **body text** is committed in this PR only after the approver's decisions arrive as a review by the approver account, as CR-43 did with Q21; until then the table is the intended text. ADR-003, ADR-008, ADR-009, and ADR-010 are not edited.

| Record | Intended change |
|---|---|
| [ADR-001](../../adr/ADR-001-trust-model-and-execution.md) | Amended. Decision 1: two named hosts become AI hosts (PA-2). Decision 5 removed. Decision 7 (D16): restore becomes bootstrap (PA-6). Section 3: Z2, Z4, Z6, Z7 removed, Z1 generalised. Section 4: OCI and operator credential rows removed. Section 4a replaced. Section 5: `terraform`, `tofu`, and `oci` rows removed (PA-5). B1 and B3 lose the OCI clauses. ADR-001 gains PA-3. Decisions 2, 3, 4, 6, 8 and RR-8 to RR-10 keep their text |
| [ADR-002](../../adr/ADR-002-infrastructure-deployment-pipeline.md) | Superseded in full |
| [ADR-005](../../adr/ADR-005-toolchain.md) | Amended. Decision 6 (Ansible), decision 9 (builder content), decision 10 (operator profile), and the `lab` profile are superseded; decisions 1 to 5, 7, 8 stay, read with one gate profile (PA-7). Context: the lab VM line is removed |
| [ADR-011](../../adr/ADR-011-operator-tier.md) | Superseded in full |

## 6. Alternatives considered

| Alternative | Outcome | Reason |
|---|---|---|
| Keep the operator tier for GitHub-only tasks | Not chosen (Q1) | The tier exists for OCI credentials; GitHub settings stay the approver's manual list (ADR-009 decision 13) |
| Claude Code opens SSH to lab hosts itself | Rejected (user) | Reverses the key and host rules and needs a new trust ADR |
| Merge this repository and the template | Not chosen | The template is a generated payload with its own release tags; PA-12 keeps them apart |
| Keep Ansible for host setup | Rejected | It is platform and OS specific; the host contract plus a read-only check is enough |
| Delete merged code in the design PR | Rejected | PC-4: a design PR changes `docs/` only, and class 3 implementation follows the merge |
| Rename the repository now | Deferred (Q3) | A repository setting; names come from configuration |

## 7. Questions for the approver

Each has a recommended default that the criteria and the plan assume until the review says otherwise.

| ID | Question | Recommended default |
|---|---|---|
| Q1 | The GitHub-scope tooling (`github-setup`, `facts` for GitHub, `github-desired-state.toml`) runs only on the operator machines. Keep it? | Retire it with the operator tier. The approver's manual list (ADR-009 decision 13, the Stage 0 runbook) stays. CR-43 PR 6 is re-scoped to documentation only |
| Q2 | PC-8 and `operator-contract`: keep as generic rules, inactive with no operator paths? | Keep; make `OPERATOR_PATHS` configuration with an empty value here |
| Q3 | Rename the repository? | Keep the name for now; the approver may rename later as a setting |
| Q4 | Replace baseline v0.1 with a short v0.2 in a follow-up PR? | Yes (plan PR 6) |
| Q5 | Is the host contract (section 4) the right minimum, and is a Python 3 requirement acceptable? | Yes; Python 3 is already needed by `pr-contract` and the gate |
| Q6 | Close issue #16 and PR #17 (OCI seed) when this design merges? | Yes, by a PR comment, not before the design merges |

## 8. Risks and what stays open

- **RR-P1.** Removing the operator tier removes the only scripted path for approver-run GitHub setup; settings drift becomes a manual check. Mitigation: the ordered list of ADR-009 decision 13, kept in the runbook (Q1).
- **RR-P2.** An AI host is no longer a known, provisioned machine, so guardrail strength depends on the host owner (RR-8 grows). Mitigation: the host contract, `scripts/bootstrap` checks, rulesets on public repositories, `forbidden-api`, and the approver's review remain the authority.
- **RR-P3.** Deleting code in several PRs can leave a half-state. Mitigation: the removal order of the plan; the aggregate `quality-gate` is green after each PR.
- Not verified: how much of `tests/quality-gate` and the CI jobs refer to operator or lab content (the plan's first PR inventories it); whether any merged document outside the list above names OCI; the template repository's current preset; baseline sections beyond the decision index (not read).
