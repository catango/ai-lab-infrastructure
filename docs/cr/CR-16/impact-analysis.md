# CR-16 Impact analysis

## 1. What changes

| Area | Change | When |
|---|---|---|
| `docs/cr/CR-16/`, `docs/adr/ADR-004-oci-baseline.md` | Added by this design PR (documents only) | Design PR |
| `docs/README.md`, `docs/architecture/baseline-v0.1.md` | Index entry for CR-16 and ADR-004; D3 to D6 recorded as accepted | Design PR |
| `scripts/checks/iac.sh`, `scripts/stack-zip`, tests, CI | New gate check and stack packaging | Implementation |
| `terraform/bootstrap/` | New bootstrap stack | Implementation |
| `terraform/lab/` and cloud-init | New lab stack | Implementation |
| `docs/operations/oci-seed.md` | New runbook | Implementation |
| OCI tenancy | Compartment, quotas, budget, IAM, Vault, then the lab resources, all created by the approver | After the implementation PRs, by the approver |

Nothing in the repository changes in the design PR other than files under `docs/` (PC-4).

## 2. Affected components and records

| Item | Effect |
|---|---|
| ADR-001 section 4 | The instance principal and the SSH key handling are implemented as written. The public key and the allowed source range are stack variables, not repository content |
| ADR-002 sections 2 and 4 | The bootstrap separation is implemented. The federation trust and Resource Manager execution policies are deferred to Stage 4 (after Spike S2) and arrive through a new design PR |
| ADR-005 | Unchanged. The gate's new `iac` check uses the OpenTofu already in the toolchain |
| Baseline section 6, stage 2 | The entry criterion "D3 to D6 approved" is met. "O-9 known" is needed before the first lab apply, not before this design merges |
| Baseline section 7 | ADR-004 moves from "to be written" to "Proposed" |

## 3. Security and privacy

- The repository is public. All identifiers (OCIDs, namespace, addresses, network ranges, SSH public key, alert recipient, availability-domain names) are stack variables or looked up at apply time. The gate keeps them out of committed text.
- The lab VM keeps no OCI credentials. Its instance principal can read, and write only to one bucket (ADR-001 section 4).
- The SSH exposure is the main new attack surface: one TCP port, key-only, restricted to a variable range that cannot be `0.0.0.0/0`.
- The compartment quotas are a hard guard that holds even if the Terraform code is wrong (ADR-002 section 4).
- Claude Code never runs Terraform or the OCI CLI against the tenancy and never sees an OCI credential.

## 4. Operational impact on the approver

The approver, not Claude, performs these. Each is listed with exact steps in the runbook and in the PR that needs it.

- Read-only inspection commands in Cloud Shell to answer V2-1 and V2-3.
- Create each Resource Manager stack from the zip, enter the variables, review the plan, and apply.
- Create the lab VM login key on Windows with the OS-bundled OpenSSH and add the public part as a variable.
- Run the acceptance tests that require the Console or a second network (the Bootstrap stack and Lab stack sections of the acceptance criteria).

## 5. Dependencies and assumptions

- Stage 1 is merged and the five required checks run on every PR.
- The approver has administrator rights in the tenancy, with MFA.
- The egress address result (O-9) is available before the first lab apply.
- The OCI provider version supported by Resource Manager works with the HCL subset used here (V2-3).
- A1 capacity is available in AD-1 or AD-3 at apply time. If it is not, the apply is retried (RR-S2-2).

## 6. Cost and capacity

- Target cost: zero. The account is Free Tier, and the stacks create only Always Free resource types within the allowance: one A1 instance (2 OCPU, 12 GB), 150 GB of the 200 GB volume allowance, one bucket within 20 GB, Bastion, and Vault with a software key.
- Budget alerts and compartment quotas guard against any other spend.
- Resource Manager stacks and jobs are in the Always Free allotment.

## 7. Rollback

- Design PR: revert the merge commit.
- Implementation PRs: each is independent and revertible in the repository.
- OCI: destroy the lab stack from the Console. The block volume has `prevent_destroy`, so the approver first removes that protection in a reviewed PR, or deletes the volume by hand after copying its data. Then destroy the bootstrap stack. The compartment can be deleted only when it is empty.
- Quotas are removed by destroying the bootstrap stack. No other tenancy resource depends on them.

## 8. Alternatives considered

| Alternative | Why not chosen |
|---|---|
| Resource Manager source-control connection to GitHub | Needs a token held by OCI and gives Resource Manager a standing link to the repository, which the manual stage does not need. The pipeline (Stage 4) revisits it |
| Terraform in Cloud Shell with local state | State handling by hand, and a larger credential surface |
| Cloud-init that runs the whole Stage 3 Ansible `lab` profile | Mixes provisioning and configuration; the profile changes without a VM replace and needs its own verification |
| A private subnet with a NAT gateway | A NAT gateway is not in the Always Free list, and a private-only host needs Bastion for every session |
