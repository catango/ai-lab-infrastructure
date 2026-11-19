# ADR-009: Security and CI Baseline: Required Checks, Actions Hardening, Repository Security Features, and the Check Catalogue

| Field | Value |
|---|---|
| Status | **Proposed** (CR-43 design PR; accepted when that PR is merged by the approver) |
| Date | 2026-11-19 |
| Repositories | `ai-lab-infrastructure` (this record), `ai-software-template`, and every application repository generated from it |
| Change request | CR-43 (issue #43) |
| Scope | Required status checks, Actions hardening, repository security features on GitHub Free for public and private repositories, fork pull requests and third-party Actions, the host-reported evidence line, the rulesets printed for a new repository, the gate checks `forbidden-api`, `operator-contract`, and `owned-drift`, the catalogue of gate checks, rule sharing between this repository and the template, and the settings the approver applies by hand. Not ADR-010 (token optimisation, metrics) |
| Related | Baseline v0.1 sections 3, 6, 7; ADR-001 (section 5, RR-10), ADR-003 (sections 5, 6), ADR-005 (decisions 3, 7), ADR-008 (decisions 6, 9, 10), ADR-011 (decision 3), ADR-010 (reserved; dependencies in design section 13) |

> This ADR records a decision. It does not create or change a repository, a label, a ruleset, a workflow, a setting, a secret, or a tag, and it does not authorize any of them.
> Detail, rationale, the facts read from GitHub's documentation, and the questions for the approver are in `docs/cr/CR-43/design.md`. Amendments to accepted records are **proposed** there (section 14) and are not part of this record until the approver decides them.

---

## 1. Context

- Baseline Stage 5 (software template) needs ADR-008, ADR-009, and ADR-010 approved. ADR-008 lists its dependencies on this record as D9-1 to D9-4 and D9-6 to D9-8 (CR-39 design section 11).
- GitHub Free offers different features for public and private repositories: rulesets, secret scanning, push protection, and code scanning are available on public repositories only (design section 5).
- A pull request can change the workflow that reports its own check, and a fork PR runs the workflow file of the PR. A required check is therefore evidence, and the approver's review stays the authority (ADR-003 section 5).

## 2. Decision

1. **Required status checks** are `pr-contract` and `quality-gate`, from GitHub Actions. `quality-gate` is an aggregate job that needs the matrix jobs `quality-gate-<arch>` and fails unless each succeeded. A required job always runs: no `paths` filter, no job-level skip, no `continue-on-error`. They are required by the branch ruleset on a public repository. On a private repository on GitHub Free they are advisory and the approver confirms them before each merge (ADR-001 RR-10).
2. **Actions hardening** is the rule set WP-1 to WP-15 (design section 4), enforced by the `workflow-policy` and `no-claude-in-workflows` checks. Beyond today's rules: no `write` permission, action owners and `runs-on` labels from a configured list, `persist-credentials: false`, a timeout on every job, container images by digest, `inputs.*` as untrusted input, and no cache or artifact action in v1.
3. **Repository Actions settings**: selected actions with GitHub-owned allowed and nothing else, full-SHA pinning required, a read-only default token, no PR creation or approval by Actions, approval of workflow runs from all external contributors, 30-day retention, no self-hosted runner.
4. **Third-party Actions** are not allowed. A new one needs a PR with the workflow change justification and the approver's allowlist entry, in that order.
5. **Fork pull requests** run on `pull_request` only, with a read-only token and no secrets; `pull_request_target` and `workflow_run` are forbidden. The approver reads the workflow diff before approving a fork run.
6. **Repository security features** follow the matrix of design section 5: public repositories have secret scanning, push protection, Dependabot alerts and security updates, private vulnerability reporting, and CodeQL default setup once there is analysable content. A private repository on GitHub Free has Dependabot and the dependency graph only. Every repository has `dependabot.yml` with the `github-actions` ecosystem (gate check `dependabot-config`) and a generic `SECURITY.md` seeded by the template.
7. **Host-reported evidence.** For an architecture with no runner for the repository, the PR body carries one fixed-format line produced by `scripts/gate-evidence` on that host, and a new `pr-contract` rule PC-9 checks its form and that its SHA equals the PR's current head. It is informational evidence that the approver accepts per PR.
8. **Printed rulesets.** `initialize-project` prints `main-protection` (with the required checks) and, where configured, `release-tags` for a public repository, as Console steps and a JSON body, and for a private repository prints that rulesets are not available and the RR-10 note. It creates nothing.
9. **Gate checks of the template.** `forbidden-api` is extended with more endpoint classes and rejects a non-literal `gh api` endpoint. `operator-contract` is inactive only for an explicit empty `operator_paths` and fails closed otherwise. `owned-drift` reads hashes from `.template/state.toml` on the base commit and allows a `uses:`-only drift limited to the SHA and the version comment. None can be removed by an override.
10. **Catalogue.** Every gate check has a `# class:` header: `generic`, `template`, or `platform` (design section 10). The catalogue is the specification of the checks.
11. **Rule sharing without a live link.** This record and the catalogue are the specification; generic checks have the same fixtures in both repositories; rule changes go design PR, template, then this repository; a manual parity script on the workspace compares the generic checks and is not a CI job.
12. **Cost.** The personal account's Actions spending limit is zero, so that metered usage cannot become a cost (zero-cost constraint, baseline section 2).
13. **Settings by hand.** The ordered list of design section 12 is the approver's procedure for a new repository and for the two platform repositories. Claude Code applies none of it.

## 3. Alternatives considered

| Alternative | Outcome | Reason |
|---|---|---|
| Require each `quality-gate-<arch>` by name | Not chosen (Q1) | A change of architectures would need a ruleset edit; the aggregate is stable. Offered to the approver as the alternative |
| Allow verified third-party Actions with SHA pins | Not chosen | A larger surface than the platform needs; a script with a checksum-verified tool covers every current use |
| `pull_request_target` for fork PR checks | Rejected | It runs with write rights in the base context; `pull_request` with a read-only token is enough |
| Reusable workflows or a shared Action from the template | Rejected (CR-39 Q7, Q14) | A live trust edge between repositories |
| A CI job that compares this repository with the template | Rejected | CI fetches no other repository (CR-39 T-14, T-21); the parity script is manual |
| Caches and artifacts in v1 | Deferred | Nothing needs them; a restored cache is unpinned code and an artifact on a public repository is public |
| Require branches to be up to date | Not chosen (Q3) | With re-approval on every push it multiplies approvals for one approver |
| The evidence line typed by hand | Rejected | It would be unverifiable prose; a script prints it from the host's own values |
| Code scanning only after a first alert elsewhere | Not chosen | Public repositories get it free; enabling needs analysable content only |
| OpenSSF Scorecard now | Deferred | Baseline Stage 7 |

## 4. Consequences

- Every workflow in this repository and in the template must satisfy WP-1 to WP-15. Today's workflows already satisfy the new rules in practice; the check makes them rules. Platform jobs that use containers keep their digests.
- A private repository on GitHub Free has no enforced protection and no secret scanning. This is accepted risk RR-10, restated in proposed amendment A3.
- The template gets `SECURITY.md`, `scripts/gate-evidence`, the aggregate job, and the `dependabot-config` check through the CR-39 implementation PRs (design section 15, Q22). This repository follows through to PC-9 with the preset change PR.
- ADR-001, ADR-003, ADR-005, and ADR-008 change only if the approver accepts the amendments of design section 14.
- Stage 5 cannot start until ADR-010 is also approved. This CR delivers ADR-009 only.

## 5. Open items

Listed in `docs/cr/CR-43/design.md` section 16: the live state of the two repositories, the check name of a matrix job, CodeQL languages, the ARM64 private runner, the billing limit wording, the `integration_id`, the preset, adoption of the template's checks, and ADR-010.

## 6. Acceptance criteria

Criteria S-1 to S-19 and their evidence are in `docs/cr/CR-43/acceptance-criteria.md`. Each is verified by a gate check or CI, or by a settings check that the approver runs.
