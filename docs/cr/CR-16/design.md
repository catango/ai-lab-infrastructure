# CR-16 Design: Stage 2 OCI seed

| Field | Value |
|---|---|
| CR | issue #16 (Class 3) |
| Governing records | ADR-001 (D4 to D6, sections 2 to 4), ADR-002 (sections 2, 4, 5), ADR-005, baseline v0.1 (sections 3, 6, 7) |
| New record | [ADR-004](../../adr/ADR-004-oci-baseline.md) (Proposed). Decision 10 also amends ADR-001 decision 5 and the OCI credentials row of its section 4 (operator tier, section 6.3) |
| Scope | Design only. No Terraform, scripts, cloud-init, or workflows are added by this PR. |

## 1. Goal and scope

Stage 2 exit criteria (baseline section 6): a VM is running in `uk-london-1` and SSH through `ProxyJump` works.
This design covers:

| Part | Deliverable | Section |
|---|---|---|
| a | Bootstrap stack (Tier 0): compartments, quotas, budget, instance-principal IAM, Vault | 4 |
| b | Lab stack: network, instance, block volume, backup bucket, Bastion | 5 |
| c | Cloud-init for the instance | 6.1 |
| d | Static checks for the Terraform code (format, validate, allowlist, no identifiers) | 6.2 |
| e | Operator tier: the rules for scripts run by the operator user, and what the lab build provides for it | 6.3 |

Out of scope: the deployment pipeline and the federation trust (Stage 4, after Spike S2), the `lab` toolchain profile and
`labctl` (Stage 3), the backup design and retention (ADR-007), the rebuild path (ADR-006), the software template.

Both stacks are applied by the approver in the OCI Console in this stage. Claude Code writes the code and never runs
Terraform or the OCI CLI against the tenancy (CLAUDE.md, ADR-001 section 2). Tasks that need credentials or permissions the AI
must not hold are run by hand by the operator user, with AI-written scripts (section 6.3).

## 2. Decisions in this design

| ID | Decision | Rationale |
|---|---|---|
| S2-1 | Two Resource Manager stacks with separate state: `bootstrap` and `lab`. | ADR-002 section 2.6: the pipeline must never manage IAM, quotas, budget, or its own trust. The split also lets the lab stack be destroyed and rebuilt without touching Tier 0. |
| S2-2 | Code in `terraform/bootstrap/` and `terraform/lab/`, written in the HCL subset OpenTofu and Terraform share. No modules in v1. | Two small roots are easier to review than a module tree. ADR-002 keeps OpenTofu compatibility for portability. |
| S2-3 | The stack configuration is a zip of one directory, uploaded by the approver. `scripts/stack-zip` builds it deterministically from a git tag. | No GitHub token or Resource Manager source-control connection is needed for the manual stage, and the same bytes can be rebuilt and compared. |
| S2-4 | Always Free enforcement in three layers: Free Tier account state, compartment quotas (zero except the allowlist), and in-code validation plus a resource-type allowlist. | Defense in depth. The quotas are the layer that holds even if the code or a variable is wrong. |
| S2-5 | Two compartments directly under the tenancy: the lab compartment `ai-lab`, which holds every lab resource, and a separate security compartment `ai-lab-security`, which holds the Vault and its key. Both names are variables. | Quotas, policies, and the dynamic group scope to the lab compartment. A Vault in the lab compartment would widen what the Stage 4 job principal (which manages that compartment) can reach, so the Vault lives outside it. |
| S2-6 | One instance, `VM.Standard.A1.Flex`, 2 OCPU, 12 GB, in the AD chosen by variable (AD-1 or AD-3). | The A1 limit is 2 OCPU and 12 GB in total, and zero in AD-2. |
| S2-7 | 50 GB boot volume and 100 GB block volume mounted at `/srv/work` (D5). The block volume has `prevent_destroy`. | Workspaces are the only data that matters on the VM. 50 GB of the 200 GB allowance stays free for the rebuild path. |
| S2-8 | SSH only from a variable list of source ranges, never `0.0.0.0/0`, no default. Key-only. Bastion port-forwarding sessions as break-glass (D4); Bastion is not the primary path. | The VM is internet-facing and AI-operated (zone Z2). Until O-9 is known the instance is simply unreachable, which is safe. |
| S2-9 | Instance principal through a dynamic group limited to the lab compartment, with read-only inspection, one bucket, and one secret (ADR-001 section 4). | The lab VM must never gain write rights to infrastructure. |
| S2-10 | A budget that targets the root compartment (the whole tenancy), with two alert rules: actual spend (absolute threshold) and forecast spend (100% of the budget). The amount and the recipient are variables. | Always Free should cost nothing, so any non-zero spend anywhere in the tenancy is an incident worth an email (D6). A budget scoped to the lab compartment cannot see spend elsewhere. |
| S2-11 | Nothing identifying is committed: OCIDs, namespace, addresses, network ranges, SSH public key, alert recipient, and AD names are variables or looked up at apply time. Outputs are sensitive. | The repository is public (CLAUDE.md conventions, `public-repo-hygiene`). |
| S2-12 | The first implementation PR adds an `iac` quality-gate check (`tofu fmt`, `tofu validate`, resource-type allowlist) and a CI job. | The toolchain already pins OpenTofu (ADR-005). Mechanical checks belong in a script, not in prompts. |
| S2-13 | Operator tier (requirement of 2026-11-18): the operator user on the platform workspace runs reviewed, merged, AI-written scripts for credentialed or extended-permission tasks. Every script has dry-run (default) and apply modes. Operator scripts never apply infrastructure changes. The rules are in section 6.3; the scripts themselves are a separate change request. | Keeps credentials away from the AI user while removing long copy-and-paste runbooks. The scripts are reviewed code, so the approver, not the AI, decides what runs with credentials. |
| S2-14 | The lab stack can provision a second, optional login on the lab VM for the operator: no sudo, key-only, no credentials, off unless its variables are set. | The requirement says an additional user may exist in the lab. Off by default keeps the internet-facing host's exposure unchanged. |

