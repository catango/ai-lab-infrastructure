# CR-45 Design: token optimisation and metrics (ADR-010)

| Field | Value |
|---|---|
| CR | issue #45 (Class 3) |
| Governing records | Baseline v0.1 (sections 3, 6, 7, 8), ADR-003 (sections 4, 7, 8; as amended by CR-39), ADR-008 (in full) and [CR-39 design](../CR-39/design.md) (sections 5, 6, 8, 11), CR-39 criteria T-4, T-6, T-12, T-13 |
| Record produced | [ADR-010](../../adr/ADR-010-token-optimisation-and-metrics.md), status Proposed. Amendments to ADR-003 and ADR-008 are **drafted in section 12 and not applied** (Q12, Q13) |
| Scope | Design only. Nothing is implemented, and the `ai-software-template` repository is not touched |
| State | First draft. The architecture discussion has not taken place. Every open point is a question for the approver (section 13) or a verification item (section 14) |

## 1. Scope and boundaries

In scope (ADR-010, baseline section 7): the context loading strategy (what is loaded at session start, what a Skill may load, in which order), the size budgets that CR-39 left as placeholders (D10-1), the checkpoint format beyond the ADR-003 markers (D10-2), concise CI output, the context-discipline rules and whether they need numbers, the cost of the review loop, and the metrics: what is measured, how, where it is stored, who reads it, how a baseline is recorded, and what a regression is.

