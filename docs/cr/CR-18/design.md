# CR-18 Design: Operator tier

| Field | Value |
|---|---|
| CR | issue #18 (Class 3) |
| Governing records | ADR-001 (decision 5, section 4, B1, B3), ADR-002 (section 2), ADR-003, ADR-005 |
| New record | [ADR-011](../../adr/ADR-011-operator-tier.md) (Proposed). This PR also amends ADR-001 (zones Z6 and Z7, B3, credential rows) and ADR-005 (the `operator` profile) |
| Scope | Design only. No machines, users, credentials, scripts, roles, or workflows are added by this PR. |

## 1. Goal and scope

Give the approver one-command, reviewable procedures for tasks the AI must not or cannot run, without giving any AI user a
credential. The procedures run on two dedicated operator machines. This design covers:

| Part | Deliverable | Section |
|---|---|---|
| a | The two operator machines and their separation from the AI hosts | 3 |
| b | The common contract for operator scripts | 4 |
| c | The scripts, the operator profile, the runbooks, and break-glass | 5 |
| d | Credential handling | 6 |
| e | What the lab build must provide | 7 |

Out of scope:

- The scripts, roles, and workflows themselves (implementation PRs).
- Changing OCI infrastructure from operator scripts (never, ADR-011 decision 5).
- Building the lab operator VM, the alarms, and the rebuilds: CR-16 and ADR-004 do that in a new design PR after this one merges. This design sets the requirements (section 7).
- The new rule PC-8 for ADR-003 (separate design PR) and the changes to `CLAUDE.md` and the deny rules (separate change PR).
- The project-side operator contract (ADR-008).

## 2. Decisions in this design