## 3. Repository layout and variables

```text
terraform/
  bootstrap/        # versions.tf, variables.tf, compartment.tf, quotas.tf, budget.tf, iam.tf, vault.tf, outputs.tf
  lab/              # versions.tf, variables.tf, network.tf, compute.tf, storage.tf, bucket.tf, bastion.tf, outputs.tf
  lab/cloud-init/   # user-data template, rendered by the stack
scripts/
  stack-zip         # deterministic zip of one terraform/ directory at a tag
  checks/iac.sh     # gate check: format, validate, allowlist
docs/operations/
  oci-seed.md       # runbook: apply order, variables, tests, rollback
```

Variables are entered in the Console when the stack is created or edited. None has a default that is an identifier.

| Stack | Variable | Meaning | Validation in code |
|---|---|---|---|
| bootstrap | `tenancy_ocid` | Tenancy (Console provides it) | none (Resource Manager supplies it) |
| bootstrap | `compartment_name` | Name of the lab compartment | non-empty |
| bootstrap | `security_compartment_name` | Name of the security compartment (Vault and key) | non-empty and different from `compartment_name` |
| bootstrap | `budget_amount` | Monthly budget in the account's currency | `> 0` and `<= 5` |
| bootstrap | `budget_alert_recipient` | Email list for alerts | non-empty (an address is never committed) |
| lab | `compartment_ocid` | From the bootstrap outputs | none |
| lab | `availability_domain_index` | 1 or 3 | `contains([1, 3], value)` |
| lab | `ssh_public_key` | Public key of the lab VM login | starts with `ssh-ed25519 ` |
| lab | `ssh_source_cidrs` | Allowed SSH sources | non-empty list and no `0.0.0.0/0` (validation blocks the all-addresses range) |
| lab | `vcn_cidr`, `subnet_cidr` | Network ranges | valid CIDR; the subnet lies inside the VCN |
| lab | `bastion_client_cidrs` | Source ranges allowed to reach the Bastion endpoint (break-glass) | non-empty list of valid CIDRs; the all-addresses range is rejected, as for SSH |
| lab | `bucket_name` | Backup bucket | non-empty |
| lab | `operator_user_name` | Login name of the optional operator user on the lab VM. Empty (default) means no second user | empty, or a valid Linux login name that is not `root` and differs from the default login user |
| lab | `operator_ssh_public_key` | Public key of the operator login | required when `operator_user_name` is set, and starts with `ssh-ed25519 ` |

Fixed in code and validated, not variables: shape `VM.Standard.A1.Flex`, OCPUs fixed at 2, memory fixed at 12 GB,
boot volume 50 GB, block volume 100 GB, public SSH port 22.

