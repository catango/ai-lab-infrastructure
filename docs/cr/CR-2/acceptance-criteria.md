# CR-2 Acceptance criteria

Verified by the implementation PRs. Each criterion names its evidence. "CI" means a green run of the named check on a test PR.
Criteria from accepted ADRs that this CR must satisfy are cross-referenced in the last column.

## Toolchain (T)

| ID | Criterion | Evidence | ADR link |
|---|---|---|---|
| T-1 | `scripts/toolchain check` rejects a manifest with a missing architecture, a malformed checksum, a non-`https` URL, `latest`, an unknown key, or a version absent from the URL. | Unit tests with one failing fixture per case | ADR-001 section 5 |
| T-2 | `scripts/toolchain install` refuses an artifact whose checksum differs and leaves nothing installed. | Unit test with a tampered artifact served locally | |
| T-3 | Archive extraction rejects absolute paths, `..`, escaping links, device files, and setuid bits. | Unit tests with crafted archives | |
| T-4 | Install is idempotent: a second run reports zero changes and downloads nothing. | Unit test; `builder-profile` second apply shows `changed=0` | |
| T-5 | `--dry-run` writes nothing and downloads nothing. | Unit test comparing the file tree before and after | CLAUDE.md |
| T-6 | Every download in the manifest has amd64 and arm64 artifacts with checksums that match upstream. | CI `toolchain-amd64` and `toolchain-arm64` | CLAUDE.md |
| T-7 | Every tool's smoke command succeeds and reports the manifest version on both architectures. | CI `toolchain-amd64` and `toolchain-arm64` | |
| T-8 | `ansible/builder.yml` applies cleanly on Debian 13 x86-64 and `scripts/toolchain verify` passes afterward. | CI `builder-profile`; later AC1-7 | ADR-001 section 4a |
| T-9 | `ansible/builder.yml` aborts with one message on any other OS or architecture. `ansible/lab.yml` passes `--syntax-check` and fails with the Stage 3 message when applied. | `ansible` quality-gate check; manual negative run | |
| T-10 | `fd`, `rg`, `gh`, `yq`, `shellcheck`, and `actionlint` resolve from `<prefix>/bin` under their expected names. | `verify` output | |
| T-11 | ADR-005 is part of the merged design PR before the implementation PR that adds the manifest is opened (the merge is the acceptance; its status line is stated in the ADR). | PC-3 (design PR merged) | Baseline section 6 |

## Restore (R)

| ID | Criterion | Evidence | ADR link |
|---|---|---|---|
| R-1 | `restore.sh --dry-run` makes no change to the system, the home directory, or the network state, and prints the planned actions. | Recorded run plus a file-tree comparison | ADR-001 section 4a step 3 |
| R-2 | `restore.sh` refuses to run without a terminal on stdin and when Claude Code session markers are present. | Scripted negative test; manual attempt from a Claude session | AC1-8 |
| R-3 | The token is read with no echo, appears in no log, no `argv`, no shell history, and no file written by the script. | Review plus `ps` and history inspection during the reset test | AC1-8 |
| R-4 | After a simulated home reset, `restore.sh` restores a verified workspace within 15 minutes. The only manual input is token T1 (and the sudo prompt if sudo needs a password). | Timed run by the user, with the per-step timing output | AC1-7 |
| R-5 | Re-running `restore.sh` on a restored workspace changes nothing, does not prompt for the token, and does not reset dirty clones. | Recorded second run | |
| R-6 | Existing user-level configuration differing from `workspace/claude-user/` is backed up before being replaced. Files outside the allowlist, `~/.claude/remote/`, and credential files are untouched. | Test with a pre-populated `~/.claude/` in a temporary home | |
| R-7 | Open PRs of the machine account have local tracking branches after restore. | Recorded run | ADR-001 section 4a step 5 |
| R-8 | `verify.sh` fails (exit 1) when: a tool version differs, a required deny rule is missing, token scopes lack `repo` or `workflow`, an `OCI_` variable or `~/.oci/` exists, or the git identity is wrong. | One negative test per check | AC1-3, AC1-5 |
| R-9 | `verify.sh` output never contains token or environment variable values. | Test with a canary variable value and a canary token string | AC1-8 |

## Quality gate (Q)

