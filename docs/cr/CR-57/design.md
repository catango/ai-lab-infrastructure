# CR-57 Design: a platform-agnostic AI workflow platform

Status: revised with the approver's decisions (review of the approver account on design PR 58, submitted 2026-11-23T18:27:31Z), the approver's round 2 review (19:25:51Z), round 3 review (20:14:13Z), and round 4 review (20:33:32Z), and round 5 review (20:46:44Z), which resolve the points of the earlier revisions. Design only: nothing is implemented, no setting changes. Decisions are PA-1 to PA-46 (section 4); the answers to the former questions Q1 to Q6 are in section 7; the round 2 decisions on the interactions and open points are in sections 10 and 11. The earlier default answers of the first draft are replaced and are not repeated.

## 1. Requirement and the decisions already taken

Requirement (user, 2026-11-23): simplify; discard all platform-related requirements; the project is platform agnostic and focuses on **preconfigured AI** and **integrated GitHub workflows**; it uses Claude Code and connects to an AI lab environment over SSH; everything technology-specific belongs to the project that the platform drives; **discard all OCI configuration**.

| Input | Decision |
|---|---|
| SSH model | **Claude Desktop SSH sessions** (ADR-001 decision 2, baseline D1): Claude Desktop on the Windows client opens SSH sessions to the AI lab and Claude Code runs there as the AI user. No local Claude Code session on Windows. Claude Code opens no onward SSH |
| CR-55 (cross-builds) | Withdrawn; cross-builds are project-owned. PR 56 and issue 55 are closed |
| Approver's decisions | The review named above (18:27:31Z) and the round 2 review (19:25:51Z). The first replaces the default answers of the first draft, adds PA-13 to PA-46, ADR-012, the risks of section 9, and the acceptance changes; the second decides the open points O-1 to O-16, the interactions I-1 to I-15, and the items C-1, C-2, X-1 to X-4, R-1; a round 3 review (20:14:13Z) decides O-17, O-18, and C-3 to C-8; a round 4 review (20:33:32Z) decides O-19 to O-24 and C-9; a round 5 review (20:46:44Z) decides O-25 and O-26. A review of 18:48:20Z (a revision plan) is not used (user's choice) |
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

**PA-5 Guardrails.** On the AI lab the guardrails live in managed settings only. RR-8 is restated as: a user or repository setting can tighten but never relax the managed settings. The existing generic infrastructure-apply deny entries (`terraform`, `tofu`, `oci`) stay in the core list. The plan names the PR that puts them into managed settings (implementation step 2): they are copied there, and the repository files and the core list keep them (PA-A10 allows added deny lines only).

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

**PA-16 Lab setup** is the Ansible lab profile (PA-31), run by the lab admin from a clone the admin owns at a release tag; dry run by default (check mode with diff); idempotent. On a fresh VM it accepts the one provisioned key of the AI user and of the lab admin, and fails when a managed account has no key or more than one, a key is shared between accounts, root or any other account has a key, the AI user's `~/.ssh` holds a private key, or `AuthorizedKeysCommand`, `TrustedUserCAKeys`, or `AuthorizedPrincipalsFile` is set. The checks fail when sshd reads keys from any location other than the root-owned one, and warn on an inert leftover `authorized_keys` file in a user's home (round 2, X-1). It applies: archive prerequisites; the gate tools into `/opt/ai-lab`; root-owned managed settings and a managed CLAUDE.md carrying the settings of `workspace/claude-user/` and the non-relaxable rules of its CLAUDE.md (merged, never replaced; round 3, C-8); the system-wide git identity; the provisioned keys copied to the root-owned authorized-keys location, with sshd switched only after a second login with each account is confirmed while the current session stays open; LC-13; unattended security updates; project toolchains and package lists (PA-34); and the root-owned token step and lab check. It prints the host key fingerprints for information, removes nothing, writes nothing into a user's home, and never executes from a path the AI user can write.

**PA-17 What the user runs on the AI lab.** Logged in as the AI user in a plain SSH terminal, only the root-owned token step (T1 login; refuses without a TTY or inside a Claude Code session) and the read-only lab check.

**PA-18 Hosts the AI user needs** (input for the network project; the AI host document lists them): `api.anthropic.com`, `platform.claude.com`, `claude.ai`, `github.com`, `api.github.com`, `code.claude.com`, and `downloads.claude.ai` only if the lab fetches the Claude Code engine itself (the lab setup PR records which applies). Managed settings disable claude.ai MCP connectors, nonessential traffic, and artifacts.

**PA-19 No onward SSH, no key access (PA-3 restated).** (a) Deny rules for the SSH client family and Read/Edit deny on `~/.ssh/**`. Proposed entries, the list that plan PR 3 implements in the three deny-list copies and the managed settings: `Bash(ssh *)`, `Bash(scp *)`, `Bash(sftp *)`, `Bash(rsync *)`, `Bash(ssh-keygen *)`, `Bash(ssh-add *)`, `Bash(ssh-agent *)`, `Read(~/.ssh/**)`, and `Edit(~/.ssh/**)`; how Claude Code's deny rules match variants (absolute paths, `env ssh`, wrappers) is not verified (section 12). (b) the LC-6 checks; (c) LC-11 and LC-13 on the server; (d) Claude Code never reaches the operator machine, the lab admin account, or the lab host. This replaces the repository rule "never try to reach the lab VM", which goes with the rewrite of `CLAUDE.md` (plan step 9).