## 4. Bootstrap stack (part a)

Applied once by the approver, as an administrator, in the Console. It is the only stack that touches IAM, quotas, and the budget.

| Resource | Purpose |
|---|---|
| Compartment `ai-lab` (`compartment_name`) | Container for every lab resource |
| Compartment `ai-lab-security` (`security_compartment_name`) | Container for the Vault and its key only. Not managed by any pipeline principal in Stage 4 |
| Quota policies | Set every compute, storage, database, networking, and other family to zero in the compartment except the allowlist below, and cap A1 at 2 OCPU and 12 GB |
| Budget and alert rules | One budget targeting the root compartment. Rule 1: actual spend, absolute threshold at the smallest value Oracle accepts. Rule 2: forecast spend at 100% of the budget amount. The exact thresholds are confirmed after V2-4 |
| Dynamic group | Matches instances in the lab compartment only |
| Policy for the dynamic group | Read-only inspection of the lab compartment; object read and write on the backup bucket; read one Vault secret in the security compartment, limited by a condition on the secret's name (syntax: V2-2) |
| Vault (type pinned to the default type) and one software-protected key, in the security compartment | Holds the restic password secret in Stage 3. The key has `prevent_destroy`. The secret value is created by the approver in the Console, never in Terraform, so it never enters the state |

**Allowlist (resource families that may exist in the lab compartment):** compute (one A1 instance), block storage (volumes within the cap),
virtual networking (one VCN, subnet, internet gateway, route table, NSG, security list), Object Storage (the backup bucket within 20 GB),
and Bastion. The security compartment allows the one Vault and its key. Everything else is zero in both compartments. The list of families is generated by the approver from the limits service in
Cloud Shell (read-only) when the bootstrap PR is prepared, so that no family is missed (verification V2-1).

Outputs (sensitive): the lab compartment OCID, which the approver pastes into the lab stack's variables.

**Not in this stack:** the federation trust and the Resource Manager execution policies for the pipeline. They depend on Spike S2 and arrive in Stage 4 by a new design PR that amends this stack.

## 5. Lab stack (part b)

Applied by the approver after the bootstrap stack, using the approver's own Resource Manager permissions (ADR-002 section 3 break-glass path).

### 5.1 Network

| Resource | Setting |
|---|---|
| VCN | `vcn_cidr`, no IPv6 |
| Internet gateway and route table | Default route to the gateway for the one public subnet |
| Security list | Replaces the default one with no ingress rules. All real rules are in the NSG |
| Public subnet | `subnet_cidr`, regional, uses the security list above |
| NSG on the instance VNIC | Ingress: TCP 22 from each range in `ssh_source_cidrs` and from the Bastion's private endpoint address (one `/32`, taken from the Bastion resource's attribute, never typed in), stateful. Egress: all (the host needs apt, GitHub, and the Claude service) |

With an empty `ssh_source_cidrs` the validation fails, so the stack cannot be applied without a source range. The approver sets the value from O-9, or, when the egress address is not stable, from the range IT confirms. If O-9 shows no usable range, the design is revisited in a new design PR; Bastion as the primary path is rejected (section 9.2).

### 5.2 Compute

- Image: the latest Canonical Ubuntu 24.04 aarch64 platform image found by a data source filter, with `lifecycle { ignore_changes = [source_details] }` so a new image release does not replace a running instance.
- Shape `VM.Standard.A1.Flex`, 2 OCPU, 12 GB, in the AD selected by `availability_domain_index` (looked up by position, so the tenancy-specific AD prefix never appears in the repository).
- Public IP assigned to the VNIC (ephemeral). The address is a sensitive output read in the Console.
- Metadata: the SSH public key and the rendered cloud-init. `preserve_boot_volume = false`.
- Instance principal: enabled by the dynamic group of section 4. No credentials are placed on the host.
- If the apply fails with an out-of-capacity error, the approver re-runs the apply (jobs are free) and, after repeated failures, changes `availability_domain_index` to the other allowed value. No script retries on the approver's behalf.

### 5.3 Storage

| Volume | Size | Handling |
|---|---|---|
| Boot | 50 GB | Created with the instance |
| Block | 100 GB | Paravirtualized attachment; `prevent_destroy`; no backup policy in Stage 2 (restic and the five volume backups are decided in ADR-007) |

