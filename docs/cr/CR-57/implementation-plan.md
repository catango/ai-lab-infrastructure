# CR-57 Implementation plan

Starts only after the design PR is merged (ADR-003 section 4). Each PR runs in its own session, in `ai-lab-infrastructure` unless stated, branch `impl/CR-57-<slug>`, and declares `Implements: #57` and `Design:` with the design PR number (the last PR carries `Closes #57`, section 4). Slugs and file lists are proposals read from `main` at `85360e8`; each PR starts with an inventory that corrects them. No ADR, `design.md`, or acceptance file is edited in an implementation PR (PC-5); a needed change is a new design PR. ADR-012 is written in the design PR, not in an implementation PR.

## 1. Order and rules

The order is the approver's (review of 2026-11-23T18:27:31Z, steps 1 to 10), with **step 0** added: the `operator_paths` configuration must exist before the first removal (corrections of the independent review). The order is strict (PA-26): the repository `CLAUDE.md` keeps a rule until the PR that removes its subject (PA-11), the aggregate `quality-gate` is green after every PR, and required check names do not change. **No release tag is cut while a removal is in progress** (PA-26); open point O-3 records what that means for lab setup and the operator configuration, which refuse to run except at a release tag. A removal PR deletes, in the same PR, the code, its tests and fixtures, the rows and links that name it in `docs/README.md` and the operations documents, and the checks that hard-code it; a link to a deleted file fails the `links` check. Each PR body gives the PC-8 section when it touches a PC-8 path and the PC-6 section when it touches a workflow (PA-A5); a path becomes a PC-8 path only once the base commit lists it, so a PR that adds profile paths states them in its body.

## 2. The PRs

