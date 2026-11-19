# CR-43 Design: security and CI baseline (ADR-009)

| Field | Value |
|---|---|
| CR | issue #43 (Class 3) |
| Governing records | Baseline v0.1 (sections 3, 6, 7), ADR-001 (section 5, decisions 3, 4, 8, RR-10), ADR-003 (sections 5, 6), ADR-005 (decisions 3, 7), ADR-008 and CR-39 design (sections 5, 8, 10, 11), the Stage 0 runbook `docs/operations/github-setup.md` |
| Record produced | [ADR-009](../../adr/ADR-009-security-and-ci-baseline.md), status Proposed |
| Scope | Design only. Nothing is implemented. No setting, ruleset, secret, variable, collaborator, workflow, or tag changes, and the `ai-software-template` repository is not touched |
| State | Draft for the architecture discussion. Every open point is a question for the approver (section 15). Accepted records are **not** edited: proposed amendments are drafted in section 14 |

## 1. Scope and boundaries

In scope: the dependencies D9-1 to D9-4 and D9-6 to D9-8 of [CR-39 design section 11](../CR-39/design.md) (D9-5 was withdrawn there), the catalogue of quality-gate checks, how this repository and the template share rules without a live link (CR-39 decision Q7), and the settings the approver applies by hand. The OpenSSF Scorecard is a later item (baseline Stage 7) and is only mentioned in section 16.

Out of scope: ADR-010 (token optimisation, metrics). Section 13 lists where ADR-009 depends on it and what it assumes. Also out of scope: implementation, the template's content beyond what ADR-009 constrains, ADR-002's pipeline workflows and environments (Stage 4, postponed), and this platform's preset.

**Facts this design starts from** (as built, from the repository, not from the live settings, which I could not read):

- `ci.yml` has jobs `quality-gate`, `operator-profile`, `operator-limits`, `toolchain-<arch>` (matrix, `ubuntu-24.04` and `ubuntu-24.04-arm`), and `builder-profile`. `pr-contract.yml` has the job `pr-contract` on `pull_request`, with the base commit checked out. Both set `permissions: {}` at the top and grant `contents: read` (and read scopes) per job.
- `scripts/checks/workflow-policy.sh` forbids a missing top-level `permissions:`, `write-all` and `read-all`, `paths` filters, `pull_request_target`, `workflow_run`, any secret except `GITHUB_TOKEN`, a download piped to a shell, an untrusted expression in a `run:` block, and an action not pinned to a 40-character SHA with a trailing version comment.
- `scripts/operator/github-desired-state.toml` is the wanted state of settings, Actions, security features, and the rulesets `main-protection` and `release-tags`. Required status checks are **not** in it ("rule types not listed are kept as they are"). ADR-003 section 6 says `pr-contract` is a required status check on a public repository; whether the Stage 1 hand-off step that adds `pr-contract` and `quality-gate` was done is **not verified** (section 16).
- `.github/dependabot.yml` has the ecosystems `github-actions` and `pip`, weekly; Dependabot PRs fall under PC-7.

## 2. Decisions in this design