Total 150 GB of the 200 GB Always Free allowance. The cloud-init step formats the block volume only when it has no filesystem and mounts it at `/srv/work` by label with `nofail`.

### 5.4 Backup bucket and Bastion

- A private Object Storage bucket (name from a variable; the namespace is read from a data source and never output). Versioning off, no public access. The 20 GB allowance is the cap; ADR-007 sets retention.
- An OCI Bastion on the instance's subnet, with `bastion_client_cidrs` as its client allow-list. **Port-forwarding sessions are the break-glass method**: the approver creates a session in the Console on demand, and the session tunnels TCP 22 to the instance, so nothing depends on an agent plugin on the host. The Bastion carries no standing access. Its private endpoint address is the second NSG source in section 5.1. The maximum session lifetime and the port used to reach the endpoint are verification V2-5.

## 6. Cloud-init and static checks

### 6.1 Cloud-init (part c)

Minimal and deterministic. It makes the host reachable and ready for the Stage 3 Ansible `lab` profile, and nothing more.

1. Disable password and root SSH login with a drop-in file, restrict logins to the default user and, when set, the operator user, and reload `sshd`.
2. Install `git` and `ansible-core` from the Ubuntu archive. No downloads from other sources (supply-chain rule: no `curl | sh`).
3. Format (if blank) and mount the block volume at `/srv/work`, owned by the login user.
4. Leave the Ubuntu default of unattended security upgrades on.
5. Write a marker file with the cloud-init completion time, so Stage 3 can tell that provisioning finished.
6. Only when `operator_user_name` is set: create that user with the supplied public key, no password, no `sudo`, `adm`, or other privileged group, and a home directory readable by that user only. The user cannot write to `/srv/work` (S2-14).

Cloud-init holds no secrets and no identifiers. The host's own firewall rules from the Oracle image are kept as they are; this design adds no `ufw` layer (verification V2-6).

### 6.2 Static checks (part d)

A new gate check `scripts/checks/iac.sh`, ordered with the other Stage 1 checks:

| Check | Rule |
|---|---|
| Format | `tofu fmt -check -recursive terraform/` |
| Validate | `tofu init -backend=false` then `tofu validate` in each root. The provider version is pinned exactly and its checksums are committed in the lock file. Skips (exit 77) when the provider cannot be downloaded, for example in a sandbox without network |
| Resource-type allowlist | Every `resource` block type in `terraform/lab/` is in the allowlist; every one in `terraform/bootstrap/` is in its own allowlist. Anything else fails |
| Shape and size guards | The literal shape, OCPU, memory, and volume sizes in the code match the Always Free values |
| No identifiers | The existing `public-repo-hygiene` check already covers OCIDs and addresses; `*.tfstate*` and `*.tfvars` are added to `.gitignore` and rejected by the check |

CI runs the check in the existing `quality-gate` job. Nothing in CI contacts OCI (ADR-002 section 3.1).

### 6.3 Operator tier (requirement of 2026-11-18, part e)

**Requirement (approver, 2026-11-18).** A dedicated Linux user exists on the platform workspace (zone Z1), has internet access and no admin privileges, and is separate from the AI user. A second such user may be provisioned on the lab VM (Z2). The operator runs, by hand, scripts the AI provides, for tasks the AI should not or cannot call directly: tasks that need dedicated credentials (for example OCI) or extended permissions (for example configuring GitHub repositories). Every provided script offers a dry-run mode and an apply mode. Three existing manual procedures are to be simplified on this principle: the Gate 0 audit, the GitHub setup, and acceptance tests that need many individual calls.

**Facts checked on Z1 (read-only; counts and modes only, no names).** Two login users have home directories, both with mode 700. The AI user is a member of the `sudo` group. The restore runs prompted the approver for the sudo password, so sudo is not passwordless for the AI user. I did not test sudo (Claude never runs it), so that point is an inference, and acceptance O-1 checks it. The OCI CLI is not installed on Z1; `gh` is.

**What it conflicts with.** ADR-001 decision 5 and the OCI credentials row of its section 4 say no OCI credentials exist on Z1 or Z2, and B1 calls that an enforced property. Acceptance K-3 and `workspace/verify.sh` check for it. ADR-004 decision 10 (Proposed) amends the wording: the AI user holds none on Z1, none exist on Z2, and the operator user on Z1 may hold short-lived credentials. ADR-001 carries a pointer to the amendment. Nothing changes until the approver accepts ADR-004.