| ID | Criterion | Evidence | ADR link |
|---|---|---|---|
| Q-1 | Exit codes are 0, 1, 2, 3 as specified. | Tests for each | |
| Q-2 | `--list`, `--only`, `--skip`, `--base`, `--strict` behave as specified. | Tests | |
| Q-3 | A missing tool is `SKIP` locally and exit 3 under `--strict`. | Tests with a restricted `PATH` | |
| Q-4 | Failure output shows at most 20 findings per check plus a count, and one summary line. | Test with 30 seeded findings | ADR-003 section 7 |
| Q-5 | `workflow-policy` fails on: an unpinned or tag-pinned `uses:`, `pull_request_target`, a missing top-level `permissions:`, a PR-controlled expression in `run:`, and `curl` piped to a shell. | One fixture per case | CLAUDE.md |
| Q-6 | `no-claude-in-workflows` fails on a workflow referencing Claude or Anthropic. | Fixture | AC3-6 |
| Q-7 | `public-repo-hygiene` fails on an `ocid1.` identifier, a non-documentation IPv4 address, an email address, a key fingerprint, a private-key header, and a token prefix; it accepts documentation ranges and `noreply` forms. | Fixtures | CLAUDE.md |
| Q-8 | The gate writes nothing to the repository and needs no network or credentials. | Test (clean `git status`, no-network run) | |
| Q-9 | Under GitHub Actions the summary is appended to `$GITHUB_STEP_SUMMARY`. | CI run | ADR-003 section 7 |

## pr-contract (P)

| ID | Criterion | Evidence | ADR link |
|---|---|---|---|
| P-1 | PC-1: a body missing or leaving empty any template section fails; sections that contain only the template comment fail; headings inside code fences or comments do not count. | Fixtures | ADR-003 section 6 |
| P-2 | PC-2: wrong or unknown branch prefix, missing marker, and marker and branch mismatch each fail. | Fixtures | |
| P-3 | PC-3: an implementation PR referencing an unmerged, non-design, or other-issue design PR fails. | Fixtures; one test PR | AC3-1 |
| P-4 | PC-4: a design PR touching a path outside `docs/` (including a rename source) fails. | Fixtures | |
| P-5 | PC-5: an implementation or change PR touching an existing or new `design.md`, `acceptance-criteria.md`, or `docs/adr/` file fails. | Fixtures; one test PR | AC3-2 |
| P-6 | PC-6: a workflow change without a non-empty "Workflow change justification" fails. | Fixtures | |
| P-7 | PC-7: a Dependabot PR changing only manifests, lockfiles, or `uses:` lines passes; any other change, or a missing patch, fails. | Fixtures | |
| P-8 | Hostile PR text (command substitution, backticks, expression syntax, workflow commands, 1 MB body, control and bidirectional characters, newlines in title) produces no side effect and no unsanitized output. | Fixtures and output assertions | ADR-003 section 6 |
| P-9 | API failure, rate limit, and malformed response each produce a non-zero exit. | Tests with a failing client | |
| P-10 | The workflow passes only `--repo` and `--pr` to the script and runs it from the base checkout. | `workflow-policy` check plus review | ADR-003 section 6 |
| P-11 | The check works with a read-only `GITHUB_TOKEN` on this public repository. | CI run on a test PR | V3-4 |

## CI (C)

| ID | Criterion | Evidence | ADR link |
|---|---|---|---|
| C-1 | Both workflows declare top-level `permissions: {}` and per-job least privilege as in the design. | `workflow-policy` check; review | ADR-009 (pending) |
| C-2 | All `uses:` are pinned to full SHAs that match the named upstream tags; the container image is pinned by digest. | Review evidence in the PR; `workflow-policy` check | CLAUDE.md |
| C-3 | A job runs on `ubuntu-24.04-arm` and passes. | CI `toolchain-arm64` | ADR-001 O-1 |
| C-4 | Check names are exactly `pr-contract`, `quality-gate`, `toolchain-amd64`, `toolchain-arm64`, `builder-profile`. | CI run | |
| C-5 | CI is green on a test PR (Stage 1 exit criterion). | Test PR link | Baseline section 6 |
| C-6 | No workflow uses `pull_request_target`, `workflow_run`, secrets, or a Claude credential. | `workflow-policy` and `no-claude-in-workflows` checks | AC3-6 |
| C-7 | Required jobs have no `paths:` filters. | `workflow-policy` check | |

## Document and process (D)

| ID | Criterion | Evidence |
|---|---|---|
| D-1 | A short runbook `docs/operations/workspace-restore.md` describes the user-run steps, the sudo commands, and the reset test. | Review |
| D-2 | `docs/README.md` lists CR-2 and ADR-005. | Review |
| D-3 | No file, commit, or PR text contains an OCID, IP address, email, key, or fingerprint. | `public-repo-hygiene` check |
