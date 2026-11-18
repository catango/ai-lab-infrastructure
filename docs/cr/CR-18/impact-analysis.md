# CR-18 Impact analysis

## 1. What changes

- A new ADR (ADR-011) that adds the operator tier and amends ADR-001's credential placement.
- ADR-001 gains zones Z6 and Z7 and credential rows, and ADR-005 gains the `operator` profile. Both edits are in this design PR.
- A new directory `scripts/operator/` with a shared Python library, the `setup` script, the `facts` script, `github-setup`, `acceptance`, and a machine-profile data file, built in later implementation PRs.
- A new Ansible playbook `ansible/operator.yml` with its roles, and `toolchain/python/operator.lock`, built in the `operator-profile` PR.
- A new runbook `docs/operations/operator.md`: the platform operator VM runbook, the lab operator VM bootstrap, the `ssh` config templates, and the break-glass runbook.
- The manual runbooks `docs/operations/gate-0-audit.md` and `github-setup.md` are shortened to the parts that stay manual, and point at the scripts, once the scripts exist. The removed steps stay in an appendix.
- The lab build (CR-16) gains a lab operator VM, alarms, and rebuild requirements (section 2, design section 7), through a new design PR.
- Two separate PRs, not part of this one: a design PR that adds rule PC-8 to ADR-003, and a change PR for `CLAUDE.md` and the deny rules.

Nothing in this design PR creates a machine, a user, a token, a script, or an OCI or GitHub change.

## 2. Affected components and records

| Item | Effect |
|---|---|
| ADR-001 | Amended in this PR: zones Z6 and Z7, B3, the OCI credentials and personal-account rows, and new rows for T2, T3, the instance principal of the lab operator VM, the operator SSH keys, the SSH key to the lab VM, the operator sudo password, the `ssh` config entries, and the notification recipient. Decision 5, B1, AC1-3, and RR-8 keep their wording. T1 is re-entered on Z2 after a lab VM rebuild and is never placed on an operator machine |
| ADR-002 | No new trigger and no automated apply. Monitoring and Notifications are added to the plan allowlist, and a new allowlist rule requires an alarm per instance. Break-glass is a normal stack apply through the gates. Both are done in the CR-16 design PR |
| ADR-003 | Operator scripts are code, so they follow the PR workflow and the quality gate. PC-8 is proposed in a separate design PR. The tag ruleset of R3 is repository configuration applied by the approver |
| ADR-005 | The `operator` profile for minimal Ubuntu 24.04 x86-64 and `toolchain/python/operator.lock`. The CR-2 manifest check rule is extended from `builder` and `lab` to `operator` |
| ADR-006 | D7, in-place boot-volume replacement, becomes the break-glass mechanism for both OCI VMs. Durable state only on `/srv/work` and in GitHub |
| ADR-007 | restic protects `/srv/work`. The volume backup count is shared |
| ADR-008 | Carries the project-side operator contract, including read-only fact credentials for project environments under Q39 |
| CR-16 and ADR-004 | A new design PR after both changes are merged adds: the lab operator VM in a public subnet with the reserved public IP, the minimal Ubuntu 24.04 image if available, no Bastion, in-place rebuild of both VMs as break-glass, the allowlist, public keys, and cloud-init release tag as stack variables, the read-only dynamic group for the lab operator VM in the bootstrap stack with tenancy limits read, one absence alarm per instance with the Q35 parameters, one Notifications topic, an NSG rule from the operator VM to the lab VM, cloud-init running `setup --apply`, the A1 allowance of 2 OCPU and 12 GB, a block storage budget with two boot volumes and replacement headroom that leaves about 50 GB for D5, and the availability domain. CR-16 is not edited by this PR |
| D4 | Aligned per Q31: an SSH allowlist, rebuild as break-glass, no Bastion |
| D5 | About 50 GB or less (Q24). The baseline proposes about 100 GB |
| D6 | The compartment quotas allow Monitoring alarms and Notifications |
| CHG-001 | Unchanged. Access uses the OS-bundled OpenSSH. Break-glass and Cloud Shell runs use the browser |
| `workspace/verify.sh` V-4 | Unchanged. It checks the invoking user's home, and it runs as the AI user |
| `CLAUDE.md` and the deny rules | A separate change PR names both operator machines as hosts the AI never reaches or probes, points to the machine-profile file, and adds deny rules for `scripts/operator/*` and for `ansible-playbook` with `ansible/operator.yml` |
| `docs/operations/gate-0-audit.md`, `github-setup.md` | Shortened by the implementation PRs, not by this PR |

