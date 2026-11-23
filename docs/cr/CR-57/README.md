# CR-57: A platform-agnostic AI workflow platform

| Field | Value |
|---|---|
| Issue | #57 |
| Class | 3 |
| Status | Design proposal for the architecture discussion. Nothing is implemented |
| ADR | Supersedes (Proposed) [ADR-002](../../adr/ADR-002-infrastructure-deployment-pipeline.md) and [ADR-011](../../adr/ADR-011-operator-tier.md); amends [ADR-001](../../adr/ADR-001-trust-model-and-execution.md) and [ADR-005](../../adr/ADR-005-toolchain.md); see design section 5. ADR-003, ADR-008, ADR-009, and ADR-010 are not edited |
| Origin | User requirement of 2026-11-23: "simplify the approach and discard all platform related requirements ... platform agnostic, focus on preconfigured ai and integrated github workflows ... connect to any ai lab environment via ssh ... Discard all OCI configuration and lab setup" |

## Summary

The platform becomes two things: preconfigured AI (Claude Code settings, rules, Skills, guardrails) and integrated GitHub workflows (the PR-centric workflow, the CI and security baseline, the software template). Claude Code runs on any SSH-reachable Linux host that the user provides, through Claude Desktop SSH sessions; the platform states a small host contract and nothing else about hosts. Everything technology-specific belongs to the project the platform drives. The OCI configuration, the lab setup, the operator tier, Ansible, and the host profiles are discarded; the toolchain shrinks to the tools of this repository's own gate. CR-55 (cross-builds) is withdrawn, since cross-builds are now project-owned. Design only.

## Files

| File | Purpose |
|---|---|
| [impact-analysis.md](impact-analysis.md) | What changes, security impact, cost, rollback |
| [design.md](design.md) | Decisions PA-1 to PA-12, the host contract, amendments and supersession, alternatives, questions Q1 to Q6, risks |
| [acceptance-criteria.md](acceptance-criteria.md) | Criteria PA-A1 to PA-A10 with evidence |
| [implementation-plan.md](implementation-plan.md) | Proposed implementation PRs in removal order, preconditions, user-only steps |

## Notes

Drafted from ADR-001 (decisions, zones, credential matrix, section 5, risks), ADR-002 and ADR-011 (decisions), ADR-005 (decisions 6, 9, 10), the baseline decision index, and the file inventory of `main` at `85360e8`. I did not read the rest of the baseline, CR-18's design, or the template repository.