**Rules for operator scripts (the part this design fixes).**

| # | Rule | Reason |
|---|---|---|
| 1 | Separation: the operator's home is mode 700, the AI user cannot read it or become the operator, and the operator has no sudo | Credentials the AI cannot read are the point of the tier. The approver tests it (acceptance O-1) |
| 2 | Source: scripts live in `scripts/operator/` and reach `main` through a PR like all code. The operator runs them from its own clone, updated with `git pull --ff-only`, never from the AI user's working tree. A script prints the commit, and refuses to run with local changes or a commit that is not in `origin/main` | The AI can edit its own working tree. A merged commit is what the approver reviewed |
| 3 | Modes: `--dry-run` is the default. Changes need `--apply`, plus a confirmation prompt for anything that deletes or overwrites. A dry run makes no write call and prints every call it would make (read-only scripts list the calls they would send) | CLAUDE.md already requires dry-run for destructive scripts. This makes both modes universal for operator scripts |
| 4 | Credentials are prompted for or short-lived, and never stored in the repository, a file under the AI user's reach, or shell history. OCI: a session token is preferred to an API key (V2-11, Q12). GitHub configuration: a separate token T2 with extended scope, entered at the prompt, shortest practical expiry, revoked after use. T2 is not T1 | Matches the T1 handling of ADR-001 section 4. T1 has no admin rights and stays unchanged |
| 5 | Output: standard output is a sanitised summary (yes/no, counts, sizes, the format of the existing results blocks) that is safe to paste into chat. Raw responses go to a private directory in the operator's home. Identifiers, addresses, and names are filtered, and a filter that cannot decide prints a placeholder | CLAUDE.md conventions for the public repository, and the audit rules of `docs/operations/gate-0-audit.md` |
| 6 | Bounded: apply mode runs a fixed list of operations. Scripts take no command text as an argument, use no `eval`, and never run Terraform or change OCI resources (ADR-002) | An operator script must not become a second deployment path |
| 7 | Quality: ShellCheck-clean, `set -euo pipefail`, tests for both modes with stub CLIs, and the existing hygiene checks | Same gate as every other script |

**The three use cases.** The scripts are not built by this design.

| Use case | Today | With operator scripts | Stays manual |
|---|---|---|---|
| Gate 0 audit | `docs/operations/gate-0-audit.md`: about 200 lines of Cloud Shell commands | One audit script runs the read-only OCI calls and prints the results summary block | Parts that ask people questions or need the corporate network (for example Parts 1, 5 and 6) |
| GitHub setup | `docs/operations/github-setup.md`: Console steps | Idempotent `gh api` calls for repositories, settings, security, rulesets, environments, and the collaborator (Parts 3 to 9 by their headings). Dry run shows current against wanted settings | Account hardening, the machine account, token creation, chat integration (Parts 1, 2, 10, 11) |
| Acceptance tests | The B, L, K tests of this CR and the V2 checks, run one by one | One runner reports yes/no per criterion ID | Tests that need the Console, a second network (L-4), a reboot, or a stop and start |

**What the lab build provides (this CR).** The optional operator login on the lab VM (S2-14, cloud-init item 6, acceptance L-12). It has no OCI or GitHub credential and no sudo, so it can run only scripts that need neither, for example the on-VM acceptance checks (L-5, L-6). It uses the same SSH allowlist and adds no firewall rule. The acceptance runner reaches the VM from Z1 over the existing SSH path.

**What is separate.** The operator scripts, their shared library, the OCI CLI installation route on Z1 (through the toolchain manifest of ADR-005 or by the approver; V2-11), and the T2 procedure become a new change request that the approver opens. The manual runbooks stay in force until then. Because ADR-004 decision 10 amends ADR-001, this design PR must be merged before that change request starts.

## 7. Risks

