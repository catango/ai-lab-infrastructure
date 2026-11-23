# CR-55: Cross-platform architectures and cross-builds design

| Field | Value |
|---|---|
| Issue | #55 |
| Class | 3 |
| Status | Design proposal for the architecture discussion. Nothing is implemented |
| ADR | Amends (Proposed) [ADR-005](../../adr/ADR-005-toolchain.md), [ADR-008](../../adr/ADR-008-software-template.md), and [ADR-009](../../adr/ADR-009-security-and-ci-baseline.md); see design section 4. ADR-001 and ADR-003 are not amended |
| Origin | User requirement of 2026-11-23: "the lab should also be able to develop cross-platform architectures and cross-builds" |

## Summary

Designs cross-builds for application repositories and the workspace: targets `amd64` and `arm64` only, build only with pinned cross-compilers and no emulation, run on the x86-64 workspace and on a hosted amd64 CI runner, with tests staying native on the runner of each architecture. It adds a manifest field `targets`, a configuration key `cross_builds`, a script `scripts/cross-build`, a CI job `cross-build-<target>`, and a check `no-emulation`. PC-9 and `gate-evidence` are unchanged. Design only: no code, workflow, setting, ruleset, or tag changes.

## Files

| File | Purpose |
|---|---|
| [impact-analysis.md](impact-analysis.md) | What changes, security impact, cost, rollback |
| [design.md](design.md) | Decisions XB-1 to XB-14, amendments, alternatives, questions Q1 to Q8, risks |
| [acceptance-criteria.md](acceptance-criteria.md) | Criteria XB-A1 to XB-A10 with evidence |
| [implementation-plan.md](implementation-plan.md) | Proposed implementation PRs, preconditions, user-only steps |

## Notes

Drafted from ADR-005 (context, decisions 1, 3, 7, 9, 10), ADR-008 (decisions 8, 9, 10, 14), ADR-009 (decisions 1, 2, 7, 10, 12, 14), CR-43 design sections 4 and 7, and, as merged in `main` at `85360e8`, `scripts/gate-evidence`, `scripts/pr_contract/config.py` and `rules.py`, `config/project.yaml`, and `ci.yml`. I did not read the `ai-software-template` repository.