| ID | Decision | Rationale |
|---|---|---|
| SC-1 | The required status checks are `pr-contract` and `quality-gate`. `quality-gate` is the **aggregate** job; the matrix jobs `quality-gate-<arch>` are its `needs`, and the aggregate fails unless every matrix job succeeded. The check source is pinned to GitHub Actions | One stable name survives a change of architectures; a ruleset needs no edit when the configuration changes (Q1) |
| SC-2 | Required checks are enforceable only where GitHub enforces rulesets. A public repository gets them as a ruleset rule. On a **private** repository on GitHub Free they are advisory and the approver checks the three names by hand before merging (ADR-001 RR-10) | Section 5 and ADR-003 section 6 |
| SC-3 | A required job always runs and always reports: no `paths` filter, no job-level `if:` that can skip it, no `continue-on-error`, no `workflow_run` | GitHub reports a skipped job as success (section 3) |
| SC-4 | Actions hardening rules WP-1 to WP-14 (section 4), enforced by `workflow-policy` and fixtures. New rules over today: no `write` permission, action owners from a configured list, `persist-credentials: false`, job timeouts, container images by digest, `runs-on` from a configured list, no cache or artifact actions, `inputs.*` as untrusted | Section 4 |
| SC-5 | Actions repository settings: this repository's Stage 0 values, with SHA pinning required and the fork approval at "all external contributors" (section 4) | Already built here; stated once for every repository |
| SC-6 | Allowed Actions are GitHub-owned only. A new third-party Action needs a design-level justification in the PR (PC-6) and the approver's allowlist entry, in that order | The smallest supply-chain surface (section 6) |
| SC-7 | Fork PRs: `pr-contract` and CI on `pull_request` only, read-only token, no secrets; approval of every external contributor's workflow run, after reading the workflow diff | Section 6 |
| SC-8 | The security-feature matrix of section 5: what is on for a public repository and what a private repository on GitHub Free cannot have | Section 5 |
| SC-9 | The template seeds a generic `SECURITY.md` that names GitHub private vulnerability reporting and no contact data. No other community file is shipped | Q12 |
| SC-10 | **Evidence line** for an architecture with no hosted runner: one fixed-format line produced by a script on that host, checked by a new rule PC-9 against the PR head SHA | Section 7 |
| SC-11 | `initialize-project` prints the ruleset bodies of section 8 (public) or the RR-10 note (private) and creates nothing | Section 8 |
| SC-12 | `forbidden-api` is confirmed and extended: more endpoint classes, and a non-literal `gh api` endpoint fails | Section 9 |
| SC-13 | `operator-contract` is confirmed; it is inactive only for an explicit empty `operator_paths`, and fails on a missing or malformed key | Section 9 |
| SC-14 | `owned-drift` is confirmed and constrained: the hashes are read from `.template/state.toml` **on the base commit**; a `uses:`-only drift is one whose changed lines keep the repository and change only the SHA and the version comment | Section 9 |
| SC-15 | Every gate check carries a header `# class: generic`, `template`, or `platform`, and the catalogue of section 10 is the specification | Section 10 |
| SC-16 | Rules are shared without a live link: ADR-009 and the catalogue are the specification, both repositories run the same fixtures for generic checks, and a manual parity script on the workspace compares the two copies. It is not part of CI | Section 11 |
| SC-17 | The settings the approver applies by hand are an ordered list with a read-only check per step (section 12) | Section 12 |
| SC-18 | The personal account's Actions spending limit is checked to be zero, so that metered usage cannot become a cost | The zero-cost constraint; section 5 |
| SC-19 | A required check is evidence, not authority. Approval (ADR-003 section 5) stays the authority, and a PR that changes a workflow is read by the approver | A PR can change the workflow that reports its own check (section 6) |

## 3. Required status checks (D9-1)

**Names.** `pr-contract` is the job of `pr-contract.yml`. `quality-gate` is a job of `ci.yml` that `needs` the matrix jobs `quality-gate-<arch>` (one per configured architecture, `name: quality-gate-${{ matrix.arch }}`) and runs `if: always()` with one step that fails unless `needs.<job>.result` is `success` for each. The ruleset requires `pr-contract` and `quality-gate` with the source GitHub Actions (the REST field is `integration_id`; the value for the Actions app must be taken from the live ruleset, not from memory).

| Repository | Required checks | Enforced by |
|---|---|---|
| This repository (public) | `pr-contract`, `quality-gate` | Ruleset `main-protection`. The jobs `operator-profile`, `operator-limits`, `toolchain-<arch>`, `builder-profile` are platform jobs; whether they are required is Q2 |
| `ai-software-template` (public) | `pr-contract`, `quality-gate`, and after CR-39 the template jobs `manifest`, `generate`, `sync`, `skills`, `leak` (Q2) | Ruleset |
| Application repository, public | `pr-contract`, `quality-gate` | Ruleset printed by `initialize-project` (section 8) |
| Application repository, private (GitHub Free) | None enforceable | The approver confirms `pr-contract` and `quality-gate` green on the PR's head before merging (SC-2, RR-10) |

**Rules that keep the names honest (SC-3).** GitHub documents that a skipped job "will report its status as 'Success'" and does not block a merge. So a required job has no `if:` that can skip it, and the aggregate runs `always()`. A ruleset that requires a name that never reports blocks every merge: the ordered list in section 12 therefore adds the checks after a first run, or checks the names against a green run first. **Not verified in GitHub's documentation:** that a matrix job's check name is its expanded `name`, and how a `paths` filter interacts with a required check. The acceptance criteria verify the first on a real run (S-3) and `workflow-policy` forbids the second.

**Up-to-date branches.** The ruleset does not require "branches up to date" (Q3 recommends off). With "dismiss stale approvals" and "approval of the most recent reviewable push" on, every branch update is a new push that needs a new approval; an up-to-date requirement would multiply re-approvals for a single approver.

## 4. Actions hardening (D9-2)

### 4.1 Workflow rules

"Today" is `scripts/checks/workflow-policy.sh` and `workflow-policy.awk` as read. IDs WP-n are new names for the rules; the mapping to the check's current messages is kept in the implementation.