| ID | Risk | Mitigation |
|---|---|---|
| RR-S2-1 | The egress address is unstable or shared, so an allowlist range is too wide or breaks access | O-9 is an input to the first lab apply. Bastion port forwarding is the break-glass path. The allowlist is one variable and one re-apply |
| RR-S2-2 | A1 out of capacity at apply time | Retry, then the other allowed AD (section 5.2). The cost of waiting is zero |
| RR-S2-3 | Oracle reclaims an idle A1 instance (seven days below 20% utilization) | Accepted, under three conditions: (1) assume reclamation can terminate the instance, and that separately attached block volumes might not survive (V2-9); (2) the capacity runbook in `docs/operations/oci-seed.md` describes how to recreate the stack and restore from backup; (3) the address that receives Oracle's notices is monitored (a user-only action). No keep-alive load is added, because that would be a workaround against Oracle's policy |
| RR-S2-4 | The Terraform version in Resource Manager is older than OpenTofu's | The HCL stays in the shared subset; the version is checked (V2-3) before the first implementation PR that needs it |
| RR-S2-5 | The quota policies leave a family unzeroed, so a mistake could create a paid resource | The family list is generated from the limits service (V2-1), and an acceptance test tries to create a disallowed resource |
| RR-S2-6 | The block volume is destroyed by a stack change | `prevent_destroy`, plus the Console confirms a destroy job. Data is also in restic from Stage 3 |
| RR-S2-7 | A variable leaks an identifier into a public log | Outputs are sensitive, the stack runs only in the Console, and the gate blocks identifiers in committed text |
| RR-S2-8 | The dynamic group is wider than intended and gives the VM more than read access | The matching rule is a single compartment; AC tests read-only behavior from the VM in Stage 3 |
| RR-S2-9 | AI-written code runs with credentials the AI never sees, so a mistake or a prompt injection could turn a script into a destructive call or a leak | Rules 2 to 7 of section 6.3: merged commit only, dry-run default, fixed operation list, sanitised output, short-lived credentials. Operator scripts are a code-review focus for the approver |
| RR-S2-10 | The AI user and the operator share one host, kernel, and filesystem. The AI user is in the `sudo` group, and its protection is the sudo password | Mode 700 homes, no sudo for the operator, and the approver's test O-1 before the first use. If O-1 fails, the tier needs a separate host or container, and this design is revisited |
| RR-S2-11 | A second SSH identity on the internet-facing lab VM widens its attack surface | Optional and off by default, key-only, no sudo, same allowlist, no credentials (S2-14) |

## 8. Verification items

All of these are documentation checks or read-only Console or Cloud Shell inspection. Anything that creates resources is a separate, explicit action by the approver.

| ID | Question | Method | Needed before |
|---|---|---|---|
| V2-1 | Exact quota-policy syntax, and the list of families to zero | Oracle documentation, and `oci limits service list` in Cloud Shell | Bootstrap PR |
| V2-2 | Dynamic group resource type under identity domains, and policy syntax for it | Oracle documentation | Bootstrap PR |
| V2-3 | Terraform versions Resource Manager offers, the supported OCI provider version, and how Resource Manager handles the provider lock file (this is Spike item S2e) | `oci resource-manager stack list-terraform-versions` in Cloud Shell (read-only), and Oracle documentation | First Terraform PR |
| V2-4 | The minimum budget amount, whether budgets are free, whether a budget can target the root compartment, and the alert threshold types | Oracle documentation | Bootstrap PR |
| V2-5 | Bastion prerequisites for a port-forwarding session to a public-subnet instance, the maximum session lifetime, and the port used to reach the Bastion endpoint | Oracle Bastion documentation | Lab PR |
| V2-6 | Default firewall rules of the Oracle Ubuntu image and how they interact with the NSG | Oracle documentation; observed on the first VM | Lab PR |
| V2-7 | Whether volume backups count against the 200 GB storage allowance | Oracle documentation | ADR-006 and ADR-007 |
| V2-8 | The current reclamation behavior for idle A1 instances (stop or terminate), and where the notice is sent | Oracle documentation, or Oracle support | Lab PR (capacity runbook) |
| V2-9 | Whether reclamation-driven termination deletes separately attached block volumes | Oracle documentation, or Oracle support | Lab PR (capacity runbook) |
| V2-10 | Whether the Vault type and the key protection mode can change after creation | Oracle Vault documentation | Bootstrap PR |
| V2-11 | Whether OCI CLI session-token authentication (`oci session authenticate`) works for this tenancy's identity domain type, its maximum lifetime, whether a read-only identity can run the audit, and how the CLI is installed with pinned versions and checksums | Oracle CLI documentation | The operator-scripts change request (not a CR-16 implementation PR) |

## 9. Review handoff of 2026-11-17 and decisions

