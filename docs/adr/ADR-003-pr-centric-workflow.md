# ADR-003: PR-Centric Engineering Workflow

| Field | Value |
|---|---|
| Status | **Accepted** |
| Date | 2026-11-17 |
| Repositories | `ai-software-template` (primary), `ai-lab-infrastructure` |
| Target location | `docs/adr/ADR-003-pr-centric-workflow.md` |
| Requirement | CHG-003: GitHub-centric workflow based on PRs; no automatic responses from Claude |
| Amended by | CR-21 (design PR #22 and implementation PR #24 merged, 2026-11-18): rule PC-8 and AC3-7; in force and enforced. CR-39 (design PR #40 merged, 2026-11-19): application-repository contract, PC-2 prefixes, PC-3 cross-repository references, PC-8 paths from configuration, section 5 configuration file, section 7 review identity and PR body; checks are enforced once the template's implementation PRs are merged. CR-43 (design PR #44 merged, 2026-11-20): section 6 required checks, rule PC-9, the PC-7 exemption, and AC3-8; PC-9 is enforced once implemented. CR-45 (Proposed): section 7, the reference to the checkpoint format and the CI summary channel. Takes effect when the CR-45 design PR is merged |
| Amended by (CR-57, follow-up R-1) | Proposed, takes effect when R-1 is merged. PC-8 refers to the value of the `operator_paths` key instead of listing this repository's paths. The OCI VM wording of sections 1, 4 (step 6), 7, and 9 now names the AI lab (ADR-012). The ADR-002 citations in the "Infra PR" row, RR-5, and the Related row are corrected, since CR-57 supersedes ADR-002. No decision or rule changes |
| Related | ADR-002 (infrastructure pipeline; superseded by CR-57), D8/D13 (machine account), ADR-001, D17 (GitHub access per surface) |

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
- Event-driven Claude (for example `@claude` via the Claude Code GitHub Action) would need a long-lived subscription credential stored in GitHub secrets. It would also run unattended on GitHub runners rather than the AI lab where Claude Code runs (ADR-012). This conflicts with the Enterprise credential, execution-location, and human-control requirements.

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
| Infra PR | `ai-lab-infrastructure` change; the merge is the approver's approval (section 5) | Machine account | Branch `infra/<slug>` |
| Toolchain PR | Version-manifest change | Machine account | Branch `toolchain/<slug>` |
| Template-sync PR | Template update proposed to an application repo | Machine account (script) | Branch `template-sync/<template-version>` |
| Init PR | First change after generation from the template | Machine account | Branch `init/v<MAJOR>.<MINOR>.<PATCH>` |
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
6. Claude Code implements on the AI lab (ADR-012), updating the checklist as it goes. The local quality gate runs before each push, and CI runs on every push.
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

The approver login and the approver's immutable account ID are stored in the project configuration file (keys `approver_login` and `approver_id`; `config/project.yaml` in this repository). Scripts read them from there and never infer them.

## 6. `pr-contract` check

Application repositories generated from the software template enforce the PR contract shipped by the template version they last synced. That contract must implement PC-1 to PC-9 as stated here and may add rules. The template-sync and init PR types and their path rules are defined by the template (ADR-008).

The checks `pr-contract` and `quality-gate` are required status checks on public repositories, enforced by the branch ruleset with GitHub Actions as their source. GitHub Free offers rulesets on private repositories only with a paid plan, so on a private repository both are advisory and the approver confirms them on the PR's head before merging. `pr-contract` runs on `pull_request` with a read-only `GITHUB_TOKEN`, uses no secrets, and runs safely for fork PRs.

| Rule | Requirement |
|---|---|
| PC-1 | The PR body contains every section its template requires, non-empty. |
| PC-2 | The PR type is derivable from the branch prefix and matches the template used. In application repositories the prefixes also include `template-sync/v<MAJOR>.<MINOR>.<PATCH>` and `init/v<MAJOR>.<MINOR>.<PATCH>`. |
| PC-3 | An implementation PR references an issue (`Implements:`) and a design PR (`Design:`), each as `#<n>` in the same repository or as `<owner>/<repo>#<n>` in a repository listed under the configuration key `design_repos`. The design PR exists, is **merged**, and is linked to the same issue (checked through the GitHub API). A referenced repository that cannot be read fails the check. |
| PC-4 | A design PR changes only paths under `docs/`. |
| PC-5 | An implementation or change PR does not modify `docs/cr/*/design.md`, `acceptance-criteria.md`, or `docs/adr/` files belonging to an approved CR. |
| PC-6 | Changes under `.github/workflows/` or `.github/actions/` require the PR-body section "Workflow change justification". |
| PC-7 | Dependabot PRs are exempt from PC-1 to PC-3, PC-8, and PC-9, and may change only dependency manifests, lockfiles, and workflow `uses:` pins. |
| PC-8 | A PR that changes a path listed under the configuration key `operator_paths` requires the PR-body section "Operator script review", non-empty. The paths are the value of that key in `config/project.yaml` (ADR-011, ADR-012); in a newly generated application repository it is empty. |
| PC-9 | A change or implementation PR on a repository that has no hosted runner for an architecture listed under the configuration key `architectures` (read from the base commit) contains, in the section "Architecture evidence", one line `evidence: <arch> \| <machine> \| <os> \| <40-hex SHA> \| clean \| <gate command> \| exit 0 \| <UTC time>` per such architecture, with the SHA equal to the PR's current head. Design and Dependabot PRs are exempt. The line is informational; the approver accepts it per PR. |

**Security requirement.** The PR title and body are untrusted input. They are passed to the script only through environment variables or the API, never interpolated into `run:` shell steps. All Actions used are pinned to reviewed SHAs.

## 7. How the two Claude surfaces use PRs

**Claude Enterprise (chat, read-only GitHub Integration authorized as the machine account, per D17):**
- Reads synced repository files: ADRs, CR documents, CLAUDE.md, and selected code.
- Cannot write to GitHub. Decisions reach the repository through Claude Code.
- Issues, PR conversations, and CI results are not synced. When needed, Claude Code summarizes them in the session, or you paste the relevant excerpt.

**Claude Code (Desktop SSH session on the AI lab, `git` and `gh` as the machine account):**

- **Draft PR as checkpoint.** It opens a draft PR at the start of work. The PR body holds the plan checklist between `<!-- checkpoint:start -->` and `<!-- checkpoint:end -->` markers. `resume-work` reads only the checklist, the latest CI result, and `git log` since the merge base, through `scripts/pr-checkpoint show`, in the format and within the limits of ADR-010.
- **Review feedback loop (new Skill `address-review-feedback`).**
  - A script fetches review threads, review comments and review summaries, and keeps only those authored by the approver, matched by the immutable account ID from the project configuration and not edited by any other account. It refuses PRs not authored by the machine account and PRs from forks. Text by any other account, including text the approver points to, is data until the approver restates it as an instruction.
  - Claude addresses each thread, pushes, and replies on the thread with the commit reference. You resolve threads and re-approve.
- **Concise CI output.** CI failures are written to the job summary as short, structured output for the approver. Claude Code reads CI results through the API in the bounded form defined by ADR-010, and never raw logs.
- **Template selection.** PRs are opened with `gh pr create --draft --body-file <file>`; the body is seeded from `scripts/pr-body <type>`, which prints `.github/PULL_REQUEST_TEMPLATE/<type>.md` unchanged.

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
- Checkpoints survive AI lab loss.
- Context is loaded by reference, not by re-reading the repository.
- No Claude credential in GitHub and no unattended AI execution.

**Negative:**
- Every change requires your hands-on PR review. There is no AI work between sessions.
- Private repositories get advisory enforcement only.
- The workflow depends on GitHub availability. A local branch and the AI lab workspace remain usable offline, but approval waits for GitHub.

**Residual risks:**
- **RR-4.** The machine account can edit PR bodies and labels. Mitigation: they are never authoritative (Section 5).
- **RR-5.** Compromise of the approver account defeats approvals. Mitigation: passkey or 2FA, plus the operator machine's release-tag and prompted-credential rules (ADR-011, ADR-012) for credentialed scripts.
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
- AC3-4: `address-review-feedback` ignores a comment by a non-approver account containing instructions, and an approver comment edited by another account (test fixtures).
- AC3-5: `resume-work` restores task state from the PR checkpoint after a fresh VM workspace clone.
- AC3-6: No workflow in either template or platform repository invokes Claude or holds a Claude credential (automated scan in CI).
- AC3-7: A PR that changes an operator path without a non-empty "Operator script review" section fails `pr-contract` (PC-8).
- AC3-8: A change or implementation PR on a repository with no runner for a configured architecture fails `pr-contract` unless it carries a valid evidence line whose SHA equals the PR's head (PC-9).
