# Operator machine: runbook

| Field | Value |
|---|---|
| Status | Active (rewritten in CR-57 plan PR 9 for the Debian 13 operator profile) |
| Implements | ADR-011 (rules for operator scripts), ADR-012 decisions 7, 8, 12 and section 5 (OC-1 to OC-12) |
| Performed by | The approver: as the **operator admin** for the configuration, as the **operator user** for everything else, in a plain SSH terminal. Claude Code never runs, reaches, or probes the operator machine |

Operator scripts live in `scripts/operator/` and run only on the operator machine, from a root-owned installation of a release tag. Every
script is a dry run unless it gets `--apply`. Read the dry run, then apply. The contract items are in [ai-host.md](ai-host.md); the
hosts and the lab are in [lab.md](lab.md).

**Reporting.** When you report a result to Claude Code or paste output into a pull request, report yes or no, counts, and sizes. Never
paste addresses, account names, hostnames, keys, or tokens. The scripts sanitise their output; still read it before pasting.

## Placeholders

| Placeholder | Meaning |
|---|---|
| `<owner>` | The GitHub account that owns the repositories |
| `<bot>` | The machine account login |
| `<release-tag>` | The release tag to configure from, at or after the one that contains the operator profile |
| `<operator-user>`, `<admin-user>` | The two managed accounts of the machine (the repository does not name them) |

## 1. The machine and its accounts

| Aspect | Operator machine (zone Z6) |
|---|---|
| What it is | A long-lived machine provided to the approver, separate from every AI lab |
| Platform | Debian 13 on x86-64, with Python 3 and git (OC-6) |
| Accounts | The **operator user** runs operator scripts and holds no sudo (OC-8). The **operator admin** runs the operator configuration. Each has its own key (OC-11) |
| Credentials it may hold | T2 and T3, only in a script process during a run (OC-4) |

The sizes of the machine are recorded without identifiers in `scripts/operator/machine-profiles.toml`; the tests and the CI limits use it.

## 2. Separation rules

The separation test (OC-7, declared) runs after the first configuration and **before any credential is used on this machine**. Record yes
or no for each line:

