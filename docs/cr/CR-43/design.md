# CR-43 Design: security and CI baseline (ADR-009)

| Field | Value |
|---|---|
| CR | issue #43 (Class 3) |
| Governing records | Baseline v0.1 (sections 3, 6, 7), ADR-001 (section 5, decisions 3, 4, 8, RR-10), ADR-003 (sections 5, 6), ADR-005 (decisions 3, 7), ADR-008 and CR-39 design (sections 5, 8, 10, 11), the Stage 0 runbook `docs/operations/github-setup.md` |
| Record produced | [ADR-009](../../adr/ADR-009-security-and-ci-baseline.md), status Proposed. Amended in this PR: [ADR-001](../../adr/ADR-001-trust-model-and-execution.md) (A3), [ADR-003](../../adr/ADR-003-pr-centric-workflow.md) (A1), [ADR-005](../../adr/ADR-005-toolchain.md) (A4), and [ADR-008](../../adr/ADR-008-software-template.md) (A2), each with an "Amended by" entry |
| Scope | Design only. Nothing is implemented. No setting, ruleset, secret, variable, collaborator, workflow, or tag changes, and the `ai-software-template` repository is not touched |
| State | The approver's decisions Q1 to Q22 and the new decisions SC-20 and SC-21 (architecture discussion, review on PR #44, 2026-11-19) are applied in this file, in ADR-009, and in the other CR-43 files. Section 15 records them. Section 16 lists what stays open |

## 1. Scope and boundaries

In scope: the dependencies D9-1 to D9-4 and D9-6 to D9-8 of [CR-39 design section 11](../CR-39/design.md) (D9-5 was withdrawn there), the catalogue of quality-gate checks, how this repository and the template share rules without a live link (CR-39 decision Q7), and the settings the approver applies by hand. The OpenSSF Scorecard is a later item (baseline Stage 7) and is only mentioned in section 16.

Out of scope: ADR-010 (token optimisation, metrics). Section 13 lists where ADR-009 depends on it and what it assumes. Also out of scope: implementation, the template's content beyond what ADR-009 constrains, ADR-002's pipeline workflows and environments (Stage 4, postponed), and this platform's preset.

**Facts this design starts from** (as built, from the repository, not from the live settings, which I could not read):

- `ci.yml` has jobs `quality-gate`, `operator-profile`, `operator-limits`, `toolchain` (a matrix whose checks appear as `toolchain-amd64` and `toolchain-arm64`), and `builder-profile`. `pr-contract.yml` has the job `pr-contract` on `pull_request`, with the base commit checked out; it skips with a message when the base has no checker (the bootstrap skip, removed by SC-20). Both set `permissions: {}` at the top and grant read scopes per job.
- `scripts/checks/workflow-policy.sh` forbids a missing top-level `permissions:`, `write-all` and `read-all`, `paths` filters, `pull_request_target`, `workflow_run`, any secret except `GITHUB_TOKEN`, a download piped to a shell, an untrusted expression in a `run:` block, and an action not pinned to a 40-character SHA with a trailing version comment.
- `scripts/operator/github-desired-state.toml` is the wanted state of settings, Actions, security features, and the rulesets `main-protection` and `release-tags`. It has `allow_update_branch = true`, no code-owner review, and no required status checks ("rule types not listed are kept as they are"). Whether the Stage 1 hand-off step that adds required checks was done is **not verified** (section 16).
- `.github/dependabot.yml` has the ecosystems `github-actions` and `pip`, weekly; Dependabot PRs fall under PC-7.
- Any user with the Write role, including the machine account, can set a commit status or a check run of any name through the API, change alert states, and bypass push protection through the REST API. These are not blocked by rulesets (section 5, SC-4, SC-12).

## 2. Decisions in this design

