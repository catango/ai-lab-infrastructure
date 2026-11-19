# CR-45: Token optimisation and metrics design (ADR-010)

| Field | Value |
|---|---|
| Issue | #45 |
| Class | 3 |
| Status | Design in review with the approver's decisions Q1 to Q15 applied (architecture discussion, 2026-11-19). Nothing is implemented |
| ADR | [ADR-010](../../adr/ADR-010-token-optimisation-and-metrics.md) (Proposed). The amendments to ADR-003 (section 7, header row) and ADR-008 (header row, decisions 2 and 7, consequences) are applied in this PR (design section 12) |
| Origin | Baseline v0.1 section 7 (ADR-010) and the dependencies D10-1 and D10-2 of [CR-39 design section 11](../CR-39/design.md) |

## Summary

Designs the token optimisation strategy and the measurable metrics of every repository on this platform: size budgets and loading order for `CLAUDE.md`, its two imports, the rules, and the eight Skills; script output limits and concise CI output; the checkpoint format and what `resume-work` reads; the cost of the review loop; the context-discipline numbers; and the metrics (what, how, where stored, who reads them), the baseline, and what a regression is. Metrics come from repository files, PR data, and script output alone; the user's own usage figures from Claude Desktop are an optional input that the user supplies and no script collects. Design only: no change to code, a workflow, a setting, a ruleset, or the `ai-software-template` repository.

Stage 5 entry needs ADR-008, ADR-009, and ADR-010 approved. This CR delivers ADR-010 only. ADR-009 is a separate CR (#43); design section 11 lists the overlaps as dependencies and decides nothing of it.

## Files

| File | Purpose |
|---|---|
| [impact-analysis.md](impact-analysis.md) | What changes, security and privacy, rollback, alternatives |
| [design.md](design.md) | Decisions TM-1 to TM-17, the measurements behind the budgets, loading order, checkpoint format, metrics, dependencies, the applied amendments, the approver's decisions Q1 to Q15, and what stays open |
| [acceptance-criteria.md](acceptance-criteria.md) | Criteria M-1 to M-17 with evidence |
| [implementation-plan.md](implementation-plan.md) | Four proposed implementation PRs in `ai-software-template`, preconditions, and user-only actions |

## Notes

Drafted from baseline sections 3, 6, 7, and 8, ADR-003 sections 4, 7, and 8, ADR-008 and CR-39 (design sections 5, 6, 8, 11 and criteria T-4, T-6, T-12, T-13), and this repository's `CLAUDE.md`. Of ADR-009 I read only the `README.md` of its CR. I did not read the `ai-software-template` repository, and I did not verify the Claude Code loading behaviour or the Claude Desktop usage figures (design section 14, V-1 to V-4).