Out of scope: ADR-009 (CR #43, open in parallel): which checks are required, Actions hardening, repository security features, the check catalogue as a whole, the evidence line. Section 11 lists each overlap as a dependency. Also out of scope: any change to the template, code, workflows, labels, rulesets, or settings; any telemetry service, credential, MCP server, scheduled or event-driven run, or workflow that invokes Claude.

I read of ADR-009 only the `README.md` of its CR (`docs/cr/CR-43/`). Its design has not been read, so section 11 states what this design assumes of it.

## 2. Decisions in this design

| ID | Decision | Rationale |
|---|---|---|
| TM-1 | Budgets are limits on **lines and bytes** of files, checked by the gate. Tokens are never computed or gated. `ceil(bytes / 4)` is printed as an indication only | Bytes are exact, offline, and independent of the model. A line limit alone is bypassed by long lines (section 3) |
| TM-2 | Per-file values in section 4.1 (Q1) | Basis in section 3: about twice the measured size of comparable files |
| TM-3 | The **always-loaded set** has an aggregate limit of 20 KiB (Q2) | The set is paid in every session; per-file limits alone allow a sum nobody chose |
| TM-4 | `.template/budgets.toml` is **owned** (as ADR-008 design section 3 already classes it) and is never declared as a whole-file override. `size-budget` reads every value from it. A project raises a single value with a per-key entry in the seeded `.template/overrides.toml`, table `[[budget]]` with `class`, `key`, `value`, `reason`, and `pr`. `size-budget` applies each entry, prints each active raise as `raise: <class>.<key> <old> -> <new> (<pr>)`, and fails a whole-file override of `budgets.toml`. `template-sync` lists the active raises in the sync PR body (Q3) | A raise becomes visible in review and in the sync PR; no code change moves a budget. A per-path override would freeze every future budget, output limit, and threshold for that project |
| TM-5 | **One loading order for every Skill:** its `SKILL.md`, the output of its script, then only the files that output names, by range. Each `SKILL.md` has the headings `Reads (in order)`, `Does not read`, `Report`; new gate check `skill-layout` (Q15) | Makes "what a Skill may load" checkable instead of advisory |
| TM-6 | The per-Skill reads of section 5.2 | One decision per Skill, so the check has something to test |
| TM-7 | CR files: `README.md` first, then the others by outline (`scripts/cr-context` prints the `##` headings with line numbers). ADR files: by heading and range. `docs/README.md` is the locator. Gated: the docs index and the CR `README.md`. Reported, not gated: ADR files and the other CR files (Q4) | A hard cap on a design pushes content into more files; the control is reading by section |
| TM-8 | Scripts print a bounded output and end with one summary line that starts `<script>: `. New gate check `output-budget` measures each script's output on its fixture against `budgets.toml` (Q15) | The cost of a script is the bytes it prints; fixtures make that deterministic |
| TM-9 | Concise CI output: at most 20 findings per check (as now), each at most 200 characters; under Actions, one check-run **annotation** per failed check (at most 10), read by Claude Code through `gh api`. The job summary stays for the approver (Q6) | The step summary is not readable through the API (section 3); annotations need no permission and no Action |
| TM-10 | Checkpoint format of section 7.1, validated by `scripts/pr-checkpoint` (Q5) | Bounds the one thing every `resume-work` reads |
| TM-11 | `resume-work` reads only `scripts/pr-checkpoint show` (section 7.2) | Restates ADR-003 section 7 with a size and a list of what it must not read |
| TM-12 | Review loop: `review-threads` pages (5 threads per page), never truncates an approver's text; the per-round bound of section 9 (Q8) | The loop's cost is rounds times a bounded round; rounds are measured |
| TM-13 | Context-discipline numbers in the owned `CLAUDE.md`: range of at most 200 lines; a file over 200 lines is not read whole; command output over 40 lines is summarised (Q7) | A number is followed more reliably than "targeted"; it is an instruction, not a control |
| TM-14 | Metrics in **three tiers** (section 10): A from repository files and script fixtures, B from PR data read-only, C the user's own usage figures. `scripts/metrics` has `static`, `prs`, `snapshot`, and `compare`. Snapshots are committed numbers-only files. No Skill loads them (Q9) | Tiers A and B are proxies; only tier C holds token counts |
| TM-15 | **Baseline:** static baseline at the Stage 5 exit; full baseline at Stage 7. **Regression:** a budget overrun fails the gate; a drift against the baseline is reported by `metrics compare` with thresholds in `budgets.toml` and fails nothing (Q10, Q11) | Baseline Stage 7 says "metrics baseline recorded" without saying what it holds |
| TM-16 | Tier C is **optional and user-supplied**: the user types numbers from Claude Desktop into a snapshot, or keeps them locally. No script and no Claude Code session reads Claude Desktop, a transcript, or a credential (Q14) | Constraint of this CR |
| TM-17 | No collection: nothing runs on a schedule or an event, and summary lines are not stored | ADR-003 decision 7; the constraint of this CR |

## 3. What the measurements say

Measured in this session on this repository (`wc`, 2026-11-19). The template does not exist yet, so the template's own sizes are estimates.

| Fact | Value | Used for |
|---|---|---|
| `CLAUDE.md` of this repository | 58 lines, 5,473 B (94 B per line, about 1,400 tokens) | Line and byte limits (TM-2): 120 lines is about twice this |
| CR-39 files read whole | five files, 68,492 B (about 17,000 tokens); `design.md` alone 44,184 B in 14 sections | The case for outline reading (TM-7) |
| `README.md` plus one `design.md` section | about 2.5 KB plus 3.2 KB on average, 8% of the whole CR | The same |
| ADR files | ADR-001 21,956 B, ADR-003 14,773 B, ADR-008 11,456 B | Reading by heading (TM-7) |
| `docs/README.md` of this repository | 65 lines, 6,405 B, one row per document | Index limit (section 4.1) |
| Gate output | `MAX_FINDINGS=20`, `PASS`/`FAIL` lines, one summary line | TM-8, TM-9 keep it |
| CI summary channel, latest run on `main` | the check-run `output.summary` is empty and the run has no annotations; the job log holds the gate's own lines (`PASS ...`, `FAIL ...`, the summary line) | TM-9 |

The step summary that `$GITHUB_STEP_SUMMARY` receives is not in the check-runs API response. ADR-003 section 7 says Claude "reads the summary through `gh`"; as implemented that is not possible for the summary, only for the log. Section 12 drafts the correction (Q12).

**Estimate of the always-loaded set for the template** (nothing exists to measure): `CLAUDE.md` about 6 KB (this repository's neutral part plus the precedence sentence and the discussion-prompt rule), `docs/PLATFORM.md` 3 to 4 KB, `docs/PROJECT.md` 2 to 3 KB at start, the always-applied rule `public-repo.md` about 1.5 KB, eight Skill descriptions about 2 KB: **about 14 to 16 KiB, 4,000 tokens** (the listed parts sum to 14.2 to 16.1 KiB). The first implementation PR measures the real set and reconfirms the limits.

## 4. Budgets (D10-1)

### 4.1 Values

The CR-39 placeholders are `CLAUDE.md` 120 lines, a rule 40, a `SKILL.md` 60. The lines are confirmed and bytes are added (Q1). The byte limits are set to bind before the line limits for prose at the measured density (94 B per line in this repository's `CLAUDE.md`; a 120-line `CLAUDE.md` would be about 11 KiB). This is intended: bytes track cost, lines bound layout.

"Basis" says whether the value rests on a measurement of this repository (`measured`) or on an estimate for the template, which does not exist yet (`estimate`).

| Class | Paths | Lines | Bytes | Basis | Rationale |
|---|---|---|---|---|---|
| `claude-md` | `CLAUDE.md` | 120 | 10 KiB | measured | About twice this repository's file (58 lines); room for the precedence sentence and the discussion-prompt rule |
| `platform` | `docs/PLATFORM.md` | 80 | 6 KiB | estimate | The ADR-001 and ADR-011 specifics as rules, not text copied from the ADRs |
| `project` | `docs/PROJECT.md` | 80 | 6 KiB | estimate | Seeded small and grown by the project; the limit forces links to `docs/` instead of inline text |
| `rule` | `.claude/rules/*.md` | 40 | 3 KiB | estimate | The six rules of CR-39 design section 5 are five to fifteen bullets each |
| `skill` | `.claude/skills/*/SKILL.md` | 60 | 4 KiB | estimate | Design section 6 lists six parts of a `SKILL.md`; about 25 to 35 lines, twice that as headroom |
| `skill-description` | `description` in each `SKILL.md` frontmatter | | 300 characters | estimate | Descriptions are loaded for every Skill in every session (V-1); a trigger sentence needs about 150 |
| `docs-index` | `docs/README.md` | 80 | 8 KiB | measured | This repository's index is 65 lines and 6.4 KB |
| `cr-readme` | `docs/cr/CR-*/README.md` | 50 | 4 KiB | measured | Read first on every CR; CR-39's is 28 lines, CR-18's 45 |

**ADR files and the other CR files are reported by `metrics static`, not gated** (TM-7, Q4). The reading rule is by outline and range.

### 4.2 The always-loaded set

The set is `CLAUDE.md`, the two files it imports, every rule without path scoping, and the name and description of every Skill. `size-budget` computes it from the files (it parses the rule frontmatter) and fails above **20 KiB**, about 5,000 tokens or 2.5% of a 200,000-token window. This is a judgement, not a measurement: the aim is a fixed cost that stays small against a long session, and the estimate of section 3 leaves 4 to 6 KiB of headroom. The limits of the table cannot all be reached at once (their sum is 28 KiB, which assumes exactly one rule without path scoping); that is intended.

Outside the set and not budgeted: user-level configuration under `~/.claude/` (on this platform restored from `workspace/claude-user/`, ADR-001 D16) and Claude Code's own system prompt and tool definitions. The share of the context window depends on the model.

### 4.3 How `size-budget` reads the values

`.template/budgets.toml` (owned). Illustrative; the implementation PR fixes the schema.

```toml
schema = 1

[class.claude-md]
paths = ["CLAUDE.md"]
max_lines = 120
max_bytes = 10240

[class.rule]
paths = [".claude/rules/*.md"]
max_lines = 40
max_bytes = 3072

[class.skill-description]
paths = [".claude/skills/*/SKILL.md"]   # the frontmatter field
max_chars = 300

[group.always-loaded]
max_bytes = 20480

[outputs]                              # bytes on the script's fixture (section 6)
cr-context = 4096
pr-checkpoint-show = 2048

[regression]                           # section 10.4; placeholders until the baseline
always_loaded_bytes_pct = 10
output_bytes_pct = 25
```

A project raises one value in the seeded `.template/overrides.toml` (illustrative):

```toml
[[budget]]
class  = "rule"
key    = "max_bytes"
value  = 4096
reason = "the project's security rule needs the room"
pr     = "owner/repo#12"
```

`size-budget` expands the globs, counts lines and bytes (`wc -l`, `wc -c` semantics) and characters for the description, compares them with the class, and prints `path: <lines> lines > <max>` style findings. A class with no matching file passes. A value changed in the file changes the outcome without a code change.

`.template/budgets.toml` is owned and is never declared as a whole-file override. A project raises a single value with a per-key entry in the seeded `.template/overrides.toml`, table `[[budget]]` with `class`, `key`, `value`, `reason`, and `pr`. `size-budget` applies each entry, prints each active raise as `raise: <class>.<key> <old> -> <new> (<pr>)`, and fails a whole-file override of `budgets.toml`. `template-sync` lists the active raises in the sync PR body. The reason for the per-key form: a per-path override would freeze every future budget, output limit, and threshold for that project, because the project's copy would no longer follow the template's releases. The ADR-008 change that records this is in section 12 (Q13).

## 5. Loading order (D10-1)

### 5.1 At session start and in a Skill

- **At start**, the always-loaded set (section 4.2) and nothing else. Path-scoped rules load when matching files are read (V-1).
- **In a Skill:** (1) the `SKILL.md`; (2) the output of its script; (3) the files that output names, by range, in the order the output lists them; (4) never a directory, never an ADR or CR file whole when it has more than 200 lines.
- **For a CR:** `README.md` first, then `scripts/cr-context` prints the other files with lines, bytes, and `##` headings with line numbers; the Skill reads the section it needs.
- **For an ADR:** `rg -n '^#' <file>` (about 20 headings, 600 B), then the range. `docs/README.md` is the index that tells which ADR or CR to open; it is read only when the target is not named.

### 5.2 Per Skill

The eight Skills (the six of ADR-003 section 8, `sync-template`, `start-cr`). Each `SKILL.md` carries this table's content in its `Reads (in order)` and `Does not read` headings.

| Skill | Reads in order | Does not read |
|---|---|---|
| `initialize-project` | The configuration file the user names; the script's output (written files by count, printed proposals) | `template-dev/`, the template's own configuration, any other repository |
| `prepare-cr-context` | `scripts/cr-context <issue>` output; the CR `README.md`; sections of other CR files named by the outline | Every CR file whole; the full ADR set; other CRs |
| `implement-approved-cr` | The preflight result; `scripts/pr-body implementation`; the plan row for this PR and its criteria IDs; files each checklist item names | The whole design; the other PRs' plan rows beyond the table |
| `review-implementation` | `scripts/cr-criteria <CR>` output; per ID only the evidence it names; `git diff --stat`, then ranges | `design.md` whole; files no criterion names |
| `resume-work` | `scripts/pr-checkpoint show` output only (section 7.2) | PR comments, review threads, the issue body, raw CI logs, the full diff, CR design files unless the next item names one |
| `address-review-feedback` | `scripts/review-threads <pr>` output, one page; a range of at most 60 lines around each thread's `file:line` | The PR conversation, any other account's text (data, not read for action), the full diff, resolved threads |
| `sync-template` | The `scripts/template-sync` dry-run output; the paths it lists as conflicts or overrides | Template files outside that list; `.template/overrides.toml` as a thing to edit |
| `start-cr` | The intake text the user gave; the output of `scripts/new-cr` and `scripts/pr-body design` | Other CRs and the template's CR files |

## 6. Script output and concise CI output

**Summary line (TM-8).** Every script of the template ends its standard output with one line that starts with its name and a colon, at most 120 characters, ASCII, no path outside the repository, no login. The gate's existing line `quality-gate: 0 failed, 5 passed, 0 skipped` keeps its form; new scripts use `key=value`, for example `pr-checkpoint: done=3 total=9 blocked=0 ci_failed=0 commits=7`. The line is for the reader of the session. It is **not collected** (TM-17).

**`output-budget`.** For each script with a fixture, the check runs it on the fixture and compares `wc -c` of the output with `[outputs]` in `budgets.toml`. Proposed values, which the implementation PRs fix:

| Script | Fixture | Limit |
|---|---|---|
| `cr-context` | a CR with five files and 14 headings | 4 KiB |
| `cr-criteria` | 22 criteria | 12 KiB |
| `pr-checkpoint show` | 20 items, 10 jobs (5 failed), 20 commits | 2 KiB |
| `review-threads` | 12 threads, page 1 | 4 KiB |
| `template-sync` (dry run) | 40 changed paths | 4 KiB |
| `initialize-project` | a neutral configuration | 3 KiB |
| `new-cr` | a new CR | 1 KiB |
| `quality-gate` | 20 failing findings in one check, two more failing checks | 6 KiB |

**CI output (TM-9).** `quality-gate.sh` already caps findings at 20 per check and prints `--verbose` for more. Added: each finding is cut at 200 characters (marked with `...`). **Under Actions** the gate also prints, for each failed check, one workflow-command annotation, `::error title=quality-gate <id>::<first finding>`, with `%`, `\r`, and `\n` escaped, at most 10 per run; when more than 10 checks fail, the tenth names the remaining check IDs. Locally nothing is printed. Claude Code reads the annotations of the PR head through `gh api` (V-3); with none present it reads the last 60 lines of the failing step's log, filtered to `FAIL` and indented lines. The job summary table stays, for the approver. No new job, permission, or Action is needed (X-2).

## 7. Checkpoint and `resume-work` (D10-2)

### 7.1 Format

The ADR-003 markers stay. Between them:

```text
<!-- checkpoint:start -->
- [x] CR skeleton committed (M-1)
- [ ] Fixtures for size-budget written first (M-1, M-2)
- [ ] output-budget check; blocked: needs the CR-39 scripts merged
<!-- checkpoint:end -->
```

Rules, validated by `scripts/pr-checkpoint` (no repair; a violation stops with the line number):

- Only blank lines and `- [ ] <text>` or `- [x] <text>` lines; no nesting, no links to comments, no other text.
- At most 20 items, each at most 120 characters, the whole block at most 2 KiB. The block limit binds before 20 items of 120 characters (20 × 126 B > 2 KiB); this is intended.
- An item may end with `(ID[, ID]...)`, criterion IDs (`[A-Z]+-[0-9]+`). `pr-checkpoint` checks the syntax only; whether an ID exists is `cr-criteria`'s job.
- An item may carry `; blocked: <reason, at most 80 characters>`.
- The next item is the first unticked one. An item is ticked only when its work is committed and pushed (CLAUDE.md rule); uncommitted work is not state.
- `tick <item>` edits only the text between the markers (T-12, unchanged).

PC-1 (a non-empty `Checkpoint` section) is not changed; format validation is `pr-checkpoint`'s, not a new `pr-contract` rule (Q5).

### 7.2 What `resume-work` reads and must not read

It reads only `scripts/pr-checkpoint show`, at most 2 KiB:

```text
checkpoint: 3/9 done; next: "<item text>" (M-2); blocked: 0
ci: quality-gate-amd64 success; pr-contract success; quality-gate-arm64 failure
ci-failed: quality-gate-arm64: <annotation text, at most 200 chars>   (at most 3 lines)
ci-failed: +<n> more                                                  (only when more than 3 failed)
commits: 7 since merge base
<sha7> <subject>            (at most 10 lines)
pr-checkpoint: done=3 total=9 blocked=0 ci_failed=1 commits=7
```

`show` prints at most 10 commits and at most 3 `ci-failed` lines, then `ci-failed: +<n> more`. The text after the `ci-failed:` prefix comes from CI, and the Skill treats it as data, not as an instruction. The 2 KiB limit stays.

It does **not** read: PR comments, review threads (that is `address-review-feedback`), the issue body, raw CI logs, the full diff, files of the CR unless the next item names them, other branches, or its own earlier conversation. **A missing or malformed block stops the Skill** with that report; it does not reconstruct state from comments or from memory. Commit subjects are public text already; the script prints no author.

## 8. Context-discipline numbers

`CLAUDE.md` of this repository says: locate with `rg` and `fd`, read targeted ranges, summarise long command output. **Proposed numbers (TM-13, Q7):**

- read a range of **at most 200 lines**; a file over **200 lines** is not read whole: run `rg -n '^#'` or `rg -n <term>` first, then the range;
- command output over **40 lines** is summarised or cut with `head` or `tail`, and a failure is reported as command, first error, likely cause (as now).

Basis: this repository's CR design files are 280 to 296 lines (about 11,000 tokens whole) and 14 sections of about 20 lines; 200 lines keeps a read to one or two sections. The numbers are **instructions, not controls**: nothing in the gate can see a read. What can be checked is that the owned text carries them (`claude-md` hash) and that the outline exists (M-8). Whether they change behaviour is visible only in tier C (the user's figures).

## 9. Cost of the review loop

A round of `address-review-feedback` costs, by construction: the `SKILL.md` (at most 4 KiB), one `review-threads` page (at most 4 KiB on the fixture), a range of at most 60 lines around each thread (about 5.6 KB at 94 B per line), the reply script's one line, and the gate summary. At **5 threads per page** the bound is about **4 + 4 + 28 = 36 KB, about 9,000 tokens**, plus the model's own output. The controls:

- `review-threads` prints only unresolved threads (outdated ones flagged), 5 per page (`--page <n>` for the rest), and the counts of excluded items by reason (T-11, unchanged). It **never truncates the approver's text**: an instruction cut short is worse than a long page.
- Rounds are not capped by design: the approver drives them. They are **measured** (tier B: `review_rounds`, `pushes_after_ready`) so a rising count shows up in `metrics compare`.

This changes `review-threads` (CR-39 design section 6) by adding paging; the design there says "prints compact JSON", so paging is additive. It is a requirement on implementation PR 3 of this CR's plan, not an amendment.

## 10. Metrics

### 10.1 What can be measured from what

| Source | Can measure | Cannot |
|---|---|---|
| Repository files and script fixtures (tier A) | Lines and bytes per budgeted file; the always-loaded set; Skill count and description length; output bytes of each script on its fixture; heading counts of ADR and CR files. Exact, offline, repeatable | Tokens actually used; whether an instruction was followed |
| PR data through read-only `gh api` (tier B) | Per PR: review rounds (approver review submissions that request changes), pushes after ready for review, workflow runs and whether the first gate run passed, commits, checkpoint items, PR body bytes. Counts only | Tokens; time inside a session |
| Script output alone | One summary line per run (counts) | Anything over time; nothing is stored (TM-17) |
| The user's own usage figures from Claude Desktop (tier C) | Tokens per session or per PR (input, output, cache), hence tokens per checklist item, per review round, per merged PR | Everything, if the user does not supply it. **Unverified:** which figures Claude Desktop shows (V-4) |

### 10.2 `scripts/metrics`

Owned template script, run **only on the user's request** in a session the user starts; no workflow calls it. It is not a Skill (a ninth Skill would add to the always-loaded set; Q9).

| Command | Does | Network |
|---|---|---|
| `metrics static` | Tier A for the working tree; prints a compact table | None |
| `metrics prs --last <n>` or `--prs <list>` | Tier B for merged PRs; counts and medians; refuses fewer than `min_prs` for a median and says "indicative" | `gh api` GET only (`forbidden-api` applies) |
| `metrics snapshot --label <l>` | Writes `docs/metrics/<l>.toml` from the two above plus the optional `[usage]` table; refuses to overwrite | As above |
| `metrics compare <a> <b>` | Prints each value that crosses a `[regression]` threshold; exit 1 if any, 0 if none | None |

It has `--fixture` for offline tests, calls `gh api` with argument arrays, reads no path outside the repository, and prints **no login, name, email, or token**: approver identity is matched by account ID and only counts are printed.

### 10.3 Storage and readers

Snapshots are committed in a change PR as `docs/metrics/<label>.toml`: numbers, PR numbers (public), and a label. No date (git has it), no identifier. The schema:

```toml
schema = 1
label = "baseline"
template_version = "v0.1.0"            # the tag in .template/state.toml

[static]
always_loaded_bytes = 16384
always_loaded_est_tokens = 4096        # ceil(bytes / 4), indication only
skills = 8
skill_description_chars = 1900
[static.files]                         # path = [lines, bytes], budgeted classes
"CLAUDE.md" = [58, 5473]
[outputs]                              # script = bytes on its fixture
cr-context = 2100

[prs.123]
review_rounds = 1
pushes_after_ready = 0
ci_runs = 3
ci_first_pass = true
commits = 12
checkpoint_items = 9
pr_body_bytes = 2300

[usage.123]                            # optional, typed by the user (TM-16)
sessions = 2
input_tokens = 0
output_tokens = 0
cache_read_tokens = 0
```

Numbers above are placeholders to show the shape, not measurements. **Readers:** the approver at a metrics review and when a budget change is proposed; Claude Code only when the user asks in the session to run `metrics compare` or to read a snapshot. No Skill loads `docs/metrics/`, and `docs/README.md` lists the directory as "not read by default".

### 10.4 Baseline and regression (TM-15)

| | When | Holds | Recorded by |
|---|---|---|---|
| **Static baseline** | The last implementation PR of the template, the Stage 5 exit | Tier A on the template and on a generated repository | `metrics snapshot --label baseline-static` in that PR |
| **Full baseline** | Stage 7 ("metrics baseline recorded"), after the first real project (Stage 6) | Tiers A and B over the PRs of one full Class 3 CR, tier C if the user supplies it | A change PR `docs/metrics/baseline.toml`, reviewed by the approver |

Stage 7 waits for the postponed Stages 2 to 4 (baseline section 6). The static baseline does not.

**What a regression is.**

1. **Hard, in the gate:** any budget of section 4 exceeded, or any script output over its `[outputs]` value. Fails CI. Deterministic.
2. **Soft, reported by `compare`, decided by the approver:** against the baseline, always-loaded bytes up by more than 10%; a script's fixture output up by more than 25%; for tier B over at least 5 PRs, median `review_rounds` up by 1 or more, first-pass rate down by 20 points or more, median `pushes_after_ready` up by 2 or more; for tier C, median tokens per merged PR up by more than 30%. A soft regression changes no exit code in CI, because CI computes none of it.

The soft thresholds are **placeholders**: no data exists. They live in `[regression]` of `budgets.toml`, and the approver re-confirms them in the baseline PR (Q11). With fewer than 5 PRs the output says "indicative only".

## 11. Dependencies and assumptions

Listed, not decided. ADR-009's design was not read, only its CR `README.md` (CR-43).

| ID | Depends on | Assumption in this design |
|---|---|---|
| X-1 | ADR-009: the catalogue of gate checks | It lists `size-budget` (already in CR-39 design section 8) and accepts two more, `output-budget` and `skill-layout`, plus the extension of `size-budget` of section 4. If ADR-009 names or splits them differently, the implementation follows its catalogue |
| X-2 | ADR-009: Actions hardening and `workflow-policy` | Annotations are workflow commands printed by the gate; no new permission, Action, or workflow. No workflow runs `scripts/metrics` |
| X-3 | ADR-009: required status checks, job summary, the `not run: <arch>` line and the evidence line | Unchanged. This design adds no job; every new check runs inside the gate. The annotation is in addition to the summary |
| X-4 | ADR-009: `public-repo-hygiene` patterns | Snapshots and fixtures must pass them; no new pattern is needed |
| X-5 | ADR-008 (CR-39): `size-budget`, `claude-md`, `owned-drift`, Skills, `pr-checkpoint`, `cr-context`, `review-threads` | Extended as in sections 4 to 9; the amendment text is in section 12 (Q13) |
| X-6 | ADR-003: PC-1 and the checkpoint markers | Format validation is `pr-checkpoint`'s; no new `pr-contract` rule |
| D10-1 | CR-39 design section 11 | **Answered** by sections 4 and 5 and Q1 to Q4. The CR-39 file is approved and is not edited; this table records the closure |
| D10-2 | CR-39 design section 11 | **Answered** by sections 6, 7, and 10 and Q5, Q6, Q9 to Q11. CR-39 assumed one summary line per run and no collection; that holds (TM-8, TM-17) |

## 12. Proposed amendments (drafted, not applied)

Applied only if the approver decides yes in Q12 or Q13. Wording is mine.

**ADR-003** (Q12). Header row `Amended by`: append "CR-45 (Proposed): section 7, the reference to the checkpoint format and the CI summary channel. Takes effect when the CR-45 design PR is merged". Section 7:

- Bullet *Draft PR as checkpoint*: replace the last sentence ("`resume-work` reads only the checklist, the latest CI summary, and `git log` since the merge base.") with: "`resume-work` reads only the checklist, the latest CI result, and `git log` since the merge base, through `scripts/pr-checkpoint show`, in the format and within the limits of ADR-010."
- Bullet *Concise CI output*: replace the text with: "CI failures are written to the job summary as short, structured output for the approver, and as at most 10 check-run annotations, one per failed check, for Claude Code, which reads them through `gh api` and not raw logs. The step summary itself is not exposed by the API. Sizes are limited by ADR-010."

**ADR-008** (Q13). Add the header row `| Amended by | ADR-010 (Proposed, CR-45): budgets and loading order, checkpoint format, metrics; closes D10-1 and D10-2 of design section 11. Takes effect when the CR-45 design PR is merged |`. Append to decision 7: "Each `SKILL.md` has the headings `Reads (in order)`, `Does not read`, and `Report`, and stays within the size budgets of ADR-010." Append to section 4 (Consequences): "ADR-010 adds `scripts/metrics`, the gate checks `output-budget` and `skill-layout`, an extended `size-budget`, and the values of `.template/budgets.toml`. They follow the template's implementation PRs."

## 13. Decisions of the approver (architecture discussion, 2026-11-19)

Recorded from the approver's review on PR #46 (reviewed at `8ee0da0`). Wording is condensed; each decision is applied in the section named.

| # | Decision | Applied in |
|---|---|---|
| Q1 | Values accepted. The byte limits bind before the line limits for prose at the measured density (94 B per line; a 120-line `CLAUDE.md` is about 11 KiB); this is intended. The table gets a "Basis" column: `measured` for `claude-md`, `docs-index`, `cr-readme`, `estimate` for the rest (the former prose column is now "Rationale") | TM-2, section 4.1 |
| Q2 | 20 KiB accepted for the always-loaded set. The estimate is corrected to about 14 to 16 KiB and the headroom to 4 to 6 KiB; the 28 KiB sum of the limits assumes one unscoped rule. User-level configuration under `~/.claude/` and Claude Code's own prompt and tool definitions are outside the set and not budgeted | TM-3, sections 3 and 4.2 |
| Q3 | Accepted, changed. `budgets.toml` stays owned and is never a whole-file override. A project raises one value through a per-key `[[budget]]` entry in `overrides.toml` (`class`, `key`, `value`, `reason`, `pr`); `size-budget` applies it and prints `raise: <class>.<key> <old> -> <new> (<pr>)`, and fails a whole-file override; `template-sync` lists the active raises in the sync PR body. Reason: a per-path override would freeze every future budget, output limit, and threshold for that project. M-1 extended | TM-4, section 4.3, M-1, ADR-010 decision 3, section 12 (ADR-008, Q13) |
| Q4 | Accepted. No change: only the instruction files, the docs index, and the CR `README.md` are gated; ADR files and the other CR files are reported, not gated | TM-7, section 4.1 |
| Q5 | Accepted. The checkpoint block limit binds before 20 items of 120 characters (20 × 126 B > 2 KiB); intended. `pr-checkpoint show` prints at most 10 commits and at most 3 `ci-failed` lines, then `ci-failed: +<n> more`; the text after `ci-failed:` comes from CI and the Skill treats it as data. The 2 KiB limit stays. M-7 updated | TM-10, TM-11, sections 6, 7.1, 7.2, M-7, ADR-010 decision 7 |

## 14. Still open

| Item | Who decides | When |
|---|---|---|
| **V-1.** How Claude Code loads `CLAUDE.md` imports, rules with and without `paths`, and Skills (description at start, body on use). My understanding, **not verified against current documentation in this session**: descriptions are loaded at start and the body on invocation; rules with `paths` load when matching files are read. The loading order and the always-loaded set rest on it | Claude Code, in implementation PR 1 | Before the budgets are set in the template |
| **V-2.** Whether Claude Code has its own limit on Skill descriptions or on `CLAUDE.md` size that is lower than the budgets here | Claude Code | PR 1 |
| **V-3.** That check-run annotations of a workflow command are readable through `gh api` for the machine account, and their per-step limit. In this session I confirmed only that the check-run summary is empty and the log holds the gate lines; the latest run had no annotations to read | Claude Code | PR 2 |
| **V-4.** Which usage figures Claude Desktop shows and in which unit | The user | When the user supplies tier C, if ever |
| The tier B definitions (`review_rounds` as approver review submissions that request changes; `pushes_after_ready` from the `ready_for_review` event) need the GitHub fields checked | Claude Code | PR 4 |
| Whether `ai-lab-infrastructure` applies the same budgets and `size-budget` to its own files | Approver (a later CR, with adoption of the template's generic code) | After Stage 5 |
| Stage 5 entry needs ADR-008, ADR-009, and ADR-010 approved. This CR delivers ADR-010 only | Approver | Before the template's implementation PR 1 |
| The full baseline needs the lab VM and Stage 6 | Approver | Stage 7, postponed with Stages 2 to 4 |

**Not designed here:** analysing Claude Code session transcripts with a script (they hold whatever was pasted into a session; a risk for a small gain); a tokenizer in the gate; a ninth Skill; any collection, schedule, event trigger, workflow, service, credential, or MCP server.