| ID | Decision | Rationale |
|---|---|---|
| SC-1 | The required status checks are `pr-contract` and the aggregate `quality-gate`, from GitHub Actions. Never a per-architecture name. For a matrix job, `needs.<id>.result` is one combined result, so the aggregate needs the job, not its legs | One stable name survives a change of architectures; a ruleset needs no edit when the configuration changes (Q1) |
| SC-2 | The required set is exactly **two names**, `pr-contract` and `quality-gate`, in every repository. Here the current gate job is renamed `gate` and `quality-gate` becomes the aggregate. In the template `template-ci.yml` has its own aggregate `template-ci`, a third required check in the template only. On a **private** repository on GitHub Free, rulesets are available only with a paid plan, so the checks are advisory and the approver confirms them on the PR's head before merging (ADR-001 RR-10) | Q2; the name `quality-gate` does not change here, so no ruleset edit |
| SC-3 | A required job always runs and always reports: no `paths` filter, no job-level `if:` that can skip it, no `continue-on-error`, no `workflow_run`. The aggregate runs `if: always()` and fails on `failure`, `cancelled`, and `skipped` of any needed job | GitHub reports a skipped job as success (section 3) |
| SC-4 | The check source is pinned to GitHub Actions, because any write user can set a commit status of any name. Commit statuses and check runs are `forbidden-api` classes. No "branch up to date" requirement, and `allow_update_branch` is off, because "Update branch" would make the approver the last pusher under the last-push rule | Q3, Q4 |
| SC-5 | Actions hardening rules WP-1 to WP-16 (section 4), enforced by `workflow-policy` on a parsed form of each workflow plus a line scan for text patterns. No `write` permission at all, including `id-token: write` (ADR-002 amends at Stage 4). WP-4 is an allowlist of action repositories | Q5, Q8 |
| SC-6 | Allowed Actions are GitHub-owned only. The gate rule is advisory; the Actions allowlist setting and the absence of self-hosted runners enforce. Before a new pin, the SHA is verified as the commit of the named upstream tag and recorded in the PR; the approver's reading of the source is the authority | Q6, Q7 |
| SC-7 | Fork PRs: CI and `pr-contract` on `pull_request` only, read-only token, no secrets; approval of workflow runs for all external contributors. By default an outside PR is closed without a run; if the approver runs one, they read the diff of every file a workflow executes | Q9 |
| SC-8 | The security-feature matrix of section 5. CodeQL default setup is on now for this repository and the template, and for an application repository once it has code; it is not a required check | Q11 |
| SC-9 | The template seeds `SECURITY.md` and `.github/CODEOWNERS` with the single line `* @<approver_login>` from the configuration. `main-protection` requires code-owner review, so approval by the approver is enforced. New check `codeowners` (class template); `public-repo-hygiene` accepts that one line only. No `CONTRIBUTING` or code of conduct; the licence is per repository | Q12 |
| SC-10 | **Evidence line** for an architecture with no hosted runner: one fixed-format line produced by a script on that host, checked by rule PC-9, which reads `architectures` from the base commit. The aggregate's summary lists every architecture not run. No metered ARM64 runner is used | Q14, section 7 |
| SC-11 | `initialize-project` prints the ruleset bodies of section 8 (public) or the RR-10 note (private) and creates nothing. `main-protection` has no bypass, the two required checks, and code-owner review; `release-tags` is printed for every public repository unless `release_tags: false` | Q15 |
| SC-12 | `forbidden-api` is confirmed and extended with commit statuses and check runs, alert-state changes, push-protection bypasses, and the classes of section 9. Every endpoint and GraphQL document is a literal, for any HTTP client | Q16 |
| SC-13 | `operator-contract` is confirmed; it is inactive only for an explicit empty `operator_paths`, read from the base commit, and fails on a missing or malformed key | Q18 |
| SC-14 | `owned-drift` reads hashes from `.template/state.toml` on the base commit. The template-sync and init exemption needs `pr-contract`'s TC-1 or TC-2 result, not the branch name. A `uses:`-only bump that is not by Dependabot records the SC-6 tag check | Q17 |
| SC-15 | Every gate check carries a header `# class: generic`, `template`, `platform`, or `project`, and the catalogue of section 10 is the specification. `dependabot-config` is generic; `codeowners` is template | Q13 |
| SC-16 | Rules are shared without a live link: ADR-009 and the catalogue are the specification, both repositories run the same fixtures for generic checks, and a manual parity script on the workspace compares the copies and the fixtures and prints the template tag compared. It is not part of CI | Q19 |
| SC-17 | The settings the approver applies by hand are an ordered list with a read-only check per step (section 12) | Section 12 |
| SC-18 | No payment method and budgets at $0 with usage stopped (Stage 0 runbook Parts 1.2 and 1.3), so that metered usage cannot become a cost | The zero-cost constraint |
| SC-19 | A required check is evidence, not authority. Approval (ADR-003 section 5) stays the authority, and the approver reads a PR that changes a workflow | A PR can change the workflow that reports its own check |
| SC-20 | Every policy input from the configuration (`allowed_actions`, `runner_labels`, `architectures`, `operator_paths`, `release_tags`) is read from the **base commit** by the checks that judge a PR, and the policy checks run in `pr-contract` from the base checkout. A PR cannot widen the policy that judges it | A PR can otherwise edit the list that allows its own violation |
| SC-21 | Each required check name is defined by exactly one job in its expected file. Here `quality-gate` needs every other job of `ci.yml` | A second job with a required name would let a PR satisfy the check |

## 3. Required status checks (D9-1)

**Names.** `pr-contract` is the job of `pr-contract.yml`. `quality-gate` is the aggregate job of `ci.yml`: it `needs` every other job of the file, runs `if: always()`, and has one step that fails unless `needs.<job>.result` is `success` for each. For a matrix job, `needs.<id>.result` is **one combined result** for all its legs: it is `success` only if every leg succeeded, so the aggregate lists the job, not `quality-gate-<arch>`. The ruleset requires `pr-contract` and `quality-gate` with the source GitHub Actions (the REST field is `integration_id`; the value for the Actions app is read from the live ruleset, not from memory).

| Repository | Jobs of `ci.yml` | Required checks | Enforced by |
|---|---|---|---|
| This repository (public) | `gate` (renamed), `operator-profile`, `operator-limits`, `toolchain` (matrix), `builder-profile`, and the aggregate `quality-gate` | `pr-contract`, `quality-gate` | Ruleset `main-protection`. Platform jobs are required through the aggregate and are not required by name |
| `ai-software-template` (public) | Matrix `quality-gate-<arch>` and the aggregate `quality-gate`; `template-ci.yml` has its jobs and the aggregate `template-ci` | `pr-contract`, `quality-gate`, and `template-ci` (template only) | Ruleset |
| Application repository, public | Matrix `quality-gate-<arch>` and the aggregate `quality-gate` | `pr-contract`, `quality-gate` | Ruleset printed by `initialize-project` (section 8) |
| Application repository, private (GitHub Free) | Same | None enforceable | The approver confirms the two names green on the PR's head before merging (SC-2, RR-10) |

**Rules that keep the names honest.** GitHub documents that a skipped job "will report its status as 'Success'" and does not block a merge (SC-3). The aggregate therefore fails on `skipped` and `cancelled` as well. A job that is genuinely not run for an architecture is not skipped: it runs on a base runner and writes `not run: <arch>` (section 7). **SC-21 and WP-16:** each required name is defined by exactly one job; a second job named `quality-gate` or `pr-contract` in any workflow fails `workflow-policy`. Because the check source is pinned to GitHub Actions (SC-4), a commit status or an external app cannot supply the name. **Observed, not documented:** the checks of this design PR list the matrix job as `toolchain-amd64` and `toolchain-arm64`, its expanded `name`. **Not verified:** how a `paths` filter interacts with a required check (`workflow-policy` forbids the filter), and how the aggregate behaves on a skipped, cancelled, or not-run job (S-2, S-23 verify it).

