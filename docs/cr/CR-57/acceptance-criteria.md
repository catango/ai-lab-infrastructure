# CR-57 Acceptance criteria

Verified by the implementation PRs of the plan. "Gate check" means a fixture test run by `./scripts/quality-gate.sh` and by CI. "CI" means a green run of the named job. "Approver check" is a read-only check that the approver runs and records; Claude Code does not. The criteria bind when the design PR is merged and assume the recommended answers to Q1 to Q6 (design section 7).

| ID | Criterion | Evidence |
|---|---|---|
| PA-A1 | After the removal PRs, the repository has no `scripts/operator/`, `tests/operator/`, `ansible/`, operator or lab manifest profile, OCI CLI call, Terraform file, or document of the operator tier; a case-insensitive search for OCI, Terraform, operator VM, and lab VM over files outside `docs/adr/` and `docs/cr/` finds nothing | Approver check with the recorded `rg` output; PR diffs |
| PA-A2 | The records read as in design section 5 with the approver's text: ADR-002 and ADR-011 superseded, ADR-001 and ADR-005 amended, baseline v0.2 and `docs/README.md` consistent; ADR-003, ADR-008, ADR-009, ADR-010 unchanged | Review of the design PR and of plan PR 6 |
| PA-A3 | `docs/operations/ai-host.md` states HC-1 to HC-6, names no host, address, user, or key, and passes `public-repo-hygiene` | Gate check; review |
| PA-A4 | This repository's `CLAUDE.md` has the rule PA-3, keeps the instruction-trust rule and the Never list for merge, approval, settings, tags, `sudo`, credentials, MCP, and Actions, and has no OCI, lab VM, operator, or workspace-restore line | Review; the removal PR for each subject deletes its line |
| PA-A5 | After each removal PR the gate and CI are green, the required names `pr-contract` and `quality-gate` are unchanged, the aggregate needs exactly the remaining jobs, and checks and fixtures of removed code are deleted with it | CI; gate check `workflow-policy` fixtures (WP-16) |
| PA-A6 | `pr-contract` still enforces PC-1 to PC-9; PC-8 reads its paths from configuration with an empty value here; a fixture shows PC-8 active for a configured path and inactive for the empty value | Gate check and `pr-contract` fixtures |
| PA-A7 | The manifest has one gate profile; `scripts/toolchain check` passes; every download keeps checksums for both architectures; `toolchain-amd64` and `toolchain-arm64` install and smoke every tool | Gate check; CI |
| PA-A8 | `scripts/bootstrap` installs only the user-level Claude Code configuration, checks HC-1 to HC-6 read-only, has `--dry-run`, uses no `sudo`, never prints or reads a credential, and refuses to overwrite a changed file without the flag | Fixtures with a temporary home |
| PA-A9 | The preset of this repository for the template (`docs/PLATFORM.md`, the source of `.claude/deny.platform.txt`) has no OCI or operator content | Review of the preset change PR |
| PA-A10 | The security invariants hold: the deny rules, `forbidden-api`, T1 handling (AC1-8), and B1 and B3 are unchanged; the existing `pr-contract` and gate tests for them pass | Existing tests pass unchanged |
