# CR-39 Design: software template (ADR-008)

| Field | Value |
|---|---|
| CR | issue #39 (Class 3) |
| Governing records | Baseline v0.1 (sections 3, 6, 7, 8), ADR-001 (decisions 6 to 8, section 5), ADR-003 (sections 3 to 8), ADR-005 (decisions 3 to 7), ADR-011 (decision 17) |
| Record produced | [ADR-008](../../adr/ADR-008-software-template.md), status Proposed |
| Scope | Design only. Nothing is implemented, and the `ai-software-template` repository is not touched |
| State | **Draft.** Every point that needs the approver is a question in section 13. The recommendations are mine and are not decisions. The architecture discussion (ADR-003 section 4, step 3) has not taken place |

## 1. Scope and boundaries

In scope (ADR-008): template structure, `CLAUDE.md`, rules, Skills including `address-review-feedback`, the CR and ADR templates, template-sync, the template's own quality gate and CI (and how it relates to ADR-009), what is specific to the ARM64 lab VM, the public-repository rules, the project-side operator contract, and the Stage 5 dry run.

Out of scope: ADR-009 (security matrix, Actions hardening, which checks are required) and ADR-010 (token optimisation, metrics). Section 11 lists each dependency and the assumption this design makes. Nothing in section 11 is decided here.

## 2. Decisions in this design

| ID | Decision | Rationale |
|---|---|---|
| ST-1 | The template repository root is the generated payload. `template-dev/` is the only template-only directory and `initialize-project` removes it | The template flag is on since Stage 0 and copies the default branch; the template's own CI then tests the real payload (Q1) |
| ST-2 | Each generated file has a class in `.template/manifest.toml`: `owned`, `seeded`, or `zoned` | Sync needs to know what it may touch; an unclassified file fails the gate |
| ST-3 | Template-sync PR: `template-sync/<version>`, from a released tag, by `scripts/template-sync`, in a human-started session | ADR-003 names the PR; ADR-003 section 7 and ADR-001 exclude schedules and events (Q2, Q3, Q8) |
| ST-4 | `CLAUDE.md` is `zoned`: an owned zone between `<!-- template:start -->` and `<!-- template:end -->`, a project zone below | The instruction-trust rule and the Never list must stay identical in every repository (ADR-001 section 5); the project needs its own part (Q4) |
| ST-5 | Rules are path-scoped files under `.claude/rules/`; `.claude/settings.json` carries the ADR-001 section 5 deny rules | Context is loaded only when needed; guardrails live in the repository (ADR-001 decision 7) (Q5) |
| ST-6 | Skills are thin; each mechanical step is a script under `scripts/`; scripts have an offline mode driven by fixtures | Repository convention; makes the Stage 5 dry run possible without GitHub (Q6) |
| ST-7 | CR and ADR templates are `owned` skeletons copied by `scripts/new-cr` and by hand for ADRs; the instances are project files | Improvements reach projects; project CRs are never touched by sync (Q12) |
| ST-8 | Same gate entry point as `ai-lab-infrastructure`; generic checks `owned`, project checks in `scripts/checks.d/` `seeded` | Sync cannot collide with project checks (Q7) |
| ST-9 | The template is architecture-neutral; ARM64 appears in one rule, one CI job, and the generation test | Section 9 |
| ST-10 | Public-repository rules apply to every application repository by default | Section 10 (Q9) |
| ST-11 | The template ships the operator-script rule and PR-section hint, and no operator code | ADR-011 decision 17 (Q10) |
| ST-12 | Stage 5 exit is the scripted throwaway dry run of section 12 | Baseline section 6 (Q11) |

## 3. What is generated and what stays in the template

"Generated" means present in a new application repository after "Use this template" and `initialize-project`. Class: O = owned, S = seeded, Z = zoned.