| ID | Rule | Today | Enforced by |
|---|---|---|---|
| WP-1 | Top-level `permissions: {}` and a per-job grant of read scopes only. `write-all` and `read-all` are forbidden | Yes | `workflow-policy` |
| WP-2 | **No `write` permission** in any workflow, job, or step in v1 | New | `workflow-policy`. Neither this repository nor the template needs one; a later need amends this ADR |
| WP-3 | Every `uses:` is pinned to a full 40-character SHA with a trailing version comment | Yes | `workflow-policy`; setting `sha_pinning_required` |
| WP-4 | The owner of every `uses:` is in the configured list `allowed_action_owners` (default `actions`); a local `./` action is allowed | New | `workflow-policy`; mirrors the Actions allowlist |
| WP-5 | No `pull_request_target` and no `workflow_run` | Yes | `workflow-policy` |
| WP-6 | No secret except `secrets.GITHUB_TOKEN`; no repository, organization, or environment secret in v1 | Yes ("no secrets in Stage 1") | `workflow-policy`. ADR-002 (Stage 4) introduces environments and decides its own exception |
| WP-7 | No `paths` or `paths-ignore` on a trigger | Yes | `workflow-policy` |
| WP-8 | `github.event.*`, `github.head_ref`, and **`inputs.*`** never appear inside a `run:` value; pass them through `env:` | Partly (`inputs.*` is new) | `workflow-policy` |
| WP-9 | No download piped to a shell | Yes | `workflow-policy` |
| WP-10 | `actions/checkout` has `persist-credentials: false` | New (every workflow already does it) | `workflow-policy` |
| WP-11 | Every job has `timeout-minutes` | New (every job already has it) | `workflow-policy` |
| WP-12 | A `container:` or `services:` image is pinned by digest (`@sha256:`) | New (the two container jobs already are) | `workflow-policy` |
| WP-13 | `runs-on` is a literal from the configured list `runner_labels`, or `${{ matrix.runner }}` whose values come from that list; no self-hosted label | New | `workflow-policy`. A self-hosted runner on a public repository is a remote-code-execution path for any fork PR |
| WP-14 | No `actions/cache`, `actions/upload-artifact`, or `actions/download-artifact` in v1 | New | `workflow-policy` |
| WP-15 | No workflow invokes Claude (ADR-003, CHG-003) | Yes | `no-claude-in-workflows` |