**PA-20 Operator configuration** is the Ansible operator profile (PA-31), run by the operator admin from a clone the admin owns at a release tag; dry run by default; idempotent. On a fresh VM it applies the key rules of PA-16 to the operator user and the operator admin, with the operator user's `~/.ssh` in place of the AI user's. It installs archive prerequisites, sets the operator user without sudo, creates the output directories (PA-42), applies OC-10 only after a second login is confirmed, enables unattended security updates, installs the operator scripts per PA-42, prints the host key fingerprints, and ends by running the operator check. It never touches credentials, the operator user's output files, or production configuration, and writes nothing into a user's home.

**PA-21 Operator contract** OC-1 to OC-12 (ADR-012 section 5).

**PA-22 Operator script endpoints** are literals, listed in a configured allowlist read from the base commit (the GitHub API plus project-declared hosts); enforced by the operator code checks. It is carried by ADR-011 decision 11, which states it after this PR (it does not on `main`); ADR-012 does not repeat it (O-7). The allowlist is the policy input `operator_endpoints` (I-10).

**PA-23 ADR-011 is amended, not superseded.** Z7, OCI, alarms, lab access, and the Ubuntu operator profile are dropped. It keeps the rules for operator scripts (dry run by default, release tags, prompted credentials, sanitised output, standard-library Python) and refers to ADR-012 for the operator machine. Decisions cited by ADR-008 and ADR-009 keep their numbers.

**PA-24 ADR-005 is amended:** decisions 6 and 10 describe the Ansible lab and operator profiles on Debian 13, run by the admin users; decision 3 per PA-30; decision 5 stays; the amendment also covers decision 1's scope note, decision 7, section 1, the consequences, AC5-1, AC5-4, and AC5-6.

**PA-25 Deny entries of PA-19 in the template.** PA-19 and its deny entries go into the template's owned CLAUDE.md and required-deny list by a CR in the template repository.

**PA-26 Removal order is strict.** ARM64 is removed in two PRs: first from `architectures` and the runner labels in `config/project.yaml` with the arm64 job still running, then the job and the arm64 artifacts. (No `runner_labels` key exists in `config/project.yaml`: the labels are the `runner` and `runner_private` fields of each `architectures` entry. Code defaults that also name arm64 are `DEFAULT_ARCHITECTURES` in `scripts/pr_contract/config.py` and `DEFAULT_LABELS` in `scripts/checks/workflow_policy.py`; they change in the second PR, in this repository only, and the template keeps its own configuration listing amd64 and arm64 (round 4, O-24).) Narrowed by O-3 (round 2): the approver may cut a release tag at any PR boundary whose PA-A16 run is green, except between PR 5 and PR 6. The operator machine moves to a new tag only at or after PR 4. PA-A28 runs on a tag cut after PR 2 and is recorded in PR 3, which adds any permission PA-15 needs (C-1).

**PA-28 CI** applies the lab and operator profiles twice (the second run changes nothing) and once in dry run (the tree hash is unchanged), then runs the token step fixtures and both checks, in a pinned `debian:13` container (by digest) started with the two users and one key each (round 3, C-5); the release-tag pre-task has no bypass: the job runs the playbooks in a disposable clone whose local bare origin has `main` at the PR head and an unpushed local `v*` test tag on that commit, and a separate untagged-tree fixture shows the refusal (C-4); the aggregate `quality-gate` needs the job; required check names are unchanged.

**PA-30 This repository supports amd64 only.** The install engine and the manifest schema stay architecture-generic (ADR-008 decision 8); `scripts/toolchain check` requires artifacts for exactly the architectures listed in `config/project.yaml`; an artifact for an unlisted architecture is an error (O-4, round 2). Residual risk: the engine's arm64 path is tested only by the template's CI.

**PA-31 Lab setup and operator configuration are Ansible:** the CR-2 builder profile becomes the lab profile, the operator profile is retargeted to Debian 13, and both use one shared SSH hardening role.

**PA-34 Project toolchains on the AI lab** are installed by the lab admin with the root-owned `scripts/toolchain` from the platform's release tag, from the project's CI manifest read as "the tools CI uses" (ADR-008 decision 8 unchanged), into `/opt/ai-lab/project/`, amd64 only, with the checksum rules of the gate tools; dry run by default. A project package list of Debian archive packages, with no third-party apt sources, is applied by the lab admin through lab setup, only after the lab admin has read the dry-run output; the dry run prints every package name and version it would install (round 4, O-22). There is no package allowlist in v1: the lab admin's reading is the control (RR-P2). Inputs come from an anonymous clone at a merged commit or tag, or are extracted from the AI user's clone at a commit SHA the user supplies. Smoke tests of project tools run as the AI user, never as root. The project's own copy of `scripts/toolchain` is never executed.

**PA-36 Security updates:** lab setup and the operator configuration enable unattended Debian security updates; the operator admin schedules reboots of the operator machine; an AI lab is rebuilt rather than patched in place when a reboot is not enough.

**PA-37 T1 at disposal of an AI lab:** the disk is destroyed (G-18), so T1 is not rotated at disposal; its 90-day expiry and the ADR-001 rotation procedure stay.

**PA-38 ADR-004, ADR-006, and ADR-007 are withdrawn** in baseline v0.2; their numbers are not reused.

**PA-39 Zone Z8:** the lab host (jump host and hypervisor), outside the platform, with full control of the AI lab; recorded in ADR-012 and referenced from ADR-001 section 3.

