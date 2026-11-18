# CR-18 Design: Operator tier

| Field | Value |
|---|---|
| CR | issue #18 (Class 3) |
| Governing records | ADR-001 (decision 5, section 4, B1), ADR-002 (section 2), ADR-003, ADR-005 |
| New record | [ADR-011](../../adr/ADR-011-operator-tier.md) (Proposed). It amends ADR-001 decision 5 and the OCI credentials row of its section 4 |
| Scope | Design only. No users, credentials, scripts, or workflows are added by this PR. |

## 1. Goal and scope

Give the approver one-command, reviewable procedures for tasks the AI must not or cannot run, without giving the AI user any
credential. This design covers:

| Part | Deliverable | Section |
|---|---|---|
| a | The operator user and its separation from the AI user | 3 |
| b | The common contract for operator scripts | 4 |
| c | The three first use cases | 5 |
| d | Credential handling | 6 |
| e | What the lab build provides | 7 |
| f | The operator workspace setup script (package installation) | 5.4 |

Out of scope: the scripts (implementation PRs), changing OCI infrastructure from operator scripts (never, ADR-011 decision 5),
the OCI baseline (CR-16), and a separate host for the operator.

## 2. Decisions in this design

| ID | Decision | Rationale |
|---|---|---|
| OP-1 | One operator user on the platform workspace (Z1), without general admin rights, with its own home (mode 700), its own clone of the repository, and sudo only for package installation (OP-11). It already exists. | Credentials the AI user cannot read are the point of the tier. |
| OP-2 | Scripts live in `scripts/operator/`, reach `main` through a PR, and run only from the operator's own clone at a commit contained in `origin/main`. | The AI can edit its own working tree. A merged commit is what the approver reviewed. |
| OP-3 | Every operator script takes `--dry-run` or `--apply`. A dry run makes no change and no write call, and prints each action it would take. The rule covers operator scripts only. `CLAUDE.md` is unchanged. | The approver's requirement. Nothing else in the repository changes. |
| OP-4 | Credentials are prompted for or short-lived, and never stored in the repository, a file the AI user can read, or shell history. | Same handling as T1 in ADR-001 section 4. |
| OP-5 | OCI: a short-lived session token preferred over an API key (VO-1). GitHub configuration: a separate token T2, entered at the prompt, shortest practical expiry, revoked after use. | The administrator user has no API keys today (CR-16 inputs). T1 has no admin rights and stays unchanged. |
| OP-6 | Operator scripts never run Terraform and never create, change, or delete OCI resources. They may read OCI. | An operator script must not become a second deployment path (ADR-002). |
| OP-7 | Standard output is a sanitised summary. Raw responses stay in a private directory in the operator's home. | Public repository conventions, and the report-summaries-only rule of the Gate 0 audit. |
| OP-8 | An optional operator login on the lab VM: no sudo, key-only, no credentials, created only when its variables are set. | The requirement says an additional user may exist in the lab. Off by default keeps the exposure unchanged. |
| OP-9 | The first implementation PR builds the shared library and the runbook. The three scripts follow in separate PRs. | Each PR stays small and reviewable. |
| OP-10 | Operator scripts are held to the existing quality gate (ShellCheck, `set -euo pipefail`, hygiene) and tested in both modes with stub CLIs. | Same gate as every other script. |
| OP-11 | Approver's decision of 2026-11-18: the operator may use sudo to install packages, and package installation is triggered by one dedicated script, `scripts/operator/setup`, that sets up the operator workspace. `setup` is the only operator script that may call sudo, only to install packages from a fixed list kept in the repository. A gate check rejects `sudo` in every other operator script. | The operator must be able to install what the scripts need (for example the OCI CLI) without the AI user doing it. One script keeps the elevated step small, reviewable, and repeatable after a reset. |

## 3. The operator user on Z1

**Facts (read-only checks, counts and modes only).** Two login users have home directories, both mode 700. The AI user is in the
`sudo` group. The restore runs asked the approver for the sudo password, so sudo is not passwordless for the AI user. This is an
inference: Claude does not run sudo. The OCI CLI is not installed. `gh` is installed.

**Separation rules:**

