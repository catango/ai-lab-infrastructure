# CR-2: Stage 1 workspace foundation

| Field | Value |
|---|---|
| Issue | #2 |
| Class | 3 |
| Status | Implemented in six PRs (quality gate, `pr-contract`, toolchain, builder profile, restore, finish). Open: the timed reset test (R-4, AC1-7), run by the approver. Approval of the design was the merge of the design PR (ADR-003 section 5) |
| ADR | [ADR-005](../../adr/ADR-005-toolchain.md) (accepted by the merge of the design PR) |
| Stage | 1 of the build sequence (baseline section 6) |

## Summary

Designs the Stage 1 deliverables: toolchain manifest and Ansible layout with `builder` and `lab` profiles,
`workspace/restore.sh` (ADR-001 section 4a), `scripts/quality-gate.sh`, `scripts/pr-contract` (PC-1 to PC-7),
and the CI skeleton with an ARM64 job. Design only: no scripts, roles, or workflows in this PR.

## Files

| File | Purpose |
|---|---|
| [impact-analysis.md](impact-analysis.md) | What changes, security and operational impact, rollback |
| [design.md](design.md) | The design, decisions S1-1 to S1-7, and the approver's decisions on the open questions (section 9) |
| [acceptance-criteria.md](acceptance-criteria.md) | Testable criteria with evidence |
| [implementation-plan.md](implementation-plan.md) | Six implementation PRs, order, user-only actions |

## Next step

The approver merges the last implementation PR, creates the release tag `v0.1.0`, and runs the reset test
([runbook](../../operations/workspace-restore.md)). The acceptance evidence table is in the body of the last implementation PR.
