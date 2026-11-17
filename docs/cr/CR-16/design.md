# CR-16 Design: Stage 2 OCI seed

| Field | Value |
|---|---|
| CR | issue #16 (Class 3) |
| Governing records | ADR-001 (D4 to D6, sections 2 to 4), ADR-002 (sections 2, 4, 5), ADR-005, baseline v0.1 (sections 3, 6, 7) |
| New record | [ADR-004](../../adr/ADR-004-oci-baseline.md) (Proposed) |
| Scope | Design only. No Terraform, scripts, cloud-init, or workflows are added by this PR. |

## 1. Goal and scope

Stage 2 exit criteria (baseline section 6): a VM is running in `uk-london-1` and SSH through `ProxyJump` works.
This design covers:

| Part | Deliverable | Section |
|---|---|---|
| a | Bootstrap stack (Tier 0): compartment, quotas, budget, instance-principal IAM, Vault | 4 |
| b | Lab stack: network, instance, block volume, backup bucket, Bastion | 5 |
| c | Cloud-init for the instance | 6.1 |
| d | Static checks for the Terraform code (format, validate, allowlist, no identifiers) | 6.2 |

Out of scope: the deployment pipeline and the federation trust (Stage 4, after Spike S2), the `lab` toolchain profile and
`labctl` (Stage 3), the backup design and retention (ADR-007), the rebuild path (ADR-006), the software template.

Both stacks are applied by the approver in the OCI Console in this stage. Claude Code writes the code and never runs
Terraform or the OCI CLI against the tenancy (CLAUDE.md, ADR-001 section 2).

## 2. Decisions in this design

| ID | Decision | Rationale |
|---|---|---|
| S2-1 | Two Resource Manager stacks with separate state: `bootstrap` and `lab`. | ADR-002 section 2.6: the pipeline must never manage IAM, quotas, budget, or its own trust. The split also lets the lab stack be destroyed and rebuilt without touching Tier 0. |
| S2-2 | Code in `terraform/bootstrap/` and `terraform/lab/`, written in the HCL subset OpenTofu and Terraform share. No modules in v1. | Two small roots are easier to review than a module tree. ADR-002 keeps OpenTofu compatibility for portability. |
| S2-3 | The stack configuration is a zip of one directory, uploaded by the approver. `scripts/stack-zip` builds it deterministically from a git tag. | No GitHub token or Resource Manager source-control connection is needed for the manual stage, and the same bytes can be rebuilt and compared. |
| S2-4 | Always Free enforcement in three layers: Free Tier account state, compartment quotas (zero except the allowlist), and in-code validation plus a resource-type allowlist. | Defense in depth. The quotas are the layer that holds even if the code or a variable is wrong. |
| S2-5 | One compartment, `ai-lab` (name is a variable), directly under the tenancy. Every lab resource lives in it. | Quotas, budget, policies, and the dynamic group all scope to one compartment. |
| S2-6 | One instance, `VM.Standard.A1.Flex`, 2 OCPU, 12 GB, in the AD chosen by variable (AD-1 or AD-3). | The A1 limit is 2 OCPU and 12 GB in total, and zero in AD-2. |
| S2-7 | 50 GB boot volume and 100 GB block volume mounted at `/srv/work` (D5). The block volume has `prevent_destroy`. | Workspaces are the only data that matters on the VM. 50 GB of the 200 GB allowance stays free for the rebuild path. |
| S2-8 | SSH only from a variable list of source ranges, never `0.0.0.0/0`, no default. Key-only. Bastion as break-glass (D4). | The VM is internet-facing and AI-operated (zone Z2). Until O-9 is known the instance is simply unreachable, which is safe. |
| S2-9 | Instance principal through a dynamic group limited to the lab compartment, with read-only inspection, one bucket, and one secret (ADR-001 section 4). | The lab VM must never gain write rights to infrastructure. |
| S2-10 | A budget on the lab compartment with actual and forecast alerts at a very low amount. The recipient is a variable. | Always Free should cost nothing, so any non-zero spend is an incident worth an email (D6). |
| S2-11 | Nothing identifying is committed: OCIDs, namespace, addresses, network ranges, SSH public key, alert recipient, and AD names are variables or looked up at apply time. Outputs are sensitive. | The repository is public (CLAUDE.md conventions, `public-repo-hygiene`). |
| S2-12 | The first implementation PR adds an `iac` quality-gate check (`tofu fmt`, `tofu validate`, resource-type allowlist) and a CI job. | The toolchain already pins OpenTofu (ADR-005). Mechanical checks belong in a script, not in prompts. |

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
| bootstrap | `budget_amount` | Monthly budget in the account's currency | `> 0` and `<= 5` |
| bootstrap | `budget_alert_recipient` | Email list for alerts | non-empty (an address is never committed) |
| lab | `compartment_ocid` | From the bootstrap outputs | none |
| lab | `availability_domain_index` | 1 or 3 | `contains([1, 3], value)` |
| lab | `ssh_public_key` | Public key of the lab VM login | starts with `ssh-ed25519 ` |
| lab | `ssh_source_cidrs` | Allowed SSH sources | non-empty list and no `0.0.0.0/0` (validation blocks the all-addresses range) |
| lab | `vcn_cidr`, `subnet_cidr` | Network ranges | valid CIDR; the subnet lies inside the VCN |
| lab | `bucket_name` | Backup bucket | non-empty |

