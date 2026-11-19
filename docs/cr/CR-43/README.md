# CR-43: Security and CI baseline design (ADR-009)

| Field | Value |
|---|---|
| Issue | #43 |
| Class | 3 |
| Status | Design with the approver's decisions applied (review on PR #44, 2026-11-19). In review. Nothing is implemented |
| ADR | [ADR-009](../../adr/ADR-009-security-and-ci-baseline.md) (Proposed). This PR also amends [ADR-001](../../adr/ADR-001-trust-model-and-execution.md) (A3), [ADR-003](../../adr/ADR-003-pr-centric-workflow.md) (A1), [ADR-005](../../adr/ADR-005-toolchain.md) (A4), and [ADR-008](../../adr/ADR-008-software-template.md) (A2) |
| Origin | Baseline v0.1 section 7 (ADR-009) and the dependencies D9-1 to D9-8 of [CR-39 design section 11](../CR-39/design.md) |

## Summary

Designs the security and CI baseline of every repository on this platform: which checks are required status checks, the Actions hardening rules, the repository security features on GitHub Free for public and for private repositories, fork pull requests and third-party Actions, the host-reported evidence line for an architecture with no hosted runner, the rulesets that `initialize-project` prints, and the gate checks `forbidden-api`, `operator-contract`, and `owned-drift`. It also fixes the catalogue of quality-gate checks, how this repository and the software template share the same rules without a live link, and the settings the approver applies by hand. Design only: no change to code, a workflow, a setting, a ruleset, or the `ai-software-template` repository; the only accepted records changed are the four amendments.

Stage 5 entry needs ADR-008, ADR-009, and ADR-010 approved. This CR delivers ADR-009 only. ADR-010 (token optimisation and metrics) is a separate CR; design section 13 lists the dependencies and assumptions and decides nothing of it.

## Files

| File | Purpose |
|---|---|
| [impact-analysis.md](impact-analysis.md) | What changes, security impact, rollback, alternatives |
| [design.md](design.md) | Decisions SC-1 to SC-21, the answers to D9-1 to D9-8, the check catalogue, rule sharing, the approver's settings list, the amendments applied, the approver's decisions Q1 to Q22, and what stays open |
| [acceptance-criteria.md](acceptance-criteria.md) | Criteria S-1 to S-23 with evidence |
| [implementation-plan.md](implementation-plan.md) | Proposed implementation PRs (1, 2a, 2b, 3 to 6 and the template items), preconditions, and user-only actions |

## Notes

Drafted from baseline sections 3, 6, and 7, ADR-001 (section 5, decisions 3, 4, and 8, RR-10), ADR-003 (sections 5 and 6), ADR-005 (decisions 3 and 7), ADR-008 and CR-39 design (sections 5, 8, 10, 11), the Stage 0 runbook, this repository's workflows, `scripts/checks/workflow-policy.sh`, and `.github/dependabot.yml`. GitHub plan facts were read from GitHub's documentation on 2026-11-19; design section 5 marks what was not verified by a run. I did not read the `ai-software-template` repository and I could not read the live rulesets and settings of either repository (design section 16).