1. The operator's home is mode 700. The AI user cannot read it.
2. The AI user cannot become the operator. Switching users needs a password the AI does not have, and no sudo rule lets the AI user run commands as the operator.
3. The operator's only elevated right is sudo for package installation (OP-11, section 5.4). It is in no other privileged group. Sudo asks for the operator's password; no `NOPASSWD` rule (open question Q9).
4. The operator's clone and its credentials are in the operator's home only. The AI user's clone is never used by operator scripts.

The approver tests rules 1 to 3 before the operator holds any credential (acceptance U-1). If the test fails, this design is
revisited and a separate host or container is considered (RR-OP-2).

**Run flow.** The operator updates its clone with `git pull --ff-only`, runs the script in dry-run mode, reads the output,
and runs it again with `--apply`. Credentials are entered at a prompt during the run (section 6).

## 4. Common contract for operator scripts

| # | Rule | Reason |
|---|---|---|
| 1 | Modes: `--dry-run` or `--apply` is required. A script offers both, and with neither flag it prints usage and exits with a usage error (open question Q2) | The approver's requirement. A script never changes anything by accident |
| 2 | A dry run makes no write call. A read-only script lists the calls it would send. A changing script shows the current state against the wanted state | The approver can see the effect before it happens |
| 3 | Apply mode asks for confirmation before any step that deletes or overwrites | The last check before a change |
| 4 | Commit check: the script prints the repository commit, and refuses to run with local changes or a commit that is not contained in `origin/main` | OP-2 |
| 5 | Bounded: a fixed list of operations. No command text from arguments, no `eval`, no downloaded code, no Terraform, and no `sudo` except in `setup` | OP-6, OP-11 |
| 6 | Idempotent: running apply twice changes nothing the second time | Safe to repeat after a failure |
| 7 | Output: a sanitised summary (yes/no, counts, sizes) on standard output. Raw responses go to a directory in the operator's home with mode 700. Identifiers, addresses, and names are filtered, and a filter that cannot decide prints a placeholder | OP-7 |
| 8 | Exit codes: 0 success, 1 a check or call failed, 2 usage error, 77 skipped because a prerequisite (tool or network) is missing | Same convention as the quality gate |
| 9 | `set -euo pipefail`, ShellCheck-clean, tests for both modes with stub CLIs | OP-10 |

The shared library in `scripts/operator/lib/` implements rules 1 to 4, 7, and 8 once, so each script only lists its operations.

## 5. The three use cases

The scripts are not built by this design. This section fixes what each one replaces and what stays manual.

### 5.1 Gate 0 audit (`oci-audit`)

| Today | With the script | Stays manual |
|---|---|---|
| `docs/operations/gate-0-audit.md`, about 200 lines: account type, regions, existing resources, A1 limits, identity hygiene, Spike S2 pre-checks, run by copying Cloud Shell commands | Read-only OCI calls from the operator user, printing the results summary block of the runbook. A dry run lists the calls | Questions to people and checks on the corporate network or the Claude Desktop settings (for example Parts 1, 5 and 6) |

Cloud Shell needs no key at all, so the script is worth building only if the approver wants to stop copying commands. It
also depends on how the OCI CLI authenticates here (VO-1). The CLI is installed by `setup` (section 5.4).

### 5.2 GitHub setup (`github-setup`)

| Today | With the script | Stays manual |
|---|---|---|
| `docs/operations/github-setup.md`: Console steps for repositories, settings, security features, rulesets, environments, collaborators | Idempotent `gh api` calls from a desired-state file in the repository (no identifiers; logins are inputs). A dry run shows current against wanted settings and lists the calls | Account hardening, creating the machine account, creating tokens, connecting the chat integration (Parts 1, 2, 10, 11 by their headings) |

This needs T2 (section 6). It also removes the case where the AI cannot read a ruleset it must reason about: the audit mode
can print the current state as a summary.

### 5.3 Acceptance tests (`acceptance`)

| Today | With the script | Stays manual |
|---|---|---|
| The B, L, K, and C tests of CR-16, and the V2 checks, run one by one from the acceptance tables | One runner reports yes or no per criterion ID, in dry-run (lists the checks) and apply (runs them) | Tests that need the Console, a second network, a reboot, or a stop and start of the instance |

Read-only OCI checks run from Z1 under the operator user. On-VM checks run over SSH. The runner changes nothing in OCI (OP-6).

### 5.4 Operator workspace setup (`setup`)

