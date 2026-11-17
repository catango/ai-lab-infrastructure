# ADR-002: Infrastructure Deployment Pipeline

| Field | Value |
|---|---|
| Status | **Accepted, conditional on Spike S2** |
| Date | 2026-11-17 |
| Repository | `ai-lab-infrastructure` (target location: `docs/adr/ADR-002-infrastructure-deployment-pipeline.md`) |
| Supersedes | Earlier baseline items D2 (OpenTofu on Windows) and D12 (Cloud Shell as primary control plane) |
| Related | CHG-001 (no developer tools on Windows, MCP allowed, GitHub via plugin), CHG-002 (conditional waiver, see Section 7), D6, D8/D13, ADR-001 (pending) |

> This ADR records an architecture decision. It does **not** authorize creating OCI resources,
> IAM changes, GitHub repositories, environments, or workflows. Each of those requires separate
> explicit authorization under Section 20 of the master prompt.

---

## 1. Context

Verified facts:

- CHG-001 forbids developer tools on Windows, so no Terraform, OpenTofu, OCI CLI, or Git there.
- OCI Resource Manager is a managed Terraform service. Its stacks and jobs are in the Always Free allotment, and it stores Terraform state inside OCI.
- OCI IAM supports Workload Identity Federation (WIF): a GitHub Actions OIDC token can be exchanged for a short-lived OCI session token bound to a key pair (proof-of-possession).
- On GitHub Free, environments, environment secrets, required reviewers, and disabling admin bypass are available **only in public repositories**.
- Claude Code pushes as a machine account with write access. Repository-level Actions secrets are available to workflows on branches pushed by write-access users, so an AI-authored branch workflow could use them.
- Actions logs and artifacts in a public repository are publicly visible.

Assumptions still to verify (Section 8):

- WIF token exchange works in an Always Free tenancy's identity domain.
- Resource Manager job permissions can be scoped narrowly to one stack.

## 2. Decision

1. **Executor: OCI Resource Manager.** A single Resource Manager stack owns all lab resources. IaC is **Terraform**, written in the HCL subset compatible with OpenTofu to preserve portability.
2. **Orchestrator: GitHub Actions** in the public `ai-lab-infrastructure` repository, on standard GitHub-hosted runners only.
3. **Authentication: OIDC Workload Identity Federation.** No long-lived OCI credential is stored in GitHub. The OCI token exchange accepts only GitHub tokens whose claims match the trust rules in Section 4.
4. **Two human approval gates:**
   - **Gate 1, design and code.** A PR to `main` authored by the machine account. The ruleset requires approval by the personal account, approval of the most recent push, and passing required checks. The personal account merges.
   - **Gate 2, apply.** GitHub environment `oci-apply` lists the personal account as its **only** required reviewer. Deployments are allowed from `main` only, and administrator bypass is disabled. "Prevent self-review" stays **off**, because the personal account is both merger and approver.
5. **Plan privacy.** Full Terraform plans and job logs stay in the OCI Console. GitHub logs contain only a pass/fail summary: resource add/change/destroy counts and the allowlist-check result. No OCIDs, IP addresses, or usernames appear in public output.
6. **Bootstrap separation.** IAM policies, identity domain configuration, the WIF trust, the compartment, compartment quotas, and the budget alert live in a separate **bootstrap stack**. You apply it manually in the OCI Console. The pipeline can never manage IAM or its own trust.
7. **Break-glass.** You can run Resource Manager plan and apply jobs directly from the OCI Console at any time, independently of GitHub.

## 3. Deployment sequence

1. The machine account opens a PR with the infrastructure change. CI runs static checks with no OCI access: format, validate, IaC scanning, the "no identifiers" lint, and secret scanning.
2. You review and merge the PR. This is Gate 1.
3. A push to `main` triggers the **plan job** (environment `oci-plan`, no reviewer, `main` only):
   1. Request a GitHub OIDC token and exchange it for an OCI session token.
   2. Update the stack's configuration source from the merged commit SHA.
   3. Create a Resource Manager **plan** job and wait for it to finish.
   4. Run the resource allowlist check against the plan (shapes, sizes, services) and report only the summary.