| # | Check | Expected |
|---|---|---|
| a | No shared storage, identity, key, or route with an AI lab (OC-1): no shared mount, home, account, or credential | yes (nothing shared) |
| b | No key of an AI lab in the keys of the operator user or the operator admin | yes |
| c | No SSH route from an AI lab to this machine: try from the AI user of a lab, it must fail | yes (refused) |
| d | The machine is not a Claude Desktop target: no `~/.claude/` in any user's home (OC-1) | yes |
| e | The operator user has no sudo (OC-8) and is in no root-equivalent group | yes |
| f | The operator user's clones and any raw output are in places only it can read | yes |
| g | T1 (the AI labs' token) is not on the machine | yes |

If a check fails, stop and tell Claude Code. The design is revisited.

## 3. Operator configuration

Done by the operator admin from a clone the admin owns, at a release tag. Steps 1 to 4 need no credential.

1. **Prepare.** Two accounts, **one key each**, and no other key on the machine: the configuration refuses, and changes nothing, when a
   managed account has no key or more than one, a key is shared, or another account has a key. Git and `ansible-playbook` are installed
   (the Debian archive packages `git` and `ansible-core`; the operator admin installs them once).
2. **Anonymous clone at the release tag**, in the operator admin's home:

   ```bash
   git -c advice.detachedHead=false clone --branch <release-tag> https://github.com/<owner>/ai-lab-platform.git
   cd ai-lab-platform
   ```

   The configuration refuses to run unless HEAD is a release tag contained in `origin/main` with no local changes, and unless it is run
   by the operator admin (as that account, or as root with `SUDO_USER` set to it). Nothing skips the release check. Never edit the clone;
   check out a new tag after the approver has cut it. The operator machine moves to a new tag only at or after the operator profile.
3. **Dry run**, and read it:

   ```bash
   ansible-playbook -i ansible/inventory/localhost.yml ansible/operator.yml --check --diff -e operator_user=<operator-user> -e operator_admin_user=<admin-user>
   ```

4. **Apply** with the same command, without `--check` and with `-e operator_apply=true`. A real run without that variable stops at the
   first task. The profile installs the packages of the operator profile, enables unattended security updates (OC-12), sets the operator
   user without sudo, creates the root-owned operator tools and the output directories, installs each project's scripts (section 4), writes the
   sshd settings of OC-10, and ends by running the operator check.
5. **Switch sshd only on your word.** While the first session stays open, log in with each of the two accounts from a second session.
   Only when both worked, add `-e ssh_second_login_confirmed=true` and run the command again. Without it everything else is applied and
   sshd keeps its settings. Do not close the first session before the second login worked. After the switch only the two managed accounts
   can log in over SSH (OC-10); confirm it from a third session.
6. **A second run changes nothing.** Run it once more to confirm.
7. **The operator check.** As the operator user: `/usr/local/bin/operator-check`. It prints one `PASS`, `FAIL`, or `WARN` line per item
   and refuses to run except from the root-owned installation. Fix every `FAIL`.
8. Do the separation test of section 2.

**Manual lines (OC-9).** The root-only facts have no script, so you make them by hand, as the operator admin, and record yes or no:

- the sshd settings in force, with `sshd -T`, against OC-10;
- the sudoers files and the rights of the operator user;
- the provider's firewall and access rules, read in the provider's console;
- the SSH path from the Windows client to the machine, tested from that client;
- the corporate approval for the machine and its network use.

Reboots of the machine are scheduled by the operator admin (OC-12).

## 4. Projects

Each project's operator scripts are installed by the operator admin at **that project's release tag** (PA-42, ADR-012 decision 12). By
default the list holds this repository. To install another project, pass the **whole** list, this repository included, as `-e @file`:

```yaml
operator_projects:
  - name: ai-lab-infrastructure
    source: <absolute path of this clone>
  - name: <project>
    source: <absolute path of the project's clone at its release tag>
```

```bash
ansible-playbook -i ansible/inventory/localhost.yml ansible/operator.yml --check --diff -e operator_user=<operator-user> -e operator_admin_user=<admin-user> -e @<file>
```

A name is plain, lower case, and unique, and every source must be a clone at a release tag; the configuration checks both before it changes
anything. The scripts are installed root-owned under `/opt/ai-lab/operator`. Each project has its own output directory (mode 0700) under
`/var/lib/ai-lab/operator`, and runs are one at a time.

The operator user starts a script **only** with `operator-run`, which takes the project and a path inside its installation, starts the script in the
project's output directory with a clean environment, and refuses a second run while one is in progress:

```bash
operator-run <project> <script> [argument...]
```

## 5. Credentials: T2 and T3

Tokens are entered only at a prompt (`getpass`), kept in the script process (OC-4), and never put in a child process environment, in `argv`,
or on disk. Create one for a run, revoke it in the browser right after. T1 is never an operator credential. T2 is never used to collect facts.

| Token | Used by | Type and permissions | Expiry | Machine |
|---|---|---|---|---|
| **T3** (read-only) | `facts --scope github --use-token`, the `github-setup` dry run | Fine-grained token of the personal account, limited to the repositories of the run. Administration read, Environments read, Metadata read. The allowlist audit of [new-project.md](new-project.md) selects all repositories | 1 day | The operator machine |
| **T2** (write) | `github-setup --apply` only | Fine-grained token of the personal account, the two platform repositories only. Administration and Environments read and write, Metadata read. No Contents, Pull requests, Workflows, or Secrets write | 1 day | The operator machine only |

### 5.1 Steps for a run

1. In the browser (personal profile), create the token with exactly the permissions above and a 1-day expiry. Do not copy it anywhere
   except the prompt.
2. Run the script as the operator user with `operator-run`. Enter the token at the prompt.
3. Revoke the token in the browser (Settings, Developer settings, Fine-grained tokens) when the run ends. `github-setup` reminds you.
4. Check that the token list is empty of that token.
5. Check, as the approver: no operator credential exists on an AI lab (manual line, OC-9), and no credential, token, or raw response of an
   operator run exists in a repository, in an AI user's home, or in shell history.

If a token was ever typed outside a prompt, or you are unsure, revoke it and remove the shell history entry.

### 5.2 Facts and setup runs

```bash
operator-run ai-lab-infrastructure scripts/operator/facts                                              # dry run: lists the host checks, runs none
operator-run ai-lab-infrastructure scripts/operator/facts --apply                                      # host scope
operator-run ai-lab-infrastructure scripts/operator/facts --scope github --owner <owner> --repo ai-lab-platform --repo ai-software-template            # dry run
operator-run ai-lab-infrastructure scripts/operator/facts --scope github --owner <owner> --repo ai-lab-platform --repo ai-software-template --apply --use-token   # asks for T3
operator-run ai-lab-infrastructure scripts/operator/github-setup --owner <owner> --collaborator <bot>             # dry run, asks for T3, shows current against wanted
operator-run ai-lab-infrastructure scripts/operator/github-setup --owner <owner> --collaborator <bot> --apply     # asks for T2
```

`facts` runs no `sudo` and no root command; its "manual" lines are the manual lines of section 3. A second `github-setup --apply` must
report no change. The `release-tags` ruleset and everything under "Stays manual" in [github-setup.md](github-setup.md) remain manual. In
v1 a project gets no `github-setup` and no desired-state file.

## 6. Rollback

The manual runbooks stay valid throughout. To roll back the operator tier:

1. Revoke any T2 or T3 that still exists.
2. Delete the operator scripts and the profile through a pull request (and revert the ADR-011, ADR-001, and ADR-005 amendments in design
   pull requests).
3. Retire the operator user and the operator admin on the machine.
4. Use the appendix of [github-setup.md](github-setup.md): it keeps every manual step the script replaced, so no capability is lost.

Rolling back a single machine's configuration is by the provider's snapshot or rebuild.

## 7. Failure and recovery

| Symptom | Do |
|---|---|
| The configuration refuses: not a release tag, or local changes | `git status`, then check out the release tag cleanly. Do not edit the clone |
| It refuses at the key audit | Provision exactly one key per managed account and remove any other key; nothing was changed |
| It refuses: not run by the operator admin | Run it as the operator admin, or with sudo from that account; never as the operator user |
| It refuses a project list | Fix the list (plain unique names, each source a clone at a release tag) and run again; nothing was changed |
| `operator-check` refuses to run | Run it by its absolute path, `/usr/local/bin/operator-check`, as the operator user |
| `operator-run` refuses | A run is in progress, or the script is not a root-owned file inside that project's installation |
| A step fails halfway | Repeat the same command; every apply is idempotent |
| A token may have leaked | Revoke it in the browser, remove the history entry, tell Claude Code only that it happened |
