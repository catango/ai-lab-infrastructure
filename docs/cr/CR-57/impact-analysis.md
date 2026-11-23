# CR-57 Impact analysis

Follows the approver's decisions of 2026-11-23 (review on design PR 58, 18:27:31Z). Facts are read in `main` at `85360e8`; nothing was run.

## 1. What changes

In this design PR, under `docs/` only (PC-4):

- The CR-57 files are revised.
- New: [ADR-012](../../adr/ADR-012-host-model.md) (Proposed) and [baseline v0.2](../../architecture/baseline-v0.2.md).
- Edited bodies and headers, effective when this PR is merged: ADR-001 and ADR-005 (amended), ADR-011 (amended, not superseded), ADR-002 (superseded header), baseline v0.1 (a "superseded by v0.2" banner; the file stays so existing links survive).
- `docs/README.md`: CR-57, ADR-012, and baseline v0.2 rows and the changed statuses.
- Not edited: ADR-003, ADR-008, ADR-009, ADR-010 (PA-A2). The note on PC-8 paths is in the design only.

No code, workflow, setting, ruleset, secret, label, tag, or template-repository change.

Later, in the implementation PRs (see the plan): the `operator_paths` configuration, removal of the OCI parts, the lab profile and its CI job, the token step and lab check, the operator profile and operator check, ARM64 removal in two PRs, removal of the superseded workspace restore and Ubuntu operator profile, project toolchains, the runbooks and `CLAUDE.md` rewrite, and the preset.

## 2. Affected components and records

| Item | Effect |
|---|---|
| ADR-001 | Amended: refers to ADR-012 for the host model; zones Z1, Z6, Z8 (Z2, Z4, Z7 removed); credential matrix keeps GitHub rows; sections 1, 4a, 5, 6, 9, 10, T1 rotation, RR-8, RR-9 updated. B1 and B3 generalised. CR-43's amendments preserved |
| ADR-002 | Superseded. It was Accepted (conditional on Spike S2) and had no merged code; baseline D2, D12, and CHG-002 go with it |
| ADR-005 | Amended: profiles `lab` and `operator` on Debian 13 run by the admin users; amd64 only (the engine and schema stay architecture-generic); OpenTofu and the OCI CLI lock go |
| ADR-011 | Amended, not superseded: Z7, OCI, alarms, lab access, and the Ubuntu operator profile dropped; the rules for operator scripts stay; decision numbers cited by ADR-008 and ADR-009 stay |
| ADR-012 | New: zones Z1, Z6, Z8; credential placement; accounts and keys; lab contract LC-1 to LC-15; operator contract OC-1 to OC-12; lab setup, token step, operator configuration, project toolchains, security updates, multi-project operator machine, project credentials, pre-disposal check |
| ADR-003, ADR-008, ADR-009, ADR-010 | Not edited. Interactions are listed in design section 10 and decided later |
| ADR-004, ADR-006, ADR-007 | Withdrawn in baseline v0.2; numbers not reused (they were never written) |
| CR-18 | Closed after the design merges, by PR comment (Q6); its generic parts live on in PA-21 and the amended ADR-011 |
| `scripts/operator/` | Stays under Q1: `github-setup`, `facts` (host and GitHub scope), `github-desired-state.toml`. Removed: the OCI scope, the lab operator VM entries. `facts --privileged` and the sudo parts of `setup` go (OC-8, OC-9) |
| `ansible/`, `toolchain/`, `workspace/` | `builder` becomes the lab profile; the operator profile moves to Debian 13; the shared SSH hardening role is new; `workspace/restore.sh`, `verify.sh`, `lib/`, `repos.txt` are removed after the token step carries AC1-8; `workspace/claude-user/` stays as the content source of the managed settings and managed CLAUDE.md |
| `config/project.yaml` | New `operator_paths`; `architectures` loses arm64 in plan step 5 |
| `.github/workflows/ci.yml` | The `builder-profile` job becomes the PA-28 job; the arm64 matrix entry goes in step 6; `operator-profile` and `operator-limits` are retargeted or folded; required names `pr-contract` and `quality-gate` unchanged |
| `scripts/pr_contract/rules.py` | PC-8 reads `operator_paths` from the base commit, failing closed |
| `CLAUDE.md`, `README.md`, `.gitignore`, the three deny-list copies | Owned by named plan PRs (see the plan); `CLAUDE.md` keeps its rules until the PR that removes their subject |
| CR-43 | PR 6 (settings documentation and desired state) is not re-scoped (Q1); it edits a PC-8 path |
| CR-39, CR-45, `ai-software-template` | Unaffected by edits; interactions in design section 10. The template repository holds only a README and a licence; the preset is not built |

