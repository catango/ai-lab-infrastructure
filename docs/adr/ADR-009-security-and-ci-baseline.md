# ADR-009: Security and CI Baseline: Required Checks, Actions Hardening, Repository Security Features, and the Check Catalogue

| Field | Value |
|---|---|
| Status | **Accepted** (2026-11-20, by the merge of the CR-43 design PR #44 by the approver) |
| Date | 2026-11-19 |
| Repositories | `ai-lab-infrastructure` (this record), `ai-software-template`, and every application repository generated from it |
| Change request | CR-43 (issue #43) |
| Scope | Required status checks, Actions hardening, repository security features on GitHub Free for public and private repositories, fork pull requests and third-party Actions, the host-reported evidence line, the rulesets printed for a new repository, the gate checks `forbidden-api`, `operator-contract`, and `owned-drift`, the catalogue of gate checks, rule sharing between this repository and the template, and the settings the approver applies by hand. Not ADR-010 (token optimisation, metrics) |
| Amends | ADR-001 (B1 note, section 5, RR-10), ADR-003 (section 6, PC-7, PC-9, AC3-8), ADR-005 (section 1 context), ADR-008 (decisions 1, 2, 3, 6, 9, 10), each with an "Amended by" entry, effective when this record is accepted |
| Amended by (CR-57, follow-up R-1) | Proposed, takes effect when R-1 is merged. Status line corrected from Proposed to Accepted (merge of PR #44, 2026-11-20). Decision 11: the manual parity script runs in a session from clones of both repositories. Decision 14: the policy input `operator_endpoints` is added (ADR-011 decision 11). Related row: baseline v0.2 and ADR-012 replace baseline v0.1. No other decision changes |
| Related | Baseline v0.2 sections 3, 6, 7; ADR-012; ADR-001 (section 5, RR-10), ADR-003 (sections 5, 6), ADR-005 (decisions 3, 7), ADR-008 (decisions 6, 9, 10), ADR-011 (decision 3), ADR-010 (reserved; dependencies in design section 13) |

> This ADR records a decision. It does not create or change a repository, a label, a ruleset, a workflow, a setting, a secret, or a tag, and it does not authorize any of them.
> Detail, rationale, the facts read from GitHub's documentation, and the approver's decisions Q1 to Q22 (architecture discussion, 2026-11-19) are in `docs/cr/CR-43/design.md`. The decisions are applied below.

---

## 1. Context

- Baseline Stage 5 (software template) needs ADR-008, ADR-009, and ADR-010 approved. ADR-008 lists its dependencies on this record as D9-1 to D9-4 and D9-6 to D9-8 (CR-39 design section 11).
- GitHub Free offers different features for public and private repositories: rulesets, secret scanning, push protection, and code scanning are available on public repositories only (rulesets on private repositories need a paid plan; design section 5).
- Any user with the Write role, including the machine account, can set a commit status or a check run of any name, change alert states, and bypass push protection through the REST API. A ruleset does not restrict which write user merges an approved PR.
- A pull request can change the workflow that reports its own check, and a fork PR runs the workflow file of the PR. A required check is therefore evidence, and the approver's review stays the authority (ADR-003 section 5).

## 2. Decision

1. **Required status checks** are exactly two in every repository: `pr-contract` and the aggregate `quality-gate`, with GitHub Actions as their source. Never a per-architecture name. `quality-gate` is an aggregate job that needs every other job of `ci.yml` (a matrix job counts once: `needs.<id>.result` is one combined result) and fails unless each is `success`. Each required name is defined by exactly one job in its expected file (SC-21). In the template, `template-ci.yml` has its own aggregate `template-ci`, a third required check in the template only. A required job always runs: no `paths` filter, no job-level skip, no `continue-on-error`. They are required by the branch ruleset on a public repository. On a private repository on GitHub Free, rulesets need a paid plan, so the checks are advisory and the approver confirms them on the PR's head before merging (ADR-001 RR-10). No "branch up to date" requirement, and `allow_update_branch` is off.
2. **Actions hardening** is the rule set WP-1 to WP-16 (design section 4), enforced by `workflow-policy` on a parsed form of each workflow plus a line scan, and by `no-claude-in-workflows`. Beyond today's rules: no `write` permission at all (including `id-token: write`), an allowlist of action repositories (`allowed_actions`, default `actions/checkout`), `runner_labels` for `runs-on`, no `${{` in a `run:` value, `persist-credentials: false`, a timeout on every job, container images by digest, no cache, artifact, or `github-script` action in v1, and one defining job per required check name.
3. **Repository Actions settings**: selected actions with GitHub-owned allowed and nothing else, full-SHA pinning required, a read-only default token, no PR creation or approval by Actions, approval of workflow runs from all external contributors, update-branch suggestion off, 30-day retention, no self-hosted runner. The gate rules on actions and runners are advisory; these settings enforce.
4. **Third-party Actions** are not allowed. A new GitHub-owned Action needs a PR with the workflow change justification, the verification that its SHA is the commit of the named upstream tag, the approver's reading of its source, and the approver's allowlist entry, in that order.
5. **Fork pull requests** run on `pull_request` only, with a read-only token and no secrets; `pull_request_target` and `workflow_run` are forbidden. By default an outside PR is closed without a run; if the approver runs one, they read the diff of every file a workflow executes.
6. **Repository security features** follow the matrix of design section 5: public repositories have secret scanning, push protection, Dependabot alerts and security updates, private vulnerability reporting, and CodeQL default setup (now for the platform repositories, and for an application repository once it has code; not a required check). A private repository on GitHub Free has Dependabot and the dependency graph only. Every repository has `dependabot.yml` with the `github-actions` ecosystem (generic gate check `dependabot-config`). The template seeds a generic `SECURITY.md` and a `.github/CODEOWNERS` with the single line `* @<approver_login>` (template check `codeowners`). Dependabot does not update container digests or manifest checksums.
7. **Host-reported evidence.** For an architecture with no runner for the repository, the PR body carries one fixed-format line produced by `scripts/gate-evidence` on that host, and rule PC-9 checks its form and that its SHA equals the PR's current head. `architectures` is read from the base commit, and the aggregate's summary lists every architecture not run. No metered ARM64 runner is used. The line is informational evidence that the approver accepts per PR.
8. **Printed rulesets.** `initialize-project` prints `main-protection` (no bypass, the two required checks, code-owner review) and `release-tags` (default true for every public repository), as Console steps and a JSON body, and for a private repository prints that rulesets are not available and the RR-10 note. It creates nothing. Break-glass is a temporary disable by the approver, recorded in an issue.
9. **Gate checks of the template.** `forbidden-api` is extended: commit statuses and check runs, alert-state changes, push-protection bypasses, branch protection, secrets and variables, environments, webhooks, deploy keys, Actions permissions and runners, security-feature toggles, releases and tag refs, and `git tag`; every endpoint and GraphQL document is a literal, for any HTTP client. `operator-contract` is inactive only for an explicit empty `operator_paths` and fails closed otherwise. `owned-drift` reads hashes from `.template/state.toml` on the base commit, grants the template-sync and init exemption only on the TC-1 or TC-2 result of `pr-contract`, and allows a `uses:`-only drift limited to the SHA and the version comment. None can be removed by an override.
10. **Catalogue.** Every gate check has a `# class:` header: `generic`, `template`, `platform`, or `project` (design section 10). The catalogue is the specification of the checks.
11. **Rule sharing without a live link.** This record and the catalogue are the specification; generic checks have the same fixtures in both repositories; rule changes go design PR, template, then this repository; a manual parity script, run in a session from clones of both repositories, compares the generic checks and their fixtures, prints the template tag compared, and is not a CI job.
12. **Cost.** No payment method on the personal account and budgets at $0 with usage stopped (Stage 0 runbook Parts 1.2 and 1.3), so that metered usage cannot become a cost (zero-cost constraint, baseline section 2).
13. **Settings by hand.** The ordered list of design section 12 is the approver's procedure for the two platform repositories and for a new application repository. Claude Code applies none of it.
14. **Policy inputs come from the base commit (SC-20).** Every policy input from the configuration (`allowed_actions`, `runner_labels`, `architectures`, `operator_paths`, `operator_endpoints`, `release_tags`) is read from the base commit by the checks that judge a PR, and the policy checks (`workflow-policy`, `no-claude-in-workflows`, `forbidden-api`, `owned-drift`, `operator-contract`, `dependabot-config`) run in the `pr-contract` job from the base checkout against a read-only head checkout. The bootstrap skip of `pr-contract.yml` is removed. `operator_endpoints` lists every host an operator script may call (including `api.github.com`), is read from the base commit, and fails closed when it is missing while `operator_paths` is non-empty (ADR-011 decision 11). A PR cannot widen the policy that judges it.

## 3. Alternatives considered

| Alternative | Outcome | Reason |
|---|---|---|
| Require each `quality-gate-<arch>` by name | Rejected (Q1) | A change of architectures would need a ruleset edit; the aggregate is stable |
| Require the platform jobs by name (`operator-profile`, `toolchain-<arch>`, and so on) | Rejected (Q2) | Several names to keep in step with the workflow; the aggregate needs them and one name is required |
| Allow verified third-party Actions with SHA pins | Not chosen | A larger surface than the platform needs; a script with a checksum-verified tool covers every current use |
| WP-14 as a denylist of cache and artifact actions | Rejected (Q5) | An unlisted action would pass; WP-4's allowlist covers them by default |
| Read policy inputs from the PR head | Rejected (SC-20) | A PR could edit the list that allows its own violation |
| No `CODEOWNERS` | Rejected (Q12) | Without it, approval by the approver is not enforced by the ruleset |
| A metered ARM64 runner on private repositories | Rejected (Q14) | It uses the account's included minutes and is then charged; the evidence line costs nothing |
| `pull_request_target` for fork PR checks | Rejected | It runs with write rights in the base context; `pull_request` with a read-only token is enough |
| Reusable workflows or a shared Action from the template | Rejected (CR-39 Q7, Q14) | A live trust edge between repositories |
| A CI job that compares this repository with the template | Rejected | CI fetches no other repository (CR-39 T-14, T-21); the parity script is manual |
| Caches and artifacts in v1 | Deferred | Nothing needs them; a restored cache is unpinned code and an artifact on a public repository is public |
| Require branches to be up to date | Rejected (Q3) | The update button makes the approver the last pusher and voids the approval |
| The evidence line typed by hand | Rejected | It would be unverifiable prose; a script prints it from the host's own values |
| OpenSSF Scorecard now | Deferred | Baseline Stage 7 |

## 4. Consequences

- Every workflow in this repository and in the template must satisfy WP-1 to WP-16. Today's workflows already satisfy the new rules in practice, except the single required-name rule: the current gate job is renamed `gate` and `quality-gate` becomes the aggregate. The name does not change, so the ruleset needs no edit.
- A private repository on GitHub Free has no enforced protection and no secret scanning. This is accepted risk RR-10, restated in its amended text.
- Approval by the approver is enforced on a public repository through code-owner review. The ruleset does not restrict which write user merges an approved PR; for the machine account the deny rules and `forbidden-api` do.
- The template gets `SECURITY.md`, `CODEOWNERS`, `scripts/gate-evidence`, the aggregate jobs, and the `codeowners` and `dependabot-config` checks through the CR-39 implementation PRs (design section 15, Q22). This repository follows through to PC-9 with the preset change PR.
- ADR-001, ADR-003, ADR-005, and ADR-008 are amended in the CR-43 design PR and the amendments take effect when it merges. PC-9 is enforced once implemented.
- Stage 5 cannot start until ADR-010 is also approved. This CR delivers ADR-009 only.

## 5. Open items

Listed in `docs/cr/CR-43/design.md` section 16: the live state of the two repositories, the `integration_id`, the aggregate on skipped and cancelled jobs, single-owner code-owner review, CodeQL for Actions workflows, fork SHAs, Dependabot and digests, the exact endpoint paths, the preset, adoption of the template's checks, and ADR-010.

## 6. Acceptance criteria

Criteria S-1 to S-23 and their evidence are in `docs/cr/CR-43/acceptance-criteria.md`. Each is verified by a gate check or CI, or by a settings check that the approver runs.
