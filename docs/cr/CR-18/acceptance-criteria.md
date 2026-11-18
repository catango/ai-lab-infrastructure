# CR-18 Acceptance criteria

Verified by the implementation PRs and by the approver's acceptance run. "CI" means a green run of the named check on a test PR.
"Approver" means a test only the approver can run on the workspace or the lab VM. Evidence is reported as yes/no, counts, and
sizes, never identifiers, addresses, or names.

## Separation (U), approver

| ID | Criterion | Evidence |
|---|---|---|
| U-1 | The AI user cannot read the operator's home, cannot become the operator, and has no sudo rule to run commands as the operator. The operator has no sudo and no privileged group. | Approver's tests as each user (a read of the other's home is refused; `sudo -n true` fails for both; group list shows no privileged group), results yes/no. Done before the operator holds any credential |
| U-2 | `workspace/verify.sh` V-4 still passes when run as the AI user after the operator holds credentials. | Output of the verify script, run as the AI user |
| U-3 | No credential, token, or raw response from an operator run exists in the repository, the AI user's home, or shell history. | Approver's inspection after a run; `public-repo-hygiene` on any PR |

## Script contract (S), CI

| ID | Criterion | Evidence |
|---|---|---|
| S-1 | Every script under `scripts/operator/` accepts `--dry-run` and `--apply`, and exits with a usage error when it gets neither or both. | Test enumerating the scripts, run in CI (`gate-tests`) |
| S-2 | A dry run makes no write call: with a stub CLI that records calls, a dry run records none that change state. | Tests with stub CLIs |
| S-3 | A script refuses to run with local changes in the clone, and with a commit that is not contained in `origin/main`. | Tests in a temporary repository |
| S-4 | A second `--apply` run changes nothing. | Tests with stub state |
| S-5 | The sanitiser removes OCIDs, IPv4 and IPv6 addresses, and email addresses from sample output, and a value it cannot classify becomes a placeholder. | Unit tests with sample outputs |
| S-6 | No script contains `eval`, a download piped to a shell, a Terraform call, or an OCI write call. | Gate check over `scripts/operator/` |
| S-7 | Every script is ShellCheck-clean and uses `set -euo pipefail`. | CI `quality-gate` (`shellcheck`, `bash-hygiene`) |

## Use cases (G), approver unless stated

| ID | Criterion | Evidence |
|---|---|---|
| G-1 | `oci-audit` in dry-run lists its read-only calls. In apply it prints the results summary block of the Gate 0 audit with yes/no and counts only, and no identifier. | Approver's run, output compared against the runbook's block |
| G-2 | `github-setup` in dry-run shows current against wanted settings for both repositories without any change. In apply it brings them to the wanted state, and a second apply reports no change. | Approver's run on a throwaway or the real repositories, results yes/no |
| G-3 | `github-setup` uses T2 only from the prompt, and T2 is revoked after the run. | Approver's check of the token list |
| G-4 | `acceptance` in dry-run lists the checks by criterion ID. In apply it reports yes or no per ID for the checks it can run, and names the ones that stay manual. | Approver's run |
| G-5 | The operator scripts perform no OCI write call. | Test S-6, and the approver's review of the audit log of a run |

## Lab effect (L), approver

| ID | Criterion | Evidence |
|---|---|---|
| L-1 | After CR-16 gains the lab login (design section 7): with `operator_user_name` unset, no second login exists. With it set, the operator logs in with its key, is in no privileged group, cannot use `sudo`, cannot read the default user's home or write to `/srv/work`, and holds no OCI or GitHub credential. | Approver's login and tests, results yes/no. Checked in CR-16's acceptance run |

## Documents and process (D)

| ID | Criterion | Evidence |
|---|---|---|
| D-1 | `docs/operations/operator.md` describes the one-time setup of the operator clone, the run flow, T2 handling, and the rollback. | Review |
| D-2 | `docs/operations/gate-0-audit.md` and `github-setup.md` are shortened to the manual parts and point at the scripts. | Review |
| D-3 | ADR-001's section 4 matrix and decision 5 carry the amended wording, and `docs/README.md` lists ADR-011 and CR-18 with their current status. | Review |
| D-4 | The final implementation PR carries the evidence table and `Closes #18`. | PR body |
