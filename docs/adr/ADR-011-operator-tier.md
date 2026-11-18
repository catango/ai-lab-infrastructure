# ADR-011: Operator Tier: Two Dedicated Machines for Credentialed and Extended-Permission Scripts

| Field | Value |
|---|---|
| Status | **Proposed** (becomes Accepted when the design PR for CR-18 is merged by the approver) |
| Date | 2026-11-18 |
| Repository | `ai-lab-infrastructure` |
| Change request | CR-18 (issue #18) |
| Scope | The two operator machines (the platform operator VM and the lab operator VM), the rules for the scripts and the operator profile they run, the credential placement that follows, and the requirements the lab stack must meet. Not the scripts themselves, and not the OCI baseline: ADR-004 and CR-16 build the lab operator VM, its alarms, and the rebuilds in a new design PR |
| Related | ADR-001 (decision 5, section 4 credential matrix, B1, B3; amended by this ADR), ADR-002 (infrastructure changes), ADR-003 (a new rule PC-8 is proposed in a separate design PR), ADR-005 (operator profile; amended), CR-16, ADR-004, ADR-006, ADR-007, ADR-008 (proposed or reserved) |

> This ADR records a decision. It does not create a machine, a user, a credential, a script, or any OCI or GitHub change, and it does not authorize any of them.
> Detail and rationale are in `docs/cr/CR-18/design.md`; this record keeps the decisions themselves. Labels such as Q3 or R2 are the approver's decision labels of 2026-11-18 (design section 10).

---

## 1. Context

Some tasks cannot or should not be run by the AI user: tasks that need dedicated credentials (an OCI identity) or permissions beyond the machine account's Write role (configuring GitHub repositories). Today the approver performs them by copying commands from long runbooks (`docs/operations/gate-0-audit.md`, `docs/operations/github-setup.md`) and by running acceptance tests one call at a time.

Facts (approver's statements of 2026-11-18, and read-only checks on the platform workspace):

- A first design placed the operator as a second Linux user on the platform workspace (zone Z1). The approver then decided that operators run on dedicated machines separated from the AI hosts (Q10).
- The platform operator VM is a human-provided remote machine reached over SSH, with internet access. It is x86-64 and runs minimal Ubuntu 24.04.
- The lab operator VM does not exist yet. It is an OCI Always Free micro instance (x86-64) that the lab stack creates.
- On Z1 the AI user is a member of the `sudo` group, and the OCI CLI is not installed. This matters only for the existing operator user on Z1, which is retired (decision 1).
- ADR-001 decision 5 and the OCI credentials row of its section 4 matrix say that no OCI credentials exist on Z1 or Z2, and B1 calls that an enforced property.

## 2. Decision

1. **The operator tier is two dedicated machines** (Q10, Q11, Q16, Q25). The platform operator VM (zone Z6) and the lab operator VM (zone Z7) each run a dedicated operator user without general admin rights, which runs by hand the scripts that the AI wrote and the approver reviewed and merged. Both machines are separate from the AI hosts: no shared storage or identity, no key or route from an AI host, and no Claude Desktop SSH target. The AI never runs the scripts, never reaches the machines, and never probes them. The platform operator VM is a human-provided remote machine reached over SSH with internet access, x86-64, minimal Ubuntu 24.04. The lab operator VM is a lightweight x86 machine within the OCI Always Free tier, part of the lab, separate from the lab VM, and reached over SSH by the operator of future AI projects built in the lab. Both run the same OS. The operator user that exists on Z1 is retired once the platform operator VM works.
2. **Every operator script has a dry-run mode and an apply mode, and dry run is the default** (Q2, approver's decision). This includes `setup` and `facts`. A dry run changes nothing and shows what apply would do. The operator profile (decision 10) additionally refuses a real run unless the explicit apply variable is set. The rule applies to operator scripts only. The Bash convention in `CLAUDE.md` is unchanged.
3. **Scripts and the profile run from release tags only** (Q29, R3). The commit check requires `HEAD` to equal the commit of a release tag that is contained in `origin/main`. Tags are created by the approver only, and a tag ruleset restricts creation, update, and deletion of `v*` tags to the approver's account. A script never runs from the AI user's working tree.
4. **No OCI credential is stored or typed on any operator machine** (Q3, Q4, R6). Other credentials are prompted for or short-lived, never stored in the repository, in a place an AI user can read, or in shell history, and are handled inside the script process (decision 11).
   - OCI reads use the read-only instance principal of the lab operator VM (a dynamic group matched by compartment and tag, with read-only access to the lab compartment and to tenancy limits and resource availability). It is the one standing credential and the one exception to "prompted or short-lived". Runs before the lab operator VM exists, and the Gate 0 audit, use Cloud Shell under the approver's own session. Access to the lab operator VM itself needs no OCI credential.
   - **T2** (GitHub repository configuration, Q4): a fine-grained token of the personal account, limited to the two repositories, with Administration and Environments read and write and Metadata read only (no Contents, Pull requests, Workflows, or Secrets write), 1-day expiry, read at a prompt with `getpass`, entered only for `github-setup` apply runs, revoked in the browser after each run, used on the platform operator VM only.
   - **T3** (read-only fact collection and `github-setup` dry runs, R6): a fine-grained token of the personal account, limited to the two repositories, with Administration read, Environments read, and Metadata read only, 1-day expiry, read at a prompt, revoked after each run, usable on either operator machine. T2 is never used for fact collection.
   - Any further environment gets its own dedicated read-only credential with the same handling and an ADR-001 matrix row (Q39).
   - **T1 is never placed on an operator machine** and stays free of admin rights. Break-glass is a stack apply triggered by the approver (decision 14).
5. **Operator scripts never change infrastructure.** They may read OCI. They never run Terraform and never create, change, or delete OCI resources. Infrastructure changes follow ADR-002 only (the Console in Stages 2 and 3, the pipeline in Stage 4).
6. **Output is safe to paste.** Standard output is a sanitised summary (yes/no, counts, sizes). Raw responses stay in a private directory in the operator's home and never enter the repository.
7. **Amendment of ADR-001.** ADR-001 decision 5, B1, AC1-3, and RR-8 keep their wording. When this ADR is accepted, ADR-001 reads with this amendment: **no OCI credentials and no T2 or T3 on Z1 or Z2; operator machines may hold the credentials defined in ADR-011.** The OCI credentials row of the section 4 matrix, B3, and the personal-account row are amended, the new zones Z6 and Z7 and the credential rows are added to ADR-001 sections 3 and 4 by the design PR, and the AI-operated zones still cannot approve, merge, or modify infrastructure because the AI users hold no credential that allows it.
8. **No operator login on the lab VM** (Q5 superseded). The lab operator VM replaces the earlier optional login. The only path from an operator machine to the lab VM is the acceptance runner on the lab operator VM, which uses a dedicated SSH key over private IPs inside the VCN (Q28).
9. **Separation is tested per operator machine.** After the first operator-profile apply and before the first credential on each operator machine, the approver runs the host-separation test: no shared mount or home, no AI-host key in `authorized_keys`, no route from the AI hosts, no `~/.claude/remote/`, and the sudo settings of decision 10 (Q7, acceptance U-1).
10. **Operator workspace setup by one simple script and one Ansible profile** (Q9, Q37, R1). `scripts/operator/setup` (Bash) checks the release tag, installs `ansible-core` from apt, and runs the Ansible `operator` profile in check mode by default and applies it with `--apply`. Cloud-init on the lab operator VM calls the same script with `--apply`. The profile covers hardening, sudoers, the firewall (with a timer-based revert role), a fixed apt package list, tools through `scripts/toolchain`, and the OCI CLI in a hash-locked venv. Sudo asks for the password, with `timestamp_timeout=0`, on both machines, and no `NOPASSWD` rule exists. Sudo is allowed only in `setup` and in `facts --privileged` (R4). Every other privileged step is an Ansible task with `become` in the reviewed profile. The first run, from the provider's initial admin account, creates the operator user; locking that account's SSH access is a separate tagged play run only after an operator login is confirmed from a second session.
11. **Operator scripts are Python, except `setup`** (R2, Q13). They use only the standard library, call the OCI CLI as a subprocess with argument arrays, and call GitHub REST through `urllib` with the `pr-contract` API client, so tokens stay inside the script process and `gh` is not needed on the operator machines. The gate rejects `shell=True`, `os.system`, `eval`, and `exec`. Subprocesses are limited to `oci`, `ssh`, `git`, and the allowlisted privileged commands of `facts`. The resource limits of the operator machines are a design input for every operator script (Q13), and Claude Code assumes the machines are available and never probes them (Q14).
12. **Design principles for facts** (Q38, Q39; R4 to R6). Facts are gathered by scripts that run on the operator machines: host facts on the host they describe, OCI facts on the lab operator VM. Sudo is used only where a fact absolutely requires it. Fact collection may use API tokens to connect to other environments (for example OCI or GitHub), with read-only access only, and read-only is enforced in code. One `facts` script serves both machines, with scopes `host`, `oci`, and `github`. `oci-audit` is merged into `facts --scope oci`.
13. **Placement** (Q28). `setup`, the operator profile, and `facts` (host scope) run on both machines. `github-setup` and `facts` (GitHub scope) run on the platform operator VM, and the GitHub scope is also allowed on the lab operator VM. `facts` (OCI scope) and `acceptance` run on the lab operator VM, and `facts` (OCI scope) also runs in Cloud Shell before the lab operator VM exists.
14. **Availability and recovery** (Q14, Q17, Q23, Q24, Q30, Q33, Q34, Q36). The lab operator VM is disposable: no block volume, no volume backups, nothing durable, and it is rebuilt when it is removed (for example by idle reclamation). Break-glass for the lab VM and the lab operator VM is a rebuild through the lab stack, by in-place boot-volume replacement; an instance is terminated and recreated only when it is already gone. Everything durable on the lab VM lives on `/srv/work` or in GitHub, so a rebuild loses only the boot volume, and the approver re-enters T1 on Z2 afterwards. The block-volume budget is sized for the temporary second boot volume (D5 at about 50 GB or less, within the 200 GB Always Free block storage; more only if VO-14 shows 47 GB boot volumes or deletion of the old boot volume during replacement). After an alarm, a stopped VM is started and it is rebuilt only when it was terminated (conditional on VO-11).
15. **Removal is detected by OCI Monitoring absence alarms** (Q18 to Q20, Q35). The alarm is used for all VMs running on OCI, one alarm per instance, generated by the lab stack for every instance it defines and enforced by a plan allowlist rule that rejects an instance without an alarm. No compartment-wide alarm, and no scheduled GitHub workflow. Parameters: a 72-hour absence detection period, repeat notification every 12 hours while firing, a trigger delay of 15 to 30 minutes (longer than a reboot), `groupBy` in the query, and suppression windows for planned stops and rebuilds set by the approver.
16. **Access** (Q21, Q22, Q31, Q32). Access from the Windows laptop to the lab VM and the lab operator VM is direct SSH with the OS-bundled OpenSSH, through `~/.ssh/config` entries from a runbook template (one entry and one dedicated key per VM); there is no PowerShell script, and CHG-001 stays in force. Normal access to the lab operator VM is direct SSH to its public IP with NSG ingress from the corporate egress only; there is no Bastion. The reserved public IP goes to the lab operator VM and the lab VM uses an ephemeral IP (conditional on VO-12). D4 is aligned with this for both OCI VMs.
17. **Implementation order and scope** (Q7, Q8, Q26). The order is `operator-lib`, `operator-facts` (host scope), `operator-profile`, `github-setup` with the facts GitHub scope, the facts OCI scope, `acceptance`, `operator-finish`. Implementation PRs that do not need OCI start after the design merges. Scripts that need the lab operator VM wait for CR-16 to be merged and applied. CR-18 sets the requirements for the lab operator VM, the OCI alarms, and the rebuilds, and CR-16 and ADR-004 build them in a new design PR (decisions 14 to 16 are implemented in the lab stack that way). ADR-008 carries the project-side operator contract.

## 3. Alternatives considered

| Alternative | Outcome | Reason |
|---|---|---|
| Keep running the runbooks by hand from Cloud Shell and the web UI | Kept as the fallback | No new credential on a machine. Slow, error-prone, and the many-step acceptance tests are hard to repeat |
| Let the AI user run the scripts with credentials | Rejected | It breaks B1: a prompt injection could use the credentials directly |
| A separate host for the operator | **Chosen** (two machines, decision 1) | Replaces the first design, a second user on the AI host, whose separation rested on file permissions and sudo alone |
| An operator user on the lab VM (earlier OP-8) | Removed | The lab operator VM replaces it |
| An OCI session token or API key on the platform operator VM | Rejected | Replaced by the read-only instance principal of the lab operator VM and by Cloud Shell, which need no stored or typed credential |
| Bastion as the normal access path to the lab operator VM, with a Bastion-session credential on an operator machine or on Z0 | Omitted by the approver | Direct SSH with an NSG allowlist is simpler (decision 16) |
| Bastion as break-glass and a break-glass ladder (Bastion session, allowlist fix, serial console in maintenance mode) | Replaced | Rebuild through the lab stack (decision 14) |
| PowerShell access script on Z0 (Q21 as first decided) | Replaced | Direct SSH needs no script delivery, no execution-policy exception, and no extra CI check |
| `origin/main` `HEAD` as the run source | Replaced | Release tags, enforced by a tag ruleset (decision 3) |
| Bash with `jq`, and `gh` with `GH_TOKEN`, for operator scripts | Replaced | Python standard library, so tokens never leave the script process (decision 11) |
| Dedicated `init` and `setup` scripts that perform the host configuration themselves, with sudo in both (Q6, Q15, Q27) | Withdrawn by the approver | Replaced by one simple `setup` that triggers the operator profile (decision 10) |
| 50 GB of block storage kept as a spare for a future host (Q12) | Withdrawn by the approver | No storage is reserved for a future host |
| A facts script without any sudo, with root-only facts as manual lines (R4 as first proposed) | Superseded | `facts --privileged` runs a fixed list of read-only commands (decision 12) |
| `oci-audit` as a separate script | Merged | `facts --scope oci` (decision 12) |
| A scheduled GitHub workflow that detects a removed VM | Not pursued | The OCI Monitoring absence alarm detects it (decision 15) |
| A compartment-wide absence alarm | Not pursued | One alarm per instance, enforced by the plan allowlist (decision 15) |
| Extend the dry-run rule to every script in the repository | Not needed | The requirement covers operator scripts. The existing Bash convention stays as it is |

## 4. Consequences

**Positive:**
- The AI cannot reach credentials, and the approver still gets one-command procedures for the facts, the GitHub setup, and the acceptance tests.
- Operator scripts are reviewed code at a release tag, so what runs with credentials is what the approver reviewed and tagged.
- The operator machines are separate from the AI hosts, so the separation no longer rests on file permissions on one host.

**Negative:**
- Two more machines to build and keep, one of them in the lab stack, with alarms, rebuilds, and a public IP (RR-OP-6, RR-OP-12, RR-OP-22 to RR-OP-26).
- Credentials exist on operator machines for the first time. The read-only instance principal gives every process on the lab operator VM standing read access (RR-OP-27).
- AI-written code runs with those credentials, and `facts --privileged` runs AI-written code that calls root commands, so script review matters more than before (RR-OP-1, RR-OP-30).
- Each operator script or profile change needs a release tag from the approver before first use (RR-OP-28).
- ADR-001's text is changed in the design PR (sections 3 and 4), and ADR-005 gains an `operator` profile.

**Residual risks** are in design section 8.

## 5. References

- ADR-001, ADR-002, ADR-003, ADR-005 in this repository, and ADR-004, ADR-006, ADR-007, ADR-008 (proposed or reserved, CR-16).
- CR-18 design: `docs/cr/CR-18/design.md`.
