# CR-39: Software template design (ADR-008)

| Field | Value |
|---|---|
| Issue | #39 |
| Class | 3 |
| Status | Design with the approver's decisions Q1 to Q14 applied (architecture discussion, 2026-11-19). In review. Nothing is implemented |
| ADR | [ADR-008](../../adr/ADR-008-software-template.md) (Proposed). This PR also amends [ADR-003](../../adr/ADR-003-pr-centric-workflow.md) (Q8) and [ADR-005](../../adr/ADR-005-toolchain.md) (Q7) |
| Origin | Baseline v0.1 Stage 5 (software template), which runs first since Stages 2 to 4 are postponed (baseline section 6, 2026-11-19) |

## Summary

Designs the software template: the structure of `ai-software-template` (owned, seeded, and template-only files), template-sync and the init PR, `CLAUDE.md` (fully owned, platform-neutral, importing two seeded files), rules and guardrails, Skills including `address-review-feedback`, the CR and ADR templates, the template's own quality gate and CI, the architecture matrix, public and private repositories, the generic operator contract, and the Stage 5 exit (a scripted dry run and one real run by the approver). The template is decoupled from this platform and takes every platform value from one configuration (Q14). Design only: no change to the template repository or to any code, workflow, or setting.

Stage 5 entry needs ADR-008, ADR-009, and ADR-010 approved. This CR delivers ADR-008 only. ADR-009 and ADR-010 are separate CRs; design section 11 lists the dependencies and assumptions and decides neither.

## Files

| File | Purpose |
|---|---|
| [impact-analysis.md](impact-analysis.md) | What changes, security impact, rollback, alternatives |
| [design.md](design.md) | Decisions ST-1 to ST-15, the structure, template-sync and init, Skills, gate and CI, architectures, the Stage 5 exit, the approver's decisions Q1 to Q14, and what is still open |
| [acceptance-criteria.md](acceptance-criteria.md) | Criteria T-1 to T-22 (T-18 unused) with evidence; T-16 is the Stage 5 exit criterion |
| [implementation-plan.md](implementation-plan.md) | Nine proposed implementation PRs in `ai-software-template`, the preset outside CR-39, preconditions, and user-only actions |

## Notes

The design is drafted from the baseline (sections 3, 6, 7, 8), ADR-001, ADR-003 (sections 3 to 8), ADR-005, and ADR-011 only, and revised from the approver's decisions on PR #40. I did not read the `ai-software-template` repository. Design section 14 lists what stays open, including that this repository does not yet implement ADR-003 as amended.