**PA-40 Baseline v0.2 contains:** the constraints with zero cost restated without OCI (cited by ADR-009 decision 12); the component map (Windows client, per-project AI lab VMs, the operator machine, the lab host outside the platform, GitHub, Anthropic); the decision index with CHG-002, D2 to D7, D12, D15, and D16 superseded or reduced, and ADR-012 added; the sequence CR-57 implementation, Stage 5 (template), Stage 6 (first project on its own lab VM), Stage 7 (a timed rebuild test and metrics); PA-38.

**PA-41 Interactions.** Before the second discussion round the design session read ADR-010, the CR-45 amendments of ADR-003 section 7 and ADR-008, and the template's preset and owned CLAUDE.md (read-only), and lists every interaction with CR-57 in section 10, without deciding them.

**PA-42 Multi-project operator machine.** Each project's operator scripts are installed by the operator admin at that project's release tag into a root-owned directory per project; each project has its own output directory (mode 0700); runs are one at a time; T2 and T3 are created per run and limited to that project's repositories. One operator user serves all projects (RR-P11). One exception (round 2, O-10, C-2): the allowlist audit of PA-45 and AC1-1 runs from this repository's `facts` with a read-only T3 that selects all repositories of the personal account; it is recorded in ADR-012 decision 12.

**PA-43 Project non-production credentials** on an AI lab are entered by the user as the AI user in a plain SSH terminal, never in a Claude session; stored with file mode 0600; their names and paths are listed in the project's PROJECT.md, and the project's deny list blocks reads of those paths.

**PA-44 Pre-disposal mode.** The lab check has a read-only pre-disposal mode that lists every repository under `~/work` with uncommitted changes or unpushed commits; the user runs it before a lab is discarded.

