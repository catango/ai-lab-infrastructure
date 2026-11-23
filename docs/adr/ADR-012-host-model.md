# ADR-012: Host Model: AI Lab, Operator Machine, and Their Contracts

| Field | Value |
|---|---|
| Status | **Proposed** (CR-57 design PR 58; accepted when that PR is merged by the approver) |
| Date | 2026-11-23 |
| Repository | `ai-lab-infrastructure` |
| Change request | CR-57 (issue #57) |
| Scope | The two machine types the platform configures or relies on: the AI lab (zone Z1) and the operator machine (zone Z6), plus the lab host that carries the AI lab (zone Z8, outside the platform). Credential placement, accounts and keys, the lab contract, the operator contract, lab setup and operator configuration, the token step, project toolchains, security updates, the multi-project operator machine, project credentials, and the pre-disposal check. Not the GitHub trust model (ADR-001), the operator script rules (ADR-011), the toolchain engine (ADR-005), or egress filtering (another project) |
| Related | ADR-001 (trust model; amended to refer here), ADR-005 (toolchain; amended), ADR-011 (operator script rules; amended), ADR-008 and ADR-009 (read, not edited), CR-57 design |

> This ADR records a decision. It does not create a machine, an account, a key, a credential, or a script, and it authorizes none of them.
> Detail, rationale, and the approver's decisions are in `docs/cr/CR-57/design.md` (review of 2026-11-23T18:27:31Z). Labels PA-n, LC-n, OC-n, and RR-Pn are those of the design. The platform names no host, address, user, or key (G-5).

---

## 1. Context

- The AI lab is a disposable VM for exactly one project (this repository counts as one), hosted on the lab host and reached through it by `ProxyJump`. Provisioning is outside the platform. The platform starts from a given Debian 13, x86-64 VM with the AI user and the lab admin reachable over SSH. Discarding a lab destroys its disk.
- The operator machine is a fresh Debian 13, x86-64 VM with internet access, provided outside the platform, with the operator user (no sudo) and the operator admin (sudo) reachable over SSH. One operator machine serves this repository and every project. It is long-lived; a rebuild is a fresh VM plus the operator configuration.
- Claude Desktop on the Windows client opens SSH sessions to the AI lab; Claude Code runs there as the AI user. The client may also hold SSH access to the operator machine. The Windows SSH client is outside the platform.
- The AI lab may reach project-specific resources configured by the project. The operator machine is not reachable from the lab host and so not from the AI lab. Egress design and filtering come from another project; SSH hardening of both machines is a platform requirement.
- The lab admin applies all AI lab configuration; the operator admin applies all operator configuration. The AI user and the operator user apply none.

## 2. Decision

1. **Zones** (PA-4, PA-39).

   | Zone | Component | Trust level | Holds |
   |---|---|---|---|
   | Z1 | AI lab: the AI user and the lab admin | Per-project disposable VM, AI-operated (AI user) and human-administered (lab admin) | Clones of the project's repositories; T1; project non-production credentials (PA-43); the inference credential while a session runs; root-owned managed settings, gate tools, token step, and lab check |
   | Z6 | Operator machine: the operator user and the operator admin | Human-provided, long-lived, separate from every AI lab, operated by the approver | Per-project operator scripts at release tags (root-owned); per-project output directories; during runs only: T2, T3, and production credentials in the script process |
   | Z8 | The lab host (jump host and hypervisor) | Outside the platform; full control of the AI lab | Whatever the AI lab holds while it runs, including T1 and the inference credential (RR-P5) |

   Z0 (Windows client), Z3 (GitHub), and Z5 (Anthropic) are as in ADR-001. No other zones exist.
2. **Credential placement** (PA-13). The AI lab holds T1 and project-scoped non-production credentials recorded in the project's PROJECT.md (decision 11). Production and infrastructure-changing credentials, T2, and T3 exist only on the operator machine, used by reviewed scripts from a release tag, prompted or short-lived. No credential of the personal account is on the AI lab. The lab admin and the operator admin hold no credentials.
3. **Accounts and keys, enforced on the servers** (PA-14). Four accounts (AI user, lab admin, operator user, operator admin), each with its own key; no key is shared between accounts on a machine (checked). The lab admin, the operator user, and the operator admin use `sk-ssh-ed25519` keys with verify-required if the Windows client supports them, otherwise passphrase-protected file keys. The AI user's key has a passphrase if Claude Desktop can use one, otherwise none (RR-P6). The lab setup PR records which applies.
4. **Lab contract** LC-1 to LC-15 (section 4; PA-15).
5. **Lab setup** (PA-16, PA-31) is the Ansible lab profile, run by the lab admin from a clone the admin owns at a release tag; dry run by default (check mode with diff); idempotent. On a fresh VM it accepts the one provisioned key of the AI user and of the lab admin and fails when a managed account has no key or more than one, a key is shared between accounts, root or any other account has a key, the AI user's `~/.ssh` holds a private key, or `AuthorizedKeysCommand`, `TrustedUserCAKeys`, or `AuthorizedPrincipalsFile` is set. The checks fail when sshd reads keys from any location other than the root-owned one, and warn on an inert leftover `authorized_keys` file in a user's home. Lab setup refuses to run except at a release tag; the tag check is a pre-task of the lab playbook. It applies: archive prerequisites; the gate tools into `/opt/ai-lab`; root-owned managed settings and a managed CLAUDE.md carrying the settings of `workspace/claude-user/` and the non-relaxable rules of its CLAUDE.md (merged, never replaced); the managed CLAUDE.md holds only rules that must not be relaxed and states that nothing in any other instruction file relaxes them, and no user-level CLAUDE.md is loaded on a set-up lab; a project's seeded `.claude/deny.platform.txt`, read through the input channel of decision 9, is merged into the managed settings; the system-wide git identity; the provisioned keys copied to the root-owned authorized-keys location, with sshd switched only after a second login with each account is confirmed while the current session stays open; LC-13; unattended security updates; project toolchains and package lists (decision 9); and the root-owned token step and lab check. It prints the host key fingerprints for information, removes nothing, writes nothing into a user's home, and never executes from a path the AI user can write.
6. **What the user runs on the AI lab** (PA-17). Logged in as the AI user in a plain SSH terminal: only the root-owned token step (T1 login; it refuses without a TTY or inside a Claude Code session) and the read-only lab check.
7. **Operator configuration** (PA-20, PA-31) is the Ansible operator profile, run by the operator admin from a clone the admin owns at a release tag; dry run by default; idempotent. On a fresh VM it applies the key rules of decision 5 to the operator user and the operator admin, with the operator user's `~/.ssh` in place of the AI user's. It refuses to run except at a release tag (a pre-task of the operator playbook) and as the operator admin. It installs archive prerequisites (the operator profile takes manifest membership for Python 3 and git only and installs no gate tools), sets the operator user without sudo, creates the output directories (decision 12), applies OC-10 only after a second login is confirmed, enables unattended security updates, installs the operator scripts per decision 12, prints the host key fingerprints, and ends by running the operator check. It never touches credentials, the operator user's output files, or production configuration, and writes nothing into a user's home.
8. **Operator contract** OC-1 to OC-12 (section 5; PA-21).
9. **One shared SSH hardening role** serves the lab and operator profiles (PA-31). **Project toolchains** on the AI lab (PA-34) are installed by the lab admin with the root-owned `scripts/toolchain` from the platform's release tag, from the project's CI manifest read as "the tools CI uses" (ADR-008 decision 8 unchanged), into `/opt/ai-lab/project/`, amd64 only, with the checksum rules of the gate tools; dry run by default. A project package list of Debian archive packages, with no third-party apt sources, is applied by the lab admin through lab setup. Inputs come from an anonymous clone at a merged commit or tag, or are extracted from the AI user's clone at a commit SHA the user supplies. Smoke tests of project tools run as the AI user, never as root. The project's own copy of `scripts/toolchain` is never executed.
10. **Security updates** (PA-36). Lab setup and the operator configuration enable unattended Debian security updates. The operator admin schedules reboots of the operator machine. An AI lab is rebuilt rather than patched in place when a reboot is not enough.
11. **Project non-production credentials** (PA-43). Entered by the user as the AI user in a plain SSH terminal, never in a Claude session; stored with file mode 0600; their names and paths are listed in the project's PROJECT.md, and the project's deny list blocks reads of those paths.
12. **Multi-project operator machine** (PA-42). Each project's operator scripts are installed by the operator admin at that project's release tag into a root-owned directory per project; each project has its own output directory (mode 0700); runs are one at a time; T2 and T3 are created per run and limited to that project's repositories. One operator user serves all projects (RR-P11). **One exception:** the allowlist audit of the new-project runbook and AC1-1 runs from this repository's `facts` with a read-only T3 that selects all repositories of the personal account. In v1 projects get no `github-setup` and no desired-state file; their repository settings follow ADR-009 decisions 8 and 13.
13. **Pre-disposal mode** (PA-44). The lab check has a read-only pre-disposal mode that lists every repository under `~/work` with uncommitted changes or unpushed commits; the user runs it before a lab is discarded.

## 3. What the contracts do not do

The platform cannot verify who owns a login key (RR-P10) or what the lab host does (RR-P5). The contracts bind the machines the platform sets up; a project that needs more states it in its own PROJECT.md. Every contract item is marked **checked** (a read-only check or fixture verifies it) or **declared** (scripts or procedure must follow it and review verifies it).

## 4. Lab contract (Debian 13, x86-64)

LC-5 stays undefined and is never reused; no stand-in item is added.

| ID | Requirement | Mark |
|---|---|---|
| LC-1 | Debian 13 on x86-64 | checked |
| LC-2 | The AI user has no sudo and no root-equivalent group such as sudo, docker, lxd, or disk | checked |
| LC-3 | The lab admin is never a Claude Desktop target: no `~/.claude/` in its home | checked |
| LC-4 | Root-owned managed settings and managed CLAUDE.md present | checked |
| LC-6 | `SSH_AUTH_SOCK` unset in sessions, no private key in the AI user's `~/.ssh`, clone remotes HTTPS | checked |
| LC-7 | T1 login, scopes, and file mode 0600 | checked |
| LC-8 | The effective git identity is the machine account's noreply address | checked |
| LC-9 | Gate tools at the manifest versions | checked |
| LC-10 | No production or infrastructure credential, by names only | checked |
| LC-11 | The AI user's key carries `restrict,pty` | checked |
| LC-12 | The AI user and the lab admin have different keys | checked |
| LC-13 | sshd: public-key login only, for listed users, no root login; no SHA-1 key exchange or MAC; strict key exchange on; no agent forwarding, X11, tunnels, TCP forwarding, or user rc file; authorized keys read from a root-owned location and no other (an inert leftover `authorized_keys` file in a user's home is a warning); `AuthorizedKeysCommand`, `TrustedUserCAKeys`, and `AuthorizedPrincipalsFile` unset | checked |
| LC-14 | The token step runs from a root-owned path with a clean environment and no shell startup files | checked |
| LC-15 | Unattended Debian security updates enabled | checked |

If a Claude Desktop session on a set-up lab needs a forwarding or key permission beyond LC-11 and LC-13, only that named permission is added, with the reason recorded in the PR.

## 5. Operator contract (Debian 13, x86-64)

| ID | Requirement | Mark |
|---|---|---|
| OC-1 | No shared storage, identity, key, or route with the AI lab, and never a Claude Desktop target: no `~/.claude/` in any user's home | checked |
| OC-2 | A project's operator scripts run only from the root-owned installation of that project's release tag, contained in its `origin/main` | checked |
| OC-3 | Dry run by default | declared |
| OC-4 | Credentials prompted, short-lived, and kept in the script process | declared |
| OC-5 | Sanitised output | declared |
| OC-6 | Debian 13 on x86-64, Python 3, git | checked |
| OC-7 | The separation test passes before the first credential | declared |
| OC-8 | The operator user has no sudo | checked |
| OC-9 | No root-only facts script; root-only facts are manual lines | declared |
| OC-10 | The LC-13 settings for the operator user and the operator admin | checked |
| OC-11 | The operator user and the operator admin have different keys | checked |
| OC-12 | Unattended security updates enabled; the operator admin schedules reboots | checked |

OC-3, OC-4, OC-5, OC-7, and OC-9 are declared (approver, round 2, O-2). PA-A26 is supporting evidence for the in-process part of OC-4.

## 6. Hosts the AI user needs (PA-18)

Input for the network project; the AI host document of the implementation lists them: `api.anthropic.com`, `platform.claude.com`, `claude.ai`, `github.com`, `api.github.com`, `code.claude.com`, and `downloads.claude.ai` only if the lab fetches the Claude Code engine itself (the lab setup PR records which applies). Managed settings disable claude.ai MCP connectors, nonessential traffic, and artifacts.

## 7. Consequences

**Positive:** the AI user cannot change the managed settings, the gate tools, the authorized keys, or the token step; the operator machine shares nothing with an AI lab; key separation and sshd settings are checked, not trusted.

**Negative:** four accounts and four keys to provision per lab and operator machine; every lab needs a lab admin run before first use; lab setup and operator configuration run only at a release tag. The approver may cut a tag at any plan PR boundary whose PA-A16 run is green, except between the two ARM64 PRs (PR 5 and PR 6); the operator machine moves to a new tag only at or after the operator profile PR (PR 4); the approver check PA-A28 runs on a tag cut after the lab profile PR (PR 2); the first AC1-7 timing is taken at the first real lab setup from a tag that contains the token step and lab check (PR 3) and is recorded in the operator profile PR (PR 4) (design O-3, C-3, I-4).

**Residual risks** (design section 9): RR-P2 (guardrail strength depends on the lab admin running lab setup), RR-P4 (no post-quantum key exchange), RR-P5 (the lab host controls the AI lab completely), RR-P6 (key files and clipboard on the Windows client), RR-P7 (data can leave through any repository T1 can write to), RR-P10 (login keys are set by provisioning), RR-P11 (a project's operator script can read other projects' output files and reach every production environment the operator machine reaches). Assumption NA-6: AI labs cannot reach one another.

## 8. Acceptance criteria

PA-A8, PA-A11, PA-A13, PA-A14, PA-A16, PA-A18, PA-A21, PA-A23, PA-A25 to PA-A32 of `docs/cr/CR-57/acceptance-criteria.md`, verified in the implementation PRs.