Decided by the approver on 2026-11-18 (OP-11). It replaces installing tools by hand.

| Aspect | Design |
|---|---|
| Modes | `--dry-run` lists every package and tool with its version and source, and what is already installed. `--apply` installs what is missing |
| Packages | Debian packages from a fixed list in the repository, installed with `sudo apt-get install` for the listed names only. Sudo asks for the operator's password (Q9) |
| Other tools | The OCI CLI and any other tool that is not a Debian package come from pinned sources with checksums for both architectures, installed into the operator's home without sudo. The mechanism follows ADR-005 (a manifest entry or profile, confirmed in the implementation PR). No `curl \| sh` |
| Scope | Installs and verifies tools. It creates no credential, signs in nowhere, and changes no OCI or GitHub setting |
| Verification | After apply it prints tool names and versions only |
| Idempotent | A second apply installs nothing |
| Who runs it | The operator, by hand, on Z1. The AI user never runs it |

It is the first script built after the library (implementation plan, PR 2), because the audit script needs the OCI CLI.

## 6. Credential handling

| Credential | Where | Handling |
|---|---|---|
| OCI session token (preferred) | Operator's home, private directory | Created at the start of a run through the browser, short-lived, deleted at the end. The identity should be read-only if Oracle allows it (VO-1) |
| OCI API key (alternative) | Not planned | Would need a dedicated read-only user and a bootstrap IAM change in CR-16's stack, and it gives up "no API keys" (Q3) |
| GitHub token T2 | Prompt only, not stored | Extended scope for repository configuration, shortest practical expiry, revoked after use. Never T1. Scopes are decided in the implementation PR for `github-setup` and shown to the approver |
| T1 | Unchanged | The AI user's token. No admin rights |

The matrix wording of ADR-001 section 4 is updated by the PR that adds the first script that uses a credential.

## 7. What the lab build provides

This applies to CR-16's lab stack and is added to CR-16 by a new design PR after both changes are merged.

- **Optional login.** Variables `operator_user_name` (empty by default) and `operator_ssh_public_key`. When set, cloud-init creates that user with the key, no password, no privileged group, and a home readable only by it. It cannot write to `/srv/work`.
- **No credentials.** The operator login on the VM has no OCI credential and no GitHub token. It can run scripts that need neither, for example the on-VM acceptance checks.
- **SSH.** `sshd` allows the default user and the operator user. The network allowlist and the Bastion are unchanged.
- **Validation.** The user name is not `root` and differs from the default login user. The key is Ed25519, and it is required when the name is set.
- **Acceptance.** A new lab criterion checks that no second login exists when the variable is unset, and that the operator login has no sudo and no privileged group when set (acceptance L-1 in this CR).

## 8. Risks

| ID | Risk | Mitigation |
|---|---|---|
| RR-OP-1 | AI-written code runs with credentials the AI never sees, so a mistake or a prompt injection could become a destructive call or a leak | Merged-commit check, review by the approver, fixed operation list, dry-run before apply, short-lived credentials, sanitised output, no Terraform and no OCI writes |
| RR-OP-2 | The AI user and the operator share one host, kernel, and filesystem, and the AI user is in the `sudo` group | Mode 700 homes, no rule that lets the AI user run commands as the operator, and the approver's test U-1 before the first credential. If it fails, a separate host or container is considered and this design is revisited |
| RR-OP-3 | The sanitiser misses an identifier and the approver pastes it into chat or a PR | Filters by pattern for OCIDs, addresses, and email addresses, a placeholder when unsure, tests with sample output, and the existing `public-repo-hygiene` check on anything committed |
| RR-OP-4 | T2 outlives its use | Shortest practical expiry, revoked after each run, and the script reminds the approver at the end |
| RR-OP-5 | The operator's clone falls behind `main`, or a stale script runs | The commit check prints the commit, and `git pull --ff-only` is the first step of the runbook |
| RR-OP-6 | The operator login on the lab VM widens the internet-facing host's attack surface | Optional and off by default, key-only, no sudo, same allowlist, no credentials |
| RR-OP-7 | The OCI CLI is not installed, and `CLAUDE.md` forbids Claude from installing software | The `setup` script installs it from a pinned source with checksums for both architectures, run by the operator (OP-11, section 5.4, VO-2) |
| RR-OP-8 | The operator has sudo, so AI-written code that the operator runs could reach root | Sudo is for package installation only. Only `setup` may call it, a gate check rejects `sudo` in any other operator script, sudo asks for the operator's password, the package list is fixed in the repository, and the approver reviews `setup` with extra care. If the operator also holds credentials, root on the operator means root on the host, so these controls matter for RR-OP-2 too |

