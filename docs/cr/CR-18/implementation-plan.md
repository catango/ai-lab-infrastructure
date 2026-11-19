# CR-18 Implementation plan

Starts only after the design PR is merged (ADR-003 section 4). Each implementation PR uses branch `impl/CR-18-<slug>`, declares `Implements: #18` and `Design: #<design PR>`, and keeps its own checkpoint list. Each PR is small and reviewable in one sitting. The order follows the approver's decision Q7.

## 1. Order and dependencies

| # | PR (branch slug) | Content | Needs | Acceptance criteria |
|---|---|---|---|---|
| 1 | `operator-lib` | `scripts/operator/lib/` (modes, release-tag commit check, sanitiser, exit codes, and the HTTP client with its GET-only mode), the gate checks (S-6, S-11), `scripts/operator/machine-profiles.toml`, the CI job with resource limits, tests | Design merged | S-1 to S-7, S-10, S-11 |
| 2 | `operator-facts` | `scripts/operator/facts`, host scope with `--privileged`, `--measure-bandwidth`, and `--write-allowlist`, and its tests | PR 1; VO-15 answered | F-1 |
| 3 | `operator-profile` | `scripts/operator/setup`, `ansible/operator.yml` and its roles, `toolchain/python/operator.lock`, the `operator` profile in the manifest, and a CI job running `setup --apply` twice in a pinned minimal Ubuntu 24.04 container | PR 1 and PR 2; the platform operator VM facts pasted into the PR; the first release tag | P-1 to P-8, ADR-005 AC5-6 |
| 4 | `github-setup` | `scripts/operator/github-setup`, the desired-state file, and `facts --scope github`, with tests | PR 1 and PR 3 applied on the platform operator VM with U-1 done; VO-3, VO-4, VO-17 answered; the tag ruleset (R3) applied | F-3, G-2, G-3, U-4 |
| 5 | `facts-oci` | `facts --scope oci`, merging `oci-audit` into it, usable in Cloud Shell before CR-16, with tests using sample output | PR 2; VO-1 and VO-16 answered | F-2, G-5 |
| 6 | `acceptance` | `scripts/operator/acceptance`, the criterion registry from CR-16's acceptance tables | PR 1; CR-16 merged and its stacks applied; the lab operator VM working | G-4, L-1, L-2, W-1, W-2 |
| 7a | `operator-finish-docs` | Split from PR 7 by the approver on 2026-11-19, because the OCI VMs are postponed. `docs/operations/operator.md` for what does not need an OCI VM (platform operator VM runbook, token handling, rollback), the shortened `gate-0-audit.md` and `github-setup.md` with their appendices, `docs/README.md`, and an evidence table that marks every criterion needing an OCI VM as deferred. No `Closes #18` | PRs 1 to 5; the approver's runs on the platform operator VM (`setup`, U-1, GitHub scope) | D-2, D-3, the part of D-1 above, U-2 and U-3 for the platform operator VM |
| 7b | `operator-finish` | The rest of `docs/operations/operator.md` (lab operator VM bootstrap, `ssh` config templates for both OCI VMs, break-glass runbook), the finished evidence table; `Closes #18` | PR 6, 7a, and the approver's run on the lab operator VM | D-1, D-4, U-2, U-3 for the lab operator VM |

PRs 4 and 5 are independent of each other and may be reviewed in parallel. PR 6 may be drafted earlier, but it needs CR-16's criteria. Implementation PRs that do not need OCI (1 to 4) start after this design merges. PR 6 waits for CR-16 to be merged and applied (Q8). PR 5 does not need the lab operator VM, because the OCI scope runs in Cloud Shell until it exists.

The host-separation test U-1 runs on each operator machine after its first profile apply and before the first credential there. For the platform operator VM that is between PR 3 and PR 4.

## 2. Checklist per PR

- [ ] Draft PR opened with the implementation template, `Implements:` and `Design:` filled in
- [ ] Tests or fixtures written first for the criteria in the table above
- [ ] Implementation complete, with the "Operator script review" section of PC-8 once that rule is merged
- [ ] `./scripts/quality-gate.sh` passes; any skipped check is reported
- [ ] CI green
- [ ] Acceptance evidence recorded in the PR body
- [ ] Marked ready for review

## 3. Work detail by PR

