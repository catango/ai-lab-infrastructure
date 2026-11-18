# CR-21 Design: rule PC-8 (operator script review)

| Field | Value |
|---|---|
| CR | issue #21 (Class 3) |
| Governing records | ADR-003 (sections 6 and 11), ADR-011 (decisions 2, 3, 10, 11) |
| Scope | Design only. No change to `pr-contract`, templates, or workflows in this PR |

## 1. The rule

| Rule | Requirement |
|---|---|
| PC-8 | A PR that changes a path in the operator set must contain a PR-body section "Operator script review", non-empty. The operator set is `scripts/operator/**`, `ansible/operator.yml`, the roles of the operator profile, and their data files (see Q1 and Q2) |

PC-8 applies to every PR type. A design PR changes only `docs/` (PC-4), so it never triggers PC-8 in practice. "Non-empty" has the PC-1 meaning: the section has text other than template comments.

## 2. Decisions

| ID | Decision | Rationale |
|---|---|---|
| PC8-1 | The rule is a new row PC-8 in ADR-003 section 6, enforced by `pr-contract` like PC-6 | One check, one place, same trust model (read-only token, untrusted body) |
| PC8-2 | The section is required only when the operator set changes. It is not part of any template's required sections. Templates carry a hint comment, as for PC-6 | PC-1 would otherwise force an empty section on every PR |
| PC8-3 | The check is presence and non-emptiness only. It does not judge the content | Review is the approver's job. The rule makes it visible |
| PC8-4 | Path matching is by a fixed list in `pr-contract` and is case-sensitive, with no wildcard beyond the directory prefix | Deterministic and testable |
| PC8-5 | A failure message names the rule and the section title and prints no PR text | Same handling as the other rules |

## 3. Content of the section (proposal)

The template hint asks the author to answer, in a few lines each, with no identifier, address, or name:

1. **Credentials:** which credential the change reads or uses, and how it is handled (prompt, in-process, never in a child process environment, `argv`, or on disk).
2. **Commands:** every subprocess and every privileged command added or changed (`sudo`, `become`), and whether it is in the allowlist of ADR-011 decision 11.
3. **Modes:** what the dry run shows and what `--apply` changes, and whether a second apply changes nothing.
4. **Calls:** the OCI verbs and HTTP methods used (read-only scopes use `list`, `get`, `inspect`, and GET only).
5. **Output:** which fields reach standard output and why they are safe to paste.
6. **Resources:** the machine-profile limits the change was sized for.
7. **Release:** whether the approver must create a release tag before first use.

## 4. How PC-8 fits the existing rules

- PC-5 (no edit of approved design files in an implementation or change PR) is unchanged.
- PC-6 is the model: a path-triggered, body-section requirement.
- PC-7 (Dependabot) is addressed by Q3.

## 5. Questions for the approver

| # | Question | Recommendation | Status |
|---|---|---|---|
| Q1 | How are the roles of the operator profile identified by path? | Name them `ansible/roles/operator_*`, so the prefix matches deterministically. CR-18's `operator-profile` PR follows that naming | Not decided |
| Q2 | Does `toolchain/python/operator.lock` belong to the operator set? | Yes: it decides what code runs on the operator machines. The machine-profile file is already under `scripts/operator/` | Not decided |
| Q3 | Are Dependabot PRs exempt from PC-8? | Yes, like PC-1 to PC-3 in PC-7, since a lock-file bump has no author to write the section. The release tag (ADR-011 decision 3) still gates first use | Not decided |