| # | Branch slug | Content and files | Needs | Body sections |
|---|---|---|---|---|
| 0 | `operator-paths-config` | Add the `operator_paths` key to `config/project.yaml` (operator scripts, the lab profile, the operator profile; the paths of today plus the shared SSH hardening role and `ansible/lab.yml`). `scripts/pr_contract/rules.py`: read the key from the base commit and fail closed on a missing or malformed key (ADR-009 decision 14, CR-43 SC-13); delete the hardcoded `OPERATOR_PREFIXES` and `OPERATOR_PATHS` (lines 24, 25); keep `MANIFEST_PATHS` (line 32) until its locks change; PC-8 still counts deleted paths (line 147). Update the four PR template comments (`implementation.md`, `infra.md`, `toolchain.md`, `change.md`). Fixtures: configured, empty, missing, malformed, deleted path | Design merged; Q2 | none |
| 1 | `remove-oci` | **Inventory first, reported in the PR.** Remove the OCI scope of `facts` (`scripts/operator/lib/operator_lib/ocifacts.py`, the `oci` scope in `scripts/operator/facts`, `process.py` and `sanitize.py` OCI parts), no `acceptance` script exists on `main` (remove only if the inventory finds one), the lab operator VM entries of `scripts/operator/machine-profiles.toml` and `tests/operator/test_profiles.py`, `toolchain/python/operator.in` and `operator.lock`, the `oci-cli` and `opentofu` entries of `toolchain/manifest.toml`, `docs/operations/gate-0-audit.md`. Tests: `tests/operator/test_oci_facts.py`, `fakes_oci.py`, and the OCI parts of `test_scripts.py`, `test_modes.py`, `test_process.py`, `test_operator_inputs.py`, `test_githubstate.py`; `tests/toolchain/test_cli.py:94` (`tofu`), `test_lock_from_wheels.py` (`oci-cli` sample); `ansible/group_vars/all.yml`, `ansible/roles/operator_system/tasks/main.yml` OCI parts. Docs and links: the `docs/README.md` rows (Gate 0 audit; operator and machine-profile rows), `docs/operations/operator.md` (lab operator VM sections and the links at lines 201, 211), `README.md:2`, `.gitignore:1-9`. `CLAUDE.md`: only the lines naming the lab operator VM. Jobs stay (`operator-profile`, `operator-limits`), so `EXPECTED_NEEDS` (`tests/ci/test_required_aggregate.py:18`) and `tests/quality-gate/run.sh:278,601` do not change unless the inventory shows a job loses its subject. Records the first PA-A1 run | PR 0 | PC-8 (and PC-6 if a workflow changes) |
| 2 | `lab-profile` | The CR-2 `builder` profile becomes the lab profile (`ansible/builder.yml` into `ansible/lab.yml`; the manifest `profiles` field of every tool; `PROFILES` in `scripts/toolchain_engine/manifest.py:12`; `tests/ansible/test_profiles.py`, `tests/toolchain/*`). New shared SSH hardening role (LC-13, OC-10) and the key rules of PA-16; managed settings and managed CLAUDE.md from `workspace/claude-user/`, merged; **this PR moves the generic deny entries into managed settings** (PA-5); the second-login confirmation before the sshd switch. The `builder-profile` job becomes the PA-28 job (`debian:13` by digest, two users, one key each); `EXPECTED_NEEDS`, `tests/quality-gate/run.sh:278,601`, and the S-23 fixture follow the new job name; required names unchanged. Extends `operator_paths` with the lab profile paths in its body. Approver check PA-A28 recorded in the PR | PR 1 | PC-6, PC-8 |
| 3 | `token-step-lab-check` | Root-owned token step and lab check (LC-1 to LC-15) with the pre-disposal mode (PA-44), installed by the lab profile. PA-19(a) deny entries added to the three copies (`.claude/settings.json:59-72`, `workspace/claude-user/settings.json`, `workspace/claude-user/required-deny.txt:55-68`) with the drift test (`tests/workspace/run.sh:391-393`). **AC1-8 evidence moves** to token step fixtures (PA-A25): the checks of `tests/workspace/run.sh:383-393` are re-created and run in the PA-28 job; the old tests stay until PR 7. LC-10, PA-43 (PROJECT.md paths), LC-14 fixtures | PR 2 | PC-8 |
| 4 | `operator-profile` | The operator profile retargeted to Debian 13 (`ansible/operator.yml`, roles `operator_*`), using the shared SSH hardening role; operator configuration with per-project installation (PA-42) and the operator check (OC-1 to OC-12). `facts --privileged` and the sudo parts of `scripts/operator/setup` removed (OC-8, OC-9); `setup` retargeted or replaced (O-8). `scripts/operator/machine-profiles.toml` for Debian 13. PA-22 endpoint allowlist in the operator code check (`scripts/checks/operator_contract.py`; shared with the template, so design interaction I-9 is settled first). `tests/toolchain/test_operator_profile.py`, `tests/ansible/test_operator_profile.py`, `tests/operator/test_profiles.py`, `PROFILES`; the `operator-profile` and `operator-limits` jobs fold into the PA-28 job or are retargeted and `EXPECTED_NEEDS` follows | PR 3 | PC-6, PC-8 |
| 5 | `arm64-config` | ARM64 removal, step 1: remove the `arm64` entry (`runner`, `runner_private`) from `architectures` in `config/project.yaml`, with the `toolchain-arm64` job still running. Changes only that file plus the tests that read this repository's own configuration (inventoried); the generic fixtures under `tests/pr-contract/fixtures/pc9/` keep arm64 as sample data. The manifest and `scripts/toolchain check` still require both architectures at this step | PR 4 | none |
| 6 | `arm64-job` | ARM64 removal, step 2: the arm64 entry of the `toolchain` matrix in `.github/workflows/ci.yml` (the `toolchain-arm64` check disappears; `toolchain-amd64` stays; the aggregate `needs` on `toolchain` is unchanged), the arm64 artifacts and checksums of every tool in `toolchain/manifest.toml`, and `scripts/toolchain check` reads the architectures from `config/project.yaml` (PA-30); the engine stays generic. Text in `.github/PULL_REQUEST_TEMPLATE/toolchain.md`; fixtures `tests/toolchain/test_manifest.py` (amd64-only config; amd64 and arm64 config requires both), `tests/quality-gate/fixtures/toolchain/`. Open point O-4 (extra artifacts) and O-15 | PR 5 | PC-6 (workflow) |
| 7 | `remove-superseded` | `workspace/restore.sh`, `verify.sh`, `workspace/lib/`, `workspace/repos.txt`, `tests/workspace/` (after PR 3 moved AC1-8), `docs/operations/workspace-restore.md` and its row, the remnants of the Ubuntu operator profile (the roles `operator_firewall`, `operator_lock`, `operator_sudo`, `operator_system`, and any other role no profile uses), `PROFILES` reduced to `lab` and `operator`, `tests/ansible/opt-in-role-test.sh` if unused. Checks and catalogue rows only if their subject is gone (`tests/quality-gate/catalogue.tsv:22-23`). Final PA-A1 run for files outside `CLAUDE.md` | PR 6 | PC-8 |
| 8 | `project-toolchains` | PA-34: the lab admin installs project toolchains with the root-owned `scripts/toolchain` into `/opt/ai-lab/project/` from a merged commit, a tag, or a user-supplied SHA; project package list (Debian archive only); smoke tests as the AI user; the project's own `scripts/toolchain` is never run | PR 7 | PC-8 |
| 9 | `runbooks-claude-md` | `docs/operations/ai-host.md` (hosts of PA-18, LC and OC summary, the manual probe of PA-A13), lab and operator runbooks (`operator.md` rewritten), the new-project runbook (PA-45: repository and rulesets, lab VM and lab setup, token step, clone and `initialize-project`, operator script installation, allowlist audit including the new repository), the `CLAUDE.md` rewrite (lines 3, 8 (baseline link to v0.2), 14 to 16 ("Where you run" describes a disposable single-project lab VM), 34, 49 (amd64 only), 54 (`terraform fmt/validate`) and the PA-19 rule), `workspace/claude-user/CLAUDE.md`, `docs/README.md`. Final PA-A1 run including `CLAUDE.md` | PR 8 | none |
| 10 | `preset` | The preset for the template: `docs/PLATFORM.md` and the deny list source (ADR-008 decision 14), without OCI or operator content as PA-A9 reads (O-14). Carries `Closes #57` | PR 9 | none |
| T | template CR (template repository) | PA-19 and its deny entries into the template's owned CLAUDE.md and required-deny list (PA-25); a CR of that repository, not started from here | design merged | per that repository |