**PR 1: operator-lib.** A Python shared module used by every operator script (modes, the release-tag commit check, the sanitiser, exit codes, and an HTTP client that reuses the `pr-contract` API client and has a read-only mode that refuses any method other than GET). Gate checks reject `shell=True`, `os.system`, `eval`, `exec`, Terraform calls, OCI write verbs, and `sudo` outside `setup` and `facts --privileged`. The machine-profile data file starts with the architecture and OS of both machines. The CI job runs the tests under the memory and CPU limits of the strictest profile.

**PR 2: operator-facts.** The host scope of `facts`, the privileged mode with its fixed command list, bandwidth measurement, and the allowlist writer. It runs on minimal Ubuntu 24.04 with only `python3` and `git`.

**PR 3: operator-profile.** `setup` (the single Bash script), the Ansible playbook and its roles (hardening, sudoers, firewall with timer-based revert, packages, tools, the OCI CLI in a hash-locked venv, the lock play, the separation checks), and the CI job. The PR shows the approver the exact package list and sources, and the platform operator VM facts.

**PR 4: github-setup.** The desired state of repository settings, security features, rulesets, environments, and the collaborator as a data file, applied through GitHub REST calls with `urllib`. The dry run uses T3 and the apply uses T2. The permissions of both tokens are shown in the PR for the approver. The GitHub scope of `facts` is added here.

**PR 5: facts-oci.** The OCI scope of `facts`: `list`, `get`, and `inspect` verbs only, a dry run that prints the exact commands, and counts and yes/no as output. It replaces the separate `oci-audit` script.

**PR 6: acceptance.** A registry of criteria by ID, each with how to run it (or `manual`). The runner reports yes or no per ID and reaches the lab VM with a dedicated SSH key over private IPs.

**PR 7a: operator-finish-docs.** The runbook parts that do not need an OCI VM, the shortened manual runbooks (the removed manual steps stay in an appendix), the `docs/README.md` status, and the evidence table with the criteria that need an OCI VM marked deferred (L-1, L-2, W-1, W-2, G-4, and U-1, U-2, U-3 for the lab operator VM). Written while the OCI work is postponed (baseline, section 6). It does not close #18.

**PR 7b: operator-finish.** The runbook parts that describe the lab operator VM and the break-glass rebuild, the `ssh` config templates for both OCI VMs, and the finished evidence table. It closes #18 and needs PR 6 and the approver's runs.

## 4. User-only actions (Claude does not run these)

| When | Action |
|---|---|
| Before PR 3 | Apply the tag ruleset (R3) in the repository settings. After PR 2 merges, create the first release tag, install `git` and clone the tag on the platform operator VM, run `facts` (with `--privileged`), and paste the safe output into the PR 3 description |
| Before the CR-16 design PR | Run `facts --scope oci` in Cloud Shell (or read the Console) and give the values to the design PR |
| Before each first use of a changed operator script or profile | Create a release tag |
| After PR 3 merges | Run `setup` on the platform operator VM (dry run, review, then `--apply` with the sudo password), confirm an operator login from a second session, run the lock play, and run U-1. Retire the Z1 operator user (Q25) once the platform operator VM works |
| Each GitHub facts run or `github-setup` dry run | Create T3 at the prompt's request, then revoke it |
| Each `github-setup` apply run | Create T2 at the prompt's request, then revoke it |
| After CR-16 is applied | Check the lab operator VM (L-1, L-2), run U-1 on it, and test a break-glass rebuild once per OCI VM (W-2) |
| After PR 6 | Run the acceptance script with `--apply` on the lab operator VM |
| After PR 7a | Review and merge; the CR stays open |
| After PR 7b | Review and merge; the CR closes with the merge |

## 5. What this plan does not do

- No Terraform, no OCI resource changes from operator scripts (ADR-011 decision 5).
- No change to the `CLAUDE.md` dry-run convention. The `CLAUDE.md` and deny-rule changes are a separate change PR.
- No change to CR-16 in this plan: the lab operator VM, alarms, and rebuild requirements are added to CR-16's design by a new design PR after both changes are merged.
- No credential in the repository, in an AI user's home, or on the lab VM, and no T1 on an operator machine.
- No sudo anywhere except in `setup` and in `facts --privileged`.
