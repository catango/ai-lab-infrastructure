# CR-57 Design: a platform-agnostic AI workflow platform

Status: revised with the approver's decisions (review of the approver account on design PR 58, submitted 2026-11-23T18:27:31Z). Design only: nothing is implemented, no setting changes. Decisions are PA-1 to PA-46 (section 4); the answers to the former questions Q1 to Q6 are in section 7; points the review leaves open are in section 11. The earlier default answers of the first draft are replaced and are not repeated.

## 1. Requirement and the decisions already taken

Requirement (user, 2026-11-23): simplify; discard all platform-related requirements; the project is platform agnostic and focuses on **preconfigured AI** and **integrated GitHub workflows**; it uses Claude Code and connects to an AI lab environment over SSH; everything technology-specific belongs to the project that the platform drives; **discard all OCI configuration**.

| Input | Decision |
|---|---|
| SSH model | **Claude Desktop SSH sessions** (ADR-001 decision 2, baseline D1): Claude Desktop on the Windows client opens SSH sessions to the AI lab and Claude Code runs there as the AI user. No local Claude Code session on Windows. Claude Code opens no onward SSH |
| CR-55 (cross-builds) | Withdrawn; cross-builds are project-owned. PR 56 and issue 55 are closed |
| Approver's decisions | The review named above. It replaces the default answers of the first draft, adds PA-13 to PA-46, ADR-012, the risks of section 9, and the acceptance changes. Only that review is used; a second review of the same day (a revision plan) is not (user's choice) |
| Process | ADR and baseline bodies are edited in this PR (section 6), as CR-43 did after its review. Merged code is removed by implementation PRs after this design merges (PC-4) |

## 2. Givens (approver)

G-1 Claude Desktop on the Windows client opens SSH sessions to the AI lab; Claude Code runs there as the AI user; the client may also hold SSH access to the operator machine; no local Claude Code on Windows. G-2 AI lab: Debian 13, x86-64; the AI user is configured, has a writable home, basic packages, and no sudo; a separate non-AI lab admin has sudo; the AI lab may reach project-specific resources configured by the project. G-3 Operator machine: a fresh Debian 13 x86-64 VM with internet access, provided outside the platform, with the operator user (no sudo; runs scripts that gather facts and apply changes; may reach production environments) and the operator admin (sudo) reachable over SSH. G-4 The operator machine is never an AI workspace. G-5 The platform names no host, address, user, or key. G-6 The AI lab is a VM hosted on the jump host (the lab host) and reached through it by ProxyJump; the lab host is outside the platform and is not the operator machine. G-7 Configuration scripts run only on the AI lab and the operator machine. G-8 The Windows SSH client is outside the platform. G-9 Egress design and filtering come from another project; SSH hardening of both machines is a platform requirement. G-10 The lab admin applies all AI lab configuration; the operator admin applies all operator configuration; the AI user and the operator user apply none. G-13 Each AI lab is a disposable VM for exactly one project (this repository counts as one); provisioning is outside the platform; the platform starts from a given Debian 13 x86-64 VM with the AI user and the lab admin reachable over SSH. G-14 Each managed account's public key is provisioned with the VM; any additional key fails the setup; no fingerprint confirmation is required. G-15 The operator machine is not reachable from the lab host and so not from the AI lab; the AI lab cannot reach services on the lab host; the hosts the AI user needs (PA-18), GitHub, and the environments the operator scripts need are reachable; the AI lab's SSH host keys are new on every rebuild. G-16 One operator machine serves this repository and every project. G-17 The operator machine is long-lived; a rebuild is a fresh VM plus the operator configuration; it holds no persisted credential (OC-4), so a rebuild loses only the output directories. G-18 Provisioning destroys an AI lab's disk when the lab is discarded (confirmed).

G-11 and G-12 are not in the review (discarded items); the numbers are not reused.

## 3. Facts this design rests on

Read in `main` at `85360e8` and in the accepted records. Nothing was verified by a run.