## 3. Criteria by PR (the reverse of the PR column in the acceptance criteria)

| PR | Criteria |
|---|---|
| design (PR 58) | PA-A2, PA-A17 |
| 0 | PA-A6, PA-A10 |
| 1 | PA-A1 (first run), PA-A5, PA-A10, PA-A16 |
| 2 | PA-A5, PA-A10, PA-A11, PA-A16, PA-A18, PA-A28, PA-A29 |
| 3 | PA-A5, PA-A8, PA-A10, PA-A13, PA-A18, PA-A25, PA-A26, PA-A31, PA-A32 |
| 4 | PA-A5, PA-A10, PA-A14, PA-A15, PA-A16, PA-A18, PA-A21, PA-A26, PA-A27, PA-A29, PA-A30 |
| 5 | PA-A5, PA-A10, PA-A16, PA-A19 |
| 6 | PA-A5, PA-A7, PA-A10, PA-A16, PA-A19 |
| 7 | PA-A1, PA-A5, PA-A10, PA-A16 |
| 8 | PA-A5, PA-A10, PA-A23 |
| 9 | PA-A1 (final), PA-A3, PA-A4, PA-A10, PA-A13 |
| 10 | PA-A9, PA-A10 |
| T | PA-A13 (the template side) |

PA-A12, PA-A20, PA-A22, and PA-A24 are removed. Every other criterion PA-A1 to PA-A32 appears in at least one row, and every row's criteria appear in the PR column of the acceptance table.

## 4. Preconditions and user-only steps

