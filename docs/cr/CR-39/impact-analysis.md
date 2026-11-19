# CR-39 Impact analysis

## 1. What changes

- In this design PR: [ADR-008](../../adr/ADR-008-software-template.md) (Proposed) and the CR-39 files are added, and the documentation index gets rows for them. No accepted record is edited. The ADR-003 amendment for the template-sync PR is proposed in design section 4 and decided with Q8; it is not made in this skeleton.
- Later, in implementation PRs in `ai-software-template`: the template content of design section 3.

Nothing in this design PR changes code, a workflow, a template, a label, a setting, or a tag, and the `ai-software-template` repository is not touched.

## 2. Affected components and records

| Item | Effect |
|---|---|
| Baseline v0.1 | The decision index and component map still say ADR-008 "Pending design". They are updated when ADR-008 is accepted, not in this PR |
| ADR-003 | Section 3 names the template-sync PR; the amendment of Q8 would add a PC-2 prefix, a path rule, a PR template, and the cross-repository references of PC-3 |
| ADR-001 | Section 5 deny rules and the instruction-trust rule are carried into every application repository. No change to the ADR |
| ADR-005 | The template's CI needs the gate tools; Q7 may need a profile name in ADR-005 |
| ADR-011 | Decision 17 is answered by the project-side operator contract (design section 12) |
| ADR-009, ADR-010 | Dependencies and assumptions are listed (design section 11); neither is decided |
| `ai-software-template` | Receives the implementation (nine proposed PRs) |
| `scripts/pr_contract/`, `scripts/checks/` here | Copied into the template at a recorded commit; not changed by this CR (Q7) |
| `docs/README.md` | Rows for ADR-008 and CR-39 |

## 3. Security and privacy

- The template raises the baseline of every application repository: the deny rules, the instruction-trust rule, and `pr-contract` are generated, not re-typed per project. The risk is the opposite: a wrong file in the template reaches every repository. Template-sync, review of each sync PR, and approver-only tags are the controls.
- Template-sync runs as the machine account in a human-started session, fetches a public repository without credentials, and opens a PR. It adds no secret and no Actions workflow with write rights. It cannot merge.
- `review-threads` is the point where untrusted review text could become an instruction. It filters by `approver_login` exactly and reports the count of excluded comments.
- The template and its generated repositories are public by default (Q9). The leak check and the public-repository rules apply to the template itself.
- A private application repository has weaker enforcement (no required `pr-contract`, no rulesets on GitHub Free). Q9 asks the approver to accept that explicitly.

## 4. Operational impact on the approver

- Answers Q1 to Q12 in the architecture discussion, reviews and merges the design PR.
- Creates template release tags and reviews each template-sync PR.
- Applies the labels and the ruleset that `initialize-project` prints for a new repository, as today.
- Approves ADR-009 and ADR-010 before Stage 5 starts.

## 5. Dependencies and assumptions

- ADR-009 and ADR-010 are decided in separate CRs. Design section 11 records what this design assumes of them. If they differ, the template changes by a release and a sync, and this ADR changes only if a decision here is contradicted.
- The GitHub template-repository flag on `ai-software-template` is on (Stage 0, `docs/operations/github-setup.md`). I have not read the template repository in this session.
- The platform workspace can run the whole dry run: no OCI, no lab VM, no operator machine.
- `gh pr edit` and `gh pr ready` fail in the workspace (Projects classic error); the design avoids them (T-12).
- ARM64 hosted runners are free for public repositories (ADR-005).

## 6. Cost and capacity

No OCI cost. GitHub Actions minutes on a public repository are free; the template's CI runs a few jobs per PR on two architectures. Token cost of Skills is ADR-010's.

## 7. Rollback

Before the template is released, revert the implementation PRs. After release, an application repository reverts its sync PR (a normal PR revert), and a faulty template version is withdrawn by a corrected tag; the approver never moves or deletes a tag that a repository has synced. The design PR is reverted by a new PR if the ADR is not accepted.

## 8. Alternatives considered

| Alternative | Outcome | Reason |
|---|---|---|
| Payload in `template/` copied by a generator script | Open (Q1) | The flag is on already; see Q1 |
| Reusable workflows or a submodule for shared code | Rejected for v1 | A new trust edge for ADR-009; does not fit `.claude/` and `docs/` |
| Scheduled sync workflow | Rejected | No token for it, and ADR-003 excludes automatic actions |
| Everything owned, or everything seeded | Rejected | See ADR-008 section 3 |
| One CR for ADR-008, 009, and 010 | Not chosen | The request scopes this CR to ADR-008; separate CRs keep each design reviewable |