## 3. Security and privacy

- The GitHub trust model is unchanged: machine account, T1 entered by the user in a plain SSH terminal, rulesets, deny rules, `forbidden-api`, and the approver as the only one who approves and merges. T1 reaches every repository of the machine account from every AI lab (RR-9, accepted; a follow-up CR evaluates App tokens).
- The attack surface shrinks: no OCI credential, no lab operator machine, no Terraform path.
- It gains enforced host controls: four accounts with separate keys, sshd hardening, root-owned managed settings, a root-owned token step, and read-only checks (ADR-012). Guardrail strength depends on the lab admin running lab setup (RR-P2).
- Accepted residuals: the lab host controls the AI lab (RR-P5); key files and the clipboard on the Windows client are outside the platform (RR-P6); data can leave through any repository T1 can write to (RR-P7); login keys are set by provisioning (RR-P10); a project's operator script can read other projects' output files (RR-P11).
- No host, address, user, or key appears in any file (public repository rules). Public service names in PA-18 are not identifiers.

## 4. Operational impact on the approver

- Reviews the design and the ADR text; posts the architecture discussion's handoff as a review on this PR.
- After the merge: closes issue #16, PR #17, issue #18, and the open CR-18 PRs by comment (Q6); renames the repository after the implementation PRs (Q3); starts the template CR for PA-25.
- Provides the AI lab VMs, the operator machine, and the keys (G-13, G-14); the platform checks their number and separation, not their owner.
- Creates release tags at a PR boundary whose PA-A16 run is green, never between plan PR 5 and PR 6; the operator machine moves to a new tag only at or after PR 4 (PA-26 as narrowed by O-3).
- After the merges: tells a session to open the follow-up design PR R-1 (ADR-003 and ADR-009 text, which this PR leaves unedited) and, after the rename, the rename change PR.

## 5. Dependencies and assumptions

- CR-55 is withdrawn (PR 56 and issue 55 closed).
- CR-43 PR 4 is merged; CR-43 PR 5 and 6, CR-39, and CR-45 continue unchanged.
- Verified at `85360e8`: ADR-002 and baseline D2 and D12 are Accepted; `docs/PLATFORM.md` does not exist on `main`; the removal checks and tests named in design section 3 exist as listed.
- Not verified: how much of `tests/quality-gate` and CI beyond the listed paths refers to operator or lab content (plan PR 1 inventories it); the points of design section 12.
- Assumption NA-6: AI labs cannot reach one another (network project); the platform does not test it. Egress design and filtering belong to another project (G-9).

## 6. Cost and capacity

No cost. The zero-cost rule of ADR-009 decision 12 stays for GitHub and is restated in baseline v0.2 without OCI. ADR-002 and baseline D2 and D12 were **Accepted**, and D3 to D7 were Proposed or Pending design; all fall away with the OCI plans. Machines are provided outside the platform.

## 7. Rollback

Before implementation, revert the design PR (it removes ADR-012, baseline v0.2, the amendments, and the CR files in one commit). After implementation, each PR is a normal revert in newest-first order (plan section 5); removed code stays in history. The removal order keeps the gate green after every PR.

## 8. Alternatives considered

See design section 8.
