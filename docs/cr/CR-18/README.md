# CR-18: Operator tier

| Field | Value |
|---|---|
| Issue | #18 |
| Class | 3 |
| Status | Design in review. Nothing is decided yet; the questions in design section 10 are recommendations. Nothing is implemented |
| ADR | [ADR-011](../../adr/ADR-011-operator-tier.md) (Proposed; becomes Accepted when this design PR is merged by the approver). It amends ADR-001 decision 5 and the OCI credentials row of its section 4 |
| Stage | Runs beside Stage 2 (CR-16). The first scripts replace manual procedures from Stage 0 and the Stage 2 acceptance tests |

## Summary

Designs the operator tier: a dedicated, unprivileged Linux user on the platform workspace (and optionally on the lab VM) that
runs reviewed, merged, AI-written scripts for tasks the AI must not or cannot run itself, such as tasks that need OCI
credentials or GitHub repository permissions. Every such script has a dry-run mode and an apply mode. The design covers the
separation from the AI user, the script rules, credential handling, the three first use cases (Gate 0 audit, GitHub
setup, acceptance tests), and what the lab build must provide. Design only: no scripts, users, or credentials in this PR.

## Files

| File | Purpose |
|---|---|
| [impact-analysis.md](impact-analysis.md) | What changes, security impact, rollback |
| [design.md](design.md) | The design, decisions OP-1 to OP-10, risks, verification items, and the open questions for the approver |
| [acceptance-criteria.md](acceptance-criteria.md) | Testable criteria with evidence |
| [implementation-plan.md](implementation-plan.md) | Implementation PRs, order, user-only actions |

## Inputs recorded before this design

From the approver, 2026-11-18: a dedicated Linux user with a shell already exists on the platform workspace, has internet
access, and has no admin privileges. An additional user may be provisioned on the lab VM. Scripts for tasks that need
dedicated credentials or extended permissions are executed by this user by hand, and always offer a dry-run mode and an apply
mode. The Gate 0 audit, the GitHub setup, and acceptance tests with many calls are to be simplified this way.
The dry-run rule is not extended beyond operator scripts.