| ID | Decision | Rationale |
|---|---|---|
| OP-1 | The operator tier is two dedicated machines: the platform operator VM (Z6) and the lab operator VM (Z7). Each has a dedicated operator user without general admin rights, with its own home (mode 700) and its own clone of the repository. The Z1 operator user is retired once the platform operator VM works (Q10, Q25). | Credentials the AI users cannot reach are the point of the tier, and a host boundary is stronger than file permissions on a shared host. |
| OP-2 | Scripts live in `scripts/operator/`, reach `main` through a PR, and run only from the operator's own clone at a release tag. The commit check requires `HEAD` to equal a release tag's commit that is contained in `origin/main`. Tags are created by the approver only, enforced by a tag ruleset (Q29, R3). | The AI can edit its own working tree and push branches. A tag the approver created is what the approver reviewed. |
| OP-3 | Every operator script runs as a dry run by default, and `--apply` is required to execute changes (the approver's decision of 2026-11-18). This includes `setup` and `facts`. The operator profile also refuses a real run unless the explicit apply variable is set. The rule covers operator scripts only. `CLAUDE.md` is unchanged. | The approver's requirement. Nothing else in the repository changes. |
| OP-4 | No OCI credential is stored or typed on any operator machine. Other credentials are prompted for or short-lived, handled in-process, and never stored in the repository, a place an AI user can read, or shell history. | Same handling as T1 in ADR-001 section 4, and tokens never leave the script process (R2). |
| OP-5 | OCI reads use the read-only instance principal of the lab operator VM, and Cloud Shell under the approver's session before that VM exists. GitHub: T2 for `github-setup` apply runs, T3 for read-only fact collection and `github-setup` dry runs (Q3, Q4, R6). | No OCI credential exists to steal or type, and each GitHub token has the smallest permission set for its job. |
| OP-6 | Operator scripts never run Terraform and never create, change, or delete OCI resources. They may read OCI. | An operator script must not become a second deployment path (ADR-002). |
| OP-7 | Standard output is a sanitised summary. Raw responses stay in a private directory in the operator's home. | Public repository conventions, and the report-summaries-only rule of the Gate 0 audit. |
| OP-8 | **Removed.** There is no operator login on the lab VM (Q5 is superseded by the lab operator VM). | The lab operator VM replaces it. The acceptance runner reaches the lab VM over private IPs with a dedicated key (Q28). |
| OP-9 | Implementation order: `operator-lib`, `operator-facts` (host scope), `operator-profile`, `github-setup` with the facts GitHub scope, the facts OCI scope, `acceptance`, `operator-finish` (Q7). Each is a separate PR. | Each PR stays small and reviewable, and the facts script is available early. |
| OP-10 | Operator scripts are held to the quality gate and tested in both modes with stubs, in CI under the memory and CPU limits of the strictest machine profile (Q13). | Same gate as every other script, plus the machines are small. |
| OP-11 | One simple Bash script, `scripts/operator/setup`, installs `ansible-core` from apt and runs the Ansible `operator` profile, in check mode by default. Sudo asks for the password with `timestamp_timeout=0` and no `NOPASSWD` rule, and is allowed only in `setup` and in `facts --privileged` (Q9, Q37, R1, R4). | One reviewable entry point, the same on both machines and in cloud-init. Every other privileged step is a reviewed Ansible task. |
| OP-12 | Operator scripts other than `setup` are Python, standard library only (R2). | Tokens stay inside the script process, no `gh` or `jq` is needed, and the code is testable without a shell. |
| OP-13 | One `facts` script with scopes `host`, `oci`, and `github`, read-only by construction (Q38, Q39, R4 to R6). `oci-audit` is merged into it. | One way to gather facts, usable on both machines and in Cloud Shell. |
| OP-14 | Placement of each script on each machine as in section 5.6 (Q28). | Credentials and tools stay where they are needed. |
| OP-15 | Availability and recovery: the machines are always available and Claude Code never probes them (Q14). The lab operator VM is disposable and rebuilt when removed (Q17). Break-glass for both OCI VMs is a rebuild through the lab stack (Q23, Q24). | Simple recovery with no manual edits outside the stack. |
| OP-16 | Removal of an OCI VM is detected by one OCI Monitoring absence alarm per instance, generated by the lab stack (Q18 to Q20, Q35). | The approver learns about an idle reclamation without a scheduled workflow. |
| OP-17 | Access from Z0 is direct SSH with the OS-bundled OpenSSH, and normal access to the lab operator VM has NSG ingress from the corporate egress only, with no Bastion (Q21, Q22, Q31, Q32). | No script delivery to Z0, and a smaller, simpler access path. |

## 3. The operator machines

### 3.1 The machines

| Aspect | Platform operator VM (Z6) | Lab operator VM (Z7) |
|---|---|---|
| What it is | A human-provided remote machine | A lab OCI VM, separate from the lab VM |
| Reached | Over SSH, with internet access | Over SSH to its public IP, NSG ingress from the corporate egress only (section 7.1) |
| Architecture and OS | x86-64, minimal Ubuntu 24.04 (approver's fact) | x86-64, Always Free micro shape, minimal Ubuntu 24.04 if available for the shape (VO-8) |
| Resources | Unknown until `facts` runs on it | About 1 GB of memory and a fraction of one OCPU (VO-7) |
| Built by | The provider and the approver; configured by `setup` | The lab stack and cloud-init, which calls `setup --apply` |
| Durable state | Operator home (not an AI-host home) | None. The VM is disposable (Q33) |
| Credentials it may hold | T2 and T3 in the script process during a run | The read-only instance principal, and T3 in the script process during a run |

Q16 keeps both on the same OS (Ubuntu), so one profile and one set of tests serve both machines.

### 3.2 Separation rules

Per operator machine:

1. **No shared storage or identity with an AI host:** no shared mount, no shared home, no common account, no common credential.
2. **No key and no route from an AI host:** no AI-host key in the operator's `authorized_keys`, no SSH path from Z1 or Z2 to the machine, and (for Z7) no NSG ingress from the lab VM.
3. **No Claude Desktop SSH target:** the machine is not configured as one, and a check fails if `~/.claude/remote/` exists there.
4. **No T1.** The shared token of the AI hosts is never placed on an operator machine.
5. **Sudo asks for the operator's password**, with `timestamp_timeout=0` and no `NOPASSWD` rule (Q9). No AI user can use it.
6. **The operator's clone and any raw output are in its home only** (mode 700).

The approver tests rules 1 to 5 on each machine after its first operator-profile apply and before any credential is used there (acceptance U-1). If a test fails, this design is revisited. The existing operator user on Z1 is retired once the platform operator VM works (Q25).

**Run flow.** The operator checks out the release tag, runs the script as a dry run, reads the output, and runs it again with `--apply`. Credentials are entered at a prompt during the run (section 6).

### 3.3 Machine profiles

A data file `scripts/operator/machine-profiles.toml` records, per operator machine, the architecture, OS, memory, CPU, disk, and bandwidth, with no identifiers. Tests use it (for example to size the CI limits of OP-10), and `docs/README.md` lists it. The implementation PR `operator-lib` creates it. Entries are filled from `facts` output.

| Field | Platform operator VM | Lab operator VM |
|---|---|---|
| Architecture | x86-64 | x86-64 |
| OS | Ubuntu 24.04 (minimal) | Ubuntu 24.04 (minimal if available, VO-8) |
| Memory, CPU, disk, bandwidth | Filled from `facts` before the `operator-profile` PR | Filled from `facts` after the VM exists; memory about 1 GB is the design input |

## 4. Common contract for operator scripts

| # | Rule | Reason |
|---|---|---|
| 1 | Modes: dry run is the default and `--apply` executes the changes. A script accepts `--dry-run` explicitly too, and rejects both flags together with a usage error. This holds for `setup` and `facts`. | OP-3 |
| 2 | A dry run makes no write call, runs no check, and writes nothing. It lists the calls it would send (for the OCI scope the exact CLI commands, for the GitHub scope the GET paths). A changing script shows the current state against the wanted state. | The approver sees the effect before it happens |
| 3 | Apply mode asks for confirmation before any step that deletes or overwrites. | The last check before a change |
| 4 | Release-tag commit check: the script prints the commit and the tag, and refuses to run with local changes or when `HEAD` does not equal a release tag's commit that is contained in `origin/main`. Tag creation is restricted to the approver by a tag ruleset (R3). | OP-2, Q29 |
| 5 | Language and bounds: Python, standard library only. `setup` is the single Bash exception (`set -euo pipefail`, ShellCheck-clean). A fixed list of operations. No command text from arguments or input, no downloaded code, no Terraform, no `shell=True`, `os.system`, `eval`, or `exec`. Subprocesses are limited to `oci`, `ssh`, `git`, and the allowlisted privileged commands of `facts`. `sudo` appears only in `setup` and in `facts --privileged`. | OP-6, OP-11, OP-12 (R2) |
| 6 | Idempotent: running apply twice changes nothing the second time. An interrupted run is safe to repeat. | Safe to repeat after a failure |
| 7 | Output: a sanitised summary (yes/no, counts, sizes) on standard output, passed through the shared sanitiser. Raw responses go to a directory in the operator's home with mode 700, with a size cap and cleanup. A value the sanitiser cannot classify becomes a placeholder. | OP-7 |
| 8 | Exit codes: 0 success, 1 a check or call failed, 2 usage error, 77 skipped because a prerequisite (tool or network) is missing. | Same convention as the quality gate |
| 9 | Credentials: tokens are read with `getpass` and kept in the script process. They never appear in a child process environment, in `argv`, or on disk. The OCI CLI is called as a subprocess with argument arrays, never with `shell=True`. GitHub REST calls use `urllib` through the `pr-contract` API client. | OP-4 (R2) |
| 10 | Read-only mode: the shared HTTP client has a read-only mode that raises on any method other than GET before sending a request. `facts` uses only that mode. The OCI scope uses only `list`, `get`, and `inspect` verbs. | R6 |
| 11 | Resources: calls run sequentially, pagination is bounded, large responses stream to disk, the raw-output directory has a size cap and is cleaned, timeouts are sized for the slowest profile, and no tool needs more than the profile's memory budget. | Q13: the machines are small |
| 12 | Availability: Claude Code assumes the operator machines are available and never probes them. | Q14 |
| 13 | Tests: both modes with stub CLIs and a stub HTTP server, run in CI under the memory and CPU limits of the strictest machine profile. | OP-10, S-10 |

The shared module `scripts/operator/lib/` implements rules 1, 2, 4, 7 to 10 once: the modes, the release-tag commit check, the sanitiser, the exit codes, and the HTTP client with its read-only mode. Each script then only lists its operations. It reuses the `pr-contract` API client for GitHub.

**Kept statements.**

- **PC-8.** A rule PC-8 for ADR-003, an "Operator script review" section required for changes under `scripts/operator/`, `ansible/operator.yml`, its roles, and their data files, is proposed in a separate design PR. This design relies on it but does not define it.
- **Extended gate patterns.** The gate rejects the patterns of rule 5, any OCI verb other than `list`, `get`, or `inspect` in the OCI scope, any HTTP method other than GET in `facts`, and `sudo` outside `setup` and `facts --privileged` (acceptance S-6 and S-11).
- **Dry-run limitation.** The dry-run rule covers operator scripts only. `CLAUDE.md` and the Bash convention for other scripts are unchanged.
- **Optional inbound allowlist.** The profile reads the inbound source allowlist for SSH from an operator-local file outside the clone. The file is optional: when it is absent the apply run says so and the firewall role adds no source restriction. The implementation PR `operator-profile` confirms this behaviour with the approver.

## 5. The scripts, the profile, and the runbooks

The scripts are not built by this design. This section fixes what each one replaces and what stays manual.

### 5.1 Facts (`facts`)

One script for both operator machines (R4, R5, R6), Python standard library, with the release-tag commit check. It replaces the manual parts of `docs/operations/gate-0-audit.md` that gather machine and OCI facts, and the facts template of the stages.

| Aspect | Design |
|---|---|
| Modes | Dry run lists the checks. For the OCI scope it prints the exact CLI commands and for the GitHub scope the GET paths. `--apply` runs them and writes only local state files (mode 600) in the operator's home |
| Output | The facts template and a machine-profile entry (section 3.3) with safe values only, passed through the sanitiser. Off-host facts (provider firewall and access, the SSH path from Z0, corporate approval) are printed as manual lines |
| `--scope host` | Versions, resources, time sync, account and sudo-member counts, listening ports, firewall service state, home persistence (a marker and the boot ID), egress stability (a salted local hash of `$SSH_CLIENT`, reported only as stable yes/no and the count of distinct values), and with `--measure-bandwidth` the timing of one manifest artifact download through `urllib`, which is discarded |
| `--write-allowlist` | Writes the current egress address into the operator-local allowlist file without printing it |
| `--privileged` | Runs only a fixed list of read-only root commands with fixed arguments: `sshd -T`, `nft list ruleset`, a file count of `/etc/sudoers.d`, and a `sudo -n true` probe. It asks for the sudo password each time. Without `--privileged` the script never calls sudo |
| `--scope oci` (R5) | On the lab operator VM with the instance principal. It reports limits and usage (A1, micro, public IPv4, block storage, volume backups, alarms, Notifications), one alarm per instance (Q20), and IP retention, as counts and yes/no. Only `list`, `get`, and `inspect` verbs (gate-checked). Before the lab operator VM exists the same script runs in Cloud Shell from an anonymous clone at a release tag, under the approver's session, with the dry run printing the exact commands first. Fallback: the approver reads the values in the Console |
| `--scope github` (R6) | GET only, unauthenticated where VO-17 allows, otherwise with T3. It reports rulesets (including the R3 tag ruleset), the collaborator count, security features, environments, and settings, as yes/no and counts |

Principles (Q38, Q39): facts are gathered by scripts on the operator machines (host facts on the host they describe, OCI facts on the lab operator VM), sudo only where a fact absolutely requires it, and fact collection may use API tokens to other environments with read-only access only, enforced in code (rule 10).

### 5.2 GitHub setup (`github-setup`)

| Today | With the script | Stays manual |
|---|---|---|
| `docs/operations/github-setup.md`: Console steps for repositories, settings, security features, rulesets, environments, collaborators | Idempotent GitHub REST calls through `urllib` from a desired-state file in the repository (no identifiers; logins are inputs). The dry run uses T3, shows current against wanted settings, makes no write call, and lists the calls. The apply uses T2 | Account hardening, creating the machine account, creating tokens, connecting the chat integration (Parts 1, 2, 10, 11 by their headings), and applying the R3 tag ruleset (the first release tag needs it) |

It runs on the platform operator VM. At the end of each run it reminds the approver to revoke the token used (RR-OP-4). The exact permissions per API call and the fine-grained token type for personal-account repositories are verified first (VO-3, VO-4, VO-17).

### 5.3 Acceptance tests (`acceptance`)

| Today | With the script | Stays manual |
|---|---|---|
| The B, L, K, and C tests of CR-16, and the V2 checks, run one by one from the acceptance tables | One runner reports yes or no per criterion ID, as a dry run (lists the checks) and with `--apply` (runs them) | Tests that need the Console, a second network, a reboot, or a stop and start of the instance |

It runs on the lab operator VM. OCI checks are read-only through the instance principal. On-VM checks run over SSH to the lab VM with a dedicated key over private IPs inside the VCN. The runner changes nothing in OCI (OP-6).

### 5.4 Operator workspace setup (`setup`)

Decided by the approver (Q37). It replaces installing tools and configuring the machine by hand.

| Aspect | Design |
|---|---|
| Language | Bash, the single exception to OP-12. ShellCheck-clean, `set -euo pipefail` |
| Inputs | Only `--dry-run` and `--apply`. It accepts no other arguments and never takes command text from input |
| Release tag | It checks that it runs from a release tag (rule 4) |
| Dry run (default) | It installs nothing. It runs `ansible-playbook ansible/operator.yml --check --diff` only after confirming that `ansible-core` is present, otherwise it prints the apt command it would run |
| `--apply` | It runs `sudo apt-get install ansible-core`, then `ansible-playbook ansible/operator.yml --ask-become-pass -e operator_apply=true` |
| As root | When run as root (cloud-init on the lab operator VM, `--apply`) it skips sudo |
| Sudo | Allowed only here and in `facts --privileged` (R4). A gate check rejects it elsewhere |
| Scope | Installs and configures. It creates no credential, signs in nowhere, and changes no OCI or GitHub setting |
| Who runs it | The operator by hand, or cloud-init on the lab operator VM. The AI never runs it |

### 5.5 The operator profile (`ansible/operator.yml`)

The one Ansible playbook for both machines (R1), written for minimal Ubuntu 24.04, idempotent, with tool membership from the manifest `profiles` field (ADR-005 decision 10).

- **Hardening:** key-only SSH, password login off, automatic security updates with a fixed reboot window.
- **Sudoers:** `timestamp_timeout=0`, no `NOPASSWD` rule (Q9).
- **Inbound allowlist:** the SSH source allowlist is read from an operator-local file outside the clone (optional, section 4).
- **Firewall:** a role with a timer-based revert, which undoes the change unless it is confirmed from a second session (RR-OP-14).
- **Packages:** apt packages from a fixed list in the repository.
- **Tools:** tools through `scripts/toolchain`, and the OCI CLI in a hash-locked venv from `toolchain/python/operator.lock`.
- **Apply guard:** a pre-task refuses a real run unless the explicit apply variable is set.
- **Lock play:** a separate tagged play locks the initial admin account's SSH access. It runs only after an operator login is confirmed from a second session.
- **Separation checks** as a final task (section 3.2), and an idempotence guarantee: a second apply reports no change.
- **Privileged steps** outside `setup` and `facts --privileged` exist only as Ansible tasks with `become`.
- The first run, from the provider's initial admin account, creates the operator user. The operator's sudo password is set interactively then and never stored in the repository.

### 5.6 Placement

| Script | Platform operator VM | Lab operator VM | Cloud Shell |
|---|---|---|---|
| `setup` and the operator profile | Yes | Yes (cloud-init, `--apply`) | No |
| `facts` host scope | Yes | Yes | No |
| `facts` GitHub scope | Yes | Allowed | No |
| `github-setup` | Yes | No | No |
| `facts` OCI scope | No | Yes | Yes, before the lab operator VM exists |
| `acceptance` | No | Yes | No |

### 5.7 Runbooks

**Platform operator VM** (the full text goes to `docs/operations/operator.md` in `operator-finish`):

1. `sudo apt-get install git` (minimal Ubuntu has no git, VO-15).
2. Anonymous clone, checked out at the release tag.
3. `facts` as a dry run, then `--apply`, then `--apply --privileged`, and `--write-allowlist` when the egress is confirmed stable.
4. `setup` as a dry run, and review of its output.
5. `setup --apply`, which asks for the sudo password.
6. Confirm an operator login from a second session, then run the lock play.
7. Run the separation test U-1.
8. Only then, the first credential.

**Lab operator VM.** Cloud-init clones the release tag named in a stack variable and runs `setup --apply`. The operator then runs `facts` (host and OCI scope). Before the VM exists, `facts --scope oci` runs in Cloud Shell from an anonymous clone at a release tag.

### 5.8 Access from Z0

Direct SSH with the OS-bundled OpenSSH (Q21, revised). `docs/operations/operator.md` holds `~/.ssh/config` templates with placeholders only, one entry per OCI VM:

| Setting | Value |
|---|---|
| `Host` alias, `HostName`, `User` | Placeholders |
| `IdentityFile` | One dedicated key per VM |
| `ProxyJump` | Through the corporate hops if needed |
| `HostKeyAlias` | One per VM |
| `StrictHostKeyChecking` | `yes` |
| `ForwardAgent` | `no` |

After a rebuild the host key changes. The runbook step: compare the new key with the instance console output, then `ssh-keygen -R` the old one. No PowerShell script, and CHG-001 stays in force.

### 5.9 Break-glass: rebuild through the lab stack

Q23 and Q24. Failure cases:

| Case | Failure |
|---|---|
| F1 | The corporate egress address changed |
| F2 | An NSG error |
| F3 | A host-side fault |
| F4 | A lost key |

The approver corrects the allowlist or the public-key stack variables if needed and applies the lab stack with an in-place boot-volume replacement of the affected VM, or a recreation only if the instance is already gone. The apply is a Console job in Stages 2 and 3 and a `workflow_dispatch` apply behind `oci-apply` in Stage 4. The read-only serial console history may be used for diagnosis. There is no Bastion, no console connection, and no manual edit outside the stack. After a lab VM rebuild the approver re-enters T1 and verifies the host key.

## 6. Credential handling

| Credential | Where | Handling |
|---|---|---|
| OCI, on the lab operator VM | The VM's read-only instance principal | No stored or typed credential. Standing read-only access to the lab compartment and to tenancy limits and resource availability (RR-OP-27). No write rights |
| OCI, before that VM exists | Cloud Shell, the approver's own session | Runs the OCI scope from an anonymous clone at a release tag, restricted to `list`, `get`, and `inspect` |
| GitHub token **T2** | Prompt only, platform operator VM, in the `github-setup` process | Fine-grained token of the personal account, the two repositories only. Administration and Environments read and write, Metadata read. No Contents, Pull requests, Workflows, or Secrets write. 1-day expiry. Entered only for `github-setup` apply runs. Revoked in the browser after each run |
| GitHub token **T3** (R6) | Prompt only, either operator machine, in the script process | Fine-grained token of the personal account, the two repositories only. Administration read, Environments read, Metadata read. 1-day expiry. For `facts --scope github` and the `github-setup` dry run. Revoked after each run. Read-only is enforced in code by the GET-only client |
| T1 | Unchanged | The AI hosts' token. Never placed on an operator machine. Re-entered on Z2 after a lab VM rebuild |
| Operator sudo password | Set interactively at the first profile run | Never in the repository (Q9) |
| SSH keys | Z0 | One dedicated key per operator machine, never shared with the lab VM key. The key from the lab operator VM to the lab VM is dedicated and used by `acceptance` |

**General rule for any further environment** (Q39): one dedicated read-only credential, prompt-only, in-process, with the shortest practical expiry, revoked after use, and its own ADR-001 matrix row. T2 is never used for fact collection.

The ADR-001 zones and matrix rows for all of these are added in this PR (ADR-001 section 3 and section 4).

## 7. What the lab build must provide

These are requirements for CR-16 and ADR-004. They are added to CR-16 by a new design PR after both changes are merged. CR-16 is not edited by this PR.

### 7.1 The lab operator VM

- **Shape and image:** Always Free micro shape (x86-64), Canonical minimal Ubuntu 24.04 image if available for the micro shape (VO-8), with the Oracle Cloud Agent monitoring plugin enabled.
- **Configuration:** cloud-init running `setup --apply` from a release tag named in a stack variable.
- **Storage:** the default boot volume only, no block volume, no volume backups, nothing durable (Q33).
- **Network:** a public subnet with the reserved public IP (Q32, conditional on VO-12). NSG ingress for SSH from the corporate egress only. No Bastion. Never reached through the lab VM, and no ingress from the lab VM.
- **Identity:** its own dynamic group matched by compartment and tag, with read-only rights in the lab compartment and read-only access to tenancy limits and resource availability (Q3, R5), created by the bootstrap stack. No OCI write rights.
- **Lifecycle:** rebuilt when removed (Q17). Idle reclamation is detected by the absence alarm (section 7.3).

### 7.2 Rebuild as break-glass (Q23, Q24, Q30, Q31)

- Both OCI VMs can be rebuilt through the lab stack by in-place boot-volume replacement. A recreation is used only when the instance is already gone.
- The lab VM keeps everything durable on `/srv/work` or in GitHub, so a rebuild loses only the boot volume and uncommitted work on it.
- D5 (the block volume for `/srv/work`) is about 50 GB or less, so that the two boot volumes and the temporary second boot volume of a replacement fit in the 200 GB Always Free block storage. The baseline proposes about 100 GB for D5, so the CR-16 design PR must lower it. More is allowed only if VO-14 shows 47 GB boot volumes, or deletion of the old boot volume during replacement.
- The allowlist addresses, the SSH public keys, and the cloud-init release tag are stack variables, so one apply also fixes them.
- D4 is aligned: an SSH allowlist for normal access, rebuild as break-glass, and no Bastion. This is recorded in the CR-16 design PR.
- The lab VM uses an ephemeral public IP (Q32). The public IPv4 limit leaves no address for a third VM (RR-OP-22).

### 7.3 Absence alarms (Q19, Q20, Q35)

- Every VM in the lab stack has its own absence alarm on `CpuUtilization` in `oci_computeagent`, with `groupBy` in the query, generated by the stack for every instance it defines and referencing that instance. No compartment-wide alarm.
- Parameters: an absence detection period of 72 hours, a repeat notification every 12 hours while firing, a trigger delay of 15 to 30 minutes (longer than a reboot), and suppression windows for planned stops and rebuilds set by the approver.
- One Notifications email topic. The recipient is a stack variable and never appears in the repository.
- The plan allowlist check rejects an instance without an alarm. Monitoring and Notifications are added to the plan allowlist and the compartment quotas allow them. No instance principal holds Monitoring write rights.

### 7.4 Recovery after an alarm (Q34, Q36)

- The approver starts a stopped VM. A VM is rebuilt only when it was terminated: the lab operator VM per Q17, and the lab VM per ADR-006 and ADR-007 with Q23 and Q24.
- The rebuild is a Console job in Stages 2 and 3 and a `workflow_dispatch` apply behind `oci-apply` in Stage 4. There is no scheduled workflow and no automated apply.
- Claude never detects or triggers a recovery. Alarm emails are never pasted into chat or a PR.
- After a rebuild the approver verifies the SSH host key against the instance console output. No fingerprint is written in the repository.

## 8. Risks

Numbers RR-OP-9, RR-OP-13, RR-OP-20, RR-OP-21, and RR-OP-24 are not used.

| ID | Risk | Mitigation |
|---|---|---|
| RR-OP-1 | AI-written code runs with credentials the AI never sees, so a mistake or a prompt injection could become a destructive call or a leak | Release-tag check, review by the approver (PC-8), fixed operation list, dry run before apply, short-lived in-process credentials, sanitised output, no Terraform, no OCI writes |
| RR-OP-2 | An operator machine shares storage or identity with an AI host, or an AI host has a key or a route to it | Separate machines. The separation rules of section 3.2, the per-machine test U-1 after the first profile apply and before the first credential, the `~/.claude/remote/` check, and no T1 on an operator machine. If a test fails, this design is revisited |
| RR-OP-3 | The sanitiser misses an identifier and the approver pastes it into chat or a PR | Filters by pattern for OCIDs, addresses, and email addresses, a placeholder when unsure, safe-value-only fields, tests with sample output, and the existing `public-repo-hygiene` check on anything committed |
| RR-OP-4 | A token outlives its use | 1-day expiry, revoked after each run, and the script reminds the approver at the end |
| RR-OP-5 | The operator runs an older release tag | The script prints the commit and the tag, and the runbook starts by fetching tags and checking out the tag the approver names |
| RR-OP-6 | Exposure of both operator machines, including the public IP of the lab operator VM, to the internet or the corporate network | Key-only SSH, NSG ingress from the corporate egress only (Z7), the host firewall with the optional source allowlist, hardening and automatic security updates, no stored credential, no route from AI hosts, no ingress from the lab VM |
| RR-OP-7 | The OCI CLI is not installed, and `CLAUDE.md` forbids Claude from installing software | The operator profile installs it from a hash-locked venv, run by the operator (section 5.5, VO-7) |
| RR-OP-8 | Sudo on an operator machine, so AI-written code that the operator runs could reach root | Sudo only in `setup` and in `facts --privileged` for a fixed list of read-only commands with fixed arguments. Every other privileged step is a reviewed Ansible task with `become`. Sudo asks for the password every time (`timestamp_timeout=0`, no `NOPASSWD`). A gate check rejects `sudo` elsewhere, and the approver reviews `setup`, the profile, and `facts` with extra care |
| RR-OP-10 | T2 can remove rulesets during its 1-day lifetime | Limited to apply runs (R6), two repositories only, entered at a prompt, revoked in the browser after each run |
| RR-OP-11 | Other holders of root on the platform operator VM (a human-provided machine) can read the operator's files and process memory during a run | Nothing is stored on the machine, tokens live one day and in-process only and are revoked after each run, and `facts` reports the account and sudo-member counts. The approver treats root holders as part of the trust base |
| RR-OP-12 | An OCI VM is stopped or reclaimed as idle by Oracle | The absence alarms (section 7.3), recovery per section 7.4 and Q34, and Oracle's idle email as a backstop |
| RR-OP-14 | Lockout during the first profile apply (a firewall or SSH change) | The firewall role reverts on a timer unless confirmed from a second session, and the initial admin account is locked only by a separate play after an operator login is confirmed |
| RR-OP-15 | A new host key is accepted without verification after a start or a rebuild | `StrictHostKeyChecking yes`, a runbook step comparing the key with the instance console output, and then `ssh-keygen -R` |
| RR-OP-16 | An alarm stops firing after the 72-hour absence detection period | Oracle's idle email remains the backstop, and the repeat notification every 12 hours covers the period |
| RR-OP-17 | A false alarm when the monitoring agent stops, including an agent stopped by the AI on the lab VM | It leads to a check, never to an automatic action |
| RR-OP-18 | A VM created outside the lab stack has no alarm | Every VM is created through the stack, and the compartment quotas limit what else can exist |
| RR-OP-19 | The SSH key from the lab operator VM reaches the AI-operated lab VM | Accepted: the operator is the more trusted side. The key is dedicated, used by `acceptance` only, and its public part is a stack variable |
| RR-OP-22 | The lab VM's ephemeral IP changes if it is ever recreated, and the public IPv4 limit leaves no address for a third VM | Access uses a host key alias and the runbook of section 5.8. VO-12 checks the limits |
| RR-OP-23 | Break-glass needs a stack apply, so recovery takes longer than an interactive path, and uncommitted work on the lab VM's boot volume is lost | Everything durable lives on `/srv/work` or in GitHub (section 7.2). The elapsed time of a rebuild is recorded (W-2) |
| RR-OP-25 | A recreated A1 instance may fail on host capacity | In-place boot-volume replacement keeps the instance, and a recreation is only for an instance that is already gone |
| RR-OP-26 | Storage headroom for an in-place replacement limits D5 to about 50 GB | Recorded as a requirement for CR-16 (section 7.2), and VO-14 checks the real boot-volume sizes |
| RR-OP-27 | The read-only instance principal gives every process on the lab operator VM standing read access to the lab compartment and to tenancy limits | Read-only rights only, no write rights, nothing durable on the VM, and the VM is reachable only by the approver |
| RR-OP-28 | A release tag moved by anyone but the approver would let an unreviewed commit pass the commit check and be applied by cloud-init | The tag ruleset restricts `v*` tags to the approver (R3), with a negative test from the machine account (U-4) |
| RR-OP-29 | The facts output pasted into chat or a PR could leak an identifier if the sanitiser misses one | Safe-value-only fields, canary tests (F-1), and the `public-repo-hygiene` check |
| RR-OP-30 | `facts --privileged` runs AI-written code that invokes root commands | A fixed command list with fixed arguments, the gate check, the password prompt each time, and review |
| RR-OP-31 | `facts --scope oci` in Cloud Shell runs AI-written code with the approver's admin session | `list`, `get`, and `inspect` verbs only, the gate check, a dry run that shows the exact commands, and review |
| RR-OP-32 | A read-only token such as T3 still discloses repository configuration if stolen during its 1-day lifetime | Read-only permissions, two-repository scope, in-process handling, and revocation after each run. A token created with write permission by mistake still cannot write through `facts`, because the client is GET-only |

## 9. Verification items

Documentation checks or read-only inspection. Anything that creates credentials or changes systems is an explicit action by the approver. Where documentation does not settle a question, the approver runs a trial.

| ID | Question | Method | Needed before |
|---|---|---|---|
| VO-1 | The read-only instance principal (with tenancy limits read) covers every call of the OCI scope | Oracle IAM and CLI documentation, then a Cloud Shell or lab check | PR 5 (facts OCI scope) |
| VO-3 | The T2 and T3 permissions per API call for repository settings, security features, rulesets, and environments, and the fine-grained token type for personal-account repositories | GitHub documentation | PR 4 (`github-setup`) |
| VO-4 | The exact GitHub REST calls and desired-state fields for the settings, rulesets, and environments of `docs/operations/github-setup.md` | GitHub REST documentation | PR 4 |
| VO-7 | The OCI CLI, the Oracle Cloud Agent monitoring plugin, `ansible-core`, and the operator profile run together in 1 GB | Documentation, then a trial on a micro instance | The CR-16 design PR |
| VO-8 | The micro shape's availability domain, and the Ubuntu 24.04 (minimal) image for the micro shape | Oracle documentation and the Console | The CR-16 design PR |
| VO-9 | The platform operator VM matches the OCI image (same OS release and packages) | `facts` on both machines | The CR-16 design PR |
| VO-10 | A dynamic group matched by compartment and tag covers a recreated instance | Oracle IAM documentation | The CR-16 design PR |
| VO-11 | Idle reclamation behavior: stop or terminate, and the notice given | Oracle Always Free documentation | The CR-16 design PR |
| VO-12 | Public IPv4 limits (2 ephemeral, 1 reserved reported) and IP retention on stop, start, and in-place replacement | Oracle documentation, `facts --scope oci` | The CR-16 design PR |
| VO-13 | Alarm behavior (absence detection including whether a 72-hour period is supported, trigger delay, repeat notification, suppression, `groupBy`) and the Always Free limits for alarms and Notifications | Oracle Monitoring documentation | The CR-16 design PR |
| VO-14 | In-place boot-volume replacement keeps the instance, its IP, the alarm identifier, and the block volume, and its storage need (47 GB boot volumes, deletion of the old volume) | Oracle documentation, then a trial by the approver | The CR-16 design PR |
| VO-15 | On minimal Ubuntu 24.04, `python3` is present and `git` and `curl` may be absent. The bootstrap installs `git` from apt before the first clone | `facts` on the platform operator VM and a minimal image check | PR 2 (`operator-facts`) |
| VO-16 | An IAM policy can give the lab operator VM's dynamic group read-only access to limits and resource availability at tenancy level without any other tenancy-level right, and Cloud Shell can run the OCI scope from an anonymous clone with the approver's session | Oracle IAM documentation, then a Cloud Shell check | PR 5 (facts OCI scope) |
| VO-17 | Which GitHub facts (rulesets, the R3 tag ruleset, collaborators, security features, environments, repository settings) are readable without a token on public repositories, and which need T3 with Administration read or Environments read | GitHub REST documentation | PR 4 |

Other open inputs:

- **Platform operator VM facts** beyond architecture and release (now known): collected by `facts` (host scope, with `--privileged` where required) and its manual lines. Needed before PR 3 (`operator-profile`).
- **CR-16 inputs (verify first):** an A1 allowance of 2 OCPU and 12 GB in total (fully used by the lab VM); five volume backups shared; A1 capacity risk when an instance must be recreated; Monitoring and Notifications in the plan allowlist and the compartment quotas; console output available for host-key verification; cloud-init able to run `setup --apply` from a release tag; OCI limits gathered by `facts --scope oci` in Cloud Shell or read in the Console. Needed before the CR-16 design PR.

Closed by this revision: VO-2 (the OCI CLI source and checksums) and VO-6 (the package list) are content of the `operator-profile` PR, bounded by ADR-005 decision 10. VO-5 (sudo configuration) is acceptance U-1.

## 10. Decisions, rejections, and open items

Source: the approver's review "Decision handoff: CR-18: 2026-11-18" on PR #19. "ADR-011 d7" means ADR-011 decision 7.

### 10.1 Decided (approver, 2026-11-18)

| # | Decision | Recorded in |
|---|---|---|
| Q1 | The accepted ADR-001 amendment applies to the revised wording: no OCI credentials and no T2 or T3 on Z1 or Z2; operator machines may hold the credentials defined in ADR-011 | ADR-011 d7, ADR-001 header and section 4 |
| Q2 | Dry run by default and `--apply` to execute (answered earlier, unchanged) | OP-3, ADR-011 d2, section 4 rule 1 |
| Q3 | OCI reads run on the lab operator VM with a read-only instance principal (dynamic group by compartment and tag, created by the bootstrap stack, read-only access to tenancy limits and resource availability per R5). No OCI credential is stored or typed on any operator machine. Gate 0 and pre-CR-16 OCI facts run in Cloud Shell under the approver's session. Conditional on VO-1, VO-10, VO-16 | ADR-011 d4, OP-5, section 6 |
| Q4 | T2: fine-grained token of the personal account, two repositories, Administration and Environments read/write, Metadata read (no Contents, Pull requests, Workflows, or Secrets write), 1-day expiry, read with `getpass`, in the `github-setup` process, apply runs only, revoked in the browser after each run, platform operator VM only. Conditional on VO-3, VO-4 | ADR-011 d4, section 6 |
| Q5 | Superseded by the lab operator VM: no operator login on the lab VM | ADR-011 d8, OP-8 removed |
| Q7 | Order: `operator-lib`, `operator-facts` (host scope), `operator-profile`, `github-setup` with the facts GitHub scope, facts OCI scope (replaces `oci-audit`, usable in Cloud Shell before CR-16), `acceptance`, `operator-finish`. The host-separation test runs after the first profile apply and before the first credential on each machine | ADR-011 d9 and d17, OP-9, implementation plan |
| Q8 | Implementation PRs that do not need OCI start after this design merges. Scripts that need the lab operator VM wait for CR-16 to be merged and applied | ADR-011 d17, implementation plan |
| Q9 | Sudo asks for the password, with `timestamp_timeout=0`, on both operator machines. No `NOPASSWD` rule | ADR-011 d10, OP-11, sections 3.2 and 5.5 |
| Q10 | Operators run on dedicated machines separated from the AI hosts. Platform: a human-provided remote machine reached over SSH with internet access. Lab: an operator VM on OCI, part of the lab, separate from the lab VM, reached over SSH by the operator of future AI projects built in the lab | ADR-011 d1, OP-1, section 3 |
| Q11 | The lab operator VM is a lightweight x86 machine within the OCI Always Free tier | ADR-011 d1, sections 3.1 and 7.1 |
| Q13 | The resource constraints of the operator machines are a design input for every operator script written by the AI | ADR-011 d11, section 4 rule 11, OP-10 |
| Q14 | The operator machines are always available. Claude Code assumes this and never probes them (revised) | ADR-011 d11, section 4 rule 12 |
| Q16 | The platform operator VM runs the same OS as the OCI operator VM (Ubuntu). Fact: it is x86-64 and runs minimal Ubuntu 24.04 | ADR-011 d1, section 3.1, ADR-005 d10 |
| Q17 | The lab operator VM is rebuilt when it is removed (for example by idle reclamation) | ADR-011 d14, section 7.1 |
| Q18 | Removal of the lab operator VM is detected by an OCI Monitoring absence alarm. A scheduled GitHub workflow is not pursued | ADR-011 d15, section 7.3 |
| Q19 | The absence alarm is used for all VMs running on OCI | ADR-011 d15, section 7.3 |
| Q20 | One absence alarm per instance, generated by the lab stack for every instance it defines and enforced by a plan allowlist rule that rejects an instance without an alarm. No compartment-wide alarm | ADR-011 d15, section 7.3, L-2 |
| Q21 | Access from the Windows laptop to the lab VM and the lab operator VM is direct SSH with the OS-bundled OpenSSH, through `~/.ssh/config` entries from a runbook template (one entry and one dedicated key per VM). No PowerShell script. CHG-001 stays in force (revised) | ADR-011 d16, section 5.8, W-1 |
| Q22 | Normal access to the lab operator VM is direct SSH to its public IP with NSG ingress from the corporate egress only. No Bastion (revised) | ADR-011 d16, section 7.1 |
| Q23 | Break-glass for the lab VM and the lab operator VM is a rebuild through the lab stack | ADR-011 d14, sections 5.9 and 7.2, W-2 |
| Q24 | Break-glass rebuilds replace the boot volume in place on both OCI VMs. An instance is terminated and recreated only when it is already gone. D5 stays at about 50 GB or less to keep room for the temporary second boot volume within the 200 GB Always Free block storage (more only if VO-14 shows 47 GB boot volumes or deletion of the old boot volume during replacement) | ADR-011 d14, section 7.2 |
| Q25 | The existing operator user on Z1 is retired once the platform operator VM works | ADR-011 d1, section 3.2 |
| Q26 | CR-18 sets the requirements for the lab operator VM, the OCI alarms, and the rebuilds. CR-16 and ADR-004 build them in a new design PR. ADR-008 carries the project-side operator contract | ADR-011 d17, sections 1 and 7 |
| Q28 | Placement: `setup`, the operator profile, and `facts` (host scope) on both machines. `github-setup` and `facts` (GitHub scope) on the platform operator VM, with the GitHub scope also allowed on the lab operator VM. `facts` (OCI scope) and `acceptance` on the lab operator VM, and `facts` (OCI scope) in Cloud Shell before it exists. `acceptance` reaches the lab VM with a dedicated SSH key over private IPs inside the VCN | ADR-011 d13, section 5.6 |
| Q29 | Operator scripts and the profile run from release tags only. The commit check requires `HEAD` to equal a release tag's commit contained in `origin/main`. Tags are created by the approver only (enforced by R3) | ADR-011 d3, section 4 rule 4, S-3 |
| Q30 | Everything durable on the lab VM lives on `/srv/work` or in GitHub, so a rebuild loses only the boot volume. The approver re-enters T1 after a lab VM rebuild | ADR-011 d14, section 7.2, ADR-001 |
| Q31 | D4 is aligned with Q22 to Q24 for both OCI VMs: SSH allowlist for normal access, rebuild as break-glass, no Bastion (recorded in the CR-16 design PR) | ADR-011 d16, section 7.2 |
| Q32 | The reserved public IP goes to the lab operator VM and the lab VM uses an ephemeral IP. Conditional on VO-12 | ADR-011 d16, section 7.1 |
| Q33 | The lab operator VM is disposable: no block volume, no volume backups, nothing durable | ADR-011 d14, section 7.1 |
| Q34 | After an alarm, a stopped VM is started. It is rebuilt only when it was terminated. Conditional on VO-11 | ADR-011 d14, section 7.4 |
| Q35 | Alarm parameters for all OCI VMs: 72-hour absence detection period, repeat notification every 12 hours while firing, trigger delay of 15 to 30 minutes (longer than a reboot), `groupBy` in the query, suppression windows for planned stops and rebuilds set by the approver | ADR-011 d15, section 7.3 |
| Q36 | Recovery after an alarm: the lab operator VM per Q17 and Q34, the lab VM per ADR-006 and ADR-007, Q23 and Q24 | ADR-011 d14, section 7.4 |
| Q37 | A simple `setup` script (`scripts/operator/setup`, Bash) triggers the runbook commands: install `ansible-core` from apt, run the operator profile in check mode by default, and apply it with `--apply`. It follows the operator script contract. Cloud-init on the lab operator VM calls the same script with `--apply`. Sudo is allowed only in `setup` and in `facts --privileged` (R4) | ADR-011 d10, OP-11, section 5.4 |
| Q38 | Design principle (reading confirmed): facts are gathered by scripts that run on both operator machines (host facts on the host they describe, OCI facts on the lab operator VM). Sudo is used only where a fact absolutely requires it | ADR-011 d12, section 5.1 |
| Q39 | Design principle: fact-collection scripts may use API tokens to connect to other environments (for example OCI or GitHub), with read-only access only | ADR-011 d12, sections 4 rule 10 and 6 |
| R1 | The operator machines are configured by an Ansible `operator` profile (`ansible/operator.yml`: hardening, sudoers with `timestamp_timeout=0`, firewall with a timer-based revert role, apt packages, tools through `scripts/toolchain`, OCI CLI in a hash-locked venv `toolchain/python/operator.lock`), triggered by `setup`. A pre-task refuses a real run unless the explicit apply variable is set. The first run from the provider's initial admin account creates the operator user. Locking that account's SSH access is a separate tagged play. Privileged steps outside `setup` and `facts` exist only as Ansible tasks with `become`. Conditional on VO-7 | ADR-011 d10, section 5.5, ADR-005 d10 |
| R2 | Operator scripts other than `setup` are Python standard library. The OCI CLI is called as a subprocess with argument arrays. GitHub calls use `urllib` through the `pr-contract` API client, so tokens never leave the script process and `gh` is not needed. Gate rules: no `shell=True`, `os.system`, `eval`, or `exec`; subprocesses limited to `oci`, `ssh`, `git`, and the allowlisted privileged commands of `facts` | ADR-011 d11, section 4 rules 5 and 9, S-11 |
| R3 | A tag ruleset restricts creation, update, and deletion of `v*` tags to the approver's account, so Q29 is enforced. Verified by a negative test from the machine account. Applied by the approver in the repository settings | ADR-011 d3, U-4, RR-OP-28 |
| R4 | One `facts` script for both machines (host scope; `--privileged` runs a fixed list of read-only root commands; `--write-allowlist`; optional bandwidth; egress as a salted local hash). Off-host facts stay manual lines | ADR-011 d12, section 5.1, F-1 |
| R5 | `facts --scope oci` on the lab operator VM with the instance principal reports limits, usage, alarms per instance, and IP retention. `oci-audit` is merged into it. Before the VM exists it runs in Cloud Shell from an anonymous clone at a release tag, with `list`, `get`, and `inspect` verbs only. Fallback: the approver reads the values in the Console | ADR-011 d12, section 5.1, F-2 |
| R6 | Read-only credentials for fact collection: `facts --scope github` uses T3 (fine-grained, two repositories, Administration read, Environments read, Metadata read, 1-day expiry, `getpass`, in-process, revoked after each run), usable on either machine. `github-setup` dry runs use T3 and its apply uses T2. Read-only is enforced in code (GET-only client). Any further environment gets its own read-only credential and an ADR-001 matrix row. T1 never goes on an operator machine, and T2 is never used for fact collection | ADR-011 d4 and d12, sections 4 rule 10 and 6, F-3 |

History: the earlier decisions of 2026-11-18 (Q1, Q2, and "the operator may use sudo to install packages") stand as refined above: the sudo decision became Q9 and Q37, and the earlier reading that mapped an answer labelled Q3 to Q6 is replaced by the handoff.

### 10.2 Withdrawn and rejected

| Item | Outcome | Replaced by |
|---|---|---|
| Q6, Q15, Q27: dedicated `init` and `setup` scripts that perform the host configuration themselves, with sudo allowed in both | Withdrawn by the approver | Q37 and R1. The earlier reading that the answer labelled "Q3" on 2026-11-18 meant Q6 stays on record |
| Q12: 50 GB of block storage kept as a spare for a future host | Withdrawn by the approver | No storage is reserved for a future host |
| Q21 as first decided: a PowerShell access script on Z0 | Replaced | Direct SSH (Q21 revised): no script delivery, no execution-policy exception, no extra CI check |
| Bastion as the normal access path to the lab operator VM (access paths P2 and P3, `lab-connect`, a Bastion-session credential on the platform operator VM or Z0) | Omitted by the approver | Direct SSH with an NSG allowlist (Q22) |
| Bastion as break-glass and the break-glass ladder (Bastion session, allowlist fix, serial console in maintenance mode) | Replaced | Rebuild through the lab stack (Q23) |
| An OCI session token or API key on the platform operator VM (the Q3 alternatives) | Replaced | A read-only instance principal on the lab operator VM and Cloud Shell, which need no stored or typed credential |
| `origin/main` `HEAD` as the run source | Replaced | Release tags (Q29), enforced by R3 |
| Bash with `jq` for operator scripts and `gh` with an environment token for GitHub calls | Replaced | R2 |
| R4 as first proposed: a facts script without any sudo, with root-only facts as manual lines | Superseded | Q38 and R4 as revised |
| `oci-audit` as a separate script | Merged | `facts --scope oci` (R5) |

### 10.3 Open items and the PR each one blocks

No design question is open for the approver. What remains are verifications and inputs, each tied to the PR that needs it (details in section 9).

| Item | Blocks |
|---|---|
| Platform operator VM facts beyond architecture and release (`facts`, host scope, with `--privileged` where required, and its manual lines) | PR 3 `operator-profile` |
| VO-15 (`python3` present, `git` and `curl` may be absent on minimal Ubuntu 24.04) | PR 2 `operator-facts` |
| VO-3, VO-4, VO-17 (T2 and T3 permissions per API call, the token type for personal-account repositories, which facts need no token) | PR 4 `github-setup` |
| VO-1, VO-16 (the instance principal covers the OCI scope; tenancy-level read-only policy; Cloud Shell run from an anonymous clone) | PR 5 `facts-oci` |
| VO-7 (the OCI CLI, the monitoring plugin, `ansible-core`, and the profile fit in 1 GB) | The CR-16 design PR |
| VO-8 to VO-14 (micro AD and image, image match, dynamic group on a recreated instance, idle reclamation, IPv4 limits and IP retention, alarm behavior and limits, in-place boot-volume replacement) | The CR-16 design PR |
| The CR-16 inputs listed in section 9 | The CR-16 design PR |

### 10.4 Readings and gaps noted while applying the handoff (not decisions)

- **"Keep PC-8, the extended gate patterns, the dry-run limitation statements, and the optional egress allowlist":** these did not exist in the earlier text. They are written as the "Kept statements" of section 4, with the inbound allowlist read as optional. The approver may correct the reading.
- **VO numbering:** VO-12 is the public IPv4 limits and IP retention (so Q32 stays conditional on VO-12), and VO-13 is alarm behavior and the Always Free limits for alarms and Notifications. This is the approver's answer in the session of 2026-11-18, because the handoff's list order and Q32 disagreed.
- **VO-2, VO-5, VO-6** of the earlier design are not in the handoff's open list and are closed: VO-2 and VO-6 are content of the `operator-profile` PR, and VO-5 is acceptance U-1.
- **D5:** the baseline proposes about 100 GB for D5, and Q24 says it stays at about 50 GB or less. It is recorded as a reduction that the CR-16 design PR must carry.
- **Operator sudo password on the lab operator VM:** R1 sets it interactively at the first profile run from the provider's initial admin account, but cloud-init runs `setup --apply` as root on that VM, with no interactive run. How the password is set there is not stated. It is for the approver to decide in the `operator-profile` PR or the CR-16 design PR. Until then `facts --privileged` and a manual `setup --apply` cannot use sudo on that machine.
- **72-hour absence detection (Q35):** whether the Monitoring service supports an absence detection period of that length is checked in VO-13.

### 10.5 User-only actions (summary)

See the implementation plan, section 4. In short: apply the tag ruleset (R3) and create release tags; run `facts`, `setup`, the lock play, and U-1 on each operator machine; create and revoke T2 and T3 per run; provide the stack variables and apply the lab stack for rebuilds; retire the Z1 operator user; review operator scripts, `setup`, the profile, and `facts` with extra care.