## 9. Verification items

Documentation checks or read-only inspection. Anything that creates credentials or changes systems is an explicit action by the approver.

| ID | Question | Method | Needed before |
|---|---|---|---|
| VO-1 | Whether OCI CLI session-token authentication works for this tenancy's identity domain type, its maximum lifetime, and whether a read-only identity can run the audit | Oracle CLI documentation | PR 4 (`oci-audit`) |
| VO-2 | The install source, version, and checksums of the OCI CLI for x86-64 (and ARM64 if the manifest carries it) | Oracle's release page, and ADR-005's manifest rules | PR 2 (`operator-setup`) |
| VO-3 | The token T2 scopes and expiry that repository configuration needs, and whether a fine-grained token can do it for these repositories | GitHub documentation | PR 3 (`github-setup`) |
| VO-4 | The exact `gh api` calls and desired-state fields for the settings, rulesets, and environments of `docs/operations/github-setup.md` | GitHub REST documentation | PR 3 |
| VO-5 | How `sudo` is configured for the AI user (password required, no rule to run commands as the operator), and for the operator (password required, scope) | The approver's test U-1 | Before any credential on Z1 |
| VO-6 | The list of Debian packages `setup` installs, and how it fits ADR-005's manifest rules (profile or equivalent) | The implementation PR for `setup`, with ADR-005 | PR 2 (`operator-setup`) |

## 10. Decisions and questions

### 10.1 Decided (approver, 2026-11-18)

| # | Decision | Recorded in |
|---|---|---|
| Q1 | The amendment of ADR-001 decision 5 and the OCI credentials row is accepted. ADR-011 becomes Accepted when this PR is merged | ADR-011 decision 7 |
| Q2 | No change to the current approach: with neither `--dry-run` nor `--apply`, a script stops with a usage error (section 4 rule 1) | Section 4 |
| New | The operator may use sudo to install packages (this replaces "no admin privileges" for that one purpose) | OP-1, OP-11, ADR-011 decisions 1 and 10 |
| Q6 | Package installation, including the OCI CLI, is triggered by one dedicated script that sets up the operator workspace | OP-11, section 5.4 |

How I read the approver's answers: the message gave Q1, Q2, and a third answer labelled Q3 that is about package installation, so I
recorded it as the answer to Q6 (the OCI CLI install route). Q3 as written in this design (the OCI authentication method) is
therefore still open. The sudo sentence came with Q2 but does not concern the dry-run question, so I recorded it as its own
decision. If any of this is read wrongly, the approver corrects it and the rows change.

### 10.2 Open

| # | Question | Recommendation | Status |
|---|---|---|---|
| Q3 | OCI authentication for the operator | A short-lived session token (VO-1). An API key for a read-only user would need a bootstrap IAM change | Not decided |
| Q4 | Handling of T2 | Prompt only, shortest practical expiry, revoked after use, separate from T1 | Not decided |
| Q5 | Operator login on the lab VM | Optional, off by default, no sudo, no credentials (OP-8). The sudo decision above covers the workspace only | Not decided |
| Q7 | PR order and the user-only actions in the plan | As in implementation-plan.md (updated: `operator-setup` is PR 2) | Not decided |
| Q8 | Start the implementation after CR-16 merges? | Yes for the acceptance runner. The library, the setup script, the audit script, and the GitHub script do not depend on CR-16 | Not decided |
| Q9 | Scope of the operator's sudo | Sudo asks for the operator's password, with no `NOPASSWD` rule, and only `setup` calls it. The alternative, a sudoers rule limited to one command, only helps if that command is a root-owned file the operator cannot edit, which a script in the operator's clone is not | Not decided |

### 10.3 User-only actions (summary)

Run the separation test U-1 (now including the operator's sudo setting); choose the OCI authentication and T2 handling; run `setup` as the operator; create and revoke T2 per run; review operator scripts, `setup` first.
