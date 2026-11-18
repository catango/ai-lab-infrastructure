# CR-21 Implementation plan

Starts only after the design PR is merged (ADR-003 section 4). The PR uses branch `impl/CR-21-pc8`, declares `Implements: #21` and `Design: #<design PR>`, and keeps its own checkpoint list.

## 1. The PR

| # | PR (branch slug) | Content | Needs | Acceptance criteria |
|---|---|---|---|---|
| 1 | `pc8` | The PC-8 rule in `scripts/pr_contract/rules.py` with the path list, fixtures and tests, the hint comment in four templates, and the docs index line | Design merged; Q1 to Q3 decided | A-1 to A-9 |

## 2. Checklist

- [ ] Draft PR opened with the implementation template, `Implements:` and `Design:` filled in
- [ ] Fixtures and tests written first for A-1 to A-9
- [ ] Rule and template hints implemented
- [ ] `./scripts/quality-gate.sh` passes; any skipped check is reported
- [ ] CI green
- [ ] Marked ready for review

## 3. User-only actions

| When | Action |
|---|---|
| Before the PR | Decide Q1 to Q3 on the design PR |
| After the PR merges | Check that `pr-contract` is still a required status check (no change to settings is needed) |

## 4. What this plan does not do

- No change to repository settings or rulesets.
- No change to PC-1 to PC-7.
- No operator code: CR-18 owns it, and its PRs carry the section once PC-8 is enforced.
