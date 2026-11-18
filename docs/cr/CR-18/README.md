# CR-18: Operator tier

| Field | Value |
|---|---|
| Issue | #18 |
| Class | 3 |
| Status | Design decisions complete; verifications VO-1, VO-3, VO-4, VO-7 to VO-17 and the platform operator VM facts open, each tied to the PR that needs it (design section 10.3). Nothing is implemented |
| ADR | [ADR-011](../../adr/ADR-011-operator-tier.md) (Proposed; becomes Accepted when this design PR is merged by the approver). It amends ADR-001 (zones Z6 and Z7, B3, the OCI credentials and personal-account rows, new credential rows; decision 5, B1, AC1-3, and RR-8 keep their wording) and ADR-005 (the `operator` profile) in this PR |
| Stage | Runs beside Stage 2 (CR-16). The first scripts replace manual procedures from Stage 0 and the Stage 2 acceptance tests |

## Summary

Designs the operator tier: two dedicated machines, the platform operator VM and the lab operator VM, separate from the AI hosts,
each with a dedicated operator user that runs reviewed, merged, AI-written scripts for tasks the AI must not or cannot run, such
as tasks that need OCI facts or GitHub repository permissions. Scripts run from release tags only, and every script has a
dry-run mode (the default) and an apply mode. The design covers the separation, the script contract (Python, except `setup`),
the `facts`, `github-setup`, and `acceptance` scripts, the `setup` script and the Ansible operator profile, credential handling
(no OCI credential on any operator machine; tokens T2 and T3 in-process), and what the lab build must provide (the lab operator
VM, absence alarms, and break-glass rebuilds). Design only: no machines, scripts, roles, or credentials in this PR.

## Files

| File | Purpose |
|---|---|
| [impact-analysis.md](impact-analysis.md) | What changes, security impact, rollback |
| [design.md](design.md) | The design, decisions OP-1 to OP-17, risks, verification items VO-*, and the decisions, rejections, and open items of the approver's handoff (section 10) |
| [acceptance-criteria.md](acceptance-criteria.md) | Testable criteria with evidence |
| [implementation-plan.md](implementation-plan.md) | Implementation PRs, order, user-only actions |

## Inputs recorded before this design

From the approver, 2026-11-18: a dedicated Linux user with a shell already exists on the platform workspace, has internet
access, and had no admin privileges. An additional user may be provisioned on the lab VM. Scripts for tasks that need
dedicated credentials or extended permissions are executed by this user by hand, and always offer a dry-run mode and an apply
mode. The Gate 0 audit, the GitHub setup, and acceptance tests with many calls are to be simplified this way.
The dry-run rule is not extended beyond operator scripts.

From the approver, 2026-11-18 (review): the amendment of ADR-001 is accepted; the operator may use sudo to install packages; package
installation is triggered by a dedicated script that sets up the operator workspace.

From the approver, 2026-11-18 (decision handoff on PR #19): operators run on dedicated machines separated from the AI hosts
(Q10), and the decisions Q1 to Q39 and R1 to R6 recorded in design section 10, among them the read-only instance principal on
the lab operator VM (Q3), the T2 and T3 tokens (Q4, R6), release tags (Q29), and rebuild as break-glass (Q23, Q24). The earlier
inputs above are superseded where they conflict: the operator user on the platform workspace is retired (Q25), and the sudo
decision became Q9 and Q37.
