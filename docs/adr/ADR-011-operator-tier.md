# ADR-011: Operator Tier: a Dedicated User for Credentialed and Extended-Permission Scripts

| Field | Value |
|---|---|
| Status | **Proposed** (becomes Accepted when the design PR for CR-18 is merged by the approver) |
| Date | 2026-11-18 |
| Repository | `ai-lab-infrastructure` |
| Change request | CR-18 (issue #18) |
| Scope | The operator user on the platform workspace and on the lab VM, the rules for the scripts it runs, and the credential placement that follows. Not the scripts themselves, not the OCI baseline (ADR-004 and CR-16) |
| Related | ADR-001 (decision 5, section 4 credential matrix, B1; amended by this ADR), ADR-002 (infrastructure changes), ADR-003, ADR-005 (toolchain), CR-16 |

> This ADR records a decision. It does not create a user, a credential, a script, or any OCI or GitHub change, and it does not authorize any of them.
> Detail and rationale are in `docs/cr/CR-18/design.md`; this record keeps the decision itself.

---

## 1. Context

Some tasks cannot or should not be run by the AI user: tasks that need dedicated credentials (an OCI identity) or permissions beyond the machine account's Write role (configuring GitHub repositories). Today the approver performs them by copying commands from long runbooks (`docs/operations/gate-0-audit.md`, `docs/operations/github-setup.md`) and by running acceptance tests one call at a time.

Facts (approver's statement of 2026-11-18, and read-only checks on the platform workspace):

- A dedicated Linux user already exists on the platform workspace (zone Z1). It has internet access. It had no admin privileges; on 2026-11-18 the approver decided that it may use sudo to install packages (decision 10).
- A second such user may be provisioned on the lab VM (zone Z2).
- On Z1 there are two login users with home directories of mode 700. The AI user is a member of the `sudo` group. The restore runs asked the approver for the sudo password, so sudo is not passwordless for the AI user. This was inferred, not tested, because Claude never runs sudo.
- The OCI CLI is not installed on Z1.
- ADR-001 decision 5 and the OCI credentials row of its section 4 matrix say that no OCI credentials exist on Z1 or Z2, and B1 calls that an enforced property.

## 2. Decision

1. **An operator tier exists.** The operator is a dedicated Linux user without general admin rights, separate from the AI user, on Z1 and optionally on Z2. Its only elevated right is sudo for package installation (decision 10); it is in no other privileged group. The operator runs, by hand, scripts that the AI wrote and the approver reviewed and merged. The AI never runs them and never reads the operator's home.
2. **Every operator script has a dry-run mode and an apply mode.** A dry run changes nothing and shows what apply would do. The rule applies to operator scripts only. The Bash convention in `CLAUDE.md` is unchanged.
3. **Scripts run from merged code only.** The operator uses its own clone, updated with a fast-forward pull. A script prints its commit and refuses to run with local changes or a commit that is not in `origin/main`. It never runs from the AI user's working tree.
4. **Credentials are prompted for or short-lived.** They are never stored in the repository, in a place the AI user can read, or in shell history. OCI access uses a short-lived session token if Oracle's documentation confirms it works for this tenancy (CR-18 VO-1); otherwise the approver decides again. GitHub repository configuration uses a separate token T2 with extended scope, entered at the prompt, with the shortest practical expiry, revoked after use. T1 is unchanged and stays free of admin rights.
5. **Operator scripts never change infrastructure.** They may read OCI. They never run Terraform and never create, change, or delete OCI resources. Infrastructure changes follow ADR-002 only (the Console in Stage 2, the pipeline in Stage 4).
6. **Output is safe to paste.** Standard output is a sanitised summary (yes/no, counts, sizes). Raw responses stay in a private directory in the operator's home and never enter the repository.
7. **Amendment of ADR-001.** Decision 5 and the OCI credentials row of the section 4 matrix are replaced, when this ADR is accepted, by: the AI user holds no OCI credentials on Z1 or Z2; no OCI credentials exist on Z2; the operator user on Z1 may hold short-lived OCI credentials and the token T2. B1 stands: the AI-operated zones cannot approve or merge, and cannot modify infrastructure, because the AI user holds no credential that allows it.
8. **The lab VM login is optional.** The operator login on Z2 has no sudo, no OCI credential, and no GitHub token. The lab stack creates it only when its variables are set. The lab design carries that (CR-18 design section 7).
9. **Separation is tested before first use.** The approver confirms that the AI user cannot read the operator's home or become the operator, before the operator holds any credential.
10. **Package installation by one dedicated script.** The operator workspace is set up by a single script, `setup`, with dry-run and apply modes. It is the only operator script that may call sudo, and only to install packages from a fixed list kept in the repository. Tools that are not Debian packages are installed from pinned sources with checksums for both architectures (ADR-005), never with `curl | sh`. The AI never runs it.

## 3. Alternatives considered

| Alternative | Outcome | Reason |
|---|---|---|
| Keep running the runbooks by hand from Cloud Shell and the web UI | Kept as the fallback | No new credential on the workspace. Slow, error-prone, and the many-step acceptance tests are hard to repeat |
| Let the AI user run the scripts with credentials | Rejected | It breaks B1: a prompt injection could use the credentials directly |
| A separate host or container for the operator | Not in v1 | Stronger isolation, but another machine to build and keep. Revisit if test 1 of the acceptance criteria fails or the risk rises (CR-18 RR-OP-2) |
| An OCI API key for a dedicated read-only user | Deferred | Needs a bootstrap IAM change (ADR-004) and gives up "no API keys". A session token is preferred (VO-1) |
| An operator without any sudo | Rejected by the approver (2026-11-18) | The operator must be able to install packages. Sudo is limited to one script (decision 10) |
| Extend the dry-run rule to every script in the repository | Not needed | The requirement covers operator scripts. The existing Bash convention stays as it is |

## 4. Consequences

**Positive:**
- The AI cannot reach credentials, and the approver still gets one-command procedures for the audit, the GitHub setup, and the acceptance tests.
- Operator scripts are reviewed code in the repository, so what runs with credentials is what was merged.

**Negative:**
- Credentials exist on the workspace for the first time, under a user the AI cannot read. The separation rests on file permissions and sudo, not on a host boundary (RR-OP-2).
- The operator can become root through sudo, so AI-written code that the operator runs could reach root. The controls are the single `setup` script, a gate check that rejects `sudo` anywhere else, and the review of that script (RR-OP-8).
- AI-written code runs with those credentials, so script review matters more than before (RR-OP-1).
- ADR-001's text is changed by a pointer now and by the matrix wording when the first script lands.

**Residual risks** are in design section 8.

## 5. References

- ADR-001, ADR-002, ADR-003, ADR-005, and ADR-004 (proposed in CR-16) in this repository.
