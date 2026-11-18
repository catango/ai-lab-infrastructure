# CR-21: ADR-003 rule PC-8 (operator script review)

| Field | Value |
|---|---|
| Issue | #21 |
| Class | 3 |
| Status | Design in review. The approver accepted Q1 to Q3 on 2026-11-18 (design section 5). Nothing is implemented |
| ADR | [ADR-003](../../adr/ADR-003-pr-centric-workflow.md) (Accepted). This PR adds rule PC-8 to its section 6 and acceptance criterion AC3-7 |
| Origin | The approver's decision handoff of 2026-11-18 on PR #19 (CR-18, [ADR-011](../../adr/ADR-011-operator-tier.md)), which asked for PC-8 in a separate design PR |

## Summary

Adds rule PC-8 to the `pr-contract` check: a PR that changes operator code must carry a non-empty PR-body section
"Operator script review". Operator code is what runs with credentials or sudo on the operator machines: `scripts/operator/`,
`ansible/operator.yml`, its roles, and their data files. The rule makes the extra review that ADR-011 asks for visible in
every such PR. Design only: no change to `pr-contract`, the PR templates, or any workflow in this PR.

## Files

| File | Purpose |
|---|---|
| [impact-analysis.md](impact-analysis.md) | What changes, security impact, rollback |
| [design.md](design.md) | The rule, the section's content, decisions PC8-1 to PC8-5, and the questions for the approver |
| [acceptance-criteria.md](acceptance-criteria.md) | Testable criteria with evidence |
| [implementation-plan.md](implementation-plan.md) | The one implementation PR and the user-only actions |

## Notes

Issue #21 has a title only ("ADR-003 PC-8") and no body. The scope comes from the handoff of 2026-11-18 on PR #19: "add PC-8, an
'Operator script review' section required for changes under `scripts/operator/`, `ansible/operator.yml`, its roles and their
data files". The content of the section (design section 3) is my proposal. The path matching was decided by the approver (design section 5).
