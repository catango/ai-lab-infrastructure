# CR-16: Stage 2 OCI seed

| Field | Value |
|---|---|
| Issue | #16 |
| Class | 3 |
| Status | Design in review. The approver's review handoff of 2026-11-17 is applied, and the operator-tier requirement of 2026-11-18 is added (design section 6.3, ADR-004 decision 10). Nothing is decided yet, so Q1 to Q14 stay open (design section 9). Nothing is implemented |
| ADR | [ADR-004](../../adr/ADR-004-oci-baseline.md) (Proposed; becomes Accepted when this design PR is merged by the approver) |
| Stage | 2 of the build sequence (baseline section 6) |

## Summary

Designs the OCI baseline: the bootstrap stack (compartment, quotas, budget, instance-principal IAM, Vault), the lab stack
(network, one A1 instance, block volume, backup bucket, Bastion), cloud-init, and the static checks that keep the
Infrastructure as Code inside the Always Free allowance. Both stacks are applied by the approver in the OCI Console
(Resource Manager); the automated pipeline of ADR-002 is Stage 4. Design only: no Terraform, scripts, or workflows in this PR.

## Files

| File | Purpose |
|---|---|
| [impact-analysis.md](impact-analysis.md) | What changes, security and cost impact, rollback |
| [design.md](design.md) | The design, decisions S2-1 to S2-14, risks, and the open questions for the approver |
| [acceptance-criteria.md](acceptance-criteria.md) | Testable criteria with evidence |
| [implementation-plan.md](implementation-plan.md) | Implementation PRs, order, user-only actions |

## Inputs recorded before this design

Collected by the approver from the OCI Console and Cloud Shell (read-only, summaries only): Free Tier account;
home region `uk-london-1` with three availability domains; no compute, no block volumes, no quotas; one administrator user
with MFA and no API keys or auth tokens; A1 limits of 2 OCPU and 12 GB regionally, available in AD-1 and AD-3 and zero in AD-2.
Decisions D3 to D6 of the baseline were accepted as written. The egress address (O-9) is still being observed and enters
the design only as a variable.
