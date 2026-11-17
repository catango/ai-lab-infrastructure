# CR-16 Acceptance criteria

Verified by the implementation PRs and by the approver's acceptance run. "CI" means a green run of the named check on a test PR.
"Approver" means a test only the approver can run (Console, Cloud Shell, or the corporate network). Evidence from OCI is reported as
yes/no, counts, and sizes, never identifiers or addresses.

## Code checks (C)

| ID | Criterion | Evidence |
|---|---|---|
| C-1 | `tofu fmt -check` and `tofu validate` pass for both roots, and the provider is pinned exactly with committed checksums. | CI `quality-gate` (`iac` check) |
| C-2 | A resource type outside a root's allowlist fails the gate. | Fixture with a disallowed resource type |
| C-3 | A fixture with a different shape, a larger OCPU or memory value, or a larger volume fails the gate. | Fixtures, one per case |
| C-4 | `ssh_source_cidrs` rejects the all-addresses range and an empty list; `availability_domain_index` rejects 2; `ssh_public_key` rejects a non-Ed25519 key; `bastion_client_cidrs` rejects the all-addresses range and an empty list; `security_compartment_name` rejects a value equal to `compartment_name`. | `tofu validate` with test variable files in the test suite |
| C-5 | No identifier, `*.tfstate*`, or `*.tfvars` is committed. | `public-repo-hygiene`; fixtures for state and variable files |
| C-6 | `scripts/stack-zip` produces byte-identical zips on two runs and includes only the chosen root. | Unit test comparing checksums and listing |
| C-7 | The `iac` check reports skip (77) without network and never passes silently. | Gate test in a network-less sandbox |

## Bootstrap stack (B), approver

| ID | Criterion | Evidence |
|---|---|---|
| B-1 | The plan creates only the resources in design section 4, and no other family. | Plan review in the Console; resource counts in the PR |
| B-2 | After the apply, an attempt to create a non-allowlisted resource in the lab compartment (for example a second instance or a database) is refused by quota. | Approver's test, result yes/no |
| B-3 | The A1 quota allows exactly 2 OCPU and 12 GB. | `oci limits` in Cloud Shell (read-only), values only |
| B-4 | A budget targeting the root compartment exists, with both rules: actual spend (absolute threshold) and forecast spend (100%), and an alert recipient is configured. | Console inspection |
| B-5 | The dynamic group matches only instances of the lab compartment. | Console inspection |
| B-6 | The policy grants no write access to compute, network, IAM, or quotas. | Console inspection of the policy text |
| B-7 | The Vault is in the security compartment, uses the default type, and has one key with `prevent_destroy`. No secret value was created by Terraform. | Console inspection, and the code review of the key's lifecycle block |

## Lab stack (L), approver

| ID | Criterion | Evidence |
|---|---|---|
| L-1 | One A1 instance is running in `uk-london-1` with 2 OCPU and 12 GB, in AD-1 or AD-3. | Console, yes/no and sizes |
| L-2 | Boot volume 50 GB and block volume 100 GB; total storage is 150 GB or less. | Console, sizes |
| L-3 | SSH from the allowlisted source with the lab key succeeds, through `ProxyJump`. | Approver's login |
| L-4 | SSH with a password is refused, root login is refused, and SSH from a source outside the allowlist times out (for example from Cloud Shell). | Approver's tests, results yes/no |
| L-5 | `/srv/work` is mounted from the block volume, survives a reboot, and is owned by the login user. | `findmnt` and a reboot test |
| L-6 | Cloud-init finished without errors and wrote its marker; `git` and `ansible-core` are installed from the Ubuntu archive. | `cloud-init status` and package list |
| L-7 | A port-forwarding Bastion session reaches the instance, and the NSG's TCP 22 sources are exactly the `ssh_source_cidrs` ranges plus the Bastion's private endpoint address. | Approver's test (break-glass) and Console inspection of the NSG |
| L-8 | The instance holds no OCI credentials, and its instance principal can read the compartment but cannot create or modify any resource. | Metadata-service login test; a write attempt is refused (Stage 3 may complete this) |
| L-9 | Re-applying the unchanged stack reports no changes. | Plan summary in the Console |
| L-10 | Destroying the block volume through a stack change is refused by `prevent_destroy`. | Plan or apply error in a throwaway change in the approver's session |
| L-11 | After a stop and start of the instance, `/srv/work` mounts with its data intact. | Approver's test: write a marker file, stop and start from the Console, check the mount and the file |

## Cost and privacy (K)

| ID | Criterion | Evidence |
|---|---|---|
| K-1 | The tenancy shows zero cost for the first full billing cycle after the apply. | Cost Analysis in the Console |
| K-2 | Outputs of both stacks are marked sensitive and contain no value visible in the repository, a PR, or an Actions log. | Code review and the gate; `grep` of the PR text |
| K-3 | No OCI credential exists on the workspace or the lab VM, and no API key exists for the administrator user. | `workspace/verify.sh` V-4 and Console inspection |

## Documents and process (D)

| ID | Criterion | Evidence |
|---|---|---|
| D-1 | `docs/operations/oci-seed.md` lists the apply order, every variable, the tests above, and the rollback. | Review |
| D-2 | `docs/README.md` lists CR-16 and ADR-004 with their current status. | This design PR, then the last implementation PR |
| D-3 | The final implementation PR carries the complete evidence table and `Closes #16`. | PR body |
