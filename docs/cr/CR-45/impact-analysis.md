# CR-45 Impact analysis

## 1. What changes

In this design PR:

- [ADR-010](../../adr/ADR-010-token-optimisation-and-metrics.md) (Proposed) and the CR-45 files are added.
- `docs/README.md` gets rows for ADR-010 and CR-45.
- [ADR-003](../../adr/ADR-003-pr-centric-workflow.md) and [ADR-008](../../adr/ADR-008-software-template.md) are **not changed**. The amendment text is drafted in design section 12 and applied only if the approver decides Q12 and Q13.

Later, in implementation PRs in `ai-software-template`: the budgets and checks, the checkpoint validation, the outline and paging, the numbers in `CLAUDE.md`, and `scripts/metrics` (see the plan).

Nothing in this PR changes code, a workflow, a PR template, a label, a setting, or a tag, and the `ai-software-template` repository is not touched.

## 2. Affected components and records

| Item | Effect |
|---|---|
| ADR-003 | Proposed amendment of section 7: the checkpoint format reference and the CI summary channel (a correction: the step summary is not readable through the API) |
| ADR-008 and CR-39 design | D10-1 and D10-2 answered. ADR-008 gets a proposed amendment (header row, decision 7, consequences). The approved CR-39 design file is not edited |
| ADR-009 (CR #43) | Dependencies X-1 to X-4 (design section 11): the check catalogue lists two more checks, no new job, no new permission or Action, snapshots pass the hygiene patterns. Nothing of it is decided here |
| `ai-software-template` | Receives four implementation PRs on top of CR-39's |
| This repository's `CLAUDE.md` | Gets the context-discipline numbers in a change PR after ADR-010 is accepted (Q7) |
| `ai-lab-infrastructure` code | Not changed by CR-45. Whether it applies the budgets to its own files is a later CR |

## 3. Security and privacy

- **Public repositories.** Snapshots contain numbers, PR numbers, and a label. No login, name, email, token, or date. `scripts/metrics` prints counts and never an identity: the approver is matched by account ID and only counts are printed. Snapshots and fixtures pass `public-repo-hygiene`.
- **No new trust edge.** No credential, MCP server, telemetry service, or workflow that invokes Claude. `scripts/metrics` calls `gh api` with GET only; `forbidden-api` rejects write calls. Nothing runs on a schedule or an event.
- **Usage figures** are typed by the user. No script reads Claude Desktop, a session transcript, or a credential. Transcripts are not analysed because they hold whatever was pasted into a session.
- **Instruction trust.** The budgets bound what is loaded; they do not change who may instruct. `address-review-feedback` keeps its filters (T-11). Paging adds no filter and removes none, and never truncates approver text.
- **A budget that is too tight** could push someone to move a guardrail out of `CLAUDE.md` into a file that is not loaded. The mitigation is that the instruction-trust rule, the Never list, and the precedence sentence are in the owned `CLAUDE.md`, whose hash is checked, and the budget leaves room for them (design section 4.1).
- **Annotations** carry the first finding of a failed check, cut at 200 characters and escaped. Findings are paths and messages produced by the gate, which already sanitises them for the job summary.

## 4. Operational impact on the approver

- Decides Q1 to Q15 in the architecture discussion, reviews, and merges the design PR. Approving ADR-010 is part of the Stage 5 entry.
- Reviews four implementation PRs in the template and, when it is wanted, runs `metrics` in a session and reviews the baseline PR at Stage 7.
- **Optional:** types or supplies usage figures from Claude Desktop (tier C). Nothing requires it.

## 5. Dependencies and assumptions

- CR-39 is merged (PR #40 and #42). ADR-008, ADR-009, and ADR-010 are all needed for the Stage 5 entry.
- ADR-009 is decided in a separate CR; design section 11 records what this design assumes of it. If it differs, the implementation follows its catalogue.
- Loading behaviour of Claude Code (imports, path-scoped rules, Skill descriptions) and annotation retrieval are assumptions to verify in the implementation PRs (V-1 to V-3). The budgets are limits on files and do not depend on them; the always-loaded set definition does.
- The platform workspace can run all of it: no OCI, no lab VM, no operator machine.

## 6. Cost and capacity

No OCI cost and no new CI job. The new gate checks read a handful of small files and run each script once on a fixture. Token cost is what this CR reduces and bounds; its own cost is the Skill headings and the numbers in `CLAUDE.md` (a few hundred bytes of the 20 KiB always-loaded budget).

## 7. Rollback

Before the template is released, revert the implementation PRs. After release, a project reverts its sync PR. Raising a budget is an `overrides.toml` entry, which is also the way to live with a budget that proves too tight until a corrected tag. The design PR is reverted by a new PR if the ADR is not accepted.

## 8. Alternatives considered

See ADR-010 section 3: a tokenizer in the gate, line-only budgets, a hard cap on every ADR and CR file, collection in CI or on a schedule, transcript analysis, a ninth Skill, and reading the job summary through the API.
