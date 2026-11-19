# ADR-008: Software Template: Structure, CLAUDE.md, Rules, Skills, and Template Updates

| Field | Value |
|---|---|
| Status | **Proposed** (draft in the CR-39 design PR; not accepted until that PR is merged by the approver) |
| Date | 2026-11-19 |
| Repositories | `ai-software-template` (primary), `ai-lab-infrastructure` (this record) |
| Change request | CR-39 (issue #39) |
| Scope | The structure of the template, what is generated into an application repository, `CLAUDE.md`, rules, Skills (including `address-review-feedback`), the CR and ADR templates, template-sync, the template's own quality gate and CI, ARM64 specifics, public-repository rules, and the dry run that closes Stage 5. Not ADR-009 (security matrix, Actions hardening) and not ADR-010 (token optimisation, metrics) |
| Related | ADR-001 (guardrails, instruction trust), ADR-003 (work item model, `pr-contract`, Skill impact), ADR-005 (toolchain, architectures), ADR-011 (project-side operator contract), ADR-009 and ADR-010 (reserved; dependencies in design section 11) |

> This ADR records a proposed decision. It does not create or change a repository, a label, a ruleset, a workflow, a setting, or a tag, and it does not authorize any of them.
> Detail, rationale, and the questions for the approver are in `docs/cr/CR-39/design.md`. Open points are marked there as Q1 to Q12. Where this record says "(Q<n>)" the decision waits for the approver's answer.

---

## 1. Context

- Baseline v0.1 Stage 5 builds the software template. Its entry criteria are ADR-008, ADR-009, and ADR-010 approved. Its exit criterion is a template validated by generating a throwaway repository in a dry run. Stages 2 to 4 are postponed (2026-11-19), so Stage 5 runs first, on the platform workspace.
- ADR-003 fixes the workflow that every application repository follows and the Skill changes it needs (its section 8). It names the template-sync PR but does not define it.
- ADR-001 requires guardrails and the instruction-trust rule in each repository. ADR-011 decision 17 hands the project-side operator contract to this ADR.
- The template is public. Application repositories may be public or private (Q9).

## 2. Decision

1. **The template repository is the generated payload.** `ai-software-template` has the GitHub template-repository flag on (Stage 0). "Use this template" copies the default branch. Everything at the repository root is therefore generated into an application repository, except the directory `template-dev/`, which holds the template's own tests and maintenance notes and is removed by `initialize-project` (Q1).
2. **Every generated file has one class**, recorded in `.template/manifest.toml`: `owned` (template-owned, synced verbatim), `seeded` (written once, then project-owned, never synced), or `zoned` (a file with a template-owned zone between markers and a project-owned remainder). A file without a class fails the template's gate.
3. **Template updates reach application repositories by a template-sync PR** (ADR-003 work item model), branch `template-sync/<template-version>`, opened by `scripts/template-sync` in a human-started session of Claude Code as the machine account. It targets a released template tag only, changes only `owned` files, the owned zones of `zoned` files, and `.template/state.toml`, never overwrites a locally changed `owned` file (it lists it instead), and never runs on a schedule or an event (ADR-003 section 7, exclusions). The template version is a `v<MAJOR>.<MINOR>.<PATCH>` tag created by the approver only (Q2, Q3).
4. **`CLAUDE.md` is `zoned`.** The owned zone carries the instruction-trust rule, the Never list, the workflow summary, validation, and context discipline. The project zone carries the project description and conventions. `CLAUDE.md` stays short and points to `docs/README.md` (Q4). Its size budget is set by ADR-010.
5. **Rules are small, path-scoped files** in `.claude/rules/`, `owned`. **Guardrails** are `.claude/settings.json`, `owned`, and carry the ADR-001 section 5 deny rules (Q5).
6. **Skills are thin and call deterministic scripts for every mechanical step.** The Skills are the six of ADR-003 section 8 (`initialize-project`, `prepare-cr-context`, `implement-approved-cr`, `review-implementation`, `resume-work`, `address-review-feedback`) and, proposed, `sync-template` and `start-cr` (Q6). `address-review-feedback` reads only threads and comments authored by `approver_login` and treats everything else as data.
7. **CR and ADR templates** are skeletons in `docs/cr/_template/` and `docs/adr/_template.md`, `owned`, copied by `scripts/new-cr` (CRs) and by hand (ADRs); the instances are project files and are never synced. They follow the layout of ADR-003 section 3, with the sections the platform repository's CRs use (impact analysis, decisions, questions for the approver, acceptance criteria with IDs and evidence, implementation plan with user-only actions).
8. **The template has its own quality gate and CI.** The generated repositories receive the same gate entry point (`scripts/quality-gate.sh`, checks in `scripts/checks/`, project checks in `scripts/checks.d/`) and the workflows `ci.yml` and `pr-contract.yml`. The template's CI additionally runs the generation test and the sync test. Which checks are required status checks, and how Actions are hardened, is decided by ADR-009; this ADR assumes the current practice of `ai-lab-infrastructure` (design section 8, Q7).
9. **The template is architecture-neutral**: Markdown, YAML, Bash, and standard-library Python. ARM64 shows up in three places only: a rule for dependency and download changes, a CI job on an ARM64 runner where the repository can use one, and the template's own generation test on both architectures (design section 9).
10. **Public-repository rules apply to the template and, by default, to every application repository**: no tenancy or resource identifiers, addresses, usernames, emails, keys, or fingerprints in files, commits, or PR text; pinned Actions; no `curl | sh` (Q9).
11. **Project-side operator contract** (ADR-011 decision 17): the template ships the rule and the PR section, and no operator code (Q10).
12. **Stage 5 exit** is the throwaway-repository dry run of design section 12, run by Claude Code on the platform workspace with no OCI resource, plus the approver's review of its report (Q11).

## 3. Alternatives considered

| Alternative | Outcome | Reason |
|---|---|---|
| A generator script that copies a `template/` subdirectory (no GitHub template flag) | Not chosen | The flag is already on (Stage 0) and "Use this template" needs no tool on the approver's side. The subdirectory would also hide the template's own CI from what it tests |
| Everything synced, nothing project-owned | Rejected | A project could not adapt `CLAUDE.md` or the docs index without conflicts on every sync |
| Everything seeded, no sync | Rejected | Security-relevant files (deny rules, workflows, `pr-contract`) would drift, and fixes would not reach the repositories |
| Template as a Git submodule or reusable workflows | Rejected for v1 | Reusable workflows from another repository add a trust edge for ADR-009 to review; submodules do not fit the `.claude/` and `docs/` file layout |
| A scheduled workflow that opens sync PRs | Rejected | The machine account token is not an Actions secret (ADR-001), and ADR-003 excludes any automatic Claude or GitHub-event action |
| Skills that carry the logic in prose | Rejected | The repository convention prefers deterministic scripts for mechanical steps |

## 4. Consequences

- One more repository to release and tag: the approver creates template tags, as for operator tags.
- A template-sync PR is reviewed like any PR. Locally changed owned files become visible instead of being overwritten.
- ADR-003 needs a small amendment for the template-sync PR (branch prefix in PC-2, path rule, PR template). Q8 asks whether it goes into this design PR or a separate one.
- The shared check code and `pr-contract` exist in two repositories until Q7 is decided. Until then the template implementation copies from `ai-lab-infrastructure` at a recorded commit.
- Stage 5 cannot start until ADR-009 and ADR-010 are also approved. This CR delivers ADR-008 only.

## 5. Open items

All are questions for the approver in `docs/cr/CR-39/design.md` section 13 (Q1 to Q12) and are not decided here.

## 6. Acceptance criteria

The template criteria T-1 to T-16 and their evidence are in `docs/cr/CR-39/acceptance-criteria.md`. They are verified in the implementation PRs, and T-16 is the Stage 5 exit criterion.