**PA-45 Runbook.** Plan step 9 adds a new-project runbook: repository and rulesets (user), lab VM and lab setup (lab admin), token step (user), clone and `initialize-project` (Claude Code), operator script installation (operator admin), allowlist audit including the new repository (from this repository's `facts` with the read-only T3 of the PA-42 exception).

**PA-46 ADR-012 "Host model"** is added in this design PR (Proposed; accepted by its merge). It carries PA-13 to PA-21, PA-31, PA-34, PA-36, PA-42, PA-43, PA-44, and the zones Z1, Z6, and Z8. ADR-001 keeps its trust model and GitHub decisions and points to ADR-012 by an amendment entry.

## 5. Contracts

The two contracts are specified in [ADR-012](../../adr/ADR-012-host-model.md): the lab contract LC-1 to LC-15 (section 4) and the operator contract OC-1 to OC-12 (section 5), both for Debian 13 on x86-64 (Q5). Each item is marked **checked** (a read-only check or fixture verifies it) or **declared** (a rule that scripts or procedure must follow and that review verifies). The marks of the review are kept; OC-3, OC-4, OC-5, OC-7, and OC-9 carry no mark in the review and are declared (O-2, confirmed in round 2; PA-A26 is supporting evidence for the in-process part of OC-4). LC-5 stays undefined and is never reused; no stand-in item is added (O-1).

## 6. Amendments and supersession (the process of this PR)

An accepted record changes by a header entry that takes effect when this design PR is merged, and by body text committed in this PR after the approver's decisions arrived as a review (CR-43 process). All entries below are marked Proposed until the merge. ADR-003, ADR-008, ADR-009, and ADR-010 are **not edited** (PA-A2).

| Record | Change in this PR |
|---|---|
| [ADR-001](../../adr/ADR-001-trust-model-and-execution.md) | Amended. Decisions 1, 5, and 7 and sections 3, 4a, 5 (settings location), and 6 refer to ADR-012 for the host model. Sections 1, 9, and 10 are updated: AC1-1 and AC1-6 evidenced by facts on the operator machine; AC1-3 generalised; AC1-4 removed; AC1-7 per PA-6; AC1-8 through the token step. The T1 rotation procedure (no `labctl verify`; it was never built), "both hosts" in decision 4 and D17, and the RR-8 and RR-9 texts are updated (RR-9 per section 9). Section 4 keeps the GitHub credential rows and refers to ADR-012 for host credentials (the four account keys, "the admins hold no credentials", production credentials on Z6 only, project non-production credentials on Z1). CR-43's amendments are preserved. The agent-forwarding rule and "addresses never in the repository" are kept, generalised |
| [ADR-002](../../adr/ADR-002-infrastructure-deployment-pipeline.md) | Superseded (the platform no longer provisions infrastructure); its Status cell says it is superseded when the CR-57 design PR merges (X-4) |
| [ADR-005](../../adr/ADR-005-toolchain.md) | Amended per PA-24, PA-30, PA-31. The decision 9 amendment stands as written (O-5); item O5-3 notes that the OpenTofu choice is superseded by CR-57; the operator profile takes manifest membership for Python 3 and git only (O-15) |
| [ADR-011](../../adr/ADR-011-operator-tier.md) | Amended per PA-23: Z7, OCI, alarms, lab access, and the Ubuntu operator profile dropped; rules for operator scripts kept; decision numbers kept. Decision 5 is dropped and points to ADR-001 B3 as amended, with no replacement rule (O-6); decision 11 carries PA-22 and the key `operator_endpoints` (O-7, I-10); the sudo-based `setup` is deleted in plan step 4 (O-8) |
| [ADR-012](../../adr/ADR-012-host-model.md) | New, Proposed (PA-46) |
| [Baseline v0.2](../../architecture/baseline-v0.2.md) | New, with the content of PA-40 and PA-38. [Baseline v0.1](../../architecture/baseline-v0.1.md) stays, with a "superseded by v0.2" banner, so existing links survive |
| ADR-003, ADR-008, ADR-009, ADR-010 | Unchanged in this PR. Q2 note: PC-8 paths come from configuration (ADR-003 as amended by CR-39), and the sentence of ADR-003 that names this repository's paths described the configuration of its time. Round 2 (R-1): after the CR-57 design PR merges (the CR-45 design PR merged on 2026-11-20, commit 36ae074), one docs-only design PR, opened by Claude Code on the approver's instruction, carries I-1, I-2, I-10, I-15, the ADR-009 status line (O-12) and the ADR-010 status line (Proposed to Accepted, merge of PR 46; O-23), and the "workspace" wording of ADR-009 decision 11 |
| [docs/README.md](../../README.md) | CR-57 and ADR-012 rows, statuses, baseline v0.2 row |

## 7. Answers to the questions of the first draft

| ID | Decision (approver) |
|---|---|
| Q1 | Retirement **rejected**. `github-setup` (T2), `facts` with host and GitHub scope (T3), and `github-desired-state.toml` stay on the operator machine. Only the OCI scope, `acceptance`, the lab operator VM, and the OCI CLI lock are removed. CR-43 PR 6 is not re-scoped |
| Q2 | PC-8 and `operator-contract` stay active here. `operator_paths` lists the operator scripts, the lab profile, and the operator profile, read from the base commit. ADR-003 is not edited (note in section 6) |
| Q3 | Rename the repository after the CR-57 implementation PRs and before the template's Stage 5 real run; the new name is the approver's |
| Q4 | Baseline v0.2 is added in this design PR, with the content of PA-40 |
| Q5 | Two contracts in ADR-012 (PA-46): the lab contract (PA-15) and the operator contract (PA-21), both for Debian 13 on x86-64; each item is marked "checked" or "declared" |
| Q6 | After this design merges, close issue #16 and PR #17, and issue #18 and the open CR-18 PRs, by PR comment; CR-18's generic parts are carried by PA-21 and the amended ADR-011 (PA-23). State at this revision (checked on GitHub): issue #16 and PR #17 are open; issue #18 is already closed; CR-18 PR 7a (#38) is merged and no CR-18 PR is open, so there is nothing to close for #18 or the CR-18 PRs unless the approver finds one open at that time |

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
| RR-P2 | Guardrail strength depends on the lab admin running lab setup, and on the lab admin reading the dry-run output of a project package list before applying it (no package allowlist in v1, O-22); managed settings make it independent of the AI user |
| RR-P3 | Removal half-states, mitigated by PA-26 |
| RR-P4 | Accepted: the client offers no post-quantum key exchange; sessions use curve25519-sha256 |
| RR-P5 | Accepted: the lab host controls the AI lab completely, including T1 and the inference credential while a session runs. The AI lab's host keys are new on every rebuild and are accepted without fingerprint confirmation; only the lab host is in a position to intercept the inner SSH hop, so this adds no risk beyond its control |
| RR-P6 | Accepted: key files and the clipboard on the Windows client are outside the platform; mitigated by PA-14 |
| RR-P7 | Accepted: GitHub stays reachable with T1, so data can leave through any repository the machine account can write to |
| RR-P10 | Accepted: the login keys are set by provisioning, outside the platform; the setup verifies their number and separation, not their owner |
| RR-P11 | Accepted: a project's operator script can read other projects' output files and reach every production environment the operator machine reaches, without their credentials; the approver's review at each project's release tag is the control |

RR-P1 of the first draft (loss of the scripted GitHub path) is withdrawn by Q1. RR-P8 and RR-P9 are not in the review and are not reused.

## 10. Interactions (PA-41) and the round 2 decisions

Read for this section: ADR-010; the CR-45 amendments of ADR-003 section 7 and ADR-008 (header rows and decisions 2 and 7); ADR-003 PC-8 and sections 4, 7; ADR-008 decisions 5, 6, 8, 9, 11, 12, 14; ADR-009 decisions 7, 11, 12, 14; the CR-43 design (SC-13, SC-20, and the jobs it lists); the template repository on `main`. **The template repository holds only a README and a licence: there is no preset, no owned CLAUDE.md, and no `docs/PLATFORM.md` to read, so rows I-6 to I-12 rest on the text of ADR-008 and not on the template's files; PR 10 and the template CR T recheck them against the built files (O-13).** The first revision listed each interaction without deciding it; the approver decided them in the round 2 review (2026-11-23T19:25:51Z). Edits to ADR-003, ADR-008, ADR-009, and ADR-010 are not in this PR (PA-A2); those that need them are carried by R-1 (section 11). The decisions of rounds 3 and 4 that touch these rows (O-20, O-22 to O-24) are in section 11.

| ID | Where | Interaction with CR-57 | Decision (round 2) |
|---|---|---|---|
| I-1 | ADR-003 line 114 (PC-8) | Names this repository's `operator_paths`; with Q2 the key lists operator scripts, the lab profile, and the operator profile | R-1 amends ADR-003 PC-8 to refer to the `operator_paths` key instead of listing paths |
| I-2 | ADR-003 section 7 heading and lines 48, 82, 126, 164 | Section 7 is headed "Desktop SSH session on the OCI VM"; the "Infra PR" row and RR-5 cite ADR-002, which is superseded | R-1 corrects the OCI VM wording (sections 1, 4 step 6, 7 heading, 9) and the ADR-002 citations (Infra PR row, RR-5, Related row). The CR-45 design PR merged on 2026-11-20 (commit 36ae074), so R-1 waits only for the CR-57 design PR. The `infra/` branch type stays |
| I-3 | ADR-010 decisions 2, 9; CR-45 | The always-loaded budget (20 KiB) counts the repository CLAUDE.md and its imports; CR-57 adds a managed CLAUDE.md and rewrites this repository's CLAUDE.md in step 9 | The ADR-010 budgets apply to this repository's CLAUDE.md as targets from PR 9, with the measured size recorded, and are gated once `size-budget` is adopted. The managed CLAUDE.md counts in the always-loaded set and holds only rules that must not be relaxed. No user-level CLAUDE.md is loaded on a set-up lab |
| I-4 | ADR-010 decision 11; baseline v0.2 sequence | ADR-010 records the static baseline at Stage 5 exit and the full baseline at Stage 7; PA-40 puts "a timed rebuild test and metrics" in Stage 7 | The timed rebuild (AC1-7) is a separate Stage 7 exit item, not part of the metrics baseline. The first AC1-7 timing is taken at the first real lab setup from a tag that contains PR 3 (token step and lab check) and is recorded in PR 4 (round 3, C-3) |
| I-5 | ADR-010 decision 10, tier C | Usage figures are typed by the approver in a session; sessions now run as the AI user on a per-project lab | Yes. The approver types tier C figures in a session the approver starts on that project's lab, and the snapshot is committed in that project's repository by PR |
| I-6 | ADR-008 decisions 5, 6; PA-5, PA-19, PA-25 | The template's CLAUDE.md is owned and "platform-neutral"; `deny-list` compares `.claude/settings.json` with the core list plus `deny.platform.txt` | The `terraform`, `tofu`, and `oci` entries and the PA-19 entries go into the template's owned core list. ADR-008 decision 5's neutrality applies to CLAUDE.md text |
| I-7 | ADR-008 decisions 5, 6, 14; PA-43 | PROJECT.md is project-owned and lists credential paths; `settings.json` is owned and checked against the core list plus `deny.platform.txt` | A project lists its credential-path deny entries in its seeded `.claude/deny.platform.txt`. Lab setup merges that file, read through PA-34's input channel, into the lab's managed settings, and PA-A31 checks them. Template CR T settles how `deny-list` treats entries that managed settings enforce |
| I-8 | ADR-008 decision 11 and ADR-011 decision 17 | The generic `operator.md`, PC-8, `operator-contract`, and `operator_guard.py` are in the template; "the ADR-011 specifics are in the preset's PLATFORM.md"; the specifics now sit in ADR-012 | The preset's PLATFORM.md points to ADR-011 and ADR-012 by qualified reference and describes PA-42. The template's `operator.md` stays generic |
| I-9 | ADR-009 decision 11; PA-22, PA-30 | Generic checks have the same fixtures in both repositories and rule changes go design PR, template, then this repository | This repository changes first (PA-22 in PR 4, PA-30 in PR 6). The template seeds its generic code from a commit after PR 7. ADR-009 decision 11's order applies from that seed on |
| I-10 | ADR-009 decision 14, CR-43 SC-13, SC-20 | The policy inputs are `allowed_actions`, `runner_labels`, `architectures`, `operator_paths`, `release_tags`; PA-22 adds a configured allowlist | The allowlist is a sixth policy input under the key `operator_endpoints`. It lists every host including `api.github.com`, is read from the base commit, and fails closed when missing while `operator_paths` is non-empty. R-1 adds the key to ADR-009 decision 14 |
| I-11 | ADR-008 decisions 8, 9; ADR-005 decision 1 | The template's CI manifest requires both architectures and SHA-256; PA-30 makes this repository amd64 only and the check read the configured list | Yes. The rule is expressed as data: the template's configuration lists amd64 and arm64, and the engine reads the configured list |
| I-12 | ADR-008 decision 12(b), 14; Q3 | Stage 5 exit needs a real run with this platform's preset; Q3 renames this repository before that run | PR 10 lands before the rename. After the approver renames the repository, Claude Code opens a change PR on the approver's instruction that updates the name in `config/project.yaml` and in the preset's configuration. The Stage 5 real run uses the configuration after that PR |
| I-13 | ADR-008 decision 5 precedence sentence; PA-16 | The managed CLAUDE.md, the user-level CLAUDE.md (today "repository instructions take precedence"), and the repository CLAUDE.md all load | The managed CLAUDE.md states that nothing in any other instruction file relaxes its rules. The "repository instructions take precedence" text in `workspace/claude-user/CLAUDE.md` changes in PR 2, not PR 9 |
| I-14 | CR-43 plan PR 6, U-A4; Q1 | CR-43 PR 6 edits `github-desired-state.toml`, a PC-8 path, and its user-only step runs `github-setup` on the operator machine | If ready, CR-43 PR 6 merges and its tag is cut before CR-57 PR 0. Otherwise its U-A4 step runs only from the first tag allowed at or after CR-57 PR 4 |
| I-15 | ADR-009 decision 12 and baseline section 2 | The zero-cost rule cites "baseline section 2"; ADR-009's Related line cites v0.1 sections 3, 6, 7 | No pointer now. R-1 updates the Related line of ADR-009 to baseline v0.2 (v0.2 keeps section 2) |

## 11. Open points, contradictions, and follow-ups (decisions of rounds 2 to 5)

### Contradictions found in the first revision

| ID | Contradiction | Resolution |
|---|---|---|
| C-1 | PA-26 against PA-16 and PA-20: lab setup and operator configuration run only at a release tag, while PA-A28, U-5, and U-7 need real runs during the removal sequence | Resolved by O-3 |
| C-2 | PA-42 against PA-45 and AC1-1: T3 is limited per project, but the allowlist audit must see every repository | Resolved by O-10 |

### Open points (all decided in round 2 unless marked)

| ID | Decision (approver, round 2) |
|---|---|
| O-1 | LC-5 stays undefined and is never reused; no stand-in item is added |
| O-2 | OC-3, OC-4, OC-5, OC-7, and OC-9 are declared. PA-A26 is recorded as supporting evidence for the in-process part of OC-4 |
| O-3 | PA-26 is narrowed. The approver may cut a release tag at any PR boundary whose PA-A16 run is green, except between PR 5 and PR 6. The operator machine moves to a new tag only at or after PR 4. PA-A28 runs on a tag cut after PR 2 and is recorded in PR 3, which adds any permission PA-15 needs (the PA-A28 PR column becomes 3). U-5 and U-7 follow this rule, and the ADR-012 consequences text is updated |
| O-4 | `scripts/toolchain check` requires artifacts for exactly the architectures in `config/project.yaml`; an artifact for an unlisted architecture is an error. PA-30 reads "exactly" instead of "each" |
| O-5 | The ADR-005 decision 9 amendment stands as written. ADR-005 item O5-3 gets a note that the OpenTofu choice is superseded by CR-57 |
| O-6 | No replacement rule is added. The dropped ADR-011 decision 5 points to ADR-001 B3 as amended |
| O-7 | PA-22 is carried by ADR-011 decision 11, which states it after this PR (on `main` it does not yet). The PA-22 note and O-7 are corrected; ADR-012 does not repeat it |
| O-8 | PR 4 deletes `scripts/operator/setup`. The release-tag check becomes a pre-task of both `ansible/lab.yml` and `ansible/operator.yml` |
| O-9 | Confirmed. PR 4 removes `facts --privileged` and the sudo parts of `setup`; root-only facts become manual lines in the operator runbook (PR 9) |
| O-10 | In v1, projects get no `github-setup` and no desired-state file; their repository settings follow ADR-009 decisions 8 and 13. The allowlist audit (PA-45, AC1-1) runs from this repository's `facts` with a read-only T3 that selects all repositories of the personal account, recorded in ADR-012 decision 12 as the one exception to PA-42 |
| O-11 | The PA-A1 exclusion list is confirmed as proposed. The Terraform and OCI rules of `operator_contract.py` stay as generic tool restrictions for operator scripts, consistent with ADR-011 decision 11 and PA-5 |
| O-12 | The ADR-009 status line is corrected in R-1. CR-43 PR 6 corrects `docs/operations/github-setup.md` to match CR-43 design section 12 |
| O-13 | Accepted. PR 10 and template CR T recheck I-6 to I-12 against the template's built files. T starts once the template's owned CLAUDE.md and required-deny list exist |
| O-14 | Reworded in this design PR (see PA-A3, PA-A4, PA-A9, PA-A10 in the acceptance criteria) |
| O-15 | The "one gate profile" of PA-A7 is the lab profile. The operator profile takes manifest membership for Python 3 and git only (OC-6) and installs no gate tools |
| O-16 | Reading confirmed and written into PA-A16: PR 1 uses the existing `builder-profile` and `operator-profile` jobs; PRs 2 and 3 use the PA-28 job for the lab and `operator-profile` for the operator; from PR 4 the PA-28 job covers both |

### Items of round 2

| ID | Decision |
|---|---|
| X-1 | PA-A18 is reworded in this design PR: the checks fail when sshd reads keys from any location other than the root-owned one, and warn on an inert leftover `authorized_keys` file in a user's home (PA-16) |
| X-2 | PR 1's inventory includes the Terraform gate check, its fixtures, and its catalogue row, if they exist at the pinned commit. At `85360e8` none exists (`scripts/checks/` and `tests/quality-gate/catalogue.tsv` hold no Terraform check) |
| X-3 | Baseline v0.2 section 6 reads "steps 0 to 10" |
| X-4 | ADR-002's Status cell states that the record is superseded when the CR-57 design PR merges |
| R-1 | After the CR-57 design PR merges (the CR-45 design PR merged on 2026-11-20, commit 36ae074), one docs-only design PR carries I-1, I-2, I-10, I-15, the ADR-009 status line (O-12) and the ADR-010 status line (Proposed to Accepted, merge of PR 46; O-23), and the "workspace" wording of ADR-009 decision 11. Claude Code opens it on the approver's instruction |

### Round 3 decisions (approver review of 2026-11-23T20:14:13Z on `4cd99e7`)

| ID | Decision |
|---|---|
| O-17 | This repository's CLAUDE.md uses ADR-012's term "AI lab" and never the phrase "lab VM" (nor "AI lab VM"). Plan step 9: "Where you run" describes this repository's AI lab as a disposable VM for this one project (Debian 13, x86-64), reached by Claude Desktop over SSH. PA-A4 and its grep stay as reworded in round 2. PA-A1's final run in PR 9 uses the unchanged command (CLAUDE.md excluded); CLAUDE.md is covered by PA-A4. "Including CLAUDE.md" is removed from plan step 9 |
| O-18 | Confirmed. PR 3 verifies PA-A31 against the effective managed settings, with the credential-path deny entry placed directly in the managed-settings fixture. PR 8 re-runs PA-A31 with the entry arriving from a project's `.claude/deny.platform.txt` through lab setup, plus a fixture where the entry is missing from that file and the lab check fails. Until a tag contains PR 8, a lab for a project that lists credential paths fails the lab check by design |
| C-3 | PA-A28 stays on a tag cut after PR 2. The first AC1-7 timing is taken at the first real lab setup from a tag that contains PR 3 (token step and lab check) and is recorded in PR 4. ADR-001 AC1-7, the ADR-012 consequences, plan PR 3 and PR 4, and U-6 are worded accordingly |
| C-4 | The release-tag pre-task of `ansible/lab.yml` and `ansible/operator.yml` gets no bypass. The PA-28 job runs the playbooks in a disposable clone whose local bare origin has `main` at the PR head and an unpushed local `v*` test tag on that commit. A separate untagged-tree fixture shows the refusal. PA-A11, PA-A16, and PA-A21 evidence names this setup |
| C-5 | PA-28 and ADR-005 decision 7 read: CI applies the lab and operator profiles twice (second run, zero changes) and once in dry run (tree hash unchanged), then runs the token step fixtures and both checks. This matches PA-A11, PA-A16, PA-A21, PA-A29, AC5-4, and AC5-6 |
| C-6 | The `operator_endpoints` key (listing `api.github.com`) is added to `config/project.yaml` in plan PR 0, so it is on the base commit before the PR 4 check reads it. PR 4 keeps the endpoint check and PA-A15 |
| C-7 | ADR-011 decision 4's T3 bullet names the one exception of ADR-012 decision 12 (the allowlist audit's read-only T3 over all repositories of the personal account) |
| C-8 | ADR-012 decision 5 reads "the settings of `workspace/claude-user/` and the non-relaxable rules of its CLAUDE.md". PR 2 splits `workspace/claude-user/CLAUDE.md`: the must-not-relax rules go to the managed CLAUDE.md; the rest moves to this repository's CLAUDE.md (PR 9) or template CR T, or is dropped and listed in PR 2's body |

