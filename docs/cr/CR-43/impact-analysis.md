# CR-43 Impact analysis

## 1. What changes

In this design PR:

- [ADR-009](../../adr/ADR-009-security-and-ci-baseline.md) (Proposed) and the CR-43 files are added.
- `docs/README.md` gets rows for ADR-009 and CR-43.

Nothing else. In particular, **no accepted record is edited**: the proposed amendments to ADR-001, ADR-003, ADR-005, and ADR-008 are drafted in design section 14 and are applied only after the approver decides them (as CR-39 did). No code, workflow, setting, ruleset, secret, variable, collaborator, label, or tag changes, and the `ai-software-template` repository is not touched.

Later, in implementation PRs (see the plan): the `workflow-policy` extension and check classes here, the evidence rule and script, the parity script, and the template-side items inside the CR-39 PRs.

## 2. Affected components and records

| Item | Effect |
|---|---|
| Baseline v0.1 | The decision index and the component map still say ADR-009 "Pending design". They are updated when ADR-009 is accepted, not in this PR |
| ADR-001 | Proposed A3: RR-10 extended (no secret scanning, push protection, or code scanning on a private repository on Free), and the section 5 deny rules cover the endpoint classes of SC-12 |
| ADR-003 | Proposed A1: section 6 wording for required checks, rule PC-9 |
| ADR-005 | Proposed A4: a context line about ARM64 runners on private repositories |
| ADR-008 | Proposed A2: the aggregate job, `SECURITY.md`, `scripts/gate-evidence`, the `forbidden-api` and `owned-drift` constraints. CR-39 files are not edited |
| ADR-010 | Dependencies and assumptions listed (design section 13); nothing decided |
| ADR-011 | Decision 3 (tag ruleset) is the model of `release-tags`; unchanged |
| Runbook `github-setup.md` | Later: a section for application repositories (plan PR). Not changed here |
| `github-setup` and its desired state | Later and optional (Q20); an operator script, reviewed here and run by the approver |
| `ai-software-template` | Receives the template-side items inside the CR-39 PRs 2, 3, 4, 8, and 9 (Q22) |

## 3. Security and privacy

- The design lowers the supply-chain surface of every repository: no third-party Action, no write permission, no cache or artifact action, digests on containers, runner labels from a list, `inputs.*` treated as untrusted. The risk is the opposite: a wrong rule in the template reaches every generated repository. The approver-only tags and the review of each sync PR are the controls (CR-39).
- **A required check is evidence, not authority.** A PR can change the workflow that reports its check. The approver's review of workflow diffs is the control (PC-6, SC-19).
- A **private repository on GitHub Free** has no enforced protection, secret scanning, push protection, or code scanning. This is accepted risk RR-10, restated more completely in A3. The compensation (hygiene check, procedural list) is weaker than the public path.
- The evidence line is host-reported and unverifiable beyond its form and SHA. It never replaces the approver's judgement and carries no host identity.
- The parity script reads two local clones and prints counts and paths. It makes no network call.
- Facts about GitHub plans were read from GitHub's documentation and are marked where they could not be verified (design section 5). A wrong fact would make a setting that the approver applies ineffective on a private repository; the approver checks each setting (S-3 to S-5).
- No identifier, address, email, key, or name of a person appears in these files.

## 4. Operational impact on the approver

- Reviews and merges the design PR and decides the questions of design section 15, including the four amendments.
- Applies settings by hand (design section 12), including the zero Actions spending limit, the allowlist, the rulesets, and CodeQL, and runs the read-only checks.
- Reads the workflow diff of every fork PR before approving its run, and the evidence line of every PR on a repository that lacks a runner.
- Approves ADR-010 before Stage 5 starts.

## 5. Dependencies and assumptions

- CR-39 design (PRs #40 and #42) is merged. Its section 11 is the work list of this CR.
- ADR-010 is decided elsewhere. Assumptions E-1 to E-4 (design section 13): budgets are data, metrics are one summary line per check, no artifact or cache is needed, and `size-budget` is inside the required `quality-gate`.
- I could not read the live rulesets and settings of either repository (the call was refused in this session), so the stated state is the as-built documentation and the desired-state file. Design section 16 lists the check.
- `gh pr edit` and `gh pr ready` fail in the workspace (Projects classic error); this PR uses the REST and GraphQL calls named in the task.

## 6. Cost and capacity

No OCI cost. Public repositories run Actions free. Private repositories use metered minutes from the account's included usage; SC-18 keeps the spending limit at zero. The new `workflow-policy` rules and fixtures add seconds to the gate.

## 7. Rollback

Before implementation, revert the design PR. After implementation, each implementation PR is a normal revert. Settings are changed by the approver and are rolled back by the same list in reverse; the Stage 0 runbook (appendix A and operator.md section 6) already describes the rollback of `github-setup`.

## 8. Alternatives considered

See ADR-009 section 3. The main ones: per-architecture required names, verified third-party Actions, `pull_request_target`, a shared Action or reusable workflow, a CI job that compares the repositories, caches and artifacts in v1, the up-to-date requirement, a hand-typed evidence line, and the Scorecard now.
