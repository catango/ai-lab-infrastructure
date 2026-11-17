# CR-2: Stage 1 workspace foundation

| Field | Value |
|---|---|
| Issue | #2 |
| Class | 3 |
| Status | Design PR open (informational only; approval is the merge of the design PR, ADR-003 section 5) |
| ADR | [ADR-005](../../adr/ADR-005-toolchain.md) (Proposed) |
| Stage | 1 of the build sequence (baseline section 6) |

## Summary

Designs the Stage 1 deliverables: toolchain manifest and Ansible layout with `builder` and `lab` profiles,
`workspace/restore.sh` (ADR-001 section 4a), `scripts/quality-gate.sh`, `scripts/pr-contract` (PC-1 to PC-7),
and the CI skeleton with an ARM64 job. Design only: no scripts, roles, or workflows in this PR.

## Files

| File | Purpose |
|---|---|
| [impact-analysis.md](impact-analysis.md) | What changes, security and operational impact, rollback |
| [design.md](design.md) | The design, decisions S1-1 to S1-7, and the open questions for the approver (section 9) |
| [acceptance-criteria.md](acceptance-criteria.md) | Testable criteria with evidence |
| [implementation-plan.md](implementation-plan.md) | Six implementation PRs, order, user-only actions |

## Next step

Approver answers the open questions in design section 9, then reviews and merges the design PR.
Implementation PRs follow the plan.
