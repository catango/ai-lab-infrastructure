# CR-43 Impact analysis

## 1. What changes

In this design PR:

- [ADR-009](../../adr/ADR-009-security-and-ci-baseline.md) (Proposed) and the CR-43 files are added.
- **Four accepted records are amended** with the approver's final text (decision Q21), each with an "Amended by" entry that takes effect when this PR is merged: [ADR-003](../../adr/ADR-003-pr-centric-workflow.md) (A1: section 6 required checks, PC-7 exemption, new PC-9, AC3-8), [ADR-008](../../adr/ADR-008-software-template.md) (A2: decisions 1, 2, 3, 6, 9, 10), [ADR-001](../../adr/ADR-001-trust-model-and-execution.md) (A3: B1 note, section 5 deny row, RR-10), and [ADR-005](../../adr/ADR-005-toolchain.md) (A4: context on ARM64 runners).
- `docs/README.md` gets rows for ADR-009 and CR-43 and the amended statuses.

Nothing else. No code, workflow, setting, ruleset, secret, variable, collaborator, label, or tag changes, and the `ai-software-template` repository is not touched.

Later, in implementation PRs (see the plan): the `workflow-policy` rules and check classes here, the aggregate `quality-gate` and the policy checks from the base, `codeowners` and `dependabot-config`, the evidence rule and script, the parity script, and the settings desired state; and the template-side items inside the CR-39 PRs.

## 2. Affected components and records

| Item | Effect |
|---|---|
| Baseline v0.1 | The decision index and the component map still say ADR-009 "Pending design". They are updated when ADR-009 is accepted, not in this PR |
| ADR-001 | A3 applied: B1 note (the ruleset does not restrict which write user merges an approved PR), a section 5 deny row, RR-10 text |
| ADR-003 | A1 applied: section 6 wording, PC-9, AC3-8. PC-9 is enforced once implemented (PR 4) |
| ADR-005 | A4 applied: a context line about ARM64 runners on private repositories |
| ADR-008 | A2 applied. CR-39 files are not edited |
| ADR-010 | Dependencies and assumptions listed (design section 13); nothing decided |
| ADR-011 | Decision 3 (tag ruleset) is the model of `release-tags`; unchanged |
| `ci.yml` and `pr-contract.yml` here | Later (PR 2b): the current gate job is renamed `gate` and `quality-gate` becomes the aggregate; the policy checks run from the base; the bootstrap skip goes |
| Runbook `github-setup.md` and `github-desired-state.toml` | Later (PR 6): a section for application repositories; desired-state keys for required checks, code-owner review, and update branch off. Operator code, run by the approver only |
| `ai-software-template` | Receives the template-side items inside the CR-39 PRs 1, 2, 3, 4, 8, and 9 (Q22) |

## 3. Security and privacy

- The design lowers the supply-chain surface of every repository: no third-party Action, no `write` permission, no cache, artifact, or `github-script` action, digests on containers, runner labels from a list, no `${{` in a `run:` value. The risk is the opposite: a wrong rule in the template reaches every generated repository. The approver-only tags and the review of each sync PR are the controls (CR-39).
- **A required check is evidence, not authority** (SC-19). A PR can change the workflow that reports its check. SC-20 narrows this: the policy checks and their inputs come from the base commit, so a PR cannot widen the policy that judges it, and the approver reads workflow diffs (PC-6).
- **Write access findings, from GitHub's behaviour as read on 2026-11-19:** any write user, including the machine account, can set a commit status or check run of any name (hence the source pin, SC-4), change code-scanning, secret-scanning, and Dependabot alert states, and bypass push protection through the REST API. A ruleset does not restrict which write user merges an approved PR. The section 5 deny rules and `forbidden-api` are the control for the machine account, and they cover only Claude's own commands and scripts' calls (ADR-001 section 5, RR-9).
- A **private repository on GitHub Free** has no rulesets, secret scanning, push protection, or code scanning. This is accepted risk RR-10, restated in A3. The compensation (hygiene check, `forbidden-api`, procedural list) is weaker than the public path.
- The evidence line is host-reported and unverifiable beyond its form and SHA. It never replaces the approver's judgement and carries no host identity. `architectures` is read from the base commit, so a PR cannot remove its own requirement.
- The parity script reads two local clones and prints counts and paths. It makes no network call.
- Code-owner review adds one line `* @<approver_login>` to a public file. The login is already public in `config/project.yaml`.
- No identifier, address, email, key, or name of a person appears in these files beyond the public login rule above.

## 4. Operational impact on the approver

- Reviews and merges the design PR, which also accepts the four amendments.
- Applies settings by hand (design section 12): update branch off and CodeQL now on both platform repositories, the check of required checks and their source, code-owner review after PR 3, the rulesets and allowlist entries for application repositories, and the read-only checks.
- Reads the diff of every file a workflow executes before running an outside PR (default: closes it), reads the source of every new Action pin, and reads the evidence line of every PR on a repository that lacks a runner.
- Runs the `github-setup` dry run before and after PR 6; creates `v*` tags under `release-tags`.
- Approves ADR-010 before Stage 5 starts.

## 5. Dependencies and assumptions

- CR-39 design (PRs #40 and #42) is merged. Its section 11 is the work list of this CR.
- ADR-010 is decided elsewhere. Assumptions E-1 to E-4 (design section 13): budgets are data, metrics are one summary line per check, no artifact or cache is needed, and `size-budget` is inside the required `quality-gate`.
- GitHub facts were read from GitHub's documentation on 2026-11-19 and are recorded in design section 5. The documented-but-untested ones: rulesets on private repositories need a paid plan; `ubuntu-24.04-arm` is a metered standard runner for private repositories. The matrix check name `toolchain-amd64` was observed on this repository's PR checks.
- I could not read the live rulesets and settings of either repository (the call was refused in this session), so the stated state is the as-built documentation and the desired-state file. Design section 16 lists the check.
- `gh pr edit` and `gh pr ready` fail in the workspace (Projects classic error); this PR uses the REST and GraphQL calls named in the task.

## 6. Cost and capacity

No OCI cost. Public repositories run Actions free. The account has no payment method and $0 budgets (runbook Parts 1.2 and 1.3), and no metered ARM64 runner is used, so no GitHub usage can be charged. The new `workflow-policy` rules, the head checkout in `pr-contract`, and their fixtures add seconds to the gate.

## 7. Rollback

Before implementation, revert the design PR, which also reverts the four amendments (a revert PR restores their previous text). After implementation, each implementation PR is a normal revert. Settings are changed by the approver and are rolled back by the same list in reverse; the Stage 0 runbook (appendix A and operator.md section 6) describes the rollback of `github-setup`. Reverting the aggregate rename needs the job name restored in `ci.yml` only, because the required name never changed.

## 8. Alternatives considered

See ADR-009 section 3. The main ones: per-architecture required names, platform jobs required by name, verified third-party Actions, WP-14 as a denylist, policy inputs from the PR head, no `CODEOWNERS`, a metered ARM64 runner, `pull_request_target`, a shared Action or reusable workflow, a CI job that compares the repositories, caches and artifacts in v1, the up-to-date requirement, a hand-typed evidence line, and the Scorecard now.