| Step | Who | When | What |
|---|---|---|---|
| U-1 | Approver | After the design PR merges (Q6) | Close issue #16 and PR #17 (the OCI seed), issue #18, and the open CR-18 PRs (the CR-18 README row names PR 7a in review; the approver lists the set that is open then), each by a PR comment that names this CR. CR-18's generic parts are carried by PA-21 and the amended ADR-011. Not before the merge. A session closes them only if the approver tells it to |
| U-2 | Approver | With PR 10 | `Closes #57` is carried by PR 10 only. The design PR and PRs 0 to 9 declare `Implements: #57` |
| U-3 | Approver | Outside the repository | Decommission what the postponed OCI plans may have created: any tenancy resource, budget, or policy, and any token T2 or T3 still unrevoked. Nothing here touches them |
| U-4 | Approver | PA-26 | Create no release tag during the removal sequence (open point O-3); cut the first tag after the last removal PR if the strict reading stands |
| U-5 | Lab admin | After PR 3 and a tag | Run lab setup (dry run first) on a fresh VM, record the key type and forwarding settings (PA-A28) |
| U-6 | User | After lab setup | As the AI user in a plain SSH terminal: the token step, then the lab check; enter T1 only there |
| U-7 | Operator admin | After PR 4 and a tag | Run the operator configuration (dry run first), then the operator check; install each project's scripts at its release tag |
| U-8 | Approver | After PR 10, before the template's Stage 5 real run (Q3) | Rename the repository (a repository setting; the new name is the approver's) |
| U-9 | Approver | Template repository | Start the template CR of PA-25 |

## 5. Revert order

Newest PR first: 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0, then the design PR. A revert of a removal PR restores the removed code and its tests together from history; reverting PR 6 before PR 5 keeps the manifest and the configuration in step. Before implementation, reverting the design PR removes ADR-012, baseline v0.2, the ADR amendments, and the CR-57 files in one commit.

## 6. Interim status of the superseded text

ADR and baseline text describes the target from the design merge; the merged code behaves as before until the matching PR merges. Day-to-day work follows the code and `CLAUDE.md`, and nobody is asked to follow an ADR-012 procedure that no script yet supports.

| Text | Status after the design merges | Until |
|---|---|---|
| ADR-002 | Superseded; it had no merged code | — |
| ADR-011 dropped parts (OCI scope of `facts`, lab operator VM entries, Ubuntu operator profile, `facts --privileged`) | Dropped in text; the code still exists and passes its tests | PR 1 (OCI), PR 4 and 7 (profile, privileged) |
| ADR-001 section 4a and decision 7 (lab setup, token step) | Target text; `workspace/restore.sh` and `docs/operations/workspace-restore.md` remain the working procedure | PR 7 |
| ADR-005 profiles (`lab`, `operator` on Debian 13, amd64 only) | Target text; the `builder` profile, the Ubuntu operator profile, and the arm64 job remain | PR 2, 4, 6 |
| PC-8 paths | Hardcoded in `rules.py` (ADR-003 text agrees) | PR 0 |
| `CLAUDE.md` | Unchanged; its Never lines are stricter than or equal to ADR-012 | PR 9 (PR 1 edits only the lab operator VM line) |
| `docs/README.md`, baseline v0.1 links | Baseline v0.1 carries the superseded banner; the file stays | PR 9 updates `CLAUDE.md` to v0.2 |
| Operator machine | Runs the last release tag cut before the first removal; no new tag until the order allows it (O-3) | PR 7 or later |

## 7. Checklist (each PR keeps its own)

- [ ] Draft PR opened with the implementation template, `Implements:` and `Design:` filled in, PC-6 and PC-8 sections when they apply
- [ ] Inventory of the PR's files reported first (removal PRs)
- [ ] Fixtures and tests written first for the PR's criteria
- [ ] Implementation done, code and its tests, rows, and links together
- [ ] `./scripts/quality-gate.sh` passes; any skipped check is reported
- [ ] CI green
- [ ] Marked ready for review
