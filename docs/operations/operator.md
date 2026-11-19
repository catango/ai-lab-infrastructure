# Operator machines: runbook

| Field | Value |
|---|---|
| Status | Platform operator VM: active. Lab operator VM, SSH templates, break-glass: **not written yet** (PR 7b; the OCI work is postponed) |
| Implements | ADR-011 (operator tier), CR-18 design sections 3, 5.7, 6 |
| Performed by | The approver, as the operator user, in a plain SSH terminal. Claude Code never runs, reaches, or probes these machines |

This runbook is for the approver. Operator scripts live in `scripts/operator/` and run only on an operator machine, from a
release tag. Every script is a dry run unless it gets `--apply`. Read the dry run, then apply.

**Reporting.** When you report a result to Claude Code or paste output into a PR, report yes/no, counts, and sizes. Never paste
addresses, account names, hostnames, keys, tokens, or OCIDs. The scripts sanitise their output; still read it before pasting.

## Placeholders

| Placeholder | Meaning |
|---|---|
| `<owner>` | The GitHub account that owns the repositories |
| `<bot>` | The machine account login |
| `<release-tag>` | The release tag to run, for example the latest `v0.x.y` |
| `<initial-account>` | The provider's initial admin account on the machine |

## 1. The machines

| Aspect | Platform operator VM (Z6) | Lab operator VM (Z7) |
|---|---|---|
| What it is | A remote machine provided to the approver | A lab OCI VM, separate from the lab VM |
| Architecture and OS | x86-64, Ubuntu 24.04 | x86-64, Ubuntu 24.04 |
| Credentials it may hold | T2 and T3, only in a script process during a run | Instance principal (read-only) and T3 |
| Runbook | Section 3 | Section 8 (PR 7b) |

The size of each machine is recorded without identifiers in `scripts/operator/machine-profiles.toml`. Tests and CI limits use it.

## 2. Separation rules

Per operator machine (design section 3.2). U-1 tests rules 1 to 5 after the first `setup --apply` and **before any credential
is used on that machine**.

