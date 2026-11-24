# CR-57: A platform-agnostic AI workflow platform

| Field | Value |
|---|---|
| Issue | #57 |
| Class | 3 |
| Status | Design revised with the approver's decisions (review of 2026-11-23, 18:27:31Z); for the architecture discussion. Design merged (PR 58); implementation PRs 0 to 3 merged. Follow-up R-2 (design PR, Proposed): a user-level deny layer for AI labs where an organisation policy outranks the managed file (design section 13) |
| ADR | Adds [ADR-012](../../adr/ADR-012-host-model.md) (Proposed); supersedes [ADR-002](../../adr/ADR-002-infrastructure-deployment-pipeline.md); amends [ADR-001](../../adr/ADR-001-trust-model-and-execution.md), [ADR-005](../../adr/ADR-005-toolchain.md), and [ADR-011](../../adr/ADR-011-operator-tier.md); adds [baseline v0.2](../../architecture/baseline-v0.2.md). ADR-003, ADR-008, ADR-009, and ADR-010 are not edited. Follow-up R-2 (Proposed) amends ADR-001 (section 5, AC1-5, RR-8) and ADR-012 (decisions 5 and 14, LC-16, section 7) |
| Origin | User requirement of 2026-11-23: "simplify the approach and discard all platform related requirements ... platform agnostic, focus on preconfigured ai and integrated github workflows ... connect to any ai lab environment via ssh ... Discard all OCI configuration and lab setup" |

## Summary

The platform becomes two things: preconfigured AI (Claude Code settings, rules, Skills, guardrails) and integrated GitHub workflows (the PR-centric workflow, the CI and security baseline, the software template). Claude Code runs as the AI user on a per-project, disposable AI lab (Debian 13, x86-64) that Claude Desktop reaches over SSH; the AI lab and a separate operator machine meet two contracts (ADR-012), and lab setup, the token step, and read-only checks replace the workspace restore. The OCI configuration, the lab operator machine, and ARM64 support are removed; the GitHub-scope operator tooling stays. Everything technology-specific belongs to the project the platform drives. CR-55 (cross-builds) is withdrawn. Design only.

## Files

| File | Purpose |
|---|---|
| [impact-analysis.md](impact-analysis.md) | What changes, security impact, cost, rollback |
| [design.md](design.md) | Givens, decisions PA-1 to PA-46, amendments, answers to Q1 to Q6, risks, interactions (PA-41), open points; section 13 (R-2): decisions PA-47 to PA-57, alternatives, risks RR-P12 to RR-P15, open points R2-O1 to R2-O5 |
| [acceptance-criteria.md](acceptance-criteria.md) | Criteria PA-A1 to PA-A33 (four removed; PA-A33 is new), and PA-A34 to PA-A38 of R-2, with command or fixture, and the PR that verifies each; the PA-A38 approver procedure |
| [implementation-plan.md](implementation-plan.md) | PRs 0 to 10 in strict order, PR 4a (R-2), criteria by PR, user-only steps, revert order, interim status |

## Notes

Revised from the approver's review of 2026-11-23T18:27:31Z on design PR 58, which replaces the first draft's default answers, and from the approver's rounds 2 to 5 of the same day. Read for the revision: ADR-001, ADR-002, ADR-005, ADR-011, baseline v0.1, ADR-010, ADR-003 (PC-8, sections 4 and 7), ADR-008 (decisions 5, 6, 8, 9, 11, 12, 14), ADR-009 (decisions 7, 11, 12, 14), the CR-43 design (SC-13, SC-20), and the file inventory of `main` at `85360e8`. The template repository (README and licence only) and CR-18's design body were not read beyond what the records cite.
