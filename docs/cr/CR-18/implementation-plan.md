# CR-18 Implementation plan

Starts only after the design PR is merged (ADR-003 section 4). Each implementation PR uses branch `impl/CR-18-<slug>`, declares `Implements: #18` and `Design: #<design PR>`, and keeps its own checkpoint list. Each PR is small and reviewable in one sitting.

## 1. Order and dependencies

| # | PR (branch slug) | Content | Needs | Acceptance criteria |
|---|---|---|---|---|
| 1 | `operator-lib` | `scripts/operator/lib/` (modes, commit check, sanitiser, exit codes), a gate check for S-6, tests, `docs/operations/operator.md` | Design merged; U-1 done | S-1 to S-7, D-1 |
| 2 | `operator-setup` | `scripts/operator/setup` (the package list, pinned tool sources with checksums for both architectures, the only use of sudo), tests | PR 1; VO-2 and VO-6 answered; Q9 decided | S-8, G-0 |
| 3 | `github-setup` | `scripts/operator/github-setup`, the desired-state file, tests | PR 1; VO-3, VO-4 answered; T2 handling decided (Q4) | G-2, G-3 |
| 4 | `oci-audit` | `scripts/operator/oci-audit`, tests with sample output | PR 2 (installs the OCI CLI); VO-1 answered; Q3 decided | G-1, G-5 |
| 5 | `acceptance` | `scripts/operator/acceptance`, the criterion registry from CR-16's acceptance tables | PR 1; CR-16 merged and its stacks applied for the lab checks | G-4, L-1 |
| 6 | `operator-finish` | Shorten `gate-0-audit.md` and `github-setup.md`, update the ADR-001 matrix wording, `docs/README.md`, the evidence table; `Closes #18` | PRs 1 to 5 and the approver's run | D-2 to D-4, U-2, U-3, G |

PRs 3 and 4 are independent of each other and may be reviewed in parallel. PR 5 may be drafted earlier, but it needs CR-16's criteria.

## 2. Checklist per PR

- [ ] Draft PR opened with the implementation template, `Implements:` and `Design:` filled in
- [ ] Tests or fixtures written first for the criteria in the table above
- [ ] Implementation complete
- [ ] `./scripts/quality-gate.sh` passes; any skipped check is reported
- [ ] CI green
- [ ] Acceptance evidence recorded in the PR body
- [ ] Marked ready for review

## 3. Work detail by PR

**PR 1: operator-lib.** A shell library sourced by every operator script. It parses `--dry-run` and `--apply` (dry run is the default), prints the commit and refuses a dirty tree or a commit outside `origin/main`, provides the confirmation prompt, the sanitiser, and the exit-code convention. A gate check rejects `eval`, Terraform calls, and OCI write calls under `scripts/operator/`. The runbook covers the one-time clone setup, the run flow, and T2 handling.

**PR 2: operator-setup.** The one script that may call sudo. It installs a fixed list of Debian packages and, from pinned sources with checksums for both architectures, the tools that are not packages (the OCI CLI among them). A dry run lists everything and installs nothing. The PR shows the approver the exact package list and sources.

**PR 3: github-setup.** The desired state of repository settings, security features, rulesets, environments, and the collaborator as a data file, applied through `gh api`. The scopes of T2 are shown in the PR for the approver.

**PR 4: oci-audit.** The read-only calls of the Gate 0 audit, printing the results block. The authentication method follows Q3.

**PR 5: acceptance.** A registry of criteria by ID, each with how to run it (or `manual`). The runner reports yes or no per ID.

**PR 6: operator-finish.** Runbook updates, the ADR-001 matrix wording, and the evidence table.

## 4. User-only actions (Claude does not run these)

| When | Action |
|---|---|
| Before PR 1 | Run the separation test U-1 on the platform workspace |
| Before PR 2 | Decide the scope of the operator's sudo (Q9) |
| After PR 2 merges | Run `setup` as the operator, in dry-run and then apply (it asks for the sudo password) |
| Before PR 3 | Decide how T2 is handled (Q4) and check the scopes in VO-3 |
| Before PR 4 | Decide the OCI authentication (Q3) |
| Each GitHub configuration run | Create T2 at the prompt's request, then revoke it |
| Each OCI audit run | Complete the browser sign-in for the session token |
| After PR 5 | Run the acceptance script in apply mode as the operator |
| After PR 6 | Review and merge; the CR closes with the merge |

## 5. What this plan does not do

- No Terraform, no OCI resource changes from operator scripts (ADR-011 decision 5).
- No change to the `CLAUDE.md` dry-run convention.
- No change to CR-16: the lab login is added to CR-16's design by a new design PR after both changes are merged.
- No credential in the repository, in the AI user's home, or on the lab VM.
- No sudo anywhere except in `setup`.
