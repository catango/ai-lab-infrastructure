# ADR-004: OCI Baseline: Network, Storage, Cost Guards, and the Two Stacks

| Field | Value |
|---|---|
| Status | **Proposed** (becomes Accepted when the design PR for CR-16 is merged by the approver) |
| Date | 2026-11-17 |
| Repository | `ai-lab-infrastructure` |
| Change request | CR-16 (issue #16) |
| Scope | Bootstrap stack, lab stack, cloud-init, and the static checks for both. Not the deployment pipeline (ADR-002, Stage 4), not the `lab` toolchain profile (Stage 3), not backup design (ADR-007) |
| Related | ADR-001 (D4 to D6, section 4 credential placement), ADR-002 (bootstrap separation, Resource Manager), ADR-005 (toolchain), baseline sections 3, 6 and 7 |

> This ADR records a decision. It does not create any OCI resource, and it does not authorize any Terraform run, IAM change, or workflow.
> Detail and rationale are in `docs/cr/CR-16/design.md`; this record keeps the decision itself.

---

## 1. Context

Verified facts (approver's Console and Cloud Shell inspection, and Oracle's Always Free reference):

- The tenancy is a Free Tier account in `uk-london-1` with three availability domains, no compute, no volumes, and no quotas. One administrator user exists, with MFA and no API keys.
- A1 limits are 2 OCPU and 12 GB in total for the region. They are usable in AD-1 and AD-3 and are zero in AD-2.
- Always Free storage is 200 GB of combined boot and block volume, five volume backups, 20 GB Object Storage, and Resource Manager stacks and jobs. Oracle reclaims idle Always Free A1 instances (7-day utilization below 20%).
- ADR-001 requires that neither host holds OCI credentials, and ADR-002 requires that IAM, quotas, and the budget live in a separately applied bootstrap stack.

## 2. Decision

1. **Two stacks, two states, both in Resource Manager.** The **bootstrap stack** (Tier 0: compartment, quotas, budget, instance-principal IAM, Vault) and the **lab stack** (network, one instance, block volume, backup bucket, Bastion). The approver applies both in the OCI Console. The pipeline of ADR-002 takes over the lab stack only, and only in Stage 4.
2. **Always Free is enforced in three layers**: the account state (Free Tier), compartment quotas that set every family to zero except the allowlist, and input validation plus a resource-type allowlist in the code, checked in CI. A plan-level allowlist check arrives with the pipeline (ADR-002 section 5).
3. **One instance**: `VM.Standard.A1.Flex`, 2 OCPU, 12 GB, Ubuntu 24.04 aarch64, in AD-1 or AD-3 (chosen by a variable, never AD-2).
4. **Storage (D5)**: 50 GB boot volume and 100 GB block volume for `/srv/work`, 150 GB of the 200 GB allowance. The remaining 50 GB is reserved for the rebuild path of ADR-006. The block volume cannot be destroyed by a stack change.
5. **Network (D4)**: one VCN, one public subnet, an internet gateway, and one network security group (NSG) on the instance. SSH (TCP 22) is allowed only from addresses in a variable, which must not contain `0.0.0.0/0` and has no default, so the instance is unreachable until the approver sets it. SSH is key-only. OCI Bastion is the break-glass path.
6. **Cost guard (D6)**: a budget on the lab compartment with actual and forecast alerts at a very low amount, so any unplanned spend is reported within a day.
7. **Instance principal**: a dynamic group matching only the lab compartment, with a policy limited to read-only inspection of the compartment, object access to the backup bucket, and reading one Vault secret. No write access to compute, network, IAM, or quotas.
8. **No identifiers in the repository.** OCIDs, namespaces, addresses, network ranges, the SSH public key, and the alert recipient are stack variables entered in the Console. Outputs are marked sensitive and are read in the Console only.
9. **Verification before use.** The OCI-specific syntax and service behavior listed in design section 8 is verified from Oracle's documentation in the first implementation PR that depends on it, and any difference is recorded in that PR.

## 3. Alternatives considered

| Alternative | Outcome | Reason |
|---|---|---|
| Private subnet only, access through Bastion | Rejected for v1 | Every session would need a Bastion session. Claude Desktop SSH through `ProxyJump` expects a stable TCP endpoint. Bastion stays as break-glass. |
| Public SSH from anywhere with fail2ban | Rejected | Internet-wide exposure of an AI-operated host (Z2) for no benefit when the source can be restricted. |
| Reserved public IP | Not in v1 | The ephemeral address lasts for the instance's life. Revisit with ADR-006 if rebuilds replace the instance. |
| One stack for everything | Rejected | ADR-002 requires the pipeline never to manage IAM, quotas, or the budget. |
| Terraform from the workspace or the lab VM | Rejected | ADR-001 and ADR-002: no OCI credentials on either host. |
| Preserve the boot volume on instance termination | Rejected for v1 | 50 + 100 + 50 GB would use the whole 200 GB allowance and leave no room for a replacement volume. ADR-006 decides the rebuild path. |

## 4. Consequences

**Positive:**
- A mistake, a compromised branch, or a misconfigured variable cannot create paid resources: the quotas stop it at the OCI side.
- The instance is invisible to the internet until the approver supplies the allowed source range.
- Everything is reproducible from the repository plus a short list of Console variables.

**Negative:**
- Two manual applies in Stage 2, and plan review in the Console.
- If the allowed source address changes (corporate egress), the approver updates a variable and re-applies, or uses Bastion.
- The A1 instance can be reclaimed if it stays idle for seven days. This is accepted (RR-S2-3).

**Residual risks** are in design section 7.

## 5. References

- Oracle, Always Free resources: https://docs.oracle.com/en-us/iaas/Content/FreeTier/resourceref.htm
- ADR-001, ADR-002, ADR-005 in this repository.