## 3. Security and privacy

- This is a trust-boundary change: credentials exist on operator machines for the first time. The machines are separate from the AI hosts, and no OCI credential is stored or typed on any of them.
- The lab operator VM is on a public IP, with NSG ingress from the corporate egress only (RR-OP-6). Its instance principal gives standing read access (RR-OP-27).
- The operator has sudo on both machines, with a password each time. Only `setup` and `facts --privileged` call it, and every other privileged step is a reviewed Ansible task (RR-OP-8).
- AI-written code runs with credentials the AI never sees (RR-OP-1). The controls are review and release tags created by the approver, the commit check, a fixed operation list, short-lived in-process credentials, read-only fact collection enforced in code, and sanitised output.
- T2 can remove rulesets during its 1-day lifetime (RR-OP-10). T3 is read-only (RR-OP-32).
- The repository is public. Scripts, profiles, and data files contain no identifier. Their output to the approver is a summary without OCIDs, addresses, or names. The `ssh` config templates use placeholders, and alarm emails are never pasted into chat or a PR.

## 4. Operational impact on the approver

The approver, not Claude, performs these.

- Apply the tag ruleset (R3), and create a release tag before the first use of a changed operator script or profile.
- Install `git` and clone the release tag on the platform operator VM, run `facts` there (with `--privileged`), and paste the safe output into the `operator-profile` PR.
- Run `setup` on the platform operator VM, set the operator's sudo password, confirm an operator login from a second session, run the lock play, and test the separation (U-1) on each machine.
- Run `facts --scope oci` in Cloud Shell (or read the Console) before the CR-16 design PR.
- Create and revoke T3 per GitHub facts run or `github-setup` dry run, and T2 per `github-setup` apply run.
- Provide the corporate egress allowlist, the SSH public keys, the notification recipient, and the suppression windows as stack variables, and apply the lab stack for rebuilds.
- Retire the Z1 operator user once the platform operator VM works (Q25).
- Review operator scripts, `setup`, the profile, and `facts` with extra care: they are the code that runs with credentials.

## 5. Dependencies and assumptions

- Implementation PRs that do not need OCI start after this design merges. Scripts that need the lab operator VM wait for CR-16 to be merged and applied (Q8).
- The platform operator VM exists, runs minimal Ubuntu 24.04 on x86-64, is reached over SSH, and has internet access. Its other facts come from `facts`.
- The operator machines are always available. Claude Code never probes them (Q14).
- Outbound internet access works from both machines for the apt archive, the release tags, and the manifest downloads.
- The operator's name is never written in the repository.

## 6. Cost and capacity

No cost from this design PR, and no OCI resource is created by it. The later lab build adds:

- A micro instance within the Always Free tier (VO-8). Alarms and Notifications are expected to stay within the Always Free limits (VO-13).
- The A1 allowance of 2 OCPU and 12 GB is fully used by the lab VM, so the lab operator VM uses the x86 micro allowance and no A1 capacity.
- The 200 GB Always Free block storage holds two boot volumes plus the temporary second boot volume of an in-place replacement, which leaves about 50 GB for D5 (VO-14).
- Public IPv4 addresses: one reserved for the lab operator VM and one ephemeral for the lab VM, with no address left for a third VM (VO-12).
- Volume backups: five are shared, and the lab operator VM has none.
- The operator profile and its tools must fit in 1 GB of memory (VO-7).

## 7. Rollback

Delete the scripts and the profile through a PR, revoke any T2 and T3, retire the operator users, and revert ADR-011 and the ADR-001 and ADR-005 amendments. For the lab build, remove the lab operator VM, its alarm, and its dynamic group through the stack. The manual runbooks stay valid throughout, so rollback loses no capability (the shortened runbooks keep the removed steps in an appendix).

## 8. Alternatives considered

See ADR-011 section 3.
