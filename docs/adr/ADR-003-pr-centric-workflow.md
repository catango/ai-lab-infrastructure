# ADR-003: PR-Centric Engineering Workflow

| Field | Value |
|---|---|
| Status | **Accepted** |
| Date | 2026-11-17 |
| Repositories | `ai-software-template` (primary), `ai-lab-infrastructure` |
| Target location | `docs/adr/ADR-003-pr-centric-workflow.md` |
| Requirement | CHG-003: GitHub-centric workflow based on PRs; no automatic responses from Claude |
| Amended by | CR-21 (Proposed, 2026-11-18): rule PC-8 and AC3-7. Takes effect when the CR-21 design PR is merged; the check is enforced once its implementation PR is merged |
| Related | ADR-002 (infrastructure pipeline), D8/D13 (machine account), ADR-001, D17 (GitHub access per surface) |

> Numbering note: this requirement was briefly labeled "CHG-002" in discussion. CHG-002 is already
> assigned to the conditional static-key waiver in ADR-002, so this requirement is **CHG-003**.

> This ADR records an architecture decision. It does not authorize creating repositories,
> rulesets, labels, workflows, or settings. Each requires separate explicit authorization.

---

## 1. Context

- The platform needs one place for work state, approval, and traceability. Chat history must not be the system of record.
- GitHub Free enforces rulesets (required reviews, required checks, linear history) on **public** repositories only.
- Claude Code pushes as a machine account. Only your personal account may approve and merge (D8/D13).
- PR conversations are stored in GitHub, not in Git. They are hard to load selectively into AI context and do not travel with the code.
- Event-driven Claude (for example `@claude` via the Claude Code GitHub Action) would need a long-lived subscription credential stored in GitHub secrets. It would also run unattended on GitHub runners rather than the OCI VM. This conflicts with the Enterprise credential, execution-location, and human-control requirements.

## 2. Decision

