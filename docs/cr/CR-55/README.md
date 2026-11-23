# CR-55: Cross-platform architectures and cross-builds design

| Field | Value |
|---|---|
| Issue | #55 |
| Class | 3 |
| Status | Design proposal for the architecture discussion. Nothing is implemented |
| ADR | Amends (Proposed) [ADR-008](../../adr/ADR-008-software-template.md) and [ADR-009](../../adr/ADR-009-security-and-ci-baseline.md); see design section 5. ADR-001, ADR-003, and ADR-005 are not amended |
| Origin | User requirement of 2026-11-23: "the lab should also be able to develop cross-platform architectures and cross-builds" |

## Summary

Designs cross-platform support for application repositories and the workspace: `amd64` is standard, `arm64` is the target, and there is no reverse direction. **Native build and test come first** on any GitHub-hosted runner that has the target; a build-only cross-build with no emulation is the fallback, used where no native runner is allowed (the workspace, and a private repository without an ARM64 runner). Cross toolchains live in the project repository and are not covered. The design adds a script `scripts/cross-build`, a step in the existing matrix job of an architecture without a runner, and a check `no-emulation`; it adds no manifest field, no configuration key, and no required job. PC-9 and `gate-evidence` are unchanged. Design only.

## Files

| File | Purpose |
|---|---|
| [impact-analysis.md](impact-analysis.md) | What changes, security impact, cost, rollback |
| [design.md](design.md) | Hosted runners considered, decisions XB-1 to XB-12, amendments, alternatives, questions Q1 to Q4, risks |
| [acceptance-criteria.md](acceptance-criteria.md) | Criteria XB-A1 to XB-A8 with evidence |
| [implementation-plan.md](implementation-plan.md) | Proposed implementation PRs, preconditions, user-only steps |

## Notes

Drafted from ADR-005 (context), ADR-008 (decisions 8, 9, 10), ADR-009 (decisions 1, 2, 7, 10, 12), GitHub's hosted-runner pages as summarized by a search on 2026-11-23, CR-43 design sections 4 and 7, and, as merged in `main` at `85360e8`, `scripts/gate-evidence`, `scripts/pr_contract/config.py` and `rules.py`, `config/project.yaml`, and `ci.yml`. I did not read the `ai-software-template` repository.