Cache and artifact rules (WP-14) in one place: **caches** are not used because the gate installs checksum-verified tools into a temporary prefix, and a restored cache is code that nobody pinned; **artifacts** are not uploaded because every workflow reports through the job summary, and an uploaded file in a public repository is public until it expires (30 days here). Job summaries are public on a public repository: scripts print counts and names, never identifiers (the gate's existing rule). A later need (for example ADR-010 metrics) amends WP-14 with a retention and content rule.

**What no static check can see** and is left to the approver's review (SC-19): a value written to `GITHUB_ENV` or `GITHUB_PATH` from untrusted input, a script called by a step that does something unsafe, and a workflow change that makes its own required check pass. PC-6 requires the "Workflow change justification" section so that the approver reads those diffs.

### 4.2 Repository Actions settings (as built here, stated for every repository)

| Setting | Value | Applies to |
|---|---|---|
| Actions permissions | Selected actions: GitHub-owned allowed; Marketplace verified creators **not** allowed; allowlist patterns empty | All |
| Require actions to be pinned to a full-length commit SHA | On (`sha_pinning_required`) | All |
| Workflow permissions (default `GITHUB_TOKEN`) | Read repository contents and packages | All |
| Allow GitHub Actions to create and approve pull requests | Off (GitHub's default for a new personal repository) | All |
| Approval for running fork pull request workflows from contributors | **Require approval for all external contributors** | Public |
| Fork pull request workflows (private repositories): run workflows from fork PRs, send write tokens, send secrets | All off or left unset (names as listed on GitHub's page; **not verified in the interface**) | Private |
| Artifact and log retention | 30 days | All |
| Self-hosted runners | None registered | All |
| Allow auto-merge | Off | All |

## 5. Repository security features on GitHub Free (D9-3)

Verified by reading GitHub's documentation on 2026-11-19 (personal account, GitHub Free). "Could not verify" means that the pages read did not state it; nothing here was tested on a live repository.

| Feature | Public repository | Private repository | Wanted | Set by |
|---|---|---|---|---|
| Secret scanning alerts | Yes (free) | **No.** Secret Protection is sold to Team and Enterprise plans | On for public | `github-setup` (`secret_scanning`) |
| Push protection | Yes | **No** | On for public | `github-setup` |
| Dependabot alerts | Yes | Yes | On | `github-setup` (`vulnerability_alerts`) |
| Dependabot security updates | Yes | Yes | On; grouped; PRs are reviewed, never auto-merged | `github-setup` (`automated_security_fixes`); grouping manual |
| Dependabot version updates (`dependabot.yml`) | Yes | Yes | `github-actions` ecosystem in every repository; others by project | Seeded `.github/dependabot.yml`; new gate check `dependabot-config` (Q13) |
| Dependency graph | Yes | Yes | On | Default; confirm |
| Code scanning (CodeQL, default setup) | Yes | **No** | On for public once there is analysable content (Python and GitHub Actions workflows; **language support not verified here**) | Manual (Q11); the runbook defers it to "after the first code PR" |
| Private vulnerability reporting | Yes | Could not verify (documented for public repositories only) | On for public | `github-setup` |
| Dependency review action | Yes | **No** | Not in v1 | Later (section 16) |
| `SECURITY.md` | Yes | Yes | Seeded in the template (SC-9); present here | Template; this repository by a change PR |
| Artifact attestations | Yes | **No** | Not in v1 | Later |
| Rulesets and required status checks | Yes (as built here) | **Not verified**; the plans page lists protected branches for Pro and Team only, and the rulesets page says rulesets apply to Team and Enterprise plans, which is ambiguous for Free private | Public: yes. Private: treated as **not available** (ADR-003 section 6) | Section 8 |
| Community health files other than `SECURITY.md` | Could not verify | Could not verify | None shipped (Q12) | n/a |

Sources (read 2026-11-19): `docs.github.com/en/code-security/getting-started/github-security-features`, `.../get-started/learning-about-github/githubs-plans`, `.../code-security/concepts/secret-security/about-secret-scanning`, `.../code-security/concepts/supply-chain-security/dependabot-alerts`, `.../dependabot-security-updates`, `.../dependency-review`, `.../actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations`, and the rulesets and protected-branches pages.

**Consequence for a private repository on Free.** No secret scanning, no push protection, no code scanning, and no enforced branch rules. The compensation is limited: the gate's `public-repo-hygiene` (identifier and token patterns, which also runs on private repositories) and the procedural list of section 12. This extends the text of RR-10 (amendment A3).

**Hosted ARM64 runners on private repositories.** The documentation lists `ubuntu-24.04-arm` among the standard runners for private repositories, metered per minute against the included usage (the plans page gives "$12 USD of included compute usage per month" for GitHub Free; the pricing page lists Linux 2-core x64 at $0.006 and arm64 at $0.005 per minute, so about 2,000 and 2,400 minutes, which is my arithmetic, not a stated quota). CR-39 design section 9 and ADR-005's context assume hosted ARM64 runners for public repositories only. This is a correction, not a decision: whether the preset uses a metered runner is Q14, and SC-18 keeps the zero-cost constraint by a zero spending limit. **Not verified by a run.**

## 6. Fork PRs and third-party Actions (D9-4)

- **Fork PRs.** `pr-contract.yml` and the gate run on `pull_request` only. For a fork, GitHub runs it with a read-only `GITHUB_TOKEN` and no secrets (verified in the Actions settings documentation). `pr-contract` reads the PR through the API and runs the checker from the **base** commit, so the PR cannot replace the checker. `pull_request_target` and `workflow_run` are forbidden (WP-5).
- **Approval of fork runs.** On a public repository the setting is "Require approval for all external contributors" (the strictest of the three documented options). The approver reads the PR's workflow diff before approving a run, because for `pull_request` the workflow file of the PR is the one that runs. This is a user-only step (section 12, U-11). The platform does not solicit outside contributions; closing such a PR is always allowed.
- **Residual risk (SC-19).** A fork PR can change `pr-contract.yml` so that its own check passes. Merge needs the approver's approving review (ADR-003 section 5) and PC-6 requires the justification section, so the human reads that diff. A required check never replaces that.
- **`address-review-feedback`** already refuses fork PRs and PRs not authored by the machine account (ADR-008); the CI side adds nothing.
- **Third-party Actions.** The allowlist holds GitHub-owned Actions only, `verified_allowed` stays off, `patterns_allowed` stays empty, and WP-4 mirrors it in the gate. A new Action needs, in this order: (1) a PR that adds the pinned `uses:` line **and** a PC-6 section naming the repository, the SHA and version, why a script with a checksum-verified tool cannot do it, the permissions it needs, and what its source does with them (I read the source of the pinned version before proposing); (2) the approver's allowlist entry in the settings; (3) the merge. The CI of the PR fails until step 2, which is intended. No reusable workflow from another repository (CR-39 D9-5 stays withdrawn). Dependabot keeps the pins current (PC-7).
- **Containers.** An image is pinned by digest (WP-12) and comes from a registry the repository already trusts (the two current jobs use `debian` and `ubuntu`).

## 7. Host-reported evidence for an architecture with no hosted runner (D9-6)

**When.** A repository whose configuration lists an architecture for which no runner label is available to that repository: `architectures` carries per architecture a `runner` for a public repository and a `runner_private` for a private one (may be empty). The CI matrix runs the job `quality-gate-<arch>` on a base runner and the job writes `not run: <arch>` to its summary instead of the gate (SC-1: the aggregate then treats that result as success; the summary and the PR section are the record).

**What the line contains.** One line in the PR-body section "Architecture evidence" of the change and implementation templates, produced by a script on the host, never typed:

```text
evidence: <arch> | <uname -m> | <os id and version> | <40-hex head SHA> | <clean or dirty> | <command> | exit <n> | <UTC time>
```

The script is `scripts/gate-evidence <arch>`: it runs `./scripts/quality-gate.sh --strict` on the host, then prints the line from the host's own values (`git rev-parse HEAD`, `git status --porcelain`, `uname -m`, `/etc/os-release`). No host name, address, user, or path.

**How it is checked.** A new rule **PC-9** in `pr-contract` (amendment A1): for each architecture that has no runner for this repository, the body of a change or implementation PR has a line of that format with the arch field equal to it, the SHA equal to the **current head SHA of the PR**, `clean`, the command equal to the gate, and `exit 0`. A design PR (docs only) and a Dependabot PR (PC-7) are exempt. The check reads the repository's `private` flag from the API, as ADR-008 decision 10 requires. The check re-runs on `edited`, so the evidence is refreshed by editing the body after a push.

**What it does not prove.** It proves the form and the SHA, not that the command ran. It is informational evidence that the approver accepts or rejects per PR (CR-39 D9-6). Where the approver wants more, the host's run is repeated in the review session.

## 8. Branch and tag rulesets printed by `initialize-project` (D9-7)

Content equals this repository's rulesets in `github-desired-state.toml` plus the required checks of SC-1.

| Ruleset | Target | Rules | Bypass |
|---|---|---|---|
| `main-protection` (public repository) | Default branch | No deletion; linear history; no force push; pull request with one approval, stale approvals dismissed on push, approval of the most recent reviewable push, conversation resolution, merge method squash only; **required status checks** `pr-contract` and `quality-gate` from GitHub Actions, not strict | None, including the approver |
| `release-tags` | Tags `v*` | No creation, update, or deletion; no force push | Repository admin role, mode always (only the approver creates tags) |
| Private repository | n/a | **Not printed.** The output says that rulesets are not available on GitHub Free for private repositories, repeats the RR-10 note, and prints the procedural list of section 12 | n/a |

`release-tags` is printed for the template and for an application repository whose configuration has `release_tags: true` (default false; Q15). For each, the printed output has the Console steps and a JSON body for `POST /repos/{owner}/{repo}/rulesets` that the approver applies from their own terminal or from the operator machine; the template's test compares the JSON with a golden file derived from the rulesets of this repository. `initialize-project` calls no write API (ADR-008 decision 3).

**Order** (section 12, U-6 and U-7): the tag ruleset exists before the first tag; the branch ruleset is applied after the settings and **before the init PR merges**. If the required checks cannot be added before a first run, `main-protection` is applied without them and the checks are added after the first green run of the init PR, then checked (S-3). Which of the two is needed is verified in the real run (CR-39 T-16 (b)).

## 9. The three template gate checks (D9-8)

| Check | Confirmed | Extension or constraint (this ADR) |
|---|---|---|
| `forbidden-api` | Rejects, in every script, the REST calls and GraphQL mutations for merge, review submission, auto-merge, rulesets, collaborators, and repository settings (ADR-008 decision 6) | **Extended** with these endpoint classes: branch protection; repository and organization secrets and variables; environments; webhooks; deploy keys; Actions permissions and runner registration; the security-feature toggles (`vulnerability-alerts`, `automated-security-fixes`, private vulnerability reporting, code-scanning default setup); release creation and tag refs; `gh release`, `gh repo`, `gh secret`, `gh variable`, `gh ruleset`; `git tag` and `git push --tags` (creating tags is the approver's, ADR-001). **Constraint:** the endpoint of a `gh api` call must be a string literal; a variable or a built string fails. The writes that scripts need stay allowed by name: create and update a PR, post a comment, create an issue, and the GraphQL `markPullRequestReadyForReview` |
| `operator-contract` | A generic check on `operator_paths`, inactive when the list is empty | **Constrained (SC-13):** inactive only for an explicit empty list; a missing, non-list, or unreadable key fails closed. The forbidden-pattern list is owned by the template; a platform adds allowed subprocesses through the configuration, never by editing the check |
| `owned-drift` | Fails a PR that changes an owned file without an `overrides.toml` entry | **Constrained (SC-14):** hashes are read from `.template/state.toml` on the **base** commit, so a PR cannot hide a change by editing `state.toml`; a change PR that touches `state.toml` fails unless it is a sync or init PR. **My reading, offered as the answer to the CR-39 open item:** a `uses:` change is allowed when, before and after, the line is `uses: <same owner/repo>@<40-hex> # v<version>` and nothing else in the file changed |

All three stay in the gate of every generated repository and are not removable by an override. Their fixtures are criteria S-11 to S-13.

## 10. Catalogue of quality-gate checks

The class is the header `# class:` of the check (SC-15). **generic**: no platform value, identical in every repository, seeded once into the template from this repository (CR-39 ST-8). **template**: exists because a repository is generated from the template. **platform**: only this platform. Today's ids are the files of `scripts/checks/`.

| Check | Class | What it checks | Runs in |
|---|---|---|---|
| `bash-hygiene`, `shellcheck`, `yaml`, `markdown`, `links`, `actionlint`, `python`, `gate-tests` | generic | Shell, YAML, Markdown, link, workflow-syntax, and Python hygiene; the gate's own fixtures | Both repositories now; every generated repository |
| `public-repo-hygiene` | generic | No identifier, address, email, key, fingerprint, or token pattern; runs for private repositories too | Same |
| `workflow-policy` | generic | WP-1 to WP-14 (section 4), with `allowed_action_owners` and `runner_labels` from configuration | Same |
| `no-claude-in-workflows` | generic | WP-15 | Same |
| `toolchain` | generic (profile names are data) | Every manifest download has both architectures and checksums (ADR-005 decision 3) | Same; the template checks its CI manifest |
| `claude-md`, `deny-list`, `cr-layout`, `size-budget` | template | CR-39 sections 5 to 7 and 11 | The template and every generated repository; this repository on adoption |
| `forbidden-api`, `owned-drift`, `operator-contract` (generic version) | template | Section 9 | Same |
| `dependabot-config` | template (new, Q13) | `.github/dependabot.yml` exists and has the `github-actions` ecosystem | Same |
| `ansible` | platform | Ansible syntax and lint of the profile playbooks | This repository |
| `operator-contract` (current version) | platform | The checks of `operator_contract.py` for `scripts/operator/` | This repository; replaced by the generic version on adoption |
| Template jobs `manifest`, `generate`, `sync`, `skills`, `leak` | template-only | CR-39 section 8 | `template-ci.yml`, removed on generation |
| Platform CI jobs `operator-profile`, `operator-limits`, `builder-profile`, `toolchain-<arch>` | platform | Apply and verify the profiles | This repository |

Every check in the required `quality-gate` runs with `--strict` in CI (a missing tool fails). Project checks go in `scripts/checks.d/` with the same interface and the class `project`.

## 11. How the two repositories share the rules without a live link (CR-39 Q7)

1. **Specification.** ADR-009 and the catalogue (section 10) state each rule and each check's behaviour. They are the single place a rule is stated.
2. **Same fixtures.** Every generic check has the same fixture set in both repositories (`tests/quality-gate/` here; the template's own gate tests). A fixture is added to both when a rule changes.
3. **Order of change.** A rule change is a design PR here (amends ADR-009), then an implementation PR in the template (the origin of generic code after seeding), then a PR here that copies the template's check. A repository that is already generated receives it by template-sync.
4. **Parity script (manual).** A script `scripts/checks-parity <path-to-template-clone>` in this repository prints, for every generic check, whether the two files have the same SHA-256, and fails if one is missing or differs. It is run by Claude Code on the workspace with a local clone of the template at a release tag, outputs counts and paths only, and its result goes in the PR body of each PR that changes a generic check. It is **not** a CI job: CI fetches no other repository (CR-39 T-14, T-21). `template-dev/provenance.toml` records the seed commit as history only.
5. **Adoption.** Whether this repository later replaces its copies with the template's output is a later CR (CR-39 section 14). Until then the parity script is how drift is seen.

## 12. The settings the approver applies by hand (SC-17)

Ordered. Claude Code never applies, and never runs `github-setup`, which is an operator script (CLAUDE.md). "Check" is a read-only step that the approver runs and records in the PR or CR. Exact interface wording and paths are as in the runbook's appendix A.1 to A.4 for the platform repositories.

| Step | Action | Check |
|---|---|---|
| U-0 | Once per account, before the first private use of Actions: set the Actions spending limit or budget to zero so that metered usage stops (wording in GitHub's billing interface **not verified**) | The billing page shows the limit (S-17) |
| U-A1 | This repository and the template: run the `github-setup` dry run and `facts --scope github` on the platform operator VM; compare every value with sections 3, 4.2, and 5; fix a difference in the interface or with `github-setup --apply` | Dry run reports no difference (S-4, S-5) |
| U-1 | New application repository: "Use this template" with the configured visibility | Repository exists; template flag off |
| U-2 | Add the machine account as collaborator (Write) and accept the invitation; update the AC1-1 allowlist | `facts` lists it with push and no admin |
| U-3 | General settings of A.1: squash only, no auto-merge, delete head branches | Settings check (S-4) |
| U-4 | Actions settings of section 4.2 (selected actions, SHA pinning, read token, no PR approval, fork approval, retention) | S-4 |
| U-5 | Security features of section 5 (public: secret scanning, push protection, Dependabot alerts and security updates, private vulnerability reporting) | S-5 |
| U-6 | Tag ruleset `release-tags`, if configured, **before** the first tag | S-3 negative test: creating a tag as the machine account is rejected |
| U-7 | Branch ruleset `main-protection` from the printed JSON, **before the init PR merges**; then the required checks after their first green run if they could not be added earlier | S-3: the check names equal those of a green run; a PR with a failing check cannot merge |
| U-8 | Run the init PR through review and merge it | `pr-contract` and `quality-gate` green |
| U-9 | After the first code merge on a public repository: enable CodeQL default setup | Alerts page shows it enabled |
| U-10 | When a new third-party Action is proposed: add the allowlist entry after reading the PR, before the merge | CI of the PR turns green |
| U-11 | Each fork PR from an outside account: read the workflow diff, then approve the run or close the PR | n/a |
| U-12 | Each private repository: record the RR-10 note and confirm the three checks green on the head before each merge | n/a (S-16) |

## 13. Dependencies on ADR-010 and the assumptions

Listed, not decided. ADR-010 is a separate CR.

| ID | Depends on | Assumption in this design |
|---|---|---|
| E-1 | ADR-010: size budgets for `CLAUDE.md`, rules, and Skills | The `size-budget` check reads `.template/budgets.toml`; ADR-009 fixes no value |
| E-2 | ADR-010: metrics | The gate prints one summary line per check (name, status, seconds) and nothing more; ADR-009 decides no metric and no storage |
| E-3 | ADR-010 | If metrics need an artifact or a cache, ADR-010 amends WP-14 with a content and retention rule. ADR-009 assumes they do not |
| E-4 | ADR-010: loading order | None. `size-budget` is part of the required `quality-gate`, so a budget breach blocks a merge on a public repository |

## 14. Proposed amendments to accepted records (not applied)

Each is a question for the approver (Q21). The text is what would be applied, in the pattern of CR-39: an "Amended by" row and the changed text.

**A1. ADR-003 (section 6, header).** Header row: "Amended by: CR-43 (Proposed): required checks, rule PC-9." Replace the first sentence after the table intro of section 6, "This is a required status check on public repositories and advisory on private repositories (GitHub Free).", with: "The checks `pr-contract` and `quality-gate` are required status checks on public repositories, enforced by the branch ruleset. On a private repository on GitHub Free rulesets are not available, so they are advisory and the approver confirms them before merging." Add the row: "**PC-9** | A change or implementation PR for a repository that has no hosted runner for a configured architecture contains, in the section \"Architecture evidence\", one line `evidence: <arch> | <machine> | <os> | <40-hex SHA> | clean | <gate command> | exit 0 | <UTC time>` per such architecture, with the SHA equal to the PR's current head. Design and Dependabot PRs are exempt. The line is informational; the approver accepts it per PR."

**A2. ADR-008 (decisions 9, 6, 3; section 3 file list).** Decision 9, add: "The aggregate job `quality-gate` needs the matrix jobs and is the required check." Add to the owned and seeded file classes: `SECURITY.md` (seeded) and `scripts/gate-evidence` (owned). Decision 6, add: "`forbidden-api` also rejects a `gh api` call whose endpoint is not a string literal and the endpoint classes of ADR-009 SC-12." Decision 2, add: "`owned-drift` reads hashes from the base commit (ADR-009 SC-14)." Header: "Amended by CR-43".

**A3. ADR-001 (RR-10, section 5).** RR-10 replacement: "On any **private** repository on GitHub Free the following are not available: rulesets and enforced branch protection, secret scanning, push protection, and code scanning. A compromised host could push directly to `main`, and a committed secret would not be detected by GitHub. Mitigation: keep repositories public by default (Q5). If a private repository is needed, record a per-repository accepted-risk note, keep its deploy paths manual, rely on the gate's `public-repo-hygiene` and `forbidden-api`, and have the approver confirm `pr-contract` and `quality-gate` and the evidence lines before each merge." Section 5, add under the deny table: "The deny rules and the template's `forbidden-api` cover the endpoint classes listed in ADR-009 SC-12."

**A4. ADR-005 (context).** Append to the ARM64 line of section 1: "GitHub documents `ubuntu-24.04-arm` for private repositories as a metered runner (read 2026-11-19; not verified by a run). Whether a repository uses it is decided per repository (ADR-009)."

## 15. Questions for the approver

Each question has my recommendation first. None is decided.

| # | Question | Recommendation |
|---|---|---|
| Q1 | Which names are required (SC-1): the aggregate `quality-gate` plus `pr-contract`, or `pr-contract` plus each `quality-gate-<arch>`? | The aggregate. One name survives a change of architectures. The alternative lists the names from the configuration and needs a ruleset edit when it changes |
| Q2 | Are the platform jobs of this repository (`operator-profile`, `operator-limits`, `toolchain-<arch>`, `builder-profile`) and the template jobs (`manifest`, `generate`, `sync`, `skills`, `leak`) required checks too? | Yes for the template jobs, and yes for the platform jobs of this repository, because each is a test of what is merged. Say if a long job should stay advisory |
| Q3 | Require "branch up to date before merging"? | No (section 3) |
| Q4 | Pin the source of each required check to GitHub Actions? | Yes |
| Q5 | WP-2 and WP-14: no `write` permission, no cache action, no artifact action in v1? | Yes. Amend this ADR when a need appears |
| Q6 | WP-4 and WP-13: owners and runner labels from the configuration; no self-hosted runner? | Yes |
| Q7 | Third-party Actions (SC-6): GitHub-owned only, with the three-step procedure of section 6? | Yes |
| Q8 | WP-8: treat `inputs.*` as untrusted; WP-10, WP-11, WP-12 as hard rules for application repositories? | Yes |
| Q9 | Fork approval: "all external contributors" on public repositories; for private repositories no workflows from fork PRs with write tokens or secrets? | Yes |
| Q10 | SC-19 stated in the ADR: a required check is evidence, not authority, and the approver reads every workflow diff? | Yes |
| Q11 | CodeQL default setup: enable now on this repository and the template (languages Python and GitHub Actions, if GitHub offers them), and on an application repository once it has code? | Yes. The language support is not verified here; the approver sees the offered languages when enabling |
| Q12 | Seed a generic `SECURITY.md` (no contact data, points to private vulnerability reporting); no `CONTRIBUTING`, code of conduct, or `CODEOWNERS`; the licence stays a per-repository choice? | Yes |
| Q13 | New generic-class check `dependabot-config` (the `github-actions` ecosystem is present)? | Yes. Dependabot keeps the SHA pins current, and a project could otherwise delete the file |
| Q14 | ARM64 on a private repository: the documentation lists a metered hosted runner. Use it in the preset, or keep the evidence line until a run on a private test repository shows it works within the included usage? | Keep the evidence line; verify first. SC-18 (zero spending limit) applies either way |
| Q15 | Rulesets (section 8): `main-protection` without bypass, with the required checks; `release-tags` for the template always and for an application repository only when `release_tags: true`? | Yes |
| Q16 | `forbidden-api` (SC-12): the extended endpoint classes and the literal-endpoint rule? | Yes. The write allowlist keeps the scripts' legitimate calls |
| Q17 | `owned-drift` (SC-14): hashes from the base commit; the `uses:`-only reading of section 9? | Yes; it closes the CR-39 open item |
| Q18 | `operator-contract` (SC-13): fail closed on a missing key? | Yes |
| Q19 | Rule sharing (section 11): a manual parity script in this repository, no CI link? | Yes |
| Q20 | Application repositories: extend `github-setup` and its desired state to a profile for them (a platform change PR, operator-run), or keep section 12 as a manual list? | Extend it later in its own change PR. Until then the list is manual, with the read-only checks |
| Q21 | Apply amendments A1 to A4 of section 14 (each separately)? | A1, A2, A3 yes. A4 is a correction of a context line; yes |
| Q22 | How do the template's implementation PRs carry the CR-43 criteria? | In the CR-39 PRs of the plan (2, 3, 4, 8, 9), each with an extra body section "Also verifies CR-43 criteria" listing S-ids. A separate PR per criterion would touch the same files twice |

## 16. Still open

| Item | Who decides | When |
|---|---|---|
| The live state of both repositories: whether required checks, code scanning, and the settings of section 4.2 match what is stated. I could not read them. `github-setup` dry run and `facts --scope github` show it | Approver | Section 12, U-A1, before the implementation PRs |
| Whether a matrix job's check name is its expanded `name`, and how the aggregate behaves on a skipped matrix job | Claude Code and approver | First template CI run (S-3, S-2) |
| CodeQL language support for GitHub Actions workflows and Python on a personal Free account | Approver | When enabling (Q11) |
| Private vulnerability reporting and community files on private repositories | Approver | Not needed while repositories are public |
| ARM64 private runner availability and usage | Approver | Q14 |
| Where to set the zero Actions spending limit and its wording in GitHub's billing interface | Approver | U-0 |
| The `integration_id` of the GitHub Actions app for the ruleset JSON | Claude Code | Read from the live ruleset in the implementation PR |
| This repository's follow-through to ADR-003 as amended (CR-39 section 14) and the preset | Approver | The preset change PR; PC-9 is added with it |
| Whether this repository adopts the template's generic checks | Approver | A later CR |
| OpenSSF Scorecard, dependency review, artifact attestations, an allowlist of `runs-on` per repository | Approver | Later; Scorecard is baseline Stage 7 |
| ADR-010 | Approver | A separate CR. Stage 5 entry needs ADR-008, ADR-009, and ADR-010 |
