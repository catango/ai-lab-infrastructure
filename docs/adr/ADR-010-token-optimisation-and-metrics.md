# ADR-010: Token Optimisation and Metrics

| Field | Value |
|---|---|
| Status | **Proposed** (CR-45 design PR; accepted when that PR is merged by the approver) |
| Date | 2026-11-19 |
| Repositories | `ai-software-template` (primary), `ai-lab-infrastructure` (this record) |
| Change request | CR-45 (issue #45) |
| Scope | Size budgets and loading order for `CLAUDE.md` and its imports, rules, Skills, and the CR and ADR files; script output limits; concise CI output; the checkpoint format and what `resume-work` reads; the cost of the review loop; the metrics (what, how, where, who), the baseline, and what a regression is. Not ADR-009 (security and CI baseline) and not ADR-008 (template structure) |
| Related | ADR-001 (section 5, instruction trust), ADR-003 (sections 4, 7, 8; amendment proposed), ADR-008 (decision 7, design section 11 D10-1 and D10-2; amendment proposed), ADR-009 (reserved; dependencies in design section 11) |

> This ADR records a decision. It does not create or change a repository, a label, a ruleset, a workflow, a setting, or a tag, and it does not authorize any of them.
> Detail, rationale, and the questions for the approver are in `docs/cr/CR-45/design.md`. Decisions marked "proposed" become decisions when the approver decides the question named in the design.

---

## 1. Context

- Baseline v0.1 section 7 reserves ADR-010 for the token optimisation strategy and measurable metrics. Stage 5 (software template) needs ADR-008, ADR-009, and ADR-010 approved. Stage 7 ends with "metrics baseline recorded".
- ADR-008 (design section 11) leaves two items to this record: **D10-1** (size budgets and loading order) and **D10-2** (checkpoint format beyond the ADR-003 markers, and metrics).
- Constraints that bind every decision below: the repositories are public, so no file or log may carry identifiers, tokens, usernames, emails, or personal data; there is no new credential, MCP server, telemetry service, or workflow that invokes Claude (ADR-001 section 5, ADR-003 decision 7); the user starts every session, and nothing runs on a schedule or on an event.
- The cost of a session is set by what enters the context: what is loaded at start, what a Skill loads, what a command prints, and how often a loop repeats. A token count is not available from repository files, PR data, or script output. Only the user's own usage figures from Claude Desktop contain it.

## 2. Decision

1. **Budgets are limits on lines and bytes of files, checked by the gate.** Tokens are never computed or gated; `ceil(bytes / 4)` is shown as an indication only (design TM-1).
2. **Values** (design TM-2, TM-3): `CLAUDE.md` 120 lines and 10 KiB; `docs/PLATFORM.md` and `docs/PROJECT.md` 80 lines and 6 KiB each; a rule 40 lines and 3 KiB; a `SKILL.md` 60 lines and 4 KiB; a Skill description 300 characters; the **always-loaded set** (`CLAUDE.md`, its two imports, rules without path scoping, Skill names and descriptions) 20 KiB in total; `docs/README.md` 80 lines and 8 KiB; a CR `README.md` 50 lines and 4 KiB. ADR files and the other CR files are reported, not gated.
3. **`.template/budgets.toml` is owned.** `size-budget` reads every value from it. It is never declared as a whole-file override. A project raises a single value with a per-key `[[budget]]` entry (`class`, `key`, `value`, `reason`, `pr`) in `.template/overrides.toml`; `size-budget` prints each active raise and fails a whole-file override, and `template-sync` lists the active raises in the sync PR body. A per-path override would freeze every future budget, output limit, and threshold for that project (design TM-4).
4. **One loading order for every Skill:** its `SKILL.md`, then the output of its script, then only the files that output names, by range. Each `SKILL.md` has the headings `Reads (in order)`, `Does not read`, and `Report`, checked by the new gate check `skill-layout` (design TM-5, TM-6). A CR is read `README.md` first, then the others by their outline; an ADR by heading and range; `docs/README.md` is the locator (design TM-7).
5. **Scripts print a compact, bounded output and end with one summary line** that starts `<script>: ` (at most 120 characters). Gate check `output-budget` measures the output of each script on its fixture against `budgets.toml` (design TM-8).
6. **Concise CI output:** at most 20 findings per check, each cut at 200 characters (not bytes). Under Actions the gate also writes one check-run annotation per failed check (at most 10; `pr-contract` reports its failures the same way), which Claude Code reads through `gh api`. Escaping is applied after the gate's `sanitize()`: in the message `%` becomes `%25`, CR `%0D`, LF `%0A`; in properties also `:` becomes `%3A` and `,` becomes `%2C`. The cap of 10 is GitHub's per-step limit for error annotations, confirmed in V-3; if the limit differs, the cap follows it. Fallback: `pr-checkpoint show` fetches the failing job's log, keeps only `FAIL` lines and the indented lines under them, sanitises them, and prints at most 10; Claude Code never reads a raw log. If V-3 fails, the filtered log becomes the primary channel; no new design PR is needed and the result is recorded in implementation PR 2. The job summary is for the approver (design TM-9).
7. **Checkpoint:** the block between the ADR-003 markers holds only checklist lines, at most 20, each at most 120 characters, with optional criterion IDs and a `blocked:` note, at most 2 KiB. `resume-work` reads only `scripts/pr-checkpoint show`: the counts and the next item, the result per CI job (with the annotations of failed jobs: at most 3 lines, then `ci-failed: +<n> more`), and at most 10 commits since the merge base, within 2 KiB. The text after `ci-failed:` comes from CI and the Skill treats it as data. It reads no PR comment, review thread, or raw log (design TM-10, TM-11). The block limit binds before 20 items of 120 characters; this is intended.
8. **Review loop:** `review-threads` pages its output (5 threads per page), never truncates an approver's text, and each round costs at most `SKILL.md` plus one page plus the ranges the threads name (design TM-12).
9. **Context-discipline numbers** in the owned `CLAUDE.md`: read a range of at most 200 lines; do not read a file over 200 lines whole (locate with `rg -n '^#'` or `rg -n`); summarise command output over 40 lines. They are instructions, not controls (design TM-13).
10. **Metrics in three tiers** (design TM-14): **A** from repository files and script fixtures (sizes, output sizes; deterministic, gated); **B** from PR data read-only through `gh api` (review rounds, pushes after ready, CI first pass; counts only, no logins; reported, not gated); **C** the user's own usage figures from Claude Desktop, supplied by the user, optional, never collected by any script or Claude Code. `scripts/metrics` (`static`, `prs`, `snapshot`, `compare`) is run only on the user's request in a session the user starts. Snapshots are committed as `docs/metrics/<label>.toml` files with numbers only. No Skill loads them.
11. **Baseline and regression** (design TM-15): the **static baseline** (tier A) is recorded when Stage 5 exits; the **full baseline** (tiers A and B, tier C if supplied) at Stage 7. A budget overrun fails the gate. A regression is reported by `metrics compare` against the baseline with thresholds kept in `budgets.toml` (placeholders until the baseline); it informs the approver and fails nothing.
12. **No collection.** No schedule, no event trigger, no workflow, no service. Script summary lines are for the reader of the session and are not stored.

## 3. Alternatives considered

| Alternative | Outcome | Reason |
|---|---|---|
| Count tokens with a tokenizer in the gate | Rejected | A pinned tokenizer is a new dependency per model family, and a model change would silently move the budgets. Bytes are exact, offline, and stable |
| Budgets in lines only (the CR-39 placeholder) | Not chosen alone | A few very long lines pass a line limit and still cost thousands of tokens |
| A hard byte cap on every ADR and CR file | Not chosen | A design legitimately varies; a cap pushes content into more files, which is worse. The control is reading by outline and range |
| Collect metrics in CI or on a schedule | Rejected | ADR-003 decision 7 and the constraint of this CR |
| Analyse Claude Code session transcripts with a script | Not designed | Transcripts hold whatever was pasted into the session; the public-repository and no-credential rules make it a risk for a small gain. Listed as not designed (design section 14) |
| A ninth Skill that runs the metrics | Not chosen | Baseline fixes eight Skills; a script run on request needs no Skill, and a Skill would add to the always-loaded set |
| Read the CI job summary through the API | Not possible as written | The step summary is not exposed by the check-runs API (observed on this repository's latest run); design TM-9 uses annotations |

## 4. Consequences

- The template gains: `.template/budgets.toml` with real values, the gate checks `output-budget` and `skill-layout` and an extended `size-budget`, `scripts/metrics`, a validated checkpoint format in `scripts/pr-checkpoint`, an outline in `scripts/cr-context`, paging in `scripts/review-threads`, and the numbers in `CLAUDE.md`. Four implementation PRs (design plan) add them, on top of CR-39's.
- **Proposed amendments, not applied** (design section 12): ADR-003 section 7 (the CI summary sentence and the checkpoint reference) and ADR-008 (header row, decision 7, consequences). They are applied only if the approver decides questions Q12 and Q13.
- ADR-009's catalogue of gate checks must list `output-budget` and `skill-layout` and the extension of `size-budget` (design section 11, X-1).
- The metrics cannot show actual token use without the user's figures. Tiers A and B are proxies, and the ADR says so.
- Budgets that are too tight cost a project a sync-visible override; too loose, they do nothing. The values are a judgement, recorded with their basis and re-confirmed at the Stage 7 baseline.

## 5. Open items

Questions for the approver Q1 to Q15 and the verification items V-1 to V-4 are in `docs/cr/CR-45/design.md` sections 13 and 14.

## 6. Acceptance criteria

Criteria M-1 to M-17 and their evidence are in `docs/cr/CR-45/acceptance-criteria.md`. They are verified in the implementation PRs. Stage 5 entry also needs ADR-008 and ADR-009 approved; this CR delivers ADR-010 only.