Fixed in code and validated, not variables: shape `VM.Standard.A1.Flex`, OCPUs fixed at 2, memory fixed at 12 GB,
boot volume 50 GB, block volume 100 GB, public SSH port 22.

## 4. Bootstrap stack (part a)

Applied once by the approver, as an administrator, in the Console. It is the only stack that touches IAM, quotas, and the budget.

| Resource | Purpose |
|---|---|
| Compartment `ai-lab` | Container for every lab resource |
| Quota policies | Set every compute, storage, database, networking, and other family to zero in the compartment except the allowlist below, and cap A1 at 2 OCPU and 12 GB |
| Budget and alert rules | Compartment-scoped budget; one actual and one forecast alert at a low percentage |
| Dynamic group | Matches instances in the lab compartment only |
| Policy for the dynamic group | Read-only inspection of the lab compartment; object read and write on the backup bucket; read one Vault secret |
| Vault and one software-protected key | Holds the restic password secret in Stage 3. The secret value is created by the approver in the Console, never in Terraform, so it never enters the state |

**Allowlist (resource families that may exist in the lab compartment):** compute (one A1 instance), block storage (volumes within the cap),
virtual networking (one VCN, subnet, internet gateway, route table, NSG, security list), Object Storage (the backup bucket within 20 GB),
Bastion, and Vault (the one vault and key). Everything else is zero. The list of families is generated by the approver from the limits service in
Cloud Shell (read-only) when the bootstrap PR is prepared, so that no family is missed (verification V2-1).

Outputs (sensitive): the compartment OCID, which the approver pastes into the lab stack's variables.

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
| NSG on the instance VNIC | Ingress: TCP 22 from each range in `ssh_source_cidrs` (stateful). Egress: all (the host needs apt, GitHub, and the Claude service) |

With an empty `ssh_source_cidrs` the validation fails, so the stack cannot be applied without a source range. The approver sets the value from O-9, or, when the egress address is not stable, from the range IT confirms. If O-9 shows no usable range, Bastion becomes the primary path and the design is amended by a new design PR.

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
- An OCI Bastion on the instance's subnet with a client allow-list variable. Sessions are created by the approver on demand in the Console. The Bastion carries no standing access.

## 6. Cloud-init and static checks

### 6.1 Cloud-init (part c)

Minimal and deterministic. It makes the host reachable and ready for the Stage 3 Ansible `lab` profile, and nothing more.

1. Disable password and root SSH login with a drop-in file, restrict logins to the one default user, and reload `sshd`.
2. Install `git` and `ansible-core` from the Ubuntu archive. No downloads from other sources (supply-chain rule: no `curl | sh`).
3. Format (if blank) and mount the block volume at `/srv/work`, owned by the login user.
4. Leave the Ubuntu default of unattended security upgrades on.
5. Write a marker file with the cloud-init completion time, so Stage 3 can tell that provisioning finished.

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