4. You review the full plan in the OCI Console.
5. You approve the `oci-apply` environment. This is Gate 2.
6. The **apply job** obtains a fresh session token and creates a Resource Manager **apply** job that references the reviewed plan job, not a new plan.
7. The workflow records the commit SHA, plan job ID, apply job ID, and outcome as a summary. OCI Audit records the federated principal and the GitHub subject.

## 4. Trust and permission requirements

**WIF trust rules.** Final syntax depends on S2.

- Issuer must be GitHub Actions.
- The `repository` claim must match the `ai-lab-infrastructure` repository.
- The `sub` claim must match `repo:<owner>/ai-lab-infrastructure:environment:oci-plan` or `...:environment:oci-apply`. GitHub includes the environment in `sub` when a job references an environment.
- `workflow_ref`, if available as a trust condition, must be pinned to the deploy workflow file on `refs/heads/main`.
- Tokens from any other branch, workflow, environment, or fork are rejected by OCI.

**IAM intent.** This is not final policy syntax.

| Principal | Allowed | Never allowed |
|---|---|---|
| Federated `oci-plan` identity | Read the stack; update its config source; create and read **plan** jobs on that one stack | IAM, identity domains, policies, quotas, budgets; any other compartment; apply jobs |
| Federated `oci-apply` identity | Create and read **apply** jobs on that one stack | Same as above |
| Resource Manager job execution | Manage only allowlisted lab resources in the lab compartment | IAM; any resource outside the lab compartment |

If OCI IAM cannot distinguish plan jobs from apply jobs (S2d), both identities collapse into one. Gate 2 is then enforced by GitHub only. This is recorded as residual risk RR-2.

**Hard guards regardless of pipeline compromise:**

- Always-Free-only account state.
- Compartment quotas that set every non-allowlisted service to zero.
- No IAM rights for the pipeline.

## 5. Mandatory workflow controls

- Workflow-level `permissions: {}`. Jobs grant only `contents: read` and `id-token: write`.
- Triggers: `push` to `main` and `workflow_dispatch` only. No `pull_request_target`. No OCI-accessing job runs on `pull_request`.
- Every third-party Action is pinned to a reviewed commit SHA, and Dependabot updates Actions. The token exchange is implemented as a short, reviewed script rather than a community Action wherever practical.
- `concurrency` serializes deployments, with no cancellation of an in-progress apply.
- Any change under `.github/workflows/` or to the bootstrap stack is flagged in the PR template and requires an explicit review statement.
- Debug logging stays disabled in deploy jobs, and step outputs are filtered so no identifiers are echoed.
- Standard GitHub-hosted runners only. No self-hosted runner, and no runner on the OCI VM.

## 6. Alternatives considered

| Alternative | Outcome | Reason |
|---|---|---|
| Static OCI API key as a repository secret | Rejected | Reachable by workflows on any branch the machine account pushes. Long-lived. Violates the "no credentials in GitHub" requirement. |
| Static OCI API key as an `oci-apply` environment secret | **Fallback only** (Section 7) | Gated by reviewer approval, but still a long-lived credential held by a third party. |
| Terraform executed directly in Actions, state in Object Storage | Rejected | Plans and state details leak into public logs; needs extra state credentials. |
| Resource Manager from the Console only | Retained as break-glass | No automation or traceability to commits. |
| Cloud Shell + OpenTofu | Rejected as primary | Manual state handling and provider-authentication uncertainty. |
| IaC executed from the dev VM | Rejected | Gives an internet-facing, AI-operated host infrastructure-destroy rights, including over itself. |

## 7. Fallback: CHG-002 (conditional waiver)

**Trigger.** Spike S2 shows WIF token exchange is unavailable or unusable in the Always Free tenancy.