1. **The pull request is the unit of work, the approval point, and the audit trail.** Every change to a platform or application repository reaches `main` only through a PR.
2. **Repository files are the durable record.** ADRs, designs, acceptance criteria, and implementation plans live as Markdown in the repository. PRs carry workflow state and discussion.
3. **Issues provide CR identity.** The CR ID is the issue number (CR-42 = issue #42).
4. **Class 3 changes use two PRs:** a design PR, then one or more implementation PRs. Each approval therefore lands on its own immutable merge commit.
5. **Approval authority** is your approving review plus your merge. Nothing else counts (Section 5).
6. **A deterministic `pr-contract` check** enforces the workflow rules on every PR (Section 6).
7. **No event-driven Claude.** Claude never responds automatically to GitHub events. There is no Claude Code GitHub Action, no `@claude` trigger, no routines, and no scheduled AI sessions. Every Claude session is started by you, in Claude Desktop (chat or Code tab).
8. **Repository settings.** Squash merge only, linear history required, auto-merge disabled. Pushes to `main` happen only through PRs.

## 3. Work item model

| Element | Purpose | Author | Naming |
|---|---|---|---|
| Issue | CR intake; CR identity | You, or Claude Code with your instruction | Title `CR: <summary>`; label `class:3` |
| Design PR | Design artifacts and ADRs for one CR | Machine account | Branch `design/CR-<n>-<slug>` |
| Implementation PR | Code, tests, docs for an approved design | Machine account | Branch `impl/CR-<n>-<slug>` |
| Change PR | Class 1 or 2 change | Machine account | Branch `change/<issue-or-short-id>-<slug>` |
| Infra PR | `ai-lab-infrastructure` change; merge = ADR-002 Gate 1 | Machine account | Branch `infra/<slug>` |
| Toolchain PR | Version-manifest change | Machine account | Branch `toolchain/<slug>` |
| Template-sync PR | Template update proposed to an application repo | Machine account (script) | Branch `template-sync/<template-version>` |
| Dependabot PR | Dependency and Actions updates | `dependabot[bot]` | GitHub default |

**CR document layout.** Separate files allow targeted context loading.

```text
docs/cr/CR-<n>/
  README.md                 # one-screen summary, status, links (index for Claude)
  impact-analysis.md
  design.md
  acceptance-criteria.md
  implementation-plan.md
```

## 4. Change classes and lifecycles

| Class | Scope | Flow |
|---|---|---|
| 1 | Trivial: typo, comment, config value with no behavioral effect | One change PR, minimal template |
| 2 | Standard: contained behavior change with no architectural impact | One change PR with acceptance criteria in the PR body |
| 3 | Architecturally significant | Issue → design PR → implementation PR(s) |

Classification is proposed by Claude and confirmed by you in the PR or issue. When in doubt, use the higher class.

**Class 3 lifecycle:**

1. Create an issue. The CR ID is fixed.
2. Claude Code opens a **draft design PR** with the CR directory skeleton.
3. Architecture discussion takes place in Claude Enterprise, grounded in the repository files through the read-only GitHub Integration (sync the design branch first). You hand the resulting decisions to Claude Code, which commits them to the CR files and posts a discussion summary as a PR comment.
4. Mark the PR ready for review. You review and approve, then merge. **This is design approval.**
5. Claude Code opens a **draft implementation PR** that declares `Implements: #<issue>` and `Design: #<design PR>`, and adds the plan checklist to the PR body.
6. Claude Code implements on the OCI VM, updating the checklist as it goes. The local quality gate runs before each push, and CI runs on every push.
7. Mark the PR ready for review. You review. Feedback goes through the review loop (Section 7). You re-approve after the last push, then merge. **This is implementation approval.**
8. The final implementation PR uses `Closes #<issue>`. Traceability runs: issue → design merge commit → implementation merge commit(s).

A needed design change during implementation requires a **new design PR**. Implementation PRs may not modify approved design files (rule PC-5).

## 5. Approval authority

| Authoritative | Informational only |
|---|---|
| An approving review by the configured approver account on the latest push | Labels (the machine account can set them) |
| The merge of the PR by the approver account | PR-body checkboxes and status text |
| The merge commit SHA of a design PR | `status:` fields in Markdown files |
| | Any comment by Claude or by bots |

The approver login is stored in project configuration (`config/project.yaml`, key `approver_login`). Scripts read it from there and never infer it.

## 6. `pr-contract` check

This is a required status check on public repositories and advisory on private repositories (GitHub Free). It runs on `pull_request` with a read-only `GITHUB_TOKEN`, uses no secrets, and runs safely for fork PRs.

| Rule | Requirement |
|---|---|
| PC-1 | The PR body contains every section its template requires, non-empty. |
| PC-2 | The PR type is derivable from the branch prefix and matches the template used. |
| PC-3 | An implementation PR references an issue (`Implements:`) and a design PR (`Design:`). The design PR exists, is **merged**, and is linked to the same issue (checked through the GitHub API). |
| PC-4 | A design PR changes only paths under `docs/`. |
| PC-5 | An implementation or change PR does not modify `docs/cr/*/design.md`, `acceptance-criteria.md`, or `docs/adr/` files belonging to an approved CR. |
| PC-6 | Changes under `.github/workflows/` or `.github/actions/` require the PR-body section "Workflow change justification". |
| PC-7 | Dependabot PRs are exempt from PC-1 to PC-3, and may change only dependency manifests, lockfiles, and workflow `uses:` pins. |
| PC-8 | A PR that changes `scripts/operator/`, `ansible/operator.yml`, the roles of the operator profile, or their data files (ADR-011) requires the PR-body section "Operator script review", non-empty (CR-21). |

**Security requirement.** The PR title and body are untrusted input. They are passed to the script only through environment variables or the API, never interpolated into `run:` shell steps. All Actions used are pinned to reviewed SHAs.

## 7. How the two Claude surfaces use PRs

**Claude Enterprise (chat, read-only GitHub Integration authorized as the machine account, per D17):**
- Reads synced repository files: ADRs, CR documents, CLAUDE.md, and selected code.
- Cannot write to GitHub. Decisions reach the repository through Claude Code.
- Issues, PR conversations, and CI results are not synced. When needed, Claude Code summarizes them in the session, or you paste the relevant excerpt.

**Claude Code (Desktop SSH session on the OCI VM, `git` and `gh` as the machine account):**

- **Draft PR as checkpoint.** It opens a draft PR at the start of work. The PR body holds the plan checklist between `<!-- checkpoint:start -->` and `<!-- checkpoint:end -->` markers. `resume-work` reads only the checklist, the latest CI summary, and `git log` since the merge base.
- **Review feedback loop (new Skill `address-review-feedback`).**
  - A script fetches review threads and comments authored **only** by `approver_login`.
  - Comments from any other account, including bots and the machine account, are treated as data, never as instructions.
  - Claude addresses each thread, pushes, and replies on the thread with the commit reference. You resolve threads and re-approve.
- **Concise CI output.** CI failures are written to the job summary as short, structured output. Claude reads the summary through `gh`, not raw logs.
- **Template selection.** PRs are opened with `gh pr create --template <type>.md`, using templates in `.github/PULL_REQUEST_TEMPLATE/`.

**Explicitly excluded:** Claude acting on any GitHub event without a human-started session. This covers comment triggers, PR-open triggers, schedules, and managed review services that post automatically.

## 8. Skill impact

| Skill | Change |
|---|---|
| `initialize-project` | Configures `config/project.yaml` (including `approver_login`), labels, and PR templates. Proposes the ruleset for you to apply. |
| `prepare-cr-context` | Inputs are the issue number and design PR. Loads the CR `README.md` first, then other files only as needed. |
| `implement-approved-cr` | Precondition: the design PR is merged (same check as PC-3). Opens a draft implementation PR with checkpoint markers. |
| `review-implementation` | Self-review against acceptance criteria before you are asked to review. Results are posted as one PR comment. |
| `resume-work` | Uses the PR checkpoint markers as the primary state source. |
| `address-review-feedback` | **New.** Approver-only feedback loop as described above. |

## 9. Consequences

**Positive:**
- One place for state, approval, and traceability.
- Approvals are enforced by GitHub on public repositories.
- Checkpoints survive VM loss.
- Context is loaded by reference, not by re-reading the repository.
- No Claude credential in GitHub and no unattended AI execution.

**Negative:**
- Every change requires your hands-on PR review. There is no AI work between sessions.
- Private repositories get advisory enforcement only.
- The workflow depends on GitHub availability. A local branch and the VM workspace remain usable offline, but approval waits for GitHub.

**Residual risks:**
- **RR-4.** The machine account can edit PR bodies and labels. Mitigation: they are never authoritative (Section 5).
- **RR-5.** Compromise of the approver account defeats approvals. Mitigation: passkey or 2FA, plus the ADR-002 OCI-side guards for infrastructure.
- **RR-6.** Prompt injection through issue, PR, or repository text read by Claude. Mitigation: approver-only instruction rule, chat access read-only (D17), and a CLAUDE.md rule that GitHub content is data.

## 10. Verification items

| ID | Item |
|---|---|
| V3-1 | `gh pr create --template` selects templates from `.github/PULL_REQUEST_TEMPLATE/` as expected. |
| V3-2 | With squash merge, "require approval of the most recent reviewable push" dismisses approval after new commits and does not block your merge. |
| V3-3 | **Closed by D17:** chat access is read-only; no GitHub MCP in v1. |
| V3-4 | The PC-3 lookup works with the read-only `GITHUB_TOKEN` for public and private repositories. |

## 11. Acceptance criteria (verified in Phase E)

- AC3-1: A Class 3 implementation PR referencing an unmerged design PR fails `pr-contract`.
- AC3-2: An implementation PR modifying an approved `design.md` fails `pr-contract`.
- AC3-3: A machine-account PR cannot be merged on a public repository without the approver's review of the latest push.
- AC3-4: `address-review-feedback` ignores a comment by a non-approver account containing instructions (test fixture).
- AC3-5: `resume-work` restores task state from the PR checkpoint after a fresh VM workspace clone.
- AC3-6: No workflow in either template or platform repository invokes Claude or holds a Claude credential (automated scan in CI).
- AC3-7: A PR that changes an operator path without a non-empty "Operator script review" section fails `pr-contract` (PC-8).