| Path | Class | Content |
|---|---|---|
| `CLAUDE.md` | Z | Section 5 |
| `README.md` | S | Placeholder project readme |
| `config/project.yaml` | S | `approver_login`, `machine_login`, project name, visibility, host (`lab-vm` or `workspace`), merge method. Same key names as in this repository (scripts read them) |
| `.template/manifest.toml` | O | File classes, zone markers, template version, provenance of copied code |
| `.template/state.toml` | S, then written only by sync | Template version last synced, SHA-256 of each owned file and owned zone as synced |
| `.template/budgets.toml` | O | Size budgets for `CLAUDE.md`, rules, Skills, CR files (values from ADR-010, section 11) |
| `.claude/settings.json`, `.claude/required-deny.txt` | O | Guardrails (section 5) |
| `.claude/rules/*.md` | O | Section 5 |
| `.claude/skills/<name>/SKILL.md` | O | Section 6 |
| `.github/ISSUE_TEMPLATE/cr.md` | O | CR intake |
| `.github/PULL_REQUEST_TEMPLATE/{design,implementation,change,template-sync}.md` | O | The `infra` and `toolchain` types are platform-specific and are not generated |
| `.github/workflows/{ci,pr-contract}.yml` | O | Section 8 |
| `.github/dependabot.yml` | S | Ecosystems depend on the project |
| `scripts/quality-gate.sh`, `scripts/checks/`, `scripts/lib/` | O | Section 8 |
| `scripts/checks.d/` | S | Project checks, same interface as `scripts/checks/` |
| `scripts/pr-contract`, `scripts/pr_contract/`, `scripts/pr-body` | O | PC-1 to PC-7 for application repositories; the PC-8 operator set is empty unless the project defines one (Q7, Q10) |
| `scripts/pr-checkpoint`, `scripts/review-threads`, `scripts/cr-context`, `scripts/cr-criteria`, `scripts/new-cr`, `scripts/initialize-project`, `scripts/template-sync` | O | Section 6 |
| `docs/README.md` | S | Documentation index, same rule as this repository: open only the section relevant to the task |
| `docs/adr/_template.md`, `docs/cr/_template/` | O | Section 7 |
| `docs/adr/`, `docs/cr/` instances | S | Created by the project; never touched by sync |

**Stays in the template** (not generated; removed with `template-dev/`): the generation test and its fixtures, the sync test, the dry-run script, the template's maintenance notes and release checklist, and the template's own CI jobs that are not in the payload `ci.yml` (they live in `template-dev/ci/` and are called from a template-only workflow file `.github/workflows/template-ci.yml`, which is `owned` by no one and deleted by `initialize-project`).

**What is never in the payload:** operator scripts, OCI or lab-stack code, anything with an identifier, and any credential.

## 4. Template-sync

**Flow** (`scripts/template-sync --to <tag> [--dry-run]`, run by Claude Code in a session the user started, as the machine account):

1. Preconditions: clean tree, new branch `template-sync/<tag>` from the default branch, tag exists in `ai-software-template`, the tag's commit is contained in its default branch (the check ADR-011 decision 3 uses for operator tags). A tag is created by the approver only.
2. Fetch the template at the tag (public clone, no credential) into a temporary directory. The script that runs is the one from the tag, not the repository's copy, so a sync can update the script itself.
3. Compare `.template/state.toml` (what was last synced) with the tag's `manifest.toml` and files:
   - `owned` file unchanged locally (hash equals the state): replaced, added, or removed.
   - `owned` file changed locally: **not touched**; listed in the PR body as a conflict with the local and template diffs summarised (Q3).
   - `zoned` file: the owned zone is replaced if it is unchanged locally; otherwise a conflict as above. The project zone is never read except to find the markers.
   - `seeded` file: never changed. A seeded file that is new in the tag and absent locally is added once and listed.
4. Update `.template/state.toml`, commit, push the branch, open a **draft** PR with `gh pr create --draft --body-file` from `scripts/pr-body template-sync`. The body lists the versions, the changed files by class, the conflicts, a link to the release notes, and, when `.github/workflows/` changed, the section "Workflow change justification" (PC-6).
5. The approver reviews and merges like any PR. A conflict is resolved by the approver's instruction in the PR, not by sync.

