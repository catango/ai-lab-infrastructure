# CR-18 Acceptance criteria

Verified by the implementation PRs and by the approver's acceptance run. "CI" means a green run of the named check on a test PR.
"Approver" means a test only the approver can run on an operator machine, in the lab, or in GitHub. Evidence is reported as
yes/no, counts, and sizes, never identifiers, addresses, or names.

## Separation (U), approver

| ID | Criterion | Evidence |
|---|---|---|
| U-1 | Host separation, per operator machine: no shared mount or home with an AI host, no AI-host key in the operator's `authorized_keys`, no route from the AI hosts to the machine, and no `~/.claude/remote/`. The operator's sudo asks for a password (no `NOPASSWD` rule), and the operator is in no other privileged group. | Approver's tests on each machine, results yes/no. Run after the first operator-profile apply and before the first credential on that machine |
| U-2 | `workspace/verify.sh` V-4 still passes on Z1 when run as the AI user, and no operator credential exists on Z1 or Z2. | Output of the verify script, and the approver's inspection |
| U-3 | No credential, token, or raw response from an operator run exists in the repository, in an AI user's home, or in shell history. | Approver's inspection after a run; `public-repo-hygiene` on any PR |
| U-4 | The machine account cannot create, move, or delete a `v*` tag (the tag ruleset of R3). | Approver's negative test from the machine account, results yes/no |

## Script contract (S), CI

S-8 and S-9 are not used: the setup criteria are P-1 to P-8.

| ID | Criterion | Evidence |
|---|---|---|
| S-1 | Every script under `scripts/operator/` accepts `--dry-run` and `--apply`, runs as a dry run when it gets neither (it changes nothing), and exits with a usage error when it gets both. | Test enumerating the scripts, run in CI (`gate-tests`) |
| S-2 | A dry run makes no write call: with a stub CLI and a stub HTTP server that record calls, a dry run records none that change state. | Tests with stubs |
| S-3 | A script refuses to run with local changes in the clone, and refuses any commit that is not a release tag's commit contained in `origin/main`. | Tests in a temporary repository |
| S-4 | A second `--apply` run changes nothing. | Tests with stub state |
| S-5 | The sanitiser removes OCIDs, IPv4 and IPv6 addresses, and email addresses from sample output, and a value it cannot classify becomes a placeholder. | Unit tests with sample outputs |
| S-6 | No script contains `eval`, a download piped to a shell, a Terraform call, or an OCI write call. `sudo` appears only in `setup` and in `facts --privileged` with the listed read-only commands (`sshd -T`, `nft list ruleset`, the file count of `/etc/sudoers.d`, and `sudo -n true`). | Gate check over `scripts/operator/` |
| S-7 | `setup` is ShellCheck-clean and uses `set -euo pipefail`. Every Python script passes the `python` check of the gate. | CI `quality-gate` (`shellcheck`, `bash-hygiene`, `python`) |
| S-10 | Every operator script's tests pass in CI under the memory and CPU limits of the strictest machine profile. | CI job with resource limits, and `machine-profiles.toml` |
| S-11 | No operator script uses `shell=True`, `os.system`, `eval`, or `exec`, and subprocesses run only `oci`, `ssh`, `git`, or the allowlisted privileged commands of `facts`. No token appears in a child process environment, in `argv`, or on disk (canary test, R2). | Gate check, and a canary test with a recording stub |

## Setup and operator profile (P)

Replaces the earlier setup criteria (G-0 and S-8).

| ID | Criterion | Evidence |
|---|---|---|
| P-1 | `setup` without `--apply` installs nothing and changes nothing. | Test with stub `apt-get` and `ansible-playbook`; approver's dry run |
| P-2 | `setup` refuses to run outside a release tag. | Test in a temporary repository |
| P-3 | A real run of the playbook without the explicit apply variable is refused. | Test of the pre-task |
| P-4 | `setup --apply` gives key-only SSH, automatic security updates, the source allowlist (when its file exists), `timestamp_timeout=0`, and the package and tool list from the repository with pinned sources and checksums. | Approver's run on each machine, CI in the container, and the manifest check of ADR-005 for the `operator` profile (every download has a pinned version and checksums for both architectures) |
| P-5 | A second apply reports no changes. | Approver's run, and CI |
| P-6 | A firewall change that is not confirmed from a second session is reverted. | Approver's test |
| P-7 | The initial admin account's SSH access is locked only by the separate play, and only after an operator login is confirmed from a second session. | Approver's run |
| P-8 | The same `setup --apply` passes in CI twice in a pinned minimal Ubuntu 24.04 container, and passes as root without sudo. | CI job |

## Facts (F), approver unless stated