## 7. Risks

| ID | Risk | Mitigation |
|---|---|---|
| RR-S2-1 | The egress address is unstable or shared, so an allowlist range is too wide or breaks access | O-9 is an input to the first lab apply. Bastion is the fallback. The allowlist is one variable and one re-apply |
| RR-S2-2 | A1 out of capacity at apply time | Retry, then the other allowed AD (section 5.2). The cost of waiting is zero |
| RR-S2-3 | Oracle reclaims an idle A1 instance (seven days below 20% utilization) | Accepted. Workspaces are on a block volume, and ADR-007 adds backups. No keep-alive load is added, because that would be a workaround against Oracle's policy |
| RR-S2-4 | The Terraform version in Resource Manager is older than OpenTofu's | The HCL stays in the shared subset; the version is checked (V2-3) before the first implementation PR that needs it |
| RR-S2-5 | The quota policies leave a family unzeroed, so a mistake could create a paid resource | The family list is generated from the limits service (V2-1), and an acceptance test tries to create a disallowed resource |
| RR-S2-6 | The block volume is destroyed by a stack change | `prevent_destroy`, plus the Console confirms a destroy job. Data is also in restic from Stage 3 |
| RR-S2-7 | A variable leaks an identifier into a public log | Outputs are sensitive, the stack runs only in the Console, and the gate blocks identifiers in committed text |
| RR-S2-8 | The dynamic group is wider than intended and gives the VM more than read access | The matching rule is a single compartment; AC tests read-only behavior from the VM in Stage 3 |

## 8. Verification items

All of these are documentation checks or read-only Console or Cloud Shell inspection. Anything that creates resources is a separate, explicit action by the approver.

| ID | Question | Method | Needed before |
|---|---|---|---|
| V2-1 | Exact quota-policy syntax, and the list of families to zero | Oracle documentation, and `oci limits service list` in Cloud Shell | Bootstrap PR |
| V2-2 | Dynamic group resource type under identity domains, and policy syntax for it | Oracle documentation | Bootstrap PR |
| V2-3 | Terraform versions Resource Manager offers, and the supported OCI provider version (this is Spike item S2e) | `oci resource-manager stack list-terraform-versions` in Cloud Shell | First Terraform PR |
| V2-4 | Budget alert rules: threshold types, and whether budgets are free | Oracle documentation | Bootstrap PR |
| V2-5 | Bastion prerequisites for an SSH session to a public-subnet instance, and its limits | Oracle documentation | Lab PR |
| V2-6 | Default firewall rules of the Oracle Ubuntu image and how they interact with the NSG | Oracle documentation; observed on the first VM | Lab PR |
| V2-7 | Whether volume backups count against the 200 GB storage allowance | Oracle documentation | ADR-006 and ADR-007 |

## 9. Decisions requested from the approver

The decisions already taken are D3 to D6 (accepted as written). The design needs the following answers; each has a proposal.

| # | Question | Proposal |
|---|---|---|
| Q1 | O-9: the egress address result (stable, changes, or multiple), and whether outbound SSH is allowed | Needed before the first lab apply, not before this PR is merged. The design works with any answer; a range that cannot be determined moves Bastion to primary |
| Q2 | Run the read-only S2e command (V2-3) in Cloud Shell and report only the highest Terraform version offered | Needed before the first Terraform PR |
| Q3 | Budget amount and currency, and who receives the alerts | The smallest amount the Console accepts, up to five units; the recipient is a variable |
| Q4 | Compartment name | `ai-lab`, as a variable |
| Q5 | Vault and key in the bootstrap stack now, secret value created by you in the Console in Stage 3 | Yes |
| Q6 | Accept RR-S2-3 (idle reclamation) with no keep-alive load | Yes |
| Q7 | Create the Bastion by default | Yes (D4: break-glass); it costs nothing and has no standing access |
| Q8 | `preserve_boot_volume = false` in v1, with ADR-006 deciding the rebuild path | Yes |
| Q9 | Implementation PR order and the user-only actions in the plan | As in implementation-plan.md |