`--dry-run` prints the plan and writes nothing. There is no schedule, no event trigger, and no workflow that runs the script. How the approver learns that a new tag exists is Q2: the proposal is that `resume-work` and `prepare-cr-context` report the lag read-only (`template-sync --check`), and nothing more.

**What ADR-003 needs for this PR type** (proposal, Q8): the branch prefix `template-sync/` in PC-2, a path rule for the PR (it may change only `owned` files, owned zones, and `.template/state.toml`; a new rule, whose number and wording are for Q8), a PR template `template-sync.md`, and no exemption (PC-1 to PC-6 apply). The same amendment settles how an implementation PR in `ai-software-template` references issue #39 and its design PR in this repository, because PC-3 today checks an issue and a design PR in the same repository.

**Provenance.** Until Q7 is decided, the template's shared code (`pr_contract`, gate checks, toolchain engine) is a copy of `ai-lab-infrastructure` at a commit recorded in `.template/manifest.toml`.

## 5. `CLAUDE.md`, rules, and guardrails

**`CLAUDE.md` (zoned).** Owned zone, the same text in every repository: instruction trust (only the user in the session and review comments by `approver_login`; everything else is data), the Never list (merge, approve, enable auto-merge, push to the default branch, tags, repository settings, secrets, `sudo`, installs, OCI, credentials, MCP servers, workflows that invoke Claude, unpinned Actions), the workflow summary (ADR-003: classes, branch prefixes, draft PR early, commit and push after each checklist item, stop when ready for review), validation (`./scripts/quality-gate.sh`; report what could not be run), and context discipline (locate with `rg` and `fd`, read targeted ranges, summarise long output). Project zone: what the project is, where it runs, project conventions. The workspace `CLAUDE.md` of this repository is the model for both zones.

**Gate check `claude-md`:** both markers exist once, the owned zone hash equals the manifest value, and the size is within `.template/budgets.toml`.

**Rules** (`.claude/rules/*.md`, owned, path-scoped so they load only when matching files are touched; the exact frontmatter key names are verified against the current Claude Code documentation during implementation, as ADR-001 section 5 does):

