# CR-39: Software template design (ADR-008)

| Field | Value |
|---|---|
| Issue | #39 |
| Class | 3 |
| Status | Design draft. The questions for the approver (design section 13) are open and the architecture discussion has not taken place. Nothing is implemented |
| ADR | [ADR-008](../../adr/ADR-008-software-template.md) (Proposed) |
| Origin | Baseline v0.1 Stage 5 (software template), which runs first since Stages 2 to 4 are postponed (baseline section 6, 2026-11-19) |

## Summary

Designs the software template: the structure of `ai-software-template`, what is generated into an application repository and what stays in the template, `CLAUDE.md`, rules, Skills (including `address-review-feedback`), the CR and ADR templates, how template updates reach application repositories (the template-sync PR of ADR-003), the template's own quality gate and CI, what is specific to the ARM64 lab VM, the public-repository rules, the project-side operator contract of ADR-011, and the throwaway-repository dry run that is the Stage 5 exit criterion. Design only: no change to the template repository or to any code, workflow, or setting.

Stage 5 entry needs ADR-008, ADR-009, and ADR-010 approved. This CR delivers ADR-008 only. ADR-009 (security and CI baseline) and ADR-010 (token optimisation and metrics) are separate CRs; design section 11 lists the dependencies and assumptions and decides neither.

## Files

| File | Purpose |
|---|---|
| [impact-analysis.md](impact-analysis.md) | What changes, security impact, rollback, alternatives |
| [design.md](design.md) | Decisions ST-1 to ST-12, the structure, template-sync, Skills, gate and CI, ARM64, dry run, and the questions Q1 to Q12 for the approver |
| [acceptance-criteria.md](acceptance-criteria.md) | Criteria T-1 to T-16 with evidence; T-16 is the Stage 5 exit criterion |
| [implementation-plan.md](implementation-plan.md) | Nine proposed implementation PRs in `ai-software-template`, preconditions, and user-only actions |

## Notes

The design is drafted from the baseline (sections 3, 6, 7, 8), ADR-001, ADR-003 (sections 3 to 8), ADR-005, and ADR-011 only. The recommendations in section 13 are proposals for the architecture discussion and are not decisions. I did not read the `ai-software-template` repository.