**Up-to-date branches.** The ruleset does not require "branches up to date", and `allow_update_branch` is off (SC-4). The "Update branch" button makes the approver the last pusher, which under "approval of the most recent reviewable push" would void the approval from the approver's own click.

## 4. Actions hardening (D9-2)

### 4.1 Workflow rules

"Today" is `scripts/checks/workflow-policy.sh` and `workflow-policy.awk` as read. IDs WP-n are new names for the rules; the mapping to the check's current messages is kept in the implementation. The line scan keeps the text patterns; **WP-10 to WP-13 and WP-16, and the `cache:` input part of WP-14, are checked on a parsed form** of the workflow (for example `yq -o=json` and the Python `json` module), because they depend on structure.

| ID | Rule | Today |
|---|---|---|
| WP-1 | Top-level `permissions: {}` and a per-job grant of read scopes only. `write-all` and `read-all` are forbidden | Yes |
| WP-2 | **No `write` permission** in any workflow, job, or step in v1, including `id-token: write` (ADR-002 amends it at Stage 4) | New |
| WP-3 | Every `uses:` is pinned to a full 40-character SHA with a trailing version comment | Yes |
| WP-4 | Every `uses:` is an action repository in the configured allowlist `allowed_actions` (default `actions/checkout`); a local `./` action is allowed. The list also enforces WP-14: it excludes `actions/cache/*`, the artifact actions, and `actions/github-script` | New |
| WP-5 | No `pull_request_target` and no `workflow_run` | Yes |
| WP-6 | No secret except `secrets.GITHUB_TOKEN`; also no `toJSON(secrets)` and no `secrets[`. No repository, organization, or environment secret in v1 | Partly |
| WP-7 | No `paths` or `paths-ignore` on a trigger | Yes |
| WP-8 | **No `${{` anywhere in a `run:` value**; pass every value through `env:`. This covers `github.event.*`, `github.head_ref`, `inputs.*`, `toJSON(github.event)`, and `github['event']` | Partly (the current rule names `github.event.*` and `github.head_ref`) |
| WP-9 | No download piped to a shell | Yes |
| WP-10 | `actions/checkout` has `persist-credentials: false` | New (every workflow already does it) |
| WP-11 | Every job has `timeout-minutes` | New (every job already has it) |
| WP-12 | A `container:` or `services:` image is pinned by digest (`@sha256:`) | New (the two container jobs already are) |
| WP-13 | `runs-on` is a literal from the configured list `runner_labels`, or a matrix value from that list; arrays, `group:`, and matrix values are all checked; no self-hosted label | New |
| WP-14 | No `actions/cache`, no `cache:` input of an `actions/setup-*` action, no `actions/upload-artifact` or `actions/download-artifact`, and no `actions/github-script` in v1 | New |
| WP-15 | No workflow invokes Claude (ADR-003, CHG-003) | Yes (`no-claude-in-workflows`) |
| WP-16 | Each required check name (`pr-contract`, `quality-gate`, and in the template `template-ci`) is defined by exactly one job across all workflows, in its expected file | New |

**Caches and artifacts (WP-14).** A restored cache is code that nobody pinned, and an uploaded artifact on a public repository is public until it expires. The gate installs checksum-verified tools into a temporary prefix and reports through the job summary. Job summaries are public on a public repository: scripts print counts and names, never identifiers. A later need (for example ADR-010 metrics) amends WP-14 with a retention and content rule.

**Policy inputs come from the base commit (SC-20).** `allowed_actions`, `runner_labels`, `architectures`, `operator_paths`, and `release_tags` are read by the checks from the base commit. The gate rule on `uses:` and `runs-on` is **advisory**: the Actions allowlist setting and the absence of self-hosted runners are what enforce (SC-6). Verified once per repository by S-4.

**What no static check can see** and is left to the approver's review (SC-19): a value written to `GITHUB_ENV` or `GITHUB_PATH` from untrusted input, a script called by a step that does something unsafe, and a workflow change that makes its own required check pass. PC-6 requires the "Workflow change justification" section so that the approver reads those diffs. SC-20 narrows this: the policy checks run from the base checkout in the `pr-contract` job (section 6), so a PR that weakens `workflow-policy` and adds a violation still fails.

### 4.2 Repository Actions settings (as built here, stated for every repository)