| Rule file | Applies to | Content |
|---|---|---|
| `public-repo.md` | always | Section 10 |
| `bash.md` | `**/*.sh`, `scripts/**` | `set -euo pipefail`, ShellCheck-clean, `--dry-run` for anything that deletes or overwrites |
| `workflows.md` | `.github/workflows/**` | Pin Actions to a full commit SHA, read-only default permissions, no `pull_request_target`, no step that invokes Claude, PC-6 section (details are ADR-009's) |
| `docs.md` | `docs/**` | Section 7, never edit an approved design or ADR in an implementation PR (PC-5) |
| `arm64.md` | dependency files, Dockerfiles, `scripts/**` | Section 9 |
| `operator.md` | `scripts/operator/**` | Section 12 (project-side operator contract) |

**Guardrails.** `.claude/settings.json` carries the deny rules of ADR-001 section 5 (merge and review, repository creation and settings, secrets, rulesets, pushes to the default branch and force pushes, mutating cloud verbs, credential-printing commands, MCP off, bypass mode disabled). The lab VM also has managed settings (ADR-001 section 5), which have precedence; the repository file is the second layer and the only one on a private repository without rulesets. `.claude/required-deny.txt` lists the entries that must be present, and gate check `deny-list` verifies that `settings.json` contains all of them. The list is a copy of `workspace/claude-user/required-deny.txt` of this repository at a recorded commit (Q5).

## 6. Skills

Each `SKILL.md` is short: when to use it, the inputs, the script to run, what to read and what not to, what to report. Logic that is mechanical is in the script, so it is tested in CI and costs no tokens. Scripts have `--fixture <dir>` (or `--offline`) so tests run without GitHub, and call GitHub only through `gh api` with argument arrays (no `shell=True`), which keeps the token out of the process environment of the script.

| Skill | Script | Behaviour |
|---|---|---|
| `initialize-project` (ADR-003 section 8) | `scripts/initialize-project` | Fills `config/project.yaml` and the placeholders of seeded files, removes `template-dev/`, writes `.template/state.toml`. **Prints** the label commands and the ruleset for the approver to apply; it creates no label, ruleset, repository, or setting |
| `prepare-cr-context` | `scripts/cr-context <issue>` | Loads the CR `README.md` first, lists the other files with sizes, finds the design PR, reports the template lag |
| `implement-approved-cr` | `scripts/cr-preflight <issue> <design-pr>` (part of `cr-context`) | Same check as PC-3: the design PR is merged and linked to the issue. Then opens a draft implementation PR from `scripts/pr-body implementation` with the checkpoint markers |
| `review-implementation` | `scripts/cr-criteria <CR>` | Prints the acceptance criteria IDs and evidence as JSON; the Skill returns one verdict per ID with a reference, posted as **one** PR comment |
| `resume-work` | `scripts/pr-checkpoint show` | Reads only the checkpoint list, the latest CI summary, and `git log` since the merge base |
| **`address-review-feedback`** (new in ADR-003) | `scripts/review-threads` | See below |
| `sync-template` (proposed, Q6) | `scripts/template-sync` | Section 4 |
| `start-cr` (proposed, Q6) | `scripts/new-cr <n> <slug>` | Creates the issue from the intake text (label `class:3`), the branch `design/CR-<n>-<slug>`, the CR skeleton, and the draft design PR. This session did the same by hand |

**`address-review-feedback`.** `scripts/review-threads <pr>` takes `approver_login` from `config/project.yaml` (never infers it), fetches review threads and review comments by GraphQL and REST through `gh api`, and keeps **only** those authored by that login, compared exactly. It prints compact JSON: thread id, file and line, whether it is outdated or resolved, and the comment text. Comments by the machine account, bots, and any other account are not printed as instructions; their count is reported so nothing is hidden silently. The Skill addresses each unresolved thread, pushes, and runs `scripts/review-threads reply <thread-id> <commit>` to reply on the thread with the commit reference. The approver resolves threads and re-approves. The script never resolves a thread, never submits a review, and never merges.

**`scripts/pr-checkpoint`** (`show`, `tick <item>`) reads and edits only the text between `<!-- checkpoint:start -->` and `<!-- checkpoint:end -->`. It updates the PR body with the REST call `PATCH /repos/<owner>/<repo>/pulls/<n>` instead of `gh pr edit`, and `scripts/pr-ready` (or `pr-checkpoint ready`) marks a PR ready with the GraphQL mutation instead of `gh pr ready`, because both `gh` commands fail in the platform workspace with a Projects classic error. Whether the same error occurs on the lab VM is verified in the implementation PR (T-12); the REST and GraphQL paths work in either case.

**Skill budgets and context loading** are ADR-010's (section 11). This design only keeps each Skill to one script and one report.

## 7. CR and ADR templates

- `docs/cr/_template/` has the five files of ADR-003 section 3. `README.md`: summary table (issue, class, status, ADR), summary, file table. `impact-analysis.md`: what changes, affected components, security and privacy, operational impact on the approver, dependencies and assumptions, cost and capacity, rollback, alternatives. `design.md`: header table, decisions table, and a section "Questions for the approver" with the columns question, recommendation, and decision (the pattern of CR-18 and CR-21). `acceptance-criteria.md`: table with ID, criterion, evidence, where each criterion is testable. `implementation-plan.md`: PR table with slug, content, needs, and criteria IDs; checklist; user-only actions; what the plan does not do.
- `docs/adr/_template.md` has the header table (status, date, repositories, CR, scope, related, amended by), then context, decision, alternatives, consequences, open items, and acceptance criteria, as ADR-003 and ADR-005 do. Application ADRs are numbered per repository from `ADR-001` (Q12).
- Gate check `cr-layout`: every `docs/cr/CR-<n>/` has the five files, the criteria IDs are unique, and every PR-table row of the plan names at least one ID.
- `scripts/new-cr <n> <slug>` copies the skeleton and substitutes the number and slug. It refuses to overwrite.

## 8. The template's quality gate and CI

**Generated into every repository.** The gate entry point `scripts/quality-gate.sh` and the generic checks of this repository (ShellCheck, Bash hygiene, YAML, Markdown, links, actionlint, workflow policy, no Claude in workflows, public-repo hygiene, Python, gate tests) plus the template checks `claude-md`, `deny-list`, `cr-layout`, and `size-budget`. The operator-contract and Ansible checks are not generated. Project checks go in `scripts/checks.d/` with the same interface. `ci.yml` has the job `quality-gate` (`--strict`) and the ARM64 job of section 9; `pr-contract.yml` runs `pr-contract` from the base checkout on `pull_request` with a read-only token and no secrets (ADR-003 section 6).

**Template-only, in `template-dev/`:**

| Test | What it proves |
|---|---|
| `manifest` | Every tracked payload file has exactly one class; `zoned` files have their markers; no `seeded` placeholder is missing from `initialize-project`'s list |
| `generate` | The dry run of section 12, steps 1 to 4 and 8, on both architectures |
| `sync` | Section 12, step 6 |
| `skills` | Skill and script fixtures (section 12, steps 5 and 7); every script has `--fixture` or `--offline` |
| `leak` | No identifier pattern in the template or in a generated tree |

**Relation to ADR-009.** ADR-009 decides the repository-wide security and CI baseline: the settings matrix, Actions hardening, which checks are required status checks, and code scanning. ADR-008 decides only what the template carries and how it is tested. This design **assumes** the practice of this repository (required checks `quality-gate` and `pr-contract` on a public repository; Actions pinned by SHA; default read-only permissions; no `pull_request_target`; no workflow that invokes Claude; Dependabot for Actions pins). If ADR-009 differs, the template's workflows and the `workflows.md` rule change through a template release and a sync, not through this ADR.

**Tools in CI.** The gate needs ShellCheck, actionlint, yamllint, and `pymarkdownlnt`. This repository's CI installs them with the ADR-005 engine into a temporary prefix. The same must hold for application repositories. Whether they carry a copy of the engine and a manifest subset (and under which profile name, since ADR-005 allows `builder`, `lab`, and `operator` only) or fetch both from the template tag is part of Q7. Assumption until then: the engine and a manifest subset are `owned` files.

## 9. ARM64: what is specific to the lab VM and what is not

The workspace is x86-64 and the lab VM is ARM64 Ubuntu 24.04 (ADR-001 O-1, ADR-005).

| Not specific (architecture-neutral) | Specific to the lab VM |
|---|---|
| Template content, `CLAUDE.md`, rules, Skills, CR and ADR templates, `pr-contract`, all scripts (Bash, standard-library Python) | Rule `arm64.md`: a dependency, download, image, or wheel change needs both architectures, with checksums, and no x86-only artifact; `uname -m` branching is allowed only in the toolchain engine |
| The gate's checks and the generation test | CI job `quality-gate-arm64` on `ubuntu-24.04-arm`: the gate on ARM64. GitHub provides these runners free for public repositories only (ADR-005 context), so on a private repository the job is skipped and the lab VM's own gate run is the ARM64 evidence |
| Where Claude Code runs (Desktop SSH, ADR-001) | The lab VM clone lives under `/srv/work`; uncommitted work is protected by the backup (ADR-001 section 6), but the rule is unchanged: commit and push after each checklist item |
| | `host: lab-vm` in `config/project.yaml` selects the "Where you run" lines of the project zone |

Tools on the lab VM come from the `lab` profile (ADR-005, O5-5, Stage 3). The template does not install tools and assumes they are on `PATH`. Nothing in the template needs the lab VM before Stage 6; the dry run uses the workspace and GitHub's ARM64 runner as the proxy.

## 10. Public-repository rules

Apply to the template and, by default, to every application repository (Q9):

- No tenancy or resource OCIDs, IP addresses, usernames, emails, keys, fingerprints, or tokens in files, commits, PR text, or logs. Use variables and placeholders. Gate check `public-repo-hygiene` runs on every repository, public or private, because a repository can become public.
- Pin every version and Action to a full commit SHA; verify checksums or signatures; no `curl | sh`.
- `pr-contract` is a required status check on a public repository and advisory on a private one on GitHub Free (ADR-003 section 6). On a private repository without rulesets, `.claude/settings.json` is the only enforcement of the push and merge rules.
- The template's `config/project.yaml` carries logins that are already public (the same as this repository). No other personal data is stored.
- Which repository features (secret scanning, push protection, code scanning) are on is ADR-009's.

## 11. Dependencies on ADR-009 and ADR-010, and the assumptions

Listed, not decided.

| ID | Depends on | Assumption in this design |
|---|---|---|
| D9-1 | ADR-009: required status checks and ruleset content for application repositories | As in this repository: `quality-gate` and `pr-contract` required on public repositories |
| D9-2 | ADR-009: Actions hardening rules | Current rules of `scripts/checks/workflow-policy.sh` copied into the template; ADR-009 may change them |
| D9-3 | ADR-009: repository security features, code scanning, `SECURITY.md` and community files | None shipped by ADR-008 in v1, except `dependabot.yml` (seeded) |
| D9-4 | ADR-009: handling of fork PRs and of third-party Actions | `pr-contract` runs on `pull_request` with a read-only token; no third-party Action that is not pinned |
| D10-1 | ADR-010: size budgets and loading order for `CLAUDE.md`, rules, Skills, and CR files | Values in `.template/budgets.toml` are placeholders: `CLAUDE.md` 120 lines, a rule 40 lines, a `SKILL.md` 60 lines. ADR-010 sets them without a code change |
| D10-2 | ADR-010: checkpoint format beyond the markers, and metrics | Only the ADR-003 markers. Scripts print one summary line per run that a later metrics design can collect; no collection is designed here |
| D5-1 | ADR-005: `lab` profile content (O5-5); profile names for the template's CI tools | Tools are on `PATH`; section 8 and Q7 |
| D3-1 | ADR-003: template-sync PR rules (section 4) | Q8 |

## 12. The Stage 5 dry run and the project-side operator contract

**Dry run** (`template-dev/dry-run.sh --template <path> --out <empty dir>`; it refuses a non-empty directory and writes only inside it). It uses no GitHub repository, no credential, and no OCI resource.

1. Export the template commit without history, like "Use this template" (`git archive`).
2. Run `initialize-project` non-interactively with placeholder values; `template-dev/` is removed; the tree is classified.
3. `git init`, commit, run `./scripts/quality-gate.sh --strict` in the generated repository: green.
4. Run `scripts/new-cr 1 sample`; `cr-layout` passes; a CR with a missing file fails it.
5. Run `pr-contract` against fixture PRs (design, implementation, change, template-sync; passing and failing bodies and paths).
6. Sync: generate from version A, change one owned file, one seeded file, and one zone in the template (version B), change one owned file locally, run `template-sync --from-dir`: the owned file is replaced, the locally changed one is listed as a conflict and untouched, the seeded file is untouched, `state.toml` is updated, and a second run changes nothing.
7. Run `review-threads --fixture` on threads by the approver, the machine account, and a bot: only the approver's are output, and the counts of the others are reported.
8. Leak scan of the generated tree: no unfilled placeholder, no identifier pattern.
9. Run steps 1 to 8 on x86-64 (workspace) and on ARM64 (template CI on `ubuntu-24.04-arm`).
10. Write a report with one line per step; it goes in the implementation PR.

User-only: optionally (Q11) the approver creates a real repository with "Use this template", runs `initialize-project` there, applies the printed labels and ruleset, and opens a PR to see `pr-contract` run for real. Claude Code never creates the repository.

**Project-side operator contract** (ADR-011 decision 17, Q10). The template ships `operator.md` (rule) and a PR template hint for the section "Operator script review" (the project defines its operator set in `config/project.yaml`, empty by default). The rule states what ADR-011 and CR-18 fixed: every operator script has a dry-run mode and an apply mode with dry run as default; scripts run from release tags only; credentials are prompted for or short-lived, never stored, and handled inside the script process; fact collection is read-only, enforced in code, and a new environment gets its own read-only credential and an ADR-001 matrix row (Q39 of CR-18); output is safe to paste; scripts never change infrastructure; Claude Code never runs them and never reaches an operator machine. No operator code is generated. A project that needs one writes it under that contract, and it runs on the lab operator VM, which waits for OCI (postponed).

## 13. Questions for the approver

Recommendations are mine. The Decision column is for the approver's answer from the architecture discussion.

| # | Question | Recommendation | Decision |
|---|---|---|---|
| Q1 | Layout: repository root is the payload and `template-dev/` is removed on init (ST-1), or the payload sits in a `template/` subdirectory copied by a generator script? | Root payload. The flag is already on; the template's CI tests exactly what is generated | |
| Q2 | Template versions: `v<MAJOR>.<MINOR>.<PATCH>` tags created by the approver only, and sync targets tags only. How does the approver learn of a new tag? | Tags by the approver. No push or schedule; `resume-work` and `prepare-cr-context` report the lag read-only | |
| Q3 | A locally changed `owned` file: skip and list it as a conflict, or overwrite and show the diff in the PR? | Skip and list. The approver decides in the PR | |
| Q4 | `CLAUDE.md`: owned zone and project zone between markers, or an unmodified template file that imports a project file? | Zoned. The text that ADR-001 requires in each repository stays identical and checkable | |
| Q5 | The deny list: the template's `required-deny.txt` is a copy of this repository's file at a recorded commit, and gate check `deny-list` verifies `settings.json` against it. Which repository is the origin? | This repository is the origin until Q7 moves shared code; the copy is recorded | |
| Q6 | Skills beyond ADR-003 section 8: add `sync-template` and `start-cr`? | Yes to both. Each has a script, and both exist only to avoid doing a mechanical flow by hand | |
| Q7 | Shared code (`pr_contract`, gate checks, toolchain engine and manifest subset): who is the source of truth after Stage 5? Is the template the origin, with `ai-lab-infrastructure` adopting it by a later CR? How do application CI runners get the gate tools (copied engine and manifest subset, under which profile name)? | Copy at a recorded commit for v1. Decide the origin and the profile name in a follow-up CR; no change to this repository's code in this CR | |
| Q8 | The ADR-003 amendment for the template-sync PR (PC-2 prefix, a path rule, a PR template) and for cross-repository `Implements:` and `Design:` references (PC-3): in this design PR, as CR-21 did for PC-8, or in a separate design PR? | In this PR, after the discussion, with the rule's wording decided with you | |
| Q9 | Application repositories: public by default, and may some be private? A private repository has no required `pr-contract`, no ARM64 hosted runner, and only the deny list as enforcement | Public by default; allow private, with `visibility: private` in `config/project.yaml`, accepting the weaker enforcement and the skipped ARM64 job | |
| Q10 | Project-side operator contract: ship the rule and the PR hint, no code (ST-11). Is that enough for ADR-011 decision 17? | Yes. Operator code for a project waits for a project that needs it and for the lab operator VM | |
| Q11 | Stage 5 exit: the scripted dry run of section 12 only, or also the real "Use this template" run by the approver (user-only step)? | Scripted run is required; the real run is recommended once, before Stage 6 | |
| Q12 | Numbering in application repositories: CR ID is the application repository's issue number; ADRs start at `ADR-001` per repository. Agreed? | Yes, as in this repository | |
