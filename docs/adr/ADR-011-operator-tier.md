# ADR-011: Operator Tier: Rules for Credentialed and Extended-Permission Scripts

| Field | Value |
|---|---|
| Status | **Accepted** (2026-11-18, by the merge of the CR-18 design PR #19 by the approver); **amended by CR-57** (below). Verification items VO-* of CR-18 stay open only where they survive the amendment |
| Date | 2026-11-18 |
| Repository | `ai-lab-infrastructure` |
| Change request | CR-18 (issue #18) |
| Amended by (CR-57) | CR-57 (Proposed, design PR 58 for issue #57; approver's decisions of 2026-11-23, PA-23): this record is **amended, not superseded**. History: the lab operator machine (zone Z7), OCI, absence alarms, lab access, and the Ubuntu operator profile are dropped. It keeps the rules for operator scripts: dry run by default, release tags, prompted credentials, sanitised output, and standard-library Python. [ADR-012](ADR-012-host-model.md) describes the operator machine. Decisions cited by ADR-008 and ADR-009 keep their numbers. Takes effect when the CR-57 design PR is merged |
| Scope | The rules for the operator scripts that the operator user runs on the operator machine, and the credential handling that follows. The machine, its accounts, its contract, and its configuration are in ADR-012. Not the scripts themselves |
| Related | ADR-001 (B3, credential matrix; amended), ADR-003 (rule PC-8), ADR-005 (toolchain; amended), ADR-008 (decision 17 hands the project-side operator contract to ADR-008), ADR-009 (decision 3, decision 14), ADR-012 (host model) |

> This ADR records a decision. It does not create a machine, a user, a credential, a script, or any change, and it does not authorize any of them.
> Detail and rationale of the original decisions are in `docs/cr/CR-18/design.md`; labels such as Q3 or R2 are the approver's decision labels of 2026-11-18. Decisions marked *Dropped* keep their number so that citations hold.

---

## 1. Context

Some tasks cannot or should not be run by the AI user: tasks that need dedicated credentials or permissions beyond the machine account's Write role (configuring GitHub repositories, collecting facts about a host or an environment). The approver runs them as reviewed scripts on a dedicated operator machine, separate from every AI lab.

Under CR-57 there is one operator machine for this repository and every project (G-16), a Debian 13 x86-64 VM with an operator user (no sudo) and an operator admin (sudo). It holds no persisted credential, and a rebuild is a fresh VM plus the operator configuration (ADR-012).

## 2. Decision

1. **The operator tier is the operator machine** (amended; Q10, Q11 as originally decided, now one machine per G-16). The operator user runs by hand the scripts that the AI wrote and the approver reviewed and merged. The machine is separate from every AI lab: no shared storage or identity, no key or route from an AI lab, and no Claude Desktop SSH target. The AI never runs the scripts, never reaches the machine, and never probes it. Its contract is in ADR-012 section 5.
2. **Every operator script has a dry-run mode and an apply mode, and dry run is the default** (Q2, approver's decision). A dry run changes nothing and shows what apply would do. The rule applies to operator scripts only. The Bash convention in `CLAUDE.md` is unchanged.
3. **Scripts run from release tags only** (Q29, R3). The commit check requires `HEAD` to equal the commit of a release tag that is contained in `origin/main`. Tags are created by the approver only, and a tag ruleset restricts creation, update, and deletion of `v*` tags to the approver's account. A script never runs from the AI user's working tree. Amended by CR-57: on the operator machine each project's scripts run from the root-owned installation of that project's release tag (ADR-012 decisions 7 and 12).
4. **Operator credentials are prompted or short-lived** (Q3, Q4, R6; amended). They are never stored in the repository, in a place an AI user can read, or in shell history, and are handled inside the script process (decision 11).
   - **T2** (GitHub repository configuration, Q4): a fine-grained token of the personal account, limited to the repositories of the project the run serves, with Administration and Environments read and write and Metadata read only (no Contents, Pull requests, Workflows, or Secrets write), 1-day expiry, read at a prompt with `getpass`, entered only for `github-setup` apply runs, created per run, revoked in the browser after each run.
   - **T3** (read-only fact collection and `github-setup` dry runs, R6): a fine-grained token of the personal account, limited to the same repositories, with Administration read, Environments read, and Metadata read only, 1-day expiry, read at a prompt, revoked after each run. T2 is never used for fact collection.
   - Any further environment gets its own dedicated read-only credential with the same handling and a row in the ADR-001 credential matrix (Q39) or in the project's records (ADR-012 decision 2).
   - **T1 is never placed on the operator machine** and stays free of admin rights.
5. *Dropped* (CR-57; the decision was worded for OCI: operator scripts never run Terraform and never change OCI resources). No replacement rule is added; the boundary is ADR-001 B3 as amended (infrastructure or production changes happen only through reviewed operator scripts that the approver runs from a release tag). What the operator user may do is set by ADR-012.
6. **Output is safe to paste.** Standard output is a sanitised summary (yes/no, counts, sizes). Raw responses stay in the project's private output directory (mode 0700) and never enter the repository.
7. **Amendment of ADR-001** (replaced by CR-57). ADR-001 reads with ADR-012: production and infrastructure-changing credentials, T2, and T3 exist only on the operator machine (zone Z6); an AI lab holds T1 and project non-production credentials only. The AI-operated zone still cannot approve, merge, or change infrastructure because it holds no credential that allows it.
8. *Dropped* (CR-57): the operator login on the lab VM and the acceptance runner that reached it. The lab operator machine no longer exists.
9. **Separation is tested.** After the first operator configuration and before the first credential on the operator machine, the approver runs the separation test (ADR-012, OC-1 and OC-7): no shared mount or home, no AI-lab key in `authorized_keys`, no route from an AI lab, and no `~/.claude/` in any user's home.
10. **Operator configuration** (replaced by CR-57; ADR-012 decision 7). The Ansible operator profile on Debian 13, run by the operator admin from a clone at a release tag, dry run by default. The Ubuntu operator profile, the sudo-based `setup` script (deleted in plan step 4; the release-tag check becomes a pre-task of both the lab and the operator playbooks), the firewall revert timer, and the OCI CLI venv are dropped. The operator user has no sudo (OC-8).
11. **Operator scripts are Python** (R2, Q13; amended). They use only the standard library and call GitHub REST through `urllib` with the `pr-contract` API client, so tokens stay inside the script process and `gh` is not needed on the operator machine. The gate rejects `shell=True`, `os.system`, `eval`, and `exec`. Every network endpoint is a literal, listed in a configured allowlist read from the base commit (the GitHub API plus project-declared hosts), under the key `operator_endpoints`, failing closed when the key is missing while `operator_paths` is non-empty; the operator code checks enforce it (CR-57 PA-22, I-10). The Terraform and OCI restrictions of the shared `operator-contract` check stay as generic tool restrictions for operator scripts. The resource limits of the operator machine are a design input for every operator script (Q13), and Claude Code assumes the machine is available and never probes it (Q14).
12. **Design principles for facts** (Q38, Q39; R4 to R6; amended). Facts are gathered by scripts that run on the operator machine: host facts on the host they describe, GitHub facts through the API. Fact collection may use API tokens, with read-only access only, and read-only is enforced in code. One `facts` script serves scopes `host` and `github`; the `oci` scope is dropped. Root-only facts are manual lines in the operator runbook, not a privileged script (OC-9); `facts --privileged` and the sudo parts of `setup` are removed. In v1 projects get no `github-setup` and no desired-state file (ADR-012 decision 12).
13. **Placement** (Q28; amended). `github-setup` and `facts` run on the operator machine, from the installation of the project's release tag.
14. *Dropped* (CR-57): availability and recovery of the lab operator machine and break-glass through the lab stack. The operator machine is long-lived; a rebuild is a fresh VM plus the operator configuration (ADR-012).
15. *Dropped* (CR-57): absence alarms.
16. *Dropped* (CR-57): access paths to the lab VM and the lab operator machine. Access to the operator machine is by the operator user and the operator admin keys (ADR-012 decision 3).
17. **Project-side operator contract.** ADR-008 carries the project-side operator contract (generic `operator.md`, PC-8 driven by `operator_paths`, the `operator-contract` check). The implementation order of CR-18 is dropped; the order of CR-57 governs.

## 3. Alternatives considered

| Alternative | Outcome | Reason |
|---|---|---|
| Keep running the runbooks by hand from a browser | Kept as the fallback | No new credential on a machine. Slow and error-prone |
| Let the AI user run the scripts with credentials | Rejected | It breaks B1: a prompt injection could use the credentials directly |
| A separate machine for the operator | **Chosen** | Replaces the first design, a second user on the AI host, whose separation rested on file permissions and sudo alone |
| `origin/main` `HEAD` as the run source | Replaced | Release tags, enforced by a tag ruleset (decision 3) |
| Bash with `jq`, and `gh` with `GH_TOKEN`, for operator scripts | Replaced | Python standard library, so tokens never leave the script process (decision 11) |
| Extend the dry-run rule to every script in the repository | Not needed | The requirement covers operator scripts. The existing Bash convention stays as it is |
| Supersede this record in full (CR-57 first draft) | Replaced by amendment (PA-23) | The rules above are cited by ADR-008 and ADR-009 and stay |

Alternatives tied to the dropped decisions (cloud credentials, a second operator machine, Bastion access, absence alarms, a sudo-based setup script) are history of CR-18 in `docs/cr/CR-18/design.md`.

## 4. Consequences

**Positive:**
- The AI cannot reach credentials, and the approver still gets one-command procedures for the facts and the GitHub setup.
- Operator scripts are reviewed code at a release tag, so what runs with credentials is what the approver reviewed and tagged.
- The operator machine is separate from every AI lab, so the separation does not rest on file permissions on one host.

**Negative:**
- Credentials exist on the operator machine. AI-written code runs with them, so script review matters (RR-OP-1 of CR-18; RR-P11 of CR-57 for several projects).
- Each operator script or profile change needs a release tag from the approver before first use (RR-OP-28).

**Residual risks** are in `docs/cr/CR-18/design.md` section 8 (those about OCI and the lab operator machine are dropped) and `docs/cr/CR-57/design.md` section 9.

## 5. References

- ADR-001, ADR-003, ADR-005, ADR-008, ADR-009, ADR-012 in this repository.
- CR-18 design: `docs/cr/CR-18/design.md`. CR-57 design: `docs/cr/CR-57/design.md`.