1. No shared storage or identity with an AI host: no shared mount, home, account, or credential.
2. No AI-host key in the operator's `authorized_keys`, no SSH path from Z1 or Z2 to the machine.
3. The machine is not a Claude Desktop SSH target, and `~/.claude/remote/` does not exist.
4. T1 (the AI hosts' token) is never placed on an operator machine.
5. Sudo asks for the operator's password (`timestamp_timeout=0`, no `NOPASSWD` rule), and the operator is in no other
   privileged group.
6. The operator's clone and any raw output are in its home only (mode 700).

If a test fails, stop and tell Claude Code. The design is revisited.

## 3. Platform operator VM

Do the steps in order. Steps 1 to 5 need no credential. Steps 7 and later may use a token; do not start them before step 6
passes.

### 3.1 Prepare

1. **Public keys file.** `setup --apply` installs the operator login's keys from a file that must exist first: put the
   **public** keys of the operator login (one dedicated key for this machine, from Z0) in `/etc/operator/authorized_keys`.
   Public keys only. Without the file, `setup --apply` stops with a message.
2. **Git.** Minimal Ubuntu has no git: `sudo apt-get install git`.
3. **Anonymous clone at the release tag**, in the operator's home:

   ```bash
   git -c advice.detachedHead=false clone --branch <release-tag> https://github.com/<owner>/ai-lab-infrastructure.git
   cd ai-lab-infrastructure
   ```

   The scripts refuse to run from anything but a release tag's commit that is contained in `origin/main`, and refuse local
   changes. Never edit files in this clone. Check out a new tag instead, after the approver has created it.

### 3.2 Facts about the machine

```bash
scripts/operator/facts                          # dry run: lists the checks, runs none
scripts/operator/facts --apply                  # host scope
scripts/operator/facts --apply --privileged     # also three fixed read-only root commands; asks for the sudo password each time
scripts/operator/facts --apply --write-allowlist  # only when the egress is confirmed stable: writes the address to an operator-local file
```

The privileged mode runs only `sshd -T`, `nft list ruleset`, and a file count of `/etc/sudoers.d`. Output is yes/no, counts, and
sizes. The "manual (off-host)" lines it prints are the checks it cannot make: the provider's firewall and access rules, the SSH
path from Z0, and corporate approval for the machine. Do those by hand.

New machine sizes go into `machine-profiles.toml` by a PR, from this output.

### 3.3 Apply the operator profile

```bash
scripts/operator/setup            # dry run (default): installs nothing; review the diff
scripts/operator/setup --apply    # installs ansible-core if missing, then applies the profile; asks for the sudo password
```

The profile gives key-only SSH, automatic security updates, `timestamp_timeout=0` for sudo, the package and tool list from the
repository, and a firewall.

**The firewall is armed with a revert timer.** After it loads, the run pauses. Open a **second** SSH session to the machine. If it
works, press Enter in the first session to keep the firewall. If it does not, press Ctrl-C and then A: the timer removes the
change by itself after its delay. Do not close the first session before you have seen the second one work.

**Where the firewall role does not run.** It is skipped on a machine without systemd and in a container (the run lists its tasks
as `skipping`). On such a machine the provider's network rules are the only inbound filter; record that, and note that the
firewall test (P-6) cannot be made there.

**Read the run's own messages.** If it says `/etc/operator/authorized_keys does not exist`, no key was installed for the operator
login. Create the file (public keys only) and run `setup --apply` again. Do not go on to section 3.4 until the operator can log in.

A second `setup --apply` must report no changes. Run it once more to confirm (the run that installs the keys changes things, so it
is not that confirmation).

### 3.4 Confirm the operator login, then lock the initial account

1. **Set the operator's sudo password.** The profile creates the account without a password, and sudo needs one. From the initial
   account: `sudo passwd <operator-user>` (the name is the profile variable `operator_user_name`). The password never goes in the
   repository.
2. Log in as the operator user from a second session, with the key from `/etc/operator/authorized_keys`. Confirm `sudo` asks for
   the password.
3. **Do not run the lock play before step 2 works.** It closes SSH access of the provider's initial account; with no working
   operator login you would lock yourself out. Then run it:

   ```bash
   ansible-playbook -i ansible/inventory/localhost.yml ansible/operator.yml --tags operator_lock --ask-become-pass \
     -e operator_apply=true -e operator_login_confirmed=true -e operator_initial_account=<initial-account>
   ```

4. Confirm the operator login still works from a third session.

### 3.5 Separation test U-1

Run the checks of section 2 on the machine and record yes/no for each:

| # | Check | Expected |
|---|---|---|
| a | No shared mount or home with an AI host | yes (nothing shared) |
| b | No AI-host key in the operator's `authorized_keys` | yes |
| c | No SSH route from Z1 or Z2 to the machine (try from the AI user on Z1, it must fail) | yes (refused) |
| d | `~/.claude/remote/` does not exist | yes |
| e | Sudo asks for a password, with no `NOPASSWD` rule | yes |
| f | The operator is in no other privileged group | yes |
| g | The operator's home and clone are mode 700 or stricter | yes |
| h | No T1 on the machine | yes |

Report the eight answers. The first credential on this machine comes only after all are yes.

### 3.6 Retire the old Z1 operator user

Once the platform operator VM works and U-1 passed, retire the existing operator user on Z1 (decision Q25). Do it last, so a
fallback exists until then. Report "retired: yes/no".

### 3.7 After each run

Check, as the approver:

- **U-2:** `workspace/verify.sh` check V-4 passes on Z1 as the AI user, and no operator credential exists on Z1 or Z2.
- **U-3:** no credential, token, or raw response of an operator run exists in the repository, in an AI user's home, or in shell
  history.

## 4. Credentials: T2 and T3

Tokens are entered only at a prompt (`getpass`), kept in the script process, and never put in a child process environment, in
`argv`, or on disk. Create one for a run, revoke it in the browser right after. T1 is never an operator credential. T2 is never
used to collect facts.

| Token | Used by | Type and permissions | Expiry | Machine |
|---|---|---|---|---|
| **T3** (read-only) | `facts --scope github --use-token`, `github-setup` dry run | Fine-grained token of the personal account, the two repositories only. Administration read, Environments read, Metadata read | 1 day | Either operator machine |
| **T2** (write) | `github-setup --apply` only | Fine-grained token of the personal account, the two repositories only. Administration and Environments read and write, Metadata read. No Contents, Pull requests, Workflows, or Secrets write | 1 day | Platform operator VM only |

**Steps for a run**

1. In the browser (personal profile), create the token with exactly the permissions above and a 1-day expiry. Do not copy it
   anywhere except the prompt.
2. Run the script. Enter the token at the prompt.
3. Revoke the token in the browser (Settings, Developer settings, Fine-grained tokens) when the run ends. `github-setup` reminds you.
4. Check the token list is empty of that token.
5. Run the checks of section 3.7.

If a token was ever typed outside a prompt, or you are unsure, revoke it and remove the shell history entry.

### 4.1 GitHub facts and setup runs

```bash
scripts/operator/facts --scope github --owner <owner> --repo ai-lab-infrastructure --repo ai-software-template            # dry run
scripts/operator/facts --scope github --owner <owner> --repo ai-lab-infrastructure --repo ai-software-template --apply --use-token   # asks for T3
scripts/operator/github-setup --owner <owner> --collaborator <bot>             # dry run, asks for T3, shows current against wanted
scripts/operator/github-setup --owner <owner> --collaborator <bot> --apply     # asks for T2
```

A second `github-setup --apply` must report no change. The R3 tag ruleset (`release-tags`) and everything under "Stays manual"
in [github-setup.md](github-setup.md) remain manual.

## 5. Facts outside the operator machines

`facts --scope oci` runs in Cloud Shell under the approver's session until the lab operator VM exists:

```bash
scripts/operator/facts --scope oci --oci-auth instance_obo_user            # dry run: prints the exact commands first
scripts/operator/facts --scope oci --oci-auth instance_obo_user --apply
```

It uses `list`, `get`, and `inspect` calls only and handles no OCI credential. It replaces the Gate 0 OCI audit commands; see
[gate-0-audit.md](gate-0-audit.md).

## 6. Rollback

The manual runbooks stay valid throughout. To roll back the operator tier:

1. Revoke any T2 or T3 that still exists.
2. Delete the operator scripts and the profile through a PR (and revert the ADR-011, ADR-001, and ADR-005 amendments in design
   PRs).
3. Retire the operator users on the machines.
4. Use the appendices of [gate-0-audit.md](gate-0-audit.md) and [github-setup.md](github-setup.md): they keep every manual step the
   scripts replaced, so no capability is lost.

Rolling back a single machine's `setup` is by the provider's snapshot or rebuild. The profile keeps the original SSH and
firewall configuration under `/var/lib/operator` for a manual restore.

## 7. Failure and recovery

| Symptom | Do |
|---|---|
| A script refuses: not a release tag, or local changes | `git status`, then check out the release tag cleanly. Do not edit the clone |
| `setup --apply` stops about missing keys | Create `/etc/operator/authorized_keys` (public keys only), apply again |
| Locked out after the firewall step | Wait for the revert timer, then log in again. If the timer already fired, the firewall is gone; re-run `setup --apply` |
| A step fails halfway | Repeat the same command; every apply is idempotent |
| A token may have leaked | Revoke it in the browser, remove the history entry, tell Claude Code only that it happened |

## 8. Lab operator VM

> **Not written yet.** PR 7b (`operator-finish`) adds this section after the lab VM exists (the OCI work is postponed by the approver).
> Planned content: bootstrap by cloud-init running `setup --apply`, the first `facts` runs (host and OCI scope), U-1 for this
> machine, and the instance principal.

## 9. `ssh` config templates for both OCI VMs

> **Not written yet (PR 7b).** One template entry per OCI VM, placeholders only: `Host` alias, `HostName`, `User`, a dedicated
> `IdentityFile` per VM, `ProxyJump` where needed, `HostKeyAlias`, `StrictHostKeyChecking yes`, `ForwardAgent no`.

## 10. Break-glass runbook

> **Not written yet (PR 7b).** Rebuild through the lab stack after an egress change, an NSG error, a host-side fault, or a lost key,
> with the host-key check from the console output afterwards (design section 5.9).
