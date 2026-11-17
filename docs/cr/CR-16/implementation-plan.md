# CR-16 Implementation plan

Starts only after the design PR is merged (ADR-003 section 4). Each implementation PR uses branch `impl/CR-16-<slug>`, declares `Implements: #16` and `Design: #<design PR>`, and keeps its own checkpoint list. Each PR is small and reviewable in one sitting.

## 1. Order and dependencies

| # | PR (branch slug) | Content | Needs | Acceptance criteria |
|---|---|---|---|---|
| 1 | `iac-checks` | `scripts/checks/iac.sh`, `scripts/stack-zip`, fixtures and tests, `.gitignore` entries, the OpenTofu step in the `quality-gate` job | Design merged; V2-3 answered | C-1 to C-7 (on skeleton roots) |
| 2 | `bootstrap` | `terraform/bootstrap/`, the quota family list, tests for the validations | PR 1; V2-1, V2-2, V2-4 answered | C-1 to C-5 for the bootstrap root |
| 3 | `lab` | `terraform/lab/`, cloud-init template, tests for the validations and the cloud-init content | PR 2 merged and applied; V2-5, V2-6 answered | C-1 to C-5 for the lab root |
| 4 | `oci-seed-finish` | `docs/operations/oci-seed.md`, `docs/README.md` and CR-16 README updates, the acceptance evidence table; `Closes #16` | PRs 1 to 3 and the approver's acceptance run | D-1 to D-3, B, L, K |

PR 2 can be reviewed in parallel with PR 1, but it needs the gate to run its tests. PR 3 should be opened only after the approver has applied the bootstrap stack, because it needs the compartment from the outputs.

## 2. Checklist per PR

- [ ] Draft PR opened with the implementation template, `Implements:` and `Design:` filled in
- [ ] Tests or fixtures written first for the criteria in the table above
- [ ] Implementation complete
- [ ] `./scripts/quality-gate.sh` passes; any skipped check is reported
- [ ] CI green
- [ ] Acceptance evidence recorded in the PR body
- [ ] Marked ready for review

## 3. Work detail by PR

**PR 1: iac-checks.** A deterministic check script, not prompt instructions. It runs `tofu fmt -check`, `tofu init -backend=false`, and `tofu validate` for each root under `terraform/`, and compares each `resource` block type against the root's allowlist file. It reads literal values for shape, OCPUs, memory, and volume sizes. `scripts/stack-zip <root> <tag>` builds the zip from `git archive`, with sorted entries and fixed timestamps. Skeleton roots with only `versions.tf` make the check runnable before the stacks exist.

**PR 2: bootstrap.** Compartment, quota policy generated from the approved family list, budget with alerts, dynamic group and policy, Vault and key. Variable validations as in design section 3. The PR body lists the exact Console steps for the approver (create the stack from the zip, set variables, plan, review, apply) and what to report back (counts only).

**PR 3: lab.** Network, NSG, instance, volumes, bucket, Bastion, cloud-init. `lifecycle` rules: `prevent_destroy` on the block volume, `ignore_changes` on the image. Cloud-init content is tested as text (SSH drop-in, mount unit, marker) and checked against `cloud-init schema` when that tool is available (otherwise reported as skipped).

**PR 4: oci-seed-finish.** The runbook, the index updates, and the evidence table.

## 4. User-only actions (Claude does not run these)

Each is listed with its exact commands or Console steps in the runbook and in the PR that needs it.

| When | Action |
|---|---|
| Before PR 1 | Run the read-only S2e command in Cloud Shell and report the highest Terraform version offered (V2-3) |
| Before PR 2 | Run the read-only quota-family listing in Cloud Shell (V2-1), and tell me the budget amount and who receives alerts (design Q3) |
| After PR 2 merges | Build the bootstrap zip, create the stack in Resource Manager, enter the variables, review the plan, apply |
| Before PR 3 | Create the lab VM login key pair on Windows with the OS-bundled OpenSSH (ADR-001 section 4); report the egress result (O-9) |
| After PR 3 merges | Build the lab zip, create the stack, enter the variables (including the public key and the allowed range), review the plan, apply |
| After the lab apply | Run the acceptance tests of acceptance sections B and L that need the Console or a second network |
| After PR 4 | Review and merge; the CR closes with the merge |

## 5. What this plan does not do

- No pipeline: workflows that touch OCI arrive in Stage 4, after Spike S2.
- No `lab` profile content, no `labctl`, no backups: Stage 3 and ADR-006 and ADR-007.
- No OCI credential of any kind in the repository, on the workspace, or on the lab VM.