- ADR-001 already says Claude Code runs only through Claude Desktop SSH sessions (decision 2) and fixes the GitHub model: machine account, classic token T1 entered by the user in a plain SSH terminal, rulesets, deny rules (decisions 3, 4, 8, section 5, B1, B3, RR-9, RR-10).
- OCI- or lab-specific text: ADR-001 decisions 1 and 5, zones Z2, Z4, Z7, the OCI rows of section 4, section 4a and decision 7 (workspace restore, D16); all of ADR-002 (Resource Manager pipeline); ADR-011 decisions 1, 4, 5, 8, 10 to 17 in their OCI and lab-operator parts; ADR-005 decisions 6, 9, 10 and the `lab` placeholder. ADR-002 and baseline D2 and D12 are **Accepted** (ADR-002 conditional on Spike S2); D3 to D7 are Proposed or Pending design. Baseline Stages 2 to 4 are OCI plans and are postponed since 2026-11-19.
- ADR-003 names OCI or ADR-002 in lines 11, 14, 27, 48, 82, 126, 164 (the "Infra PR" row, "Claude Code (Desktop SSH session on the OCI VM...)", RR-5). ADR-003 is not edited (PA-A2); the interactions are listed in section 10. ADR-008, ADR-009, and ADR-010 name no OCI resource; ADR-008 already makes the template platform-neutral with platform values in a preset (decision 14), but `docs/PLATFORM.md` does not exist on `main` and the template repository holds only a README and a licence at the time of this revision: the preset is not built yet.
- Code and documents of the discarded parts: the OCI scope of `facts` (`scripts/operator/lib/operator_lib/ocifacts.py`), `acceptance`, the lab operator VM entries of `scripts/operator/machine-profiles.toml`, `toolchain/python/operator.in` and `operator.lock` (OCI CLI), the `oci-cli` and `opentofu` manifest entries, `docs/operations/gate-0-audit.md`, `workspace/restore.sh`, `verify.sh`, `workspace/lib/`, `workspace/repos.txt`, `tests/workspace/`, the Ubuntu operator profile (`ansible/operator.yml`, roles `operator_*`) and `scripts/operator/setup`. What stays under Q1 and Q2: `scripts/operator/github-setup`, `facts` with host and GitHub scope, `github-desired-state.toml`, PC-8, `operator-contract`.
- `config/project.yaml` has `architectures` (amd64, arm64) but no `operator_paths` key; PC-8 reads the hardcoded `OPERATOR_PREFIXES`, `OPERATOR_PATHS` (`scripts/pr_contract/rules.py:24,25`), `MANIFEST_PATHS` (line 32), and counts deleted paths (line 147 region); four PR templates repeat the paths in a comment. ADR-003 (as amended by CR-39) and ADR-009 decision 14 say the paths come from configuration read from the base commit.
- Checks that hard-code removed jobs or content: `tests/ci/test_required_aggregate.py:18` (`EXPECTED_NEEDS`), `tests/quality-gate/run.sh:278,601`, `tests/quality-gate/catalogue.tsv:22-23` (`ansible`, `operator-contract`), `tests/toolchain/test_operator_profile.py`, `tests/ansible/test_operator_profile.py`, `PROFILES` in `scripts/toolchain_engine/manifest.py:12`. Removing the operator and OCI documents breaks the `links` check at the rows of `docs/README.md` (operator, restore, gate 0 audit, machine profiles), `docs/operations/gate-0-audit.md`, `docs/operations/operator.md:201,211`, and `docs/operations/github-setup.md:41,256` unless the same PR edits them.
- Files that name the removed content and need an owner PR: `README.md:2`, `.gitignore:1-9` (Terraform state patterns), `.claude/settings.json:59-72`, `workspace/claude-user/settings.json`, `workspace/claude-user/required-deny.txt:55-68` with the drift test `tests/workspace/run.sh:391-393`, and `CLAUDE.md` lines 3, 8, 14, 15, 16, 34, 49, 54. The AC1-8 token tests are at `tests/workspace/run.sh:383-393`.
- The OCID detector in `scripts/checks/public-repo-hygiene.sh:13,83` and its fixture at `tests/quality-gate/run.sh:126` are legitimate generic content.
- The repository is public: no host, address, user, or key appears in any file (CLAUDE.md conventions). Public service names (PA-18) are not identifiers.

## 4. Decisions

PA-1 to PA-12 are the first draft's decisions as the review changes them; PA-13 to PA-46 are the review's. The numbers PA-27, PA-29, PA-32, PA-33, and PA-35 are not in the review (discarded) and are not reused.

**PA-1 Purpose.** The platform is two things: **preconfigured AI** (user-level and project Claude Code settings, rules, Skills, guardrails, the instruction-trust rule) and **integrated GitHub workflows** (the PR-centric workflow and `pr-contract`, the CI and security baseline, the software template, the machine-account model). It also provides the lab setup and the operator contract (ADR-012). It provisions no infrastructure and prescribes no technology stack.

**PA-2 An AI host is one project's disposable AI lab** per G-2 and G-13 that meets the lab contract (PA-15). The user owns the VM's provisioning, its addresses, and its keys; the platform names none.