| ID | Criterion | Evidence |
|---|---|---|
| F-1 | `facts`, host scope, on each operator machine: without `--apply` it runs no check and writes nothing. With `--apply` it writes only its local state files with mode 600. Its output contains no address, account name, hostname, or key (canary values in a test home). The egress is reported only as stable yes/no and a count. `--write-allowlist` writes the address only to the operator-local allowlist file. Without `--privileged` it never calls sudo. With `--privileged` it runs only the listed read-only commands with their fixed arguments and asks for the password each time. It runs on minimal Ubuntu 24.04 with only `python3` and `git` present. | CI tests with canary values and a stub `sudo`; approver's run on each machine |
| F-2 | `facts`, OCI scope: only `list`, `get`, and `inspect` verbs are used (gate check and stub-recorded calls). On the lab operator VM it runs with the instance principal and no other credential. In Cloud Shell its dry run prints the exact commands before any call. Its output contains counts and yes/no only. The principal cannot create, change, or delete any resource. | Gate check, tests with a stub `oci`, approver's run in Cloud Shell and on the lab operator VM. Replaces G-1 |
| F-3 | `facts`, GitHub scope: every HTTP call is a GET (a client test: any other method raises before a request is sent). T3 is used only from the prompt, has read-only permissions only, never appears in a child process environment, in `argv`, or on disk, and is revoked after the run. Its output contains yes/no and counts only. It reports whether the R3 tag ruleset exists. | Client tests, canary test, approver's run and check of the token list |

## Use cases (G), approver unless stated

| ID | Criterion | Evidence |
|---|---|---|
| G-2 | `github-setup`: the dry run uses T3 and makes no write call, and shows current against wanted settings for both repositories. The apply uses T2 with the permissions and expiry of Q4 and brings the repositories to the wanted state, and a second apply reports no change. | Approver's run on a throwaway or the real repositories, results yes/no |
| G-3 | `github-setup`: T3 and T2 stay inside the process, leave no file on disk, and are revoked after the run. | Approver's check of the token list |
| G-4 | `acceptance` in dry run lists the checks by criterion ID. With `--apply` it reports yes or no per ID for the checks it can run, and names the ones that stay manual. | Approver's run on the lab operator VM |
| G-5 | The operator scripts perform no OCI write call. | Test S-6, and the approver's review of the audit log of a run |

## Access and break-glass (W), approver

| ID | Criterion | Evidence |
|---|---|---|
| W-1 | `ssh` with the template entries reaches the lab VM and the lab operator VM from Z0 with separate keys. A changed host key is refused. Agent forwarding is off. SSH from any source outside the allowlist is refused. | Approver's tests, results yes/no |
| W-2 | Break-glass by in-place rebuild, for each OCI VM: with SSH deliberately blocked by a wrong allowlist value, one stack apply with the corrected value and a boot-volume replacement restores access from Z0. The elapsed time is recorded. The instance, its public IP, and its alarm are unchanged. For the lab VM, `/srv/work` content is unchanged afterwards. The new host key is verified from the console output. Block storage stays within 200 GB during the replacement. | Approver's test, once per OCI VM after CR-16 is applied |

## Lab effect (L), approver

| ID | Criterion | Evidence |
|---|---|---|
| L-1 | The lab operator VM, after CR-16 gains it (design section 7.1): micro shape, minimal Ubuntu 24.04 image if available, reserved public IP with SSH ingress from the corporate egress only, no Bastion, no block volume or backups, no ingress from the lab VM, its own read-only dynamic group, no OCI write rights, configured by cloud-init running `setup --apply`. A rebuild from the stack gives a working operator VM, with the elapsed time recorded, the same address afterwards, and the host key verified from the console output. | Approver's checks, results yes/no. Checked in CR-16's acceptance run. Replaces the earlier lab-login criterion |
| L-2 | For every VM in the lab stack: exactly one alarm exists and references that instance. Stopping the VM raises the alarm email after the trigger delay. A reboot within the window raises none. Starting it returns the alarm to OK. After a recreation the alarm follows the new instance and no alarm remains for the old one. A plan adding an instance without an alarm fails the allowlist check. A suppression window silences a planned stop or rebuild. | Approver's tests and a plan check in CI, results yes/no |

## Documents and process (D)

| ID | Criterion | Evidence |
|---|---|---|
| D-1 | `docs/operations/operator.md` describes the platform operator VM runbook, the lab operator VM bootstrap, the `ssh` config templates, the break-glass runbook, the handling of T2 and T3, and the rollback. | Review |
| D-2 | `docs/operations/gate-0-audit.md` and `github-setup.md` are shortened to the manual parts and point at the scripts. The shortened runbooks keep the removed manual steps in an appendix, so rollback loses no capability. | Review |
| D-3 | ADR-001 and ADR-005 carry the amendments of this design PR, and `docs/README.md` lists ADR-011, CR-18, and the machine-profile file with their current status. | Review |
| D-4 | The final implementation PR carries the evidence table and `Closes #18`. | PR body |