| Setting | Value | Applies to |
|---|---|---|
| Actions permissions | Selected actions: GitHub-owned allowed (`github_owned_allowed` stays on, for CodeQL); Marketplace verified creators **not** allowed; allowlist patterns empty | All |
| Require actions to be pinned to a full-length commit SHA | On (`sha_pinning_required`) | All |
| Workflow permissions (default `GITHUB_TOKEN`) | Read repository contents and packages | All |
| Allow GitHub Actions to create and approve pull requests | Off (GitHub's default for a new personal repository) | All |
| Approval for running fork pull request workflows from contributors | **Require approval for all external contributors** | Public |
| Fork pull request workflows (private repositories): run workflows from fork PRs, send write tokens, send secrets | All off or left unset (labels as listed on GitHub's page; **not verified in the interface**) | Private |
| Always suggest updating pull request branches (`allow_update_branch`) | **Off** (SC-4); the desired state here still has `true` | All |
| Artifact and log retention | 30 days | All |
| Self-hosted runners | None registered | All |
| Allow auto-merge | Off | All |

## 5. Repository security features on GitHub Free (D9-3)

Verified by reading GitHub's documentation on 2026-11-19 (personal account, GitHub Free). "Could not verify" means that the pages read did not state it; nothing here was tested on a live repository.

| Feature | Public repository | Private repository | Wanted | Set by |
|---|---|---|---|---|
| Secret scanning alerts | Yes (free) | **No.** Secret Protection is sold to Team and Enterprise plans | On for public | `github-setup` (`secret_scanning`) |
| Push protection | Yes. **A write user can bypass it through the REST API** (SC-12 forbids it for scripts and for Claude Code) | **No** | On for public | `github-setup` |
| Dependabot alerts | Yes | Yes | On | `github-setup` (`vulnerability_alerts`) |
| Dependabot security updates | Yes | Yes | On; grouped; PRs are reviewed, never auto-merged | `github-setup` (`automated_security_fixes`); grouping manual |
| Dependabot version updates (`dependabot.yml`) | Yes | Yes | `github-actions` ecosystem in every repository; others by project. Dependabot does **not** update container digests in workflows or the checksums of the toolchain manifest | Seeded `.github/dependabot.yml`; gate check `dependabot-config` (generic, SC-15) |
| Dependency graph | Yes | Yes | On | Default; confirm |
| Code scanning (CodeQL, default setup) | Yes | **No** | **On now** for this repository and the template; on for an application repository once it has code. Not a required check. Language support for Actions workflows is **not verified** | Manual |
| Private vulnerability reporting | Yes | Could not verify (documented for public repositories only) | On for public | `github-setup` |
| Dependency review action | Yes | **No** | Not in v1 | Later (section 16) |
| `SECURITY.md` and `.github/CODEOWNERS` | Yes | Yes | Seeded in the template (SC-9); this repository gets both by PR 3 | Template; this repository by a change |
| Artifact attestations | Yes | **No** | Not in v1 | Later |
| Rulesets and required status checks | Yes (as built here) | **Not available.** Documented as paid-plan only: the plans page lists protected branches for Pro and Team, and the rulesets page says rulesets apply to Team and Enterprise plans | Public: yes. Private: none | Section 8 |
| Community health files other than the above | Could not verify | Could not verify | None shipped | n/a |

Sources (read 2026-11-19): `docs.github.com/en/code-security/getting-started/github-security-features`, `.../get-started/learning-about-github/githubs-plans`, `.../code-security/concepts/secret-security/about-secret-scanning`, `.../code-security/concepts/supply-chain-security/dependabot-alerts`, `.../dependabot-security-updates`, `.../dependency-review`, `.../actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations`, and the rulesets and protected-branches pages.

**Consequence for a private repository on Free.** No rulesets, no secret scanning, no push protection, and no code scanning. The compensation is limited: the gate's `public-repo-hygiene` (identifier and token patterns, which also runs on private repositories), `forbidden-api`, and the procedural list of section 12. This is the text of RR-10 as amended (A3).

**Hosted ARM64 runners on private repositories.** The documentation lists `ubuntu-24.04-arm` among the standard runners for private repositories. It uses the account's included minutes (the plans page gives "$12 USD of included compute usage per month" for GitHub Free) and is charged afterwards (read 2026-11-19; **not verified by a run**). This platform does not use it (Q14): the evidence line of section 7 stays, and SC-18 keeps the account at no payment method and $0 budgets. A4 records the correction of the ADR-005 context line.

## 6. Fork PRs and third-party Actions (D9-4)

- **Fork PRs.** `pr-contract.yml` and the gate run on `pull_request` only. For a fork, GitHub runs it with a read-only `GITHUB_TOKEN` and no secrets (verified in the Actions settings documentation). `pull_request_target` and `workflow_run` are forbidden (WP-5).
- **Policy checks run from the base (SC-20).** The `pr-contract` job checks out the **base** commit and runs, from it, `pr-contract` and the policy checks `workflow-policy`, `no-claude-in-workflows`, `forbidden-api`, `owned-drift`, `operator-contract`, and `dependabot-config` against a **read-only checkout of the PR head** in a separate directory (no credentials persisted). A PR cannot replace the checkers or widen the policy inputs that judge it. The bootstrap skip in `pr-contract.yml` ("no checker on the base branch yet") is removed: a missing checker on the base is a failure. The full gate still runs in `quality-gate` on the head.
- **Approval of fork runs (Q9).** The setting stays "Require approval for all external contributors". The default is that an outside PR is closed without a run. If the approver does run one, they read the diff of **every file a workflow executes**, not only the workflow files, because the PR's own scripts run in the job. This is a user-only step (section 12, U-11).
- **Residual risk (SC-19).** A PR can change `pr-contract.yml` so that its own check passes; the base-checkout design narrows this to the workflow file itself, which PC-6 flags. Merge needs the approver's approving review (ADR-003 section 5) and PC-6 requires the justification section, so the human reads that diff. A required check never replaces that.
- **`address-review-feedback`** already refuses fork PRs and PRs not authored by the machine account (ADR-008).
- **Third-party Actions.** The allowlist holds GitHub-owned Actions only, `verified_allowed` stays off, `patterns_allowed` stays empty, and WP-4 mirrors it in the gate as an advisory rule (SC-6). A new Action needs, in this order: (1) a PR that adds the pinned `uses:` line, a PC-6 section naming the repository, the SHA and version, why a script with a checksum-verified tool cannot do it, the permissions it needs, and **the verification that the SHA is the commit of the named upstream tag** (a read-only API call, recorded in the PR); (2) the approver's reading of the source of the pinned version, which is the authority; (3) the approver's allowlist entry; (4) the merge. The CI of the PR fails until step 3, which is intended. No reusable workflow from another repository (CR-39 D9-5 stays withdrawn). The same tag check is recorded for any `uses:`-only bump that is not by Dependabot (SC-14). Dependabot keeps the pins current (PC-7).
- **Containers.** An image is pinned by digest (WP-12) and comes from a registry the repository already trusts (the two current jobs use `debian` and `ubuntu`). Dependabot does not update these digests; a digest change is a reviewed PR.

## 7. Host-reported evidence for an architecture with no hosted runner (D9-6)

**When.** A repository whose configuration lists an architecture for which no runner label is available to that repository: `architectures` carries per architecture a `runner` for a public repository and a `runner_private` for a private one (empty by default, because no metered ARM64 runner is used, Q14). `pr-contract` reads `architectures` from the base commit (SC-20) and the repository's `private` flag from the API. The CI matrix runs the job for such an architecture on a base runner, and the job writes `not run: <arch>` to its summary instead of running the gate. The **aggregate's summary lists every architecture that was not run**, so the reviewer sees it in one place.

**What the line contains.** One line in the PR-body section "Architecture evidence" of the change and implementation templates, produced by a script on the host, never typed:

```text
evidence: <arch> | <machine> | <os> | <40-hex head SHA> | clean | <gate command> | exit 0 | <UTC time>
```

The script is `scripts/gate-evidence <arch>`: it runs `./scripts/quality-gate.sh --strict` on the host, then prints the line from the host's own values (`git rev-parse HEAD`, `git status --porcelain`, `uname -m`, `/etc/os-release`). No host name, address, user, or path.

**How it is checked.** Rule **PC-9** in `pr-contract` (A1): for each architecture that has no runner for this repository, the body of a change or implementation PR has a line of that format with the arch field equal to it, the SHA equal to the **current head SHA of the PR**, `clean`, the command equal to the gate, and `exit 0`. A design PR (docs only) and a Dependabot PR (PC-7) are exempt. The check re-runs on `edited`, so the evidence is refreshed by editing the body after a push.

**What it does not prove.** It proves the form and the SHA, not that the command ran. It is informational evidence that the approver accepts or rejects per PR (CR-39 D9-6).

## 8. Branch and tag rulesets printed by `initialize-project` (D9-7)

Content equals this repository's rulesets in `github-desired-state.toml` plus the required checks and code-owner review.

| Ruleset | Target | Rules | Bypass |
|---|---|---|---|
| `main-protection` (public repository) | Default branch | No deletion; linear history; no force push; pull request with one approval, **code-owner review required**, stale approvals dismissed on push, approval of the most recent reviewable push, conversation resolution, merge method squash only; **required status checks** `pr-contract` and `quality-gate` from GitHub Actions, not strict (`template-ci` as well in the template) | None, including the approver |
| `release-tags` | Tags `v*` | No creation, update, or deletion; no force push | Repository admin role, mode always (only the approver creates tags) |
| Private repository | n/a | **Not printed.** The output says that rulesets are not available on GitHub Free for private repositories, repeats the RR-10 note, and prints the procedural list of section 12 | n/a |

`release_tags` defaults to **true** (Q15): `release-tags` is printed for every public repository unless the configuration sets `release_tags: false`. For each ruleset the output has the Console steps and a JSON body for `POST /repos/{owner}/{repo}/rulesets` that the approver applies from their own terminal or from the operator machine; the template's test compares the JSON with a golden file derived from the rulesets of this repository. `initialize-project` calls no write API (ADR-008 decision 3).

**Break-glass.** To change `main` without a machine-account PR, the approver temporarily disables the ruleset, makes the change, and re-enables it, recording the reason in an issue (runbook A.4). No bypass actor is added.

**Consequence the approver accepted (Q15).** With code-owner review, the ruleset makes approval by the approver enforced. It does **not** restrict which write user merges an approved PR. For the machine account that is blocked by the ADR-001 section 5 deny rules and the template's `forbidden-api` only, and a push after approval dismisses the approval (A3, B1 note). A machine-account approval on a Dependabot PR does not satisfy the code-owner rule (S-3).

**Order** (section 12): the tag ruleset exists before the first tag; the branch ruleset is applied after the settings and **before the init PR merges**. If the required checks cannot be added before a first run, `main-protection` is applied without them and the checks are added after the first green run of the init PR, then checked (S-3). Which is needed is verified in the real run (CR-39 T-16 (b)).

## 9. The three template gate checks (D9-8)

| Check | Confirmed | Extension or constraint (this ADR) |
|---|---|---|
| `forbidden-api` | Rejects, in every script, the REST calls and GraphQL mutations for merge, review submission, auto-merge, rulesets, collaborators, and repository settings (ADR-008 decision 6) | **Extended (SC-12)** with these classes: **commit statuses and check runs**; **code-scanning, secret-scanning, and Dependabot alert state changes**; **push-protection bypasses**; branch protection; repository and organization secrets and variables; environments; webhooks; deploy keys; Actions permissions and runner registration; the security-feature toggles (`vulnerability-alerts`, `automated-security-fixes`, private vulnerability reporting, code-scanning default setup); release creation and tag refs; `gh release`, `gh repo`, `gh secret`, `gh variable`, `gh ruleset`; `git tag` and `git push --tags`. **Constraint:** every endpoint and every GraphQL document is a string literal in the script, for any HTTP client (`gh api`, `curl`, `urllib`); a variable or a built string fails, and `-f query=@file` is allowed only if that file is scanned too. The writes that scripts need stay allowed by name: create and update a PR, post a comment, create an issue, and the GraphQL `markPullRequestReadyForReview`. **Exact endpoint paths are verified in the implementation** |
| `operator-contract` | A generic check on `operator_paths`, inactive when the list is empty | **Constrained (SC-13):** `operator_paths` is read from the base commit; inactive only for an explicit empty list; a missing, non-list, or unreadable key fails closed. The forbidden-pattern list is owned by the template; a platform adds allowed subprocesses through the configuration, never by editing the check |
| `owned-drift` | Fails a PR that changes an owned file without an `overrides.toml` entry | **Constrained (SC-14):** hashes are read from `.template/state.toml` on the **base** commit, so a PR cannot hide a change by editing `state.toml`. The template-sync and init exemption needs the **TC-1 or TC-2 result of `pr-contract`**, not the branch name. A `uses:` change is allowed when, before and after, the line is `uses: <same owner/repo>@<40-hex> # v<version>` and nothing else in the file changed; a bump that is not by Dependabot records the tag check of SC-6. **This closes the CR-39 open item** |

All three stay in the gate of every generated repository, run from the base checkout in `pr-contract` (SC-20), and are not removable by an override. Their fixtures are criteria S-11 to S-13 and S-20 to S-21.

## 10. Catalogue of quality-gate checks

The class is the header `# class:` of the check (SC-15). **generic**: no platform value, identical in every repository, seeded once into the template from this repository (CR-39 ST-8). **template**: exists because a repository is generated from the template. **platform**: only this platform. Today's ids are the files of `scripts/checks/`.

| Check | Class | What it checks | Runs in |
|---|---|---|---|
| `bash-hygiene`, `shellcheck`, `yaml`, `markdown`, `links`, `actionlint`, `python`, `gate-tests` | generic | Shell, YAML, Markdown, link, workflow-syntax, and Python hygiene; the gate's own fixtures | Both repositories now; every generated repository |
| `public-repo-hygiene` | generic | No identifier, address, email, key, fingerprint, or token pattern; runs for private repositories too. It accepts the single seeded `CODEOWNERS` line and nothing else of that form | Same |
| `workflow-policy` | generic | WP-1 to WP-16 (section 4), with `allowed_actions` and `runner_labels` from the configuration, read from the base commit | Same; also from the base in `pr-contract` |
| `no-claude-in-workflows` | generic | WP-15 | Same |
| `toolchain` | generic (profile names are data) | Every manifest download has both architectures and checksums (ADR-005 decision 3) | Same; the template checks its CI manifest |
| `dependabot-config` | **generic** | `.github/dependabot.yml` exists, has the `github-actions` ecosystem, and has no `open-pull-requests-limit: 0`. It cannot see that Dependabot does not update container digests or manifest checksums (section 5) | Same; also from the base in `pr-contract` |
| `claude-md`, `deny-list`, `cr-layout`, `size-budget` | template | CR-39 sections 5 to 7 and 11 | The template and every generated repository; this repository on adoption |
| `codeowners` | template (new) | `.github/CODEOWNERS` exists and is exactly the one line `* @<approver_login>` for the configured approver | Same |
| `forbidden-api`, `owned-drift`, `operator-contract` (generic version) | template | Section 9 | Same; also from the base in `pr-contract` |
| `ansible` | platform | Ansible syntax and lint of the profile playbooks | This repository |
| `operator-contract` (current version) | platform | The checks of `operator_contract.py` for `scripts/operator/` | This repository; replaced by the generic version on adoption |
| Template jobs `manifest`, `generate`, `sync`, `skills`, `leak` | template-only | CR-39 section 8 | `template-ci.yml` (aggregate `template-ci`), removed on generation |
| Platform CI jobs `operator-profile`, `operator-limits`, `builder-profile`, `toolchain` (matrix) | platform | Apply and verify the profiles | This repository, through the aggregate `quality-gate` |

Every check in the gate runs with `--strict` in CI (a missing tool fails). Project checks go in `scripts/checks.d/` with the same interface and the class `project`.

## 11. How the two repositories share the rules without a live link (CR-39 Q7)

1. **Specification.** ADR-009 and the catalogue (section 10) state each rule and each check's behaviour. They are the single place a rule is stated.
2. **Same fixtures.** Every generic check has the same fixture set in both repositories (`tests/quality-gate/` here; the template's own gate tests). A fixture is added to both when a rule changes.
3. **Order of change.** A rule change is a design PR here (amends ADR-009), then an implementation PR in the template (the origin of generic code after seeding), then a PR here that copies the template's check. A repository that is already generated receives it by template-sync.
4. **Parity script (manual, Q19).** `scripts/checks-parity <path-to-template-clone>` in this repository prints, for every generic check, whether the two files have the same SHA-256, **also hashes the fixtures**, **prints the template tag it compared**, and fails if one is missing or differs. It is run by Claude Code on the workspace with a local clone of the template at a release tag, outputs counts and paths only, and its result goes in the PR body of each PR that changes a generic check. It is **not** a CI job: CI fetches no other repository (CR-39 T-14, T-21). `template-dev/provenance.toml` records the seed commit as history only.
5. **Adoption.** Whether this repository later replaces its copies with the template's output is a later CR (CR-39 section 14). Until then the parity script is how drift is seen.

## 12. The settings the approver applies by hand (SC-17)

Ordered. Claude Code never applies, and never runs `github-setup`, which is an operator script (CLAUDE.md). "Check" is a read-only step that the approver runs and records in the PR or CR. Interface wording and paths are as in the runbook's appendix A.1 to A.4 for the platform repositories.

**Platform repositories (this repository and the template).**

| Step | Action | Check |
|---|---|---|
| U-0 | Already done in Stage 0: no payment method and budgets at $0 with usage stopped (runbook Parts 1.2 and 1.3). Re-read once | S-17 |
| U-A1 | **Now.** Run the `github-setup` dry run and `facts --scope github` on the platform operator VM and compare every value with sections 3, 4.2, and 5. Read by hand the required checks and their source (not in the desired state yet) | S-3 to S-5 |
| U-A2 | **Now.** Turn "Always suggest updating pull request branches" off in both repositories (the desired state follows with PR 6) | S-4 |
| U-A3 | **Now.** Enable CodeQL default setup on this repository and the template, and read the languages offered (Python and GitHub Actions workflows if GitHub offers them) | S-5 |
| U-7a | **After PR 2b's first green run.** Confirm that the required checks are exactly `pr-contract` and `quality-gate` from GitHub Actions; remove any separately required platform job names | S-3 |
| U-7b | **After PR 3 merges** (`CODEOWNERS` exists): turn on "Require review from Code Owners" in `main-protection` | S-3 |
| U-A4 | **After PR 6 merges:** run the `github-setup` dry run again | S-4 |

**Application repositories** (U-1 to U-12; the template's real run, CR-39 T-16 (b), is the first use).

| Step | Action | Check |
|---|---|---|
| U-1 | "Use this template" with the configured visibility | Repository exists; template flag off |
| U-2 | Add the machine account as collaborator (Write) and accept the invitation; update the AC1-1 allowlist | `facts` lists it with push and no admin |
| U-3 | General settings of A.1: squash only, no auto-merge, delete head branches, **update branch off** | S-4 |
| U-4 | Actions settings of section 4.2 (selected actions, SHA pinning, read token, no PR approval, fork approval, retention) | S-4 |
| U-5 | Security features of section 5 (public: secret scanning, push protection, Dependabot alerts and security updates, private vulnerability reporting) | S-5 |
| U-6 | Tag ruleset `release-tags` (default for a public repository), **before** the first tag | S-3 negative test: creating a tag as the machine account is rejected |
| U-7 | Branch ruleset `main-protection` from the printed JSON (two required checks, code-owner review), **before the init PR merges**; if the checks cannot be added earlier, after their first green run | S-3: the names equal those of a green run; a failing check blocks the merge; a machine-account approval on a Dependabot PR does not satisfy the code-owner rule |
| U-8 | Run the init PR through review and merge it | `pr-contract` and `quality-gate` green |
| U-9 | After the first code merge on a public repository: enable CodeQL default setup | Alerts page shows it enabled |
| U-10 | A new third-party Action is proposed: do the steps of section 6 in order; add the allowlist entry only after reading the source | CI of the PR turns green |
| U-11 | An outside PR: close it without a run; if a run is wanted, read the diff of every file a workflow executes, then approve | n/a |
| U-12 | A private repository: record the RR-10 note and confirm the two checks and the evidence lines on the head before each merge | n/a (S-16) |

## 13. Dependencies on ADR-010 and the assumptions

Listed, not decided. ADR-010 is a separate CR.

| ID | Depends on | Assumption in this design |
|---|---|---|
| E-1 | ADR-010: size budgets for `CLAUDE.md`, rules, and Skills | The `size-budget` check reads `.template/budgets.toml`; ADR-009 fixes no value |
| E-2 | ADR-010: metrics | The gate prints one summary line per check (name, status, seconds) and nothing more; ADR-009 decides no metric and no storage |
| E-3 | ADR-010 | If metrics need an artifact or a cache, ADR-010 amends WP-14 with a content and retention rule. ADR-009 assumes they do not |
| E-4 | ADR-010: loading order | None. `size-budget` is part of the gate inside the required `quality-gate`, so a budget breach blocks a merge on a public repository |

## 14. Amendments to accepted records (applied in this PR, Q21)

Applied with the approver's final text, each with an "Amended by" entry on the existing row (ADR-008 has none and gets one; ADR-005 gets its own row "Amended by (context)"). They take effect when this PR is merged.

| Record | Change |
|---|---|
| A1: [ADR-003](../../adr/ADR-003-pr-centric-workflow.md) | Header entry; section 6 "PC-1 to PC-9"; the two required names, GitHub Actions as source, and the private-repository wording; PC-7 exempts PC-9 too; new PC-9 (evidence line); new AC3-8 |
| A2: [ADR-008](../../adr/ADR-008-software-template.md) | New header row; decisions 1 (`SECURITY.md`, `CODEOWNERS`, `gate-evidence`), 2 (`owned-drift` base hashes and the TC-1 or TC-2 exemption), 3 (printed rulesets), 6 (`forbidden-api` classes and literals), 9 (aggregate `quality-gate`, `template-ci`), 10 (private flag, PC-9) |
| A3: [ADR-001](../../adr/ADR-001-trust-model-and-execution.md) | Header entry; B1 note (the ruleset does not restrict which write user merges an approved PR); section 5 deny row for commit statuses, check runs, alert states, and push-protection bypasses, with the pointer to ADR-009 decision 9; RR-10 text for private repositories |
| A4: [ADR-005](../../adr/ADR-005-toolchain.md) | New header row "Amended by (context)"; section 1 ARM64 bullet: private-repository runner documented as metered; this platform does not use it |

## 15. Decisions of the approver (architecture discussion, 2026-11-19)

Recorded from the approver's review on PR #44. Wording is condensed; each decision is applied in the section named.

| # | Decision | Applied in |
|---|---|---|
| Q1 | Required checks are `pr-contract` and the aggregate `quality-gate`; never per-architecture names. Each required name is defined by exactly one job across all workflows (WP-16, SC-21). For a matrix job `needs.<id>.result` is one combined result | SC-1, SC-21, WP-16, section 3 |
| Q2 | The required set is exactly those two in every repository. Here: the current gate job is renamed `gate`; `quality-gate` becomes the aggregate needing `gate`, `operator-profile`, `operator-limits`, `toolchain`, `builder-profile` (the name is unchanged, so no ruleset edit). The template's `template-ci.yml` has its own aggregate `template-ci`, a third required check in the template only | SC-2, section 3, plan |
| Q3 | No "up to date" requirement. `allow_update_branch` off, because "Update branch" would make the approver the last pusher | SC-4, sections 3, 4.2 |
| Q4 | Check source pinned to GitHub Actions, because any write user can set a commit status of any name. Commit statuses and check runs join the `forbidden-api` classes | SC-4, SC-12, section 9 |
| Q5 | No `write` permission, including `id-token: write`. WP-4 is an allowlist of action repositories (`allowed_actions`, default `actions/checkout`); it also enforces WP-14 | SC-5, WP-2, WP-4, WP-14 |
| Q6 | Allowed actions and runner labels are read from the base commit. The gate rule is advisory; the Actions allowlist setting and no self-hosted runners enforce. WP-13 covers arrays, `group:`, and matrix values | SC-6, SC-20, WP-13 |
| Q7 | GitHub-owned Actions only. Before a new pin, verify that the SHA is the commit of the named upstream tag (read-only API call) and record it in the PR. The approver's reading of the source is the authority | SC-6, section 6 |
| Q8 | WP-8: no `${{` anywhere in a `run:` value. WP-6 also forbids `toJSON(secrets)` and `secrets[`. WP-10 to WP-13 and WP-16 are checked on a parsed form; the line scan keeps text patterns only | SC-5, section 4.1 |
| Q9 | Fork approval stays "all external contributors". Default: an outside PR is closed without a run; if run, the approver reads the diff of every file a workflow executes | SC-7, section 6 |
| Q10 | SC-19 kept. The policy checks also run in the `pr-contract` job from the base checkout against a read-only head checkout. The bootstrap skip in `pr-contract.yml` is removed | SC-19, SC-20, section 6 |
| Q11 | CodeQL default setup on now for this repository and the template, and for application repositories once they have code. Not a required check. `github_owned_allowed` stays on | SC-8, section 5 |
| Q12 | Template seeds `SECURITY.md` and `.github/CODEOWNERS` (`* @<approver_login>`). `main-protection` requires code-owner review. New check `codeowners` (template); `public-repo-hygiene` accepts that one line only. No `CONTRIBUTING` or code of conduct; licence per repository | SC-9, sections 5, 8, 10 |
| Q13 | `dependabot-config` is **generic**; it also fails `open-pull-requests-limit: 0`. The gap is stated: Dependabot does not update container digests or manifest checksums | SC-15, sections 5, 10 |
| Q14 | No metered ARM64 runner; the evidence line stays. PC-9 reads `architectures` from the base commit. The aggregate's summary lists every architecture not run. SC-18 and U-0 reference runbook Parts 1.2 and 1.3 | SC-10, SC-18, section 7 |
| Q15 | `main-protection`: no bypass, the two required checks, code-owner review. `release-tags` by default for every public repository. Break-glass by temporary disable, recorded in an issue. The ruleset does not restrict which write user merges an approved PR | SC-11, section 8 |
| Q16 | `forbidden-api` adds commit statuses and check runs, alert-state changes, and push-protection bypasses. Every endpoint and GraphQL document is a literal for any HTTP client | SC-12, section 9 |
| Q17 | `owned-drift`: base hashes; the exemption needs the TC-1 or TC-2 result; a `uses:`-only bump not by Dependabot records the Q7 tag check. Closes the CR-39 open item | SC-14, section 9 |
| Q18 | `operator-contract` fails closed; `operator_paths` from the base commit | SC-13, section 9 |
| Q19 | Manual parity script, no CI link; it also hashes fixtures and prints the template tag compared | SC-16, section 11 |
| Q20 | `github-setup` for application repositories later. Plan PR 6 adds to the platform desired state `required_status_checks` (source GitHub Actions), `require_code_owner_review = true`, and `allow_update_branch = false` | Plan |
| Q21 | A1 to A4 accepted with the approver's text and applied in this PR | Section 14 |
| Q22 | Template work rides in the CR-39 PRs ("Also verifies CR-43 criteria"). The last CR-43 PR here lists them as `<owner>/ai-software-template#<n>` and closes #43 only after they merge | Plan |
| SC-20 | New. Every policy input from the configuration is read from the base commit by the checks that judge a PR, and the policy checks run in `pr-contract` from the base checkout. ADR-009 decision 14 | SC-20, ADR-009 |
| SC-21 | New. Each required check name is defined by exactly one job in its expected file; here `quality-gate` needs every other job of `ci.yml` | SC-21, ADR-009 |

## 16. Still open

| Item | Who decides | When |
|---|---|---|
| The live state of both repositories: the required checks and their source, the code-scanning state, the settings of section 4.2. I could not read them; the `github-setup` dry run and `facts --scope github` show most of it, and the required checks are read by hand | Approver | Section 12, U-A1, before the implementation PRs |
| The `integration_id` of the GitHub Actions app for the ruleset JSON | Claude Code | Read from the live ruleset in the implementation PR |
| How the aggregate `quality-gate` behaves on skipped, cancelled, and not-run jobs | Claude Code and approver | First CI run of PR 2b (S-2, S-23) |
| Whether code-owner review with a single owner behaves as intended (the approver is the only code owner and the only approver, and the machine account authors the PRs) | Approver | After PR 3 (U-7b) |
| CodeQL support for GitHub Actions workflows on a personal Free account | Approver | When enabling (U-A3) |
| Whether fork SHAs resolve through the parent repository in the head checkout, and whether the SHA allowlist patterns work for them | Claude Code and approver | PR 2b |
| Dependabot and `container:` digests: confirm that Dependabot leaves them alone, and the process for a digest bump | Claude Code | PR 2a |
| Exact endpoint paths and GraphQL documents for `forbidden-api` | Claude Code | The template PR with `forbidden-api` |
| The private fork-PR setting labels in the interface | Approver | Only if a private repository is created |
| This repository's follow-through to ADR-003 as amended (CR-39 section 14), including PC-9 and the keys `architectures`, `allowed_actions`, `runner_labels`, `release_tags` | Approver | The preset change PR |
| Whether this repository adopts the template's generic checks | Approver | A later CR |
| OpenSSF Scorecard, dependency review, artifact attestations | Approver | Later; the Scorecard is baseline Stage 7 |
| ADR-010 | Approver | A separate CR. Stage 5 entry needs ADR-008, ADR-009, and ADR-010 |