Source: the approver's review comment on PR #17 ("Decision handoff: CR-16: 2026-11-17"). It decides nothing yet:
Q1 to Q9 below are recommendations, and the approver's decisions are recorded here when given. D3 to D6 of the baseline
were accepted earlier and are not repeated.

The approver's requirement of 2026-11-18 (operator tier) is designed in section 6.3 and raises Q10 to Q14. It is recorded
as a requirement, not as a decision on those questions.

### 9.1 Decided

None.

### 9.2 Rejected (as recommended in the handoff; not yet decisions)

| Item | Reason |
|---|---|
| Bastion as the primary access path | The session lifetime and the per-session Console setup do not fit Claude Desktop over `ProxyJump`. Bastion stays as break-glass (S2-8) |
| A budget scoped only to the lab compartment | It cannot see spend elsewhere in the tenancy (S2-10) |
| A keep-alive load | A workaround against Oracle's policy (RR-S2-3) |
| A Pay As You Go upgrade | It would reopen D6 and the baseline's "Always Free only" constraint |
| The Vault in the lab compartment | It widens the Stage 4 job principal's scope (S2-5) |

### 9.3 Open

| Item | Needs |
|---|---|
| O-9 result, and whether outbound SSH works from the last corporate hop | The approver, with IT |
| Terraform version, provider version, and lock-file handling in Resource Manager (V2-3) | The approver, in Cloud Shell, read-only |
| Minimum budget amount, whether budgets are free, and whether a budget can target the root compartment (V2-4) | A documentation check |
| Whether Pay As You Go should be reconsidered (this would reopen D6) | The approver |
| Bastion maximum session lifetime and endpoint port (V2-5); reclamation behavior and notice address (V2-8); whether reclamation deletes attached block volumes (V2-9); whether Vault type and key mode can change (V2-10) | Oracle documentation, or Oracle support |
| Operator tier: Q10 to Q14; the sudo and home-directory test O-1 on Z1; opening the change request for the operator scripts; V2-11 | The approver; a documentation check |

### 9.4 Questions Q1 to Q14 (recommendations, not decided)

| # | Question | Recommendation | Status |
|---|---|---|---|
| Q1 | O-9: the egress result (stable, changes, or multiple), and whether outbound SSH is allowed | Needed before the first lab apply, not before this PR is merged. A range that cannot be determined reopens the design (Bastion as primary is rejected) | Open |
| Q2 | Run the read-only S2e command (V2-3) in Cloud Shell and report only the highest Terraform version offered | Needed before the first Terraform PR | Open |
| Q3 | Budget amount and currency, and who receives the alerts | The smallest amount the Console accepts, up to five units, targeting the root compartment with the two rules of S2-10; the recipient is a variable | Not decided |
| Q4 | Compartment names | `ai-lab` and `ai-lab-security`, as variables | Not decided |
| Q5 | Vault and key in the bootstrap stack now, in the security compartment, default type, `prevent_destroy` on the key; secret value created by the approver in the Console in Stage 3 | Yes | Not decided |
| Q6 | Accept RR-S2-3 (idle reclamation) with no keep-alive load | Yes, under the three conditions in RR-S2-3 | Not decided |
| Q7 | Create the Bastion by default, with port-forwarding sessions as the break-glass method | Yes; it costs nothing and has no standing access | Not decided |
| Q8 | `preserve_boot_volume = false` in v1, with ADR-006 deciding the rebuild path | Yes | Not decided |
| Q9 | Implementation PR order and the user-only actions in the plan | As in implementation-plan.md (updated for this handoff) | Not decided |
| Q10 | Where the operator scripts are built | In a separate change request that you open after this PR merges. CR-16 carries only the principle (ADR-004 decision 10), the lab-side login, and the acceptance criteria | Not decided |
| Q11 | May operator scripts ever change OCI resources? | No. Read-only OCI scripts only. Infrastructure changes stay with the Console in Stage 2 and the pipeline in Stage 4 (ADR-002) | Not decided |
| Q12 | OCI authentication for the operator | A short-lived session token (V2-11). The alternative, an API key for a dedicated read-only user, needs a bootstrap IAM change and gives up "no API keys" | Not decided |
| Q13 | Operator login on the lab VM | Optional, off by default, no sudo, no credentials (S2-14) | Not decided |
| Q14 | Handling of the GitHub token T2 for repository configuration | Entered at the prompt, shortest practical expiry, revoked after use, never stored, separate from T1 (section 6.3 rule 4) | Not decided |
