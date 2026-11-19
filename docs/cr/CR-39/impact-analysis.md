# CR-39 Impact analysis

## 1. What changes

In this design PR:

- [ADR-008](../../adr/ADR-008-software-template.md) (Proposed) and the CR-39 files are added.
- [ADR-003](../../adr/ADR-003-pr-centric-workflow.md) is amended (Q8): header row, init PR type, approver account ID, application-repository contract, PC-2, PC-3, PC-8 from configuration, review identity, PR template selection, AC3-4.
- [ADR-005](../../adr/ADR-005-toolchain.md) is amended in scope (Q7): the template's CI manifest is not a host profile.
- `docs/README.md` gets rows for ADR-008 and CR-39, and the stale CR-21 and ADR-003 rows are corrected.

Later, in implementation PRs in `ai-software-template`: the template content of design section 3.

Nothing in this design PR changes code, a workflow, a PR template, a label, a setting, or a tag, and the `ai-software-template` repository is not touched.

## 2. Affected components and records

| Item | Effect |
|---|---|
| Baseline v0.1 | The decision index and component map still say ADR-008 "Pending design". They are updated when ADR-008 is accepted, not in this PR |
| ADR-003 | Amended as above. PC-1 to PC-7 keep their meaning; PC-2, PC-3, and PC-8 are generalised; the init PR and the application-repository contract are added |
| ADR-005 | Scope amendment on decision 1 |
| ADR-001 | The Section 5 deny rules and the instruction-trust rule are carried into every application repository (the generic part in the template, the platform part in the preset). No change to the ADR |
| ADR-011 | Decision 17 is answered by the generic operator contract (design section 12); the ADR-011 specifics go to the preset's `docs/PLATFORM.md` |
| ADR-009, ADR-010 | Dependencies and assumptions listed (design section 11); neither decided |
| `ai-software-template` | Receives the implementation (nine proposed PRs) |
| `ai-lab-infrastructure` code | **Not changed by CR-39.** `scripts/pr_contract/` and `config/project.yaml` do not yet implement ADR-003 as amended (`approver_id`, `design_repos`, `operator_paths`, qualified PC-3, new PR types). The preset or adoption change PR does (design section 14) |
| Seeded generic code | Copied once into the template at a recorded commit; no later link |

## 3. Security and privacy

- The template raises the baseline of every application repository: the deny rules, the instruction-trust rule with a precedence sentence, `pr-contract`, and the static checks `forbidden-api`, `operator-contract`, and `owned-drift` are generated. The risk is the opposite: a wrong file in the template reaches every repository. Approver-only tags (enforced by a tag ruleset), review of each sync PR, and the repository's own reviewed copy of `template-sync` are the controls.
- **Overwrite by default** (Q3) means a sync PR can change a security-relevant file the project edited. The edit is visible in the PR and only a declared override survives; `owned-drift` makes undeclared edits fail the project's own gate.
- Template-sync runs as the machine account in a human-started session, clones a public repository with credential helpers disabled, and opens a PR. It adds no secret and no workflow with write rights. It cannot merge, and the `forbidden-api` check rejects scripts that would.
- `review-threads` is where untrusted review text could become an instruction. It matches the approver by immutable account ID, drops items edited by other accounts, refuses PRs from forks and PRs not authored by the machine account, and reports the counts excluded.
- Deny rules match only Claude's own commands. A script's subprocesses, a person's command, and a compromised host are not covered; on a private repository without rulesets, branch protection is procedural (ADR-001 RR-10). Design section 10 says so.
- `CLAUDE.md` imports two seeded files. A failed import loses project context, not guardrails. A host-local `CLAUDE.local.md` is invisible to the gate and is a residual risk.
- The template and its generated repositories are public by this platform's preset. The leak check and the public-repository rules apply to the template itself.
- The ADR-003 amendment puts an immutable account ID in a public configuration file. An account ID is not secret.

## 4. Operational impact on the approver

- Reviews and merges the design PR, which also accepts the ADR-003 and ADR-005 amendments.
- Creates template release tags and applies the tag ruleset on the template; reviews each sync PR.
- Approves ADR-009 and ADR-010 before Stage 5 starts.
- Reviews the preset change PR in `ai-lab-infrastructure`, and runs the real throwaway-repository run (design section 12 (b)), including adding and removing the machine account as collaborator for it.

## 5. Dependencies and assumptions

- ADR-009 and ADR-010 are decided in separate CRs. Design section 11 records what this design assumes of them. If they differ, the template changes by a release and a sync.
- The GitHub template-repository flag on `ai-software-template` is on (Stage 0, `docs/operations/github-setup.md`). I have not read the template repository.
- The platform workspace can run the whole scripted dry run: no OCI, no lab VM, no operator machine.
- `gh pr edit` and `gh pr ready` fail in the workspace (Projects classic error); the design avoids them (T-12).
- Hosted ARM64 runners are free for public repositories (ADR-005); whether they exist for private repositories is a verification item.
- The preset exists before the real run.

## 6. Cost and capacity

No OCI cost. GitHub Actions minutes on public repositories are free; the template's CI runs a few jobs per PR on two architectures, with two configurations in the dry run. Token cost of Skills is ADR-010's.

## 7. Rollback

Before the template is released, revert the implementation PRs. After release, an application repository reverts its sync PR (a normal PR revert), and a faulty version is superseded by a corrected tag; a tag that a repository has synced is never moved or deleted (moved tags are refused by sync). The design PR, including the two amendments, is reverted by a new PR if the ADR is not accepted.

## 8. Alternatives considered

See ADR-008 section 3. The ones the approver decided against in the discussion: a `template/` subdirectory with a generator, a zoned `CLAUDE.md`, skipping locally changed files, running the fetched sync script, a live link for shared code, and a scripted dry run as the only exit.