**PA-3 Replaced by PA-19.** (The first draft's rule that Claude Code opens no onward SSH and never reads `~/.ssh/` is restated and enforced in PA-19.)

**PA-4 Trust zones.** Z0 (Windows client), Z1 (AI lab: AI user and lab admin), Z3 (GitHub), Z5 (Anthropic), Z6 (operator machine: operator user and operator admin), Z8 (lab host, outside the platform). Z2, Z4, and Z7 are removed. Z1, Z6, and Z8 are detailed in ADR-012. B1 is generalised: AI hosts cannot approve, merge, change settings, or change infrastructure. B3 keeps the operator clause, generalised. The T2 and T3 rows stay, on Z6.

**PA-5 Guardrails.** On the AI lab the guardrails live in managed settings only. RR-8 is restated as: a user or repository setting can tighten but never relax the managed settings. The existing generic infrastructure-apply deny entries (`terraform`, `tofu`, `oci`) stay in the core list. The plan names the PR that moves them into managed settings (implementation step 2).

**PA-6 Lab setup and the token step replace the workspace restore.** D16 keeps its two rules (nothing durable lives only on a host; Claude Code configuration lives in repositories). AC1-7 becomes a timed run from VM handover (lab setup, token step, lab check) with a target of 15 minutes, excluding the time to type T1.

**PA-7 Toolchain.** The gate tools are installed by lab setup; ADR-005 is amended per PA-24.

**PA-8 Everything technology-specific is the project's.** Project resources reach the AI lab through the network project and PA-13; production work runs on the operator machine. Toolchain pins, build and deploy commands, lab connection notes, and technology deny rules live in the project repository through the template's seams (`docs/PROJECT.md`, `docs/PLATFORM.md`, `.claude/deny.platform.txt`, the CI manifest, `config/project.yaml`; ADR-008 decisions 1, 6, 8, 14).

**PA-9 ADR-002 is superseded; ADR-011 is amended (PA-23); ADR-012 is added (PA-46); CR-18 is closed (Q6).** The decision index also marks CHG-002 superseded. ADR-001 and ADR-005 are amended. Baseline v0.2 (Q4, PA-38, PA-40) marks CHG-002, D2 to D7, D12, D15, and D16 superseded or reduced.

**PA-10 PC-8 is active here**, with the paths of Q2.

**PA-11 Order of removal** (unchanged from the first draft). The repository `CLAUDE.md` keeps a rule until the PR that removes its subject; the aggregate `quality-gate` is green after each PR; required check names (`pr-contract`, `quality-gate`) do not change, so no ruleset edit is needed. PA-26 makes the order strict.

**PA-12 Name and role.** The repository keeps its role as the source of the platform's records, `pr-contract`, the generic gate checks, and the user-level AI configuration; the template stays separate. No code hardcodes the repository name (values come from `config/project.yaml`). The repository is renamed per Q3.

**PA-13 Credential placement.** The AI lab holds T1 and project-scoped non-production credentials recorded in the project's PROJECT.md (PA-43). Production and infrastructure-changing credentials, T2, and T3 exist only on the operator machine, used by reviewed scripts from a release tag, prompted or short-lived. No credential of the personal account is on the AI lab. The lab admin and the operator admin hold no credentials.

**PA-14 Accounts and keys, enforced on the servers.** Four accounts (AI user, lab admin, operator user, operator admin), each with its own key; no key is shared between accounts on a machine (checked). The lab admin, the operator user, and the operator admin use sk-ssh-ed25519 keys with verify-required if the Windows client supports them, otherwise passphrase-protected file keys. The AI user's key has a passphrase if Claude Desktop can use one, otherwise none (RR-P6). The lab setup PR records which applies.

**PA-15 Lab contract** LC-1 to LC-15 (ADR-012 section 4; LC-5 is not defined). If a Claude Desktop session on a set-up lab needs a forwarding or key permission beyond LC-11 and LC-13, only that named permission is added, with the reason recorded in the PR.

**PA-16 Lab setup** is the Ansible lab profile (PA-31), run by the lab admin from a clone the admin owns at a release tag; dry run by default (check mode with diff); idempotent. On a fresh VM it accepts the one provisioned key of the AI user and of the lab admin, and fails when a managed account has no key or more than one, a key is shared between accounts, root or any other account has a key, the AI user's `~/.ssh` holds a private key, or `AuthorizedKeysCommand`, `TrustedUserCAKeys`, or `AuthorizedPrincipalsFile` is set. It applies: archive prerequisites; the gate tools into `/opt/ai-lab`; root-owned managed settings and a managed CLAUDE.md carrying the content of `workspace/claude-user/` (merged, never replaced); the system-wide git identity; the provisioned keys copied to the root-owned authorized-keys location, with sshd switched only after a second login with each account is confirmed while the current session stays open; LC-13; unattended security updates; project toolchains and package lists (PA-34); and the root-owned token step and lab check. It prints the host key fingerprints for information, removes nothing, writes nothing into a user's home, and never executes from a path the AI user can write.

**PA-17 What the user runs on the AI lab.** Logged in as the AI user in a plain SSH terminal, only the root-owned token step (T1 login; refuses without a TTY or inside a Claude Code session) and the read-only lab check.

**PA-18 Hosts the AI user needs** (input for the network project; the AI host document lists them): `api.anthropic.com`, `platform.claude.com`, `claude.ai`, `github.com`, `api.github.com`, `code.claude.com`, and `downloads.claude.ai` only if the lab fetches the Claude Code engine itself (the lab setup PR records which applies). Managed settings disable claude.ai MCP connectors, nonessential traffic, and artifacts.

**PA-19 No onward SSH, no key access (PA-3 restated).** (a) Deny rules for the SSH client family and Read/Edit deny on `~/.ssh/**`; (b) the LC-6 checks; (c) LC-11 and LC-13 on the server; (d) Claude Code never reaches the operator machine, the lab admin account, or the lab host. This replaces the repository rule "never try to reach the lab VM", which goes with the rewrite of `CLAUDE.md` (plan step 9).

**PA-20 Operator configuration** is the Ansible operator profile (PA-31), run by the operator admin from a clone the admin owns at a release tag; dry run by default; idempotent. On a fresh VM it applies the key rules of PA-16 to the operator user and the operator admin, with the operator user's `~/.ssh` in place of the AI user's. It installs archive prerequisites, sets the operator user without sudo, creates the output directories (PA-42), applies OC-10 only after a second login is confirmed, enables unattended security updates, installs the operator scripts per PA-42, prints the host key fingerprints, and ends by running the operator check. It never touches credentials, the operator user's output files, or production configuration, and writes nothing into a user's home.

**PA-21 Operator contract** OC-1 to OC-12 (ADR-012 section 5).

**PA-22 Operator script endpoints** are literals, listed in a configured allowlist read from the base commit (the GitHub API plus project-declared hosts); enforced by the operator code checks. (Not in the ADR-012 list of PA-46; see open point O-7.)

**PA-23 ADR-011 is amended, not superseded.** Z7, OCI, alarms, lab access, and the Ubuntu operator profile are dropped. It keeps the rules for operator scripts (dry run by default, release tags, prompted credentials, sanitised output, standard-library Python) and refers to ADR-012 for the operator machine. Decisions cited by ADR-008 and ADR-009 keep their numbers.

**PA-24 ADR-005 is amended:** decisions 6 and 10 describe the Ansible lab and operator profiles on Debian 13, run by the admin users; decision 3 per PA-30; decision 5 stays; the amendment also covers decision 1's scope note, decision 7, section 1, the consequences, AC5-1, AC5-4, and AC5-6.

**PA-25 Deny entries of PA-19 in the template.** PA-19 and its deny entries go into the template's owned CLAUDE.md and required-deny list by a CR in the template repository.

**PA-26 Removal order is strict** and no release tag is cut while a removal is in progress. ARM64 is removed in two PRs: first from `architectures` and the runner labels in `config/project.yaml` with the arm64 job still running, then the job and the arm64 artifacts (see O-3 for the tag rule).

**PA-28 CI** runs the lab profile, the operator profile, the token step, and both checks in dry run in a pinned `debian:13` container (by digest) started with the two users and one key each; the aggregate `quality-gate` needs the job; required check names are unchanged.

**PA-30 This repository supports amd64 only.** The install engine and the manifest schema stay architecture-generic (ADR-008 decision 8); `scripts/toolchain check` requires artifacts for each architecture listed in `config/project.yaml`. Residual risk: the engine's arm64 path is tested only by the template's CI.

**PA-31 Lab setup and operator configuration are Ansible:** the CR-2 builder profile becomes the lab profile, the operator profile is retargeted to Debian 13, and both use one shared SSH hardening role.

**PA-34 Project toolchains on the AI lab** are installed by the lab admin with the root-owned `scripts/toolchain` from the platform's release tag, from the project's CI manifest read as "the tools CI uses" (ADR-008 decision 8 unchanged), into `/opt/ai-lab/project/`, amd64 only, with the checksum rules of the gate tools; dry run by default. A project package list of Debian archive packages, with no third-party apt sources, is applied by the lab admin through lab setup. Inputs come from an anonymous clone at a merged commit or tag, or are extracted from the AI user's clone at a commit SHA the user supplies. Smoke tests of project tools run as the AI user, never as root. The project's own copy of `scripts/toolchain` is never executed.

**PA-36 Security updates:** lab setup and the operator configuration enable unattended Debian security updates; the operator admin schedules reboots of the operator machine; an AI lab is rebuilt rather than patched in place when a reboot is not enough.

**PA-37 T1 at disposal of an AI lab:** the disk is destroyed (G-18), so T1 is not rotated at disposal; its 90-day expiry and the ADR-001 rotation procedure stay.

**PA-38 ADR-004, ADR-006, and ADR-007 are withdrawn** in baseline v0.2; their numbers are not reused.

**PA-39 Zone Z8:** the lab host (jump host and hypervisor), outside the platform, with full control of the AI lab; recorded in ADR-012 and referenced from ADR-001 section 3.

**PA-40 Baseline v0.2 contains:** the constraints with zero cost restated without OCI (cited by ADR-009 decision 12); the component map (Windows client, per-project AI lab VMs, the operator machine, the lab host outside the platform, GitHub, Anthropic); the decision index with CHG-002, D2 to D7, D12, D15, and D16 superseded or reduced, and ADR-012 added; the sequence CR-57 implementation, Stage 5 (template), Stage 6 (first project on its own lab VM), Stage 7 (a timed rebuild test and metrics); PA-38.

**PA-41 Interactions.** Before the second discussion round the design session read ADR-010, the CR-45 amendments of ADR-003 section 7 and ADR-008, and the template's preset and owned CLAUDE.md (read-only), and lists every interaction with CR-57 in section 10, without deciding them.

**PA-42 Multi-project operator machine.** Each project's operator scripts are installed by the operator admin at that project's release tag into a root-owned directory per project; each project has its own output directory (mode 0700); runs are one at a time; T2 and T3 are created per run and limited to that project's repositories. One operator user serves all projects (RR-P11).

**PA-43 Project non-production credentials** on an AI lab are entered by the user as the AI user in a plain SSH terminal, never in a Claude session; stored with file mode 0600; their names and paths are listed in the project's PROJECT.md, and the project's deny list blocks reads of those paths.

**PA-44 Pre-disposal mode.** The lab check has a read-only pre-disposal mode that lists every repository under `~/work` with uncommitted changes or unpushed commits; the user runs it before a lab is discarded.

**PA-45 Runbook.** Plan step 9 adds a new-project runbook: repository and rulesets (user), lab VM and lab setup (lab admin), token step (user), clone and `initialize-project` (Claude Code), operator script installation (operator admin), allowlist audit including the new repository.

**PA-46 ADR-012 "Host model"** is added in this design PR (Proposed; accepted by its merge). It carries PA-13 to PA-21, PA-31, PA-34, PA-36, PA-42, PA-43, PA-44, and the zones Z1, Z6, and Z8. ADR-001 keeps its trust model and GitHub decisions and points to ADR-012 by an amendment entry.

## 5. Contracts

The two contracts are specified in [ADR-012](../../adr/ADR-012-host-model.md): the lab contract LC-1 to LC-15 (section 4) and the operator contract OC-1 to OC-12 (section 5), both for Debian 13 on x86-64 (Q5). Each item is marked **checked** (a read-only check or fixture verifies it) or **declared** (a rule that scripts or procedure must follow and that review verifies). The marks of the review are kept; OC-3, OC-4, OC-5, OC-7, and OC-9 carry no mark in the review and are marked declared here (O-2).

## 6. Amendments and supersession (the process of this PR)

An accepted record changes by a header entry that takes effect when this design PR is merged, and by body text committed in this PR after the approver's decisions arrived as a review (CR-43 process). All entries below are marked Proposed until the merge. ADR-003, ADR-008, ADR-009, and ADR-010 are **not edited** (PA-A2).

| Record | Change in this PR |
|---|---|
| [ADR-001](../../adr/ADR-001-trust-model-and-execution.md) | Amended. Decisions 1, 5, and 7 and sections 3, 4a, 5 (settings location), and 6 refer to ADR-012 for the host model. Sections 1, 9, and 10 are updated: AC1-1 and AC1-6 evidenced by facts on the operator machine; AC1-3 generalised; AC1-4 removed; AC1-7 per PA-6; AC1-8 through the token step. The T1 rotation procedure (no `labctl verify`; it was never built), "both hosts" in decision 4 and D17, and the RR-8 and RR-9 texts are updated (RR-9 per section 9). Section 4 keeps the GitHub credential rows and refers to ADR-012 for host credentials (the four account keys, "the admins hold no credentials", production credentials on Z6 only, project non-production credentials on Z1). CR-43's amendments are preserved. The agent-forwarding rule and "addresses never in the repository" are kept, generalised |
| [ADR-002](../../adr/ADR-002-infrastructure-deployment-pipeline.md) | Superseded (the platform no longer provisions infrastructure) |
| [ADR-005](../../adr/ADR-005-toolchain.md) | Amended per PA-24, PA-30, PA-31. Decision 9 (builder content) is amended only as far as PA-31 and the OpenTofu removal need (O-5) |
| [ADR-011](../../adr/ADR-011-operator-tier.md) | Amended per PA-23: Z7, OCI, alarms, lab access, and the Ubuntu operator profile dropped; rules for operator scripts kept; decision numbers kept. Decision 5 is OCI-worded (O-6) |
| [ADR-012](../../adr/ADR-012-host-model.md) | New, Proposed (PA-46) |
| [Baseline v0.2](../../architecture/baseline-v0.2.md) | New, with the content of PA-40 and PA-38. [Baseline v0.1](../../architecture/baseline-v0.1.md) stays, with a "superseded by v0.2" banner, so existing links survive |
| ADR-003, ADR-008, ADR-009, ADR-010 | Unchanged. Q2 note: PC-8 paths come from configuration (ADR-003 as amended by CR-39), and the sentence of ADR-003 that names this repository's paths described the configuration of its time. Recorded here only |
| [docs/README.md](../../README.md) | CR-57 and ADR-012 rows, statuses, baseline v0.2 row |

## 7. Answers to the questions of the first draft

| ID | Decision (approver) |
|---|---|
| Q1 | Retirement **rejected**. `github-setup` (T2), `facts` with host and GitHub scope (T3), and `github-desired-state.toml` stay on the operator machine. Only the OCI scope, `acceptance`, the lab operator VM, and the OCI CLI lock are removed. CR-43 PR 6 is not re-scoped |
| Q2 | PC-8 and `operator-contract` stay active here. `operator_paths` lists the operator scripts, the lab profile, and the operator profile, read from the base commit. ADR-003 is not edited (note in section 6) |
| Q3 | Rename the repository after the CR-57 implementation PRs and before the template's Stage 5 real run; the new name is the approver's |
| Q4 | Baseline v0.2 is added in this design PR, with the content of PA-40 |
| Q5 | Two contracts in ADR-012 (PA-46): the lab contract (PA-15) and the operator contract (PA-21), both for Debian 13 on x86-64; each item is marked "checked" or "declared" |
| Q6 | After this design merges, close issue #16 and PR #17, and issue #18 and the open CR-18 PRs, by PR comment; CR-18's generic parts are carried by PA-21 and the amended ADR-011 (PA-23) |

## 8. Alternatives considered

| Alternative | Outcome | Reason |
|---|---|---|
| Retire the GitHub-scope operator tooling | Rejected (Q1) | Settings and fact checks stay scripted on the operator machine; only OCI goes |
| Claude Code opens SSH to lab hosts itself | Rejected (user) | Reverses the key and host rules and needs a new trust ADR |
| Merge this repository and the template | Not chosen | The template is a generated payload with its own release tags |
| Keep a host-owner-declared "any Linux host" contract | Replaced by the lab contract | The review fixes a per-project disposable lab with a lab admin, enforced on the server (PA-14 to PA-16) |
| Delete merged code in the design PR | Rejected | PC-4: a design PR changes `docs/` only |
| Rename the repository now | Deferred (Q3) | After the implementation PRs |
| Supersede ADR-011 in full | Replaced by amendment (PA-23) | Release tags, dry-run default, prompted credentials, and the contract cited by ADR-008 and ADR-009 stay |

## 9. Risks, assumptions, and what stays open

Assumption NA-6: AI lab VMs cannot reach one another (network project); the platform does not test it.

| ID | Statement |
|---|---|
| RR-9 | Accepted: T1 reaches every repository of the machine account from every AI lab. A follow-up CR evaluates repository-scoped GitHub App tokens (ADR-001 deferred alternative) |
| RR-P2 | Guardrail strength depends on the lab admin running lab setup; managed settings make it independent of the AI user |
| RR-P3 | Removal half-states, mitigated by PA-26 |
| RR-P4 | Accepted: the client offers no post-quantum key exchange; sessions use curve25519-sha256 |
| RR-P5 | Accepted: the lab host controls the AI lab completely, including T1 and the inference credential while a session runs. The AI lab's host keys are new on every rebuild and are accepted without fingerprint confirmation; only the lab host is in a position to intercept the inner SSH hop, so this adds no risk beyond its control |
| RR-P6 | Accepted: key files and the clipboard on the Windows client are outside the platform; mitigated by PA-14 |
| RR-P7 | Accepted: GitHub stays reachable with T1, so data can leave through any repository the machine account can write to |
| RR-P10 | Accepted: the login keys are set by provisioning, outside the platform; the setup verifies their number and separation, not their owner |
| RR-P11 | Accepted: a project's operator script can read other projects' output files and reach every production environment the operator machine reaches, without their credentials; the approver's review at each project's release tag is the control |

RR-P1 of the first draft (loss of the scripted GitHub path) is withdrawn by Q1. RR-P8 and RR-P9 are not in the review and are not reused.

## 10. Interactions (PA-41), not decided

Read for this section: ADR-010; the CR-45 amendments of ADR-003 section 7 and ADR-008 (header rows and decisions 2 and 7); ADR-003 PC-8 and sections 4, 7; ADR-008 decisions 5, 6, 8, 11, 12, 14; ADR-009 decisions 7, 11, 12, 14; the CR-43 design (SC-13, SC-20, and the jobs it lists); the template repository on `main`. **The template repository holds only a README and a licence: there is no preset, no owned CLAUDE.md, and no `docs/PLATFORM.md` to read, so rows I-9 to I-12 rest on the text of ADR-008 and not on the template's files.** Each row names a point and ends in a question that this PR does not answer.

| ID | Where | Interaction with CR-57 | Open question |
|---|---|---|---|
| I-1 | ADR-003 line 114 (PC-8) | Names this repository's `operator_paths`; with Q2 the key lists operator scripts, the lab profile, and the operator profile. ADR-003 stays unedited | Which of: the design note (section 6) alone, or a later ADR-003 amendment, keeps the sentence from misleading? |
| I-2 | ADR-003 section 7 heading and lines 48, 82, 126, 164 | Section 7 (the section CR-45 amends) is headed "Desktop SSH session on the OCI VM"; the "Infra PR" row and RR-5 cite ADR-002, which is superseded | After CR-45 and CR-57 merge, who corrects the OCI VM wording and the ADR-002 citations? |
| I-3 | ADR-010 decisions 2, 9; CR-45 | The always-loaded budget (20 KiB) counts the repository CLAUDE.md and its imports. CR-57 adds a managed CLAUDE.md (PA-16) and keeps a user-level CLAUDE.md that Claude Code also loads. Step 9 rewrites this repository's CLAUDE.md | Do the budgets apply to this repository's CLAUDE.md, and does the managed or user-level file count in the always-loaded set? |
| I-4 | ADR-010 decision 11; baseline v0.2 sequence | ADR-010 records the static baseline at Stage 5 exit and the full baseline at Stage 7; PA-40 puts "a timed rebuild test and metrics" in Stage 7 | Is the rebuild test part of the metrics baseline, or a separate Stage 7 exit item? |
| I-5 | ADR-010 decision 10, tier C | Usage figures are typed by the approver in a session; sessions now run as the AI user on a per-project lab | Is a metrics snapshot committed from the lab like any PR file? |
| I-6 | ADR-008 decisions 5, 6; PA-5, PA-19, PA-25 | The template's CLAUDE.md is owned and "platform-neutral"; `deny-list` compares `.claude/settings.json` with the core list plus `deny.platform.txt`. PA-5 keeps `terraform`, `tofu`, and `oci` entries in the core list; PA-25 puts the SSH deny entries into the owned core list through a template CR | Is a technology-named entry (`terraform`, `oci`) compatible with "platform-neutral" owned files? Do PA-19 entries land in the core list or in `deny.platform.txt`? |
| I-7 | ADR-008 decisions 5, 6, 14; PA-43 | PROJECT.md is project-owned and lists credential paths (PA-43); the project's deny list blocks them. `settings.json` is owned and checked against the core list plus `deny.platform.txt` | Where does a project add a deny entry for its credential paths without failing `deny-list` or needing a whole-file override? |
| I-8 | ADR-008 decision 11 and ADR-011 decision 17 | The generic `operator.md`, PC-8, `operator-contract`, and `operator_guard.py` are in the template; "the ADR-011 specifics are in the preset's PLATFORM.md". ADR-011 is amended and the specifics now sit in ADR-012 (OC-1 to OC-12) | Does the preset point to ADR-012, and does the template's `operator.md` need the per-project installation of PA-42? |
| I-9 | ADR-009 decision 11; PA-22, PA-30 | Generic checks have the same fixtures in both repositories and rule changes go design PR, template, then this repository. PA-22 (endpoint allowlist) extends the operator code checks; PA-30 changes how `scripts/toolchain check` reads architectures; the OCI and Terraform rules of `operator_contract.py` are in the shared check | In which order do these shared-code changes reach the template, and does the template's parity script flag this repository meanwhile? |
| I-10 | ADR-009 decision 14, CR-43 SC-13, SC-20 | The policy inputs are `allowed_actions`, `runner_labels`, `architectures`, `operator_paths`, `release_tags`; `operator-contract` is inactive only for an explicit empty `operator_paths` and fails on a missing key. PA-22 adds a configured allowlist, which is not in that list | Is the allowlist a sixth policy input of ADR-009 decision 14 (an ADR-009 amendment), and under which key name? |
| I-11 | ADR-008 decisions 8, 9; ADR-005 decision 1 (CR-39 scope note) | The template's CI manifest requires both architectures and SHA-256; CI is a matrix over configured architectures; PA-30 makes this repository amd64 only and the check read the configured list | Does the template's own manifest rule ("both architectures") stay a template rule while the engine reads the configuration? |
| I-12 | ADR-008 decision 12(b), 14; Q3 | Stage 5 exit needs a real run with this platform's preset in a throwaway repository; Q3 renames this repository before that run; the preset is a change PR outside CR-39 (plan step 10) | Does the preset PR (step 10) land before the rename, and who updates names that `initialize-project --config` carries? |
| I-13 | ADR-008 decision 5 precedence sentence; PA-16 | The managed CLAUDE.md (highest precedence), the user-level CLAUDE.md (today "repository instructions take precedence"), and the repository CLAUDE.md all load on the AI lab | Which file states precedence, and is the user-level file text amended with the managed one? |
| I-14 | CR-43 plan PR 6, U-A4; Q1 | CR-43 PR 6 (settings documentation and desired state) edits `github-desired-state.toml`, a PC-8 path, and its user-only step runs `github-setup` on the operator machine. No release tag is cut during a removal (PA-26) | Does PR 6 wait for the removal sequence, or run from the last tag before it? |
| I-15 | ADR-009 decision 12 and baseline section 2 | The zero-cost rule cites "baseline section 2"; baseline v0.2 restates it | Does v0.2 keep the section number so the citation holds? (v0.2 does keep it; the question is whether ADR-009's Related line, which cites v0.1 sections 3, 6, 7, needs a pointer) |

## 11. Open points

Points where the review is silent or its decisions meet. None is guessed; each stays as written until the approver answers.

| ID | Point | Where it matters |
|---|---|---|
| O-1 | LC-5 is not in the review; the number is not defined or reused | ADR-012 section 4 |
| O-2 | OC-3, OC-4, OC-5, OC-7, and OC-9 have no "checked" mark in the review; Q5 asks for "checked" or "declared". Marked "declared" here | ADR-012 section 5 |
| O-3 | PA-26 forbids a release tag while a removal is in progress; lab setup (step 2) and the operator configuration (step 4) refuse to run except at a release tag. Strict reading: no tag, so neither runs on a real machine, until the last removal (step 7) merges; the PA-28 job tests them in CI meanwhile | Plan sections 1 and 4 |
| O-4 | PA-A7 says the manifest check requires artifacts for "exactly" the configured architectures; PA-30 says "each architecture listed". Whether an artifact for an unlisted architecture is an error is not stated. Plan step 6 keeps both architectures required until the config lists one | Plan step 6 |
| O-5 | ADR-005 decision 9 (builder content: OpenTofu, `ansible-core`, `tmux`) is not in PA-24's list; PA-31 renames the profile and PA-A1 removes Terraform | ADR-005 body |
| O-6 | ADR-011 decision 5 ("operator scripts never change infrastructure", OCI-worded) conflicts with G-3 ("apply changes") and PA-13. The amended ADR-011 marks it dropped for its OCI scope and adds no replacement rule | ADR-011 body |
| O-7 | PA-22 (endpoint allowlist) is in neither ADR-012 (PA-46) nor ADR-011 (PA-23). Carried by this design and PA-A15 | ADR-011, ADR-012 |
| O-8 | `scripts/operator/setup` (tag check, `ansible-core`, runs the Ubuntu profile) is not named; PA-20 puts the operator configuration in the operator profile. Step 4 retargets or replaces it | Plan step 4 |
| O-9 | `facts --privileged` and sudo in `setup` (ADR-011 decisions 10, 12) conflict with OC-8 and OC-9 (no sudo; no root-only facts script). Step 4 removes both | Plan step 4 |
| O-10 | Whether a project other than this repository gets `github-setup` and a desired-state file under PA-42 is not stated | ADR-012, plan step 4 |
| O-11 | The exact set of generic files excluded from the PA-A1 search is proposed in the acceptance criteria and finalised by step 1's inventory; the approver confirms it | PA-A1 |
| O-12 | Recorded inconsistencies named by the review without detail: ADR-009's status line (Proposed) against the index (Accepted, merge of PR 44); the content of CR-43 design section 12 against `docs/operations/github-setup.md`. Neither is edited here | ADR-009, CR-43 |
| O-13 | The template repository holds no preset or owned CLAUDE.md yet (PA-41) | Section 10 |

## 12. Not verified

From the review: at the lab setup PR, Claude Desktop's needs (PA-A28), `ed25519-sk` support on the Windows client (PA-14), whether Debian 13's bash reads startup files for a command run over SSH (LC-14), the managed CLAUDE.md location on Linux, whether managed settings can hold everything in `workspace/claude-user/settings.json`, and how Claude Desktop delivers and updates its engine on the lab and whether anything credential-like is stored under `~/.claude/remote/` (PA-18). At the first removal PR: which files under `scripts/operator/` are OCI-specific and whether the rest is standard library only; whether checks hardcode removed job names (section 3 lists those found); whether PC-8 counts deletions (read in `rules.py`, not run); whether `forbidden-api` and the deny rules match reads; how the aggregate and PC-9 behave when the base lists an architecture whose job the head removed; the GitHub hostnames git and `gh` need, from GitHub's published metadata; how Claude Code's deny rules match SSH command variants.

From this revision: no run exists; the claims of section 3 are read in files at `85360e8`, not executed; CI on the first draft's head was green (the earlier claim that gate tests were only locally failing is withdrawn).