**Activation.** You record the S2 result in this ADR and explicitly confirm activation before any credential is created.

**Terms while active:**

- A dedicated IAM user with the same policy scope as Section 4. Its key pair is generated in OCI Cloud Shell, never on Windows. The private key is deleted from Cloud Shell after upload to GitHub.
- The key is stored **only** as an environment secret. Both the plan and apply jobs reference reviewer-gated environments, so two approvals per deployment are accepted.
- The key is rotated at least every 90 days, and immediately on any suspected compromise. Revocation means deleting the API key in the OCI Console, which takes effect immediately.
- The waiver expires when WIF becomes available. Migration is then mandatory.

## 8. Verification items (Spike S2)

All items are documentation checks or read-only Console inspection unless marked. Any configuration step requires separate authorization.

| ID | Question | Method |
|---|---|---|
| S2a | Is WIF token exchange available in an Always Free tenancy's identity domain type? | Inspect identity domain type and features in the Console; check Oracle documentation |
| S2b | Does the exchange require an OAuth client ID and secret, and with what minimum privilege? | Oracle WIF documentation; Console inspection |
| S2c | With whose permissions do Resource Manager jobs execute, and can job creation be limited to one stack? | Resource Manager IAM documentation |
| S2d | Can IAM policy distinguish plan jobs from apply jobs? | Resource Manager IAM documentation |
| S2e | Highest Terraform version Resource Manager currently offers | `oci resource-manager stack list-terraform-versions` in Cloud Shell (read-only) |
| S2f | Which GitHub OIDC claims can OCI trust rules match (`sub`, `repository`, `workflow_ref`, `environment`)? | Oracle WIF documentation; test token exchange **(requires authorization)** |

## 9. Consequences

**Positive:**
- No long-lived OCI credential in GitHub on the primary path.
- Every infrastructure change is traceable from commit to plan job to apply job to OCI Audit.
- Two human gates.
- State and plan details stay private.
- No tooling on Windows.

**Negative:**
- The infrastructure repository must stay public, because environment controls are public-only on GitHub Free.
- Terraform is used instead of OpenTofu.
- Plan review requires the OCI Console.
- Bootstrap changes remain manual.

**Residual risks:**
- **RR-1.** A GitHub account compromise of the personal account defeats both gates. Mitigation: strong MFA on the personal account and passkeys where available. OCI quotas still cap the blast radius.
- **RR-2.** If S2d fails, the apply gate depends on GitHub enforcement alone.
- **RR-3.** Oracle changes to WIF or Always Free features could break the pipeline. Mitigation: the Console break-glass path.

## 10. Acceptance criteria (verified during implementation, Phase E)

- AC-1: A workflow on a non-`main` branch cannot obtain an OCI session token (negative test).
- AC-2: No apply job runs without personal-account approval of `oci-apply`. The machine account cannot approve.
- AC-3: The federated identities cannot read or modify IAM policies, identity domains, or quotas (negative test).
- AC-4: A plan containing a non-allowlisted shape, size, or service fails the allowlist check, and no apply is offered.
- AC-5: Public workflow logs contain no OCIDs, IP addresses, or usernames (automated grep over run logs).
- AC-6: The apply job applies exactly the reviewed plan job, matched by job ID and commit SHA.
- AC-7: Break-glass Console plan and apply works with GitHub unavailable.

## 11. References

- GitHub, deployments and environments: https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments
- GitHub, managing environments: https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments
- Oracle, OCI IAM Workload Identity Federation: https://blogs.oracle.com/cloud-infrastructure/oci-iam-workload-identity-federation
- Oracle A-Team, GitHub Actions and OCI OIDC token exchange: https://www.ateam-oracle.com/github-actions-oci-a-guide-to-secure-oidc-token-exchange
- Oracle, Always Free resources: https://docs.oracle.com/en-us/iaas/Content/FreeTier/resourceref.htm