### Corrections of facts (independent re-review, not decisions)

An independent re-review of `4cd99e7`, relayed by the session that started this one, found the following; each was verified against `main` and GitHub before it was applied. CI on `4cd99e7` failed the `markdown` check (MD036 on two bold lines used as headings); they are headings now.

- The CR-45 design PR (#46) merged on 2026-11-20 (commit `36ae074`, an ancestor of `main`); R-1 waits only for the CR-57 design PR.
- Issue #18 is closed, CR-18 PR 7a (#38) merged on 2026-11-19, and the only open pull requests are #17 and #58; issue #16 is open. Q6 and U-1 carry this state; the approver's Q6 text is kept.
- ADR-011 decision 11 states the endpoint allowlist only after this PR; on `main` it does not.
- The PA-A1 search leaves 28 files at `85360e8` (the count in the criteria said 27).
- The generic deny entries are copied into managed settings; the repository files keep them (PA-5, plan PR 2, PA-A10).
- PA-19 lists the proposed deny entries, the exact PA-A17 command is recorded, plan PR 0 changes `scripts/pr_contract/config.py` (strict reader of one key) and plan PR 1 edits `MANIFEST_PATHS`, and `config/project.yaml` has no `runner_labels` key (the labels are the `runner` and `runner_private` fields); the code defaults that name arm64 are in PA-26.

### Round 4 decisions (approver review of 2026-11-23T20:33:32Z on `b002294`)

| ID | Decision |
|---|---|
| O-19 | Keep a `builder` alias. Plan PR 2 renames the profile to `lab` in `toolchain/manifest.toml` and `PROFILES` but keeps `builder` accepted as an alias, with no change to the `--profile builder` calls of `.github/workflows/ci.yml` and `.github/workflows/pr-contract.yml` (round 5, O-25) (so PR 2's own `pr-contract` run reads a base manifest that still has the name). Plan PR 7 (`remove-superseded`) removes the alias, switches the workflows to `lab`, and reduces `PROFILES` to `lab` and `operator`. The PR 7 row, PA-A5, and PA-A7 say so. No extra PR is added |
| O-20 | CR-57 owns both files, in this order. Plan PR 1 removes the `oci-plan` and `oci-apply` environment entries from `scripts/operator/github-desired-state.toml` (a PC-8 path: the PR carries the PC-8 section) and the matching expectation in `tests/operator/test_githubstate.py`, after CR-43 PR 6 per U-11 if CR-43 PR 6 is ready first. Plan PR 9 edits `docs/operations/github-setup.md` (lines naming the platform operator VM, the OCI description, the lab VM sentence, and the `oci-plan` and `oci-apply` rows). CR-43 PR 6 still corrects the file to match CR-43 design section 12; it does not own the OCI wording. PA-A1 stays unchanged and has no new exclusion |
| O-21 | Add an approver check, new PA-A33 (the number is new; no number is reused). On the first real lab setup and the first real operator configuration, from a tag that contains the matching PR, the approver checks and records in the PR: sshd restarted only after the second login was confirmed; `sshd -T` shows LC-13 (lab) or OC-10 (operator); the unattended-upgrade units are enabled and active (LC-15, OC-12); for the operator machine, that the operator user cannot sudo. PA-A33 sits in PR 3 for the lab and PR 4 for the operator machine, beside PA-A28 (round 5, O-26 moves where the two checks are recorded: the lab check in the body of PR 4, the operator check in the body of PR 5). PA-A11, PA-A16, PA-A18, PA-A21, and PA-A29 keep their CI evidence for the parts a container can prove, and each says which parts it leaves to PA-A33. The ADR-012 consequences text names PA-A33 |
| O-22 | Require reading the dry-run output; no package allowlist in v1. PA-34 and plan PR 8 state that the lab admin reads the dry-run output of a project package list before applying it, and the dry run prints every package name and version it would install. PA-A23 gains a fixture: the dry run of a package list prints each name before anything is installed. A package allowlist is not added; the lab admin's reading is the control, and RR-P2 says so |
| O-23 | Correct the stale `docs/README.md` rows in the design PR; ADR-010's status line goes to R-1. The CR-18, CR-39, and CR-45 rows and the ADR-010 row of `docs/README.md` are updated to what GitHub shows (PR 7a merged; CR-39 and CR-45 design PRs merged; ADR-010 accepted by the merge of PR 46) in this PR; PA-A2 is unaffected (README is not an ADR). R-1 carries the ADR-010 status line (Proposed to Accepted, merge of PR 46) together with the ADR-009 status line. Baseline v0.2 keeps "Accepted" |
| O-24 | Change the arm64 defaults in plan PR 6, in this repository only. `DEFAULT_ARCHITECTURES` in `scripts/pr_contract/config.py` and `DEFAULT_LABELS` in `scripts/checks/workflow_policy.py` list amd64 only after PR 6. The template re-seeds from a commit after PR 7 (I-9) and keeps its own configuration listing amd64 and arm64 (I-11). PR 6 keeps arm64 as sample data in `tests/pr-contract/fixtures/pc9/` and states the divergence from the template in its body until the re-seed. PA-A7's `rg` therefore finds nothing after PR 6 |
| C-9 | Plan PR 2 splits `workspace/claude-user/CLAUDE.md`. Until PR 9 merges, the rules that PR 2 moves out of it remain in the file restored to existing workspaces, so nothing is lost in between: PR 2 removes from that file only the lines it copies into the managed CLAUDE.md, and the rest stays until PR 9 or PR 7 (`restore.sh` removal) deletes it. PR 2's body lists every line it moves, keeps, or drops |

### Round 5 decisions (approver review of 2026-11-23T20:46:44Z on `5f0bfd1`)

| ID | Decision |
|---|---|
| O-25 | Read O-19 as "no change to the `--profile builder` calls". Plan PR 2 keeps the `--profile builder` calls of `.github/workflows/ci.yml` (lines 31, 181-183, 233) and `.github/workflows/pr-contract.yml` (line 40) unchanged, because their runs read a base manifest that still has the name. PR 2 may still edit `ci.yml` elsewhere: it replaces the `builder-profile` job with the PA-28 job, changes the aggregate `needs`, and updates `EXPECTED_NEEDS` and the S-23 fixture. PR 2 carries the PC-6 section (it already does). The PA-28 job stays in PR 2. The sentence of O-19 that says PR 2 "changes none of" those two workflow files is replaced by this reading, in the O-19 row, plan PR 2, PA-A5, and PA-A7 |
| O-26 | Record each PA-A33 check in the body of the next PR to merge after the tag, and say so. The lab check of PA-A33 is taken on the first real lab setup from a tag that contains plan PR 3 (the token step and the lab check). It is recorded in the body of plan PR 4, together with the first AC1-7 timing (C-3), which comes from the same lab setup. The operator check of PA-A33 is taken on the first real operator configuration from a tag that contains plan PR 4 (U-7), cut at the PR 4 boundary. It is recorded in the body of plan PR 5. PA-A28 is unchanged: it runs on a tag cut after PR 2 and is recorded in PR 3. PA-A33's PR column reads "4 (lab), 5 (operator)", and the criteria-by-PR table of the plan moves PA-A33 from PR 3 and PR 4 to PR 4 and PR 5. The plan PR 3 and PR 4 rows no longer say they record PA-A33 as before; the PR 5 row says its body records the operator check; the "body sections" column of PR 5 stays "none" (the record is a line in the body, not a PC section). U-5, U-6, and U-7, and the ADR-012 consequences text, name the new places. "No tag is cut between PR 5 and PR 6" (O-3) is unaffected: the tag for the PR 4 boundary is cut before PR 5 |

### Still open (not guessed)

None.

## 12. Not verified

From the review: at the lab setup PR, Claude Desktop's needs (PA-A28), `ed25519-sk` support on the Windows client (PA-14), whether Debian 13's bash reads startup files for a command run over SSH (LC-14), the managed CLAUDE.md location on Linux, whether managed settings can hold everything in `workspace/claude-user/settings.json`, and how Claude Desktop delivers and updates its engine on the lab and whether anything credential-like is stored under `~/.claude/remote/` (PA-18). At the first removal PR: which files under `scripts/operator/` are OCI-specific and whether the rest is standard library only; whether checks hardcode removed job names (section 3 lists those found); whether PC-8 counts deletions (read in `rules.py`, not run); whether `forbidden-api` and the deny rules match reads; how the aggregate and PC-9 behave when the base lists an architecture whose job the head removed; the GitHub hostnames git and `gh` need, from GitHub's published metadata; how Claude Code's deny rules match SSH command variants.

From this revision: no run exists; the claims of section 3 are read in files at `85360e8`, not executed; CI on the first draft's head was green (the earlier claim that gate tests were only locally failing is withdrawn). After plan PR 1 removes the `oci-plan` and `oci-apply` entries from the desired state (O-20), it is not verified how `github-setup` treats the environments of those names that already exist on GitHub (flag as drift or leave alone); the approver decides what happens to them outside the repository.
