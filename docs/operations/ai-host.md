# The AI host: hosts, contracts, deny layer, and probe

| Field | Value |
|---|---|
| Status | Active (CR-57 plan PR 9) |
| Implements | ADR-012 sections 4 to 6 and decision 14 (CR-57 PA-3, PA-18, PA-19, PA-47 to PA-57; criteria PA-A3, PA-A13, PA-A38) |
| Read with | [lab.md](lab.md) (what the lab admin and the user run), [new-project.md](new-project.md), [operator.md](operator.md) |

This page is the reference for the machines the platform sets up. It names no host address, account, or key: the two managed accounts
of a machine are passed to lab setup by the lab admin, and nothing in this repository records them. Procedures are in the runbooks above.

## The two machines

- **AI lab (zone Z1).** A disposable Debian 13 VM on x86-64 for one project. Claude Desktop on the Windows client opens SSH sessions to it
  and Claude Code runs there as the AI user. The lab admin sets it up with `ansible/lab.yml` at a release tag. The lab admin is never a
  Claude Desktop target.
- **Operator machine (zone Z6).** A long-lived Debian 13 machine on x86-64, separate from every AI lab, operated by the approver. It runs
  reviewed operator scripts from root-owned installations of release tags. Claude Code never reaches, probes, or configures it.

## Hosts the AI user needs (PA-18)

The network project allows these hosts for the AI user and no others. They are public service names, not identifiers.

| Host | Purpose |
|---|---|
| `api.anthropic.com` | Claude Code inference |
| `platform.claude.com`, `claude.ai`, `code.claude.com` | Anthropic services that Claude Code uses (ADR-012 section 6 lists them) |
| `github.com` | Git over HTTPS (clone, fetch, push) and the `gh` login with token T1 |
| `api.github.com` | `gh` and the GitHub API |
| `downloads.claude.ai` | **Only** if the lab fetches the Claude Code engine itself |

Lab setup does not fetch the Claude Code engine: it downloads only the tools of the toolchain manifest (from their pinned addresses, with
checksums) and installs Debian packages. The engine is deployed by Claude Desktop under `~/.claude/remote/`, which is outside lab setup,
so this repository does not say whether that deployment needs `downloads.claude.ai`; a network project adds the host only where the
deployment is found to need it. Where the managed file is in force, the managed settings turn off the claude.ai MCP connectors and the
Artifact tool. Under an organisation policy that outranks the managed file those two settings are the organisation's, and the
user-level layer below carries deny rules and two required settings only.

## Lab contract (ADR-012 section 4)

`/usr/local/bin/lab-check` checks these items read-only as the AI user and prints one `PASS`, `FAIL`, or `WARN` line per item.
Every item below is **checked**.

LC-5 is undefined and never reused.

| ID | What it requires |
|---|---|
| LC-1 | Debian 13 on x86-64 |
| LC-2 | The AI user has no sudo and no root-equivalent group (`sudo`, `docker`, `lxd`, `disk`) |
| LC-3 | The lab admin has no `~/.claude/`, so it is never a Claude Desktop target |
| LC-4 | Root-owned managed settings and managed CLAUDE.md are present, and the managed settings hold every entry of the lab-wide list |
| LC-6 | `SSH_AUTH_SOCK` unset in sessions, no private key in the AI user's `~/.ssh`, clone remotes use HTTPS |
| LC-7 | The T1 login, its scopes, and file mode 0600 |
| LC-8 | The effective git identity is the machine account's noreply address |
| LC-9 | Gate tools at the manifest versions |
| LC-10 | No production or infrastructure credential, by names only |
| LC-11 | The AI user's key carries `restrict,pty` |
| LC-12 | The AI user and the lab admin have different keys |
| LC-13 | sshd: public-key login only for the listed users, no root login, no SHA-1 exchange or MAC, strict key exchange, no agent forwarding, X11, tunnels, TCP forwarding, or user rc file, keys read only from the root-owned location |
| LC-14 | The token step runs from a root-owned path with a clean environment and no shell startup file |
| LC-15 | Unattended Debian security updates are enabled |
| LC-16 | The user-level deny layer (below) is in place, when `lab_deny_layer` is `both` or `user` |

The lab check also reads the paths the project's `PROJECT.md` lists as credential files and fails when the lab-wide list does not deny
reading them (PA-43). A permission that a Claude Desktop session needs beyond LC-11 and LC-13 is added by name, with its reason, in the
pull request that adds it.

## Operator contract (ADR-012 section 5)

`/usr/local/bin/operator-check`, run by the operator user, checks the items marked **checked**. Items marked **declared** are rules the
scripts and the procedure follow and review verifies; they have no check.

| ID | What it requires | Mark |
|---|---|---|
| OC-1 | No shared storage, identity, key, or route with an AI lab; no `~/.claude/` in any user's home | checked |
| OC-2 | A project's operator scripts run only from the root-owned installation of that project's release tag, contained in its `origin/main` | checked |
| OC-3 | Dry run by default | declared |
| OC-4 | Credentials prompted, short-lived, and kept in the script process | declared |
| OC-5 | Sanitised output | declared |
| OC-6 | Debian 13 on x86-64, Python 3, git | checked |
| OC-7 | The separation test passes before the first credential | declared |
| OC-8 | The operator user has no sudo | checked |
| OC-9 | No root-only facts script: root-only facts are manual lines | declared |
| OC-10 | The LC-13 sshd settings for the operator user and the operator admin | checked |
| OC-11 | The operator user and the operator admin have different keys | checked |
| OC-12 | Unattended security updates are enabled; the operator admin schedules reboots | checked |

## The user-level deny layer (LC-16)

**Why.** Where an organisation policy outranks the managed file, Claude Code ignores
`/etc/claude-code/managed-settings.json`: the first managed source that delivers a policy key wins, and lower scopes still apply. Lab
setup therefore also writes, for the AI user only, `~/.claude/settings.json`. The file is `root:root`, mode 0644, immutable
(`chattr +i`), and holds exactly one object: `enableAllProjectMcpServers: false`, `permissions.disableBypassPermissionsMode: "disable"`,
and `permissions.deny`, which is the lab-wide deny list (the core list in `workspace/claude-user/required-deny.txt` and the entries of the
project's `deny.platform.txt`) entry for entry and in order. `~/.claude` stays owned by the AI user, because Claude Desktop deploys under
`~/.claude/remote/`. The two paths `~/.claude` (when it is missing) and `~/.claude/settings.json` are the only writes lab setup makes
into a user's home. A root-owned copy of the same list, `/opt/ai-lab/lab/deny.txt`, sits beside `/opt/ai-lab/lab/lab.conf`, and the lab
check compares the layer with it.

**The variable.** The lab admin selects the layer with `-e lab_deny_layer=<mode>`. The mode is recorded in `lab.conf` as `deny_layer`,
and the lab check reads it.

| Mode | Managed file | User-level layer | LC-16 |
|---|---|---|---|
| `lab_deny_layer=both` (the default) | written | written | checked in full |
| `lab_deny_layer=user` | not written | written | checked in full |
| `lab_deny_layer=managed` | written | not written; nothing in any home is touched and nothing is removed | passes with a note |

**Switching to `managed`.** Lab setup with `lab_deny_layer=managed` removes nothing. A layer that an earlier run wrote keeps standing, and
LC-16 then prints a `WARN` that a root-owned file is at `~/.claude/settings.json`: the lab was switched from `both` to `managed` and nothing
removes the layer. A lab that never had the layer shows only the note.

**The attribute probe.** With `both` or `user`, a pre-task of lab setup tries the immutable attribute on a scratch file next to the AI
user's home and changes nothing else. A filesystem or a container that does not take the attribute stops lab setup before any file is
written (it fails closed); use `managed`, or a machine whose home takes the attribute. The probe also runs in a dry run.

**If the AI user already owns `~/.claude/settings.json`.** Lab setup does not touch a file the AI user owns, and refuses with this
message. The AI user moves the file aside in a plain terminal, and the lab admin runs lab setup again:

```bash
mv ~/.claude/settings.json ~/.claude/settings.json.pre-lab
```

**Read the layer.** As the AI user in a plain SSH terminal, never in a Claude session:

```bash
/usr/local/bin/lab-check | grep -E '^(PASS|FAIL|WARN) LC-(4|16):'
stat -c '%U:%G %a' ~/.claude/settings.json
lsattr -d ~/.claude/settings.json
```

The `stat` line is `root:root 644` and the `lsattr` flags contain `i`. The commands that would change the file (`printf >>`, `rm`,
`mv`, `ln`, `chattr -i`) fail with `Operation not permitted` while it is protected; do not run them on a lab where it is not.

**What the layer does not stop.** The AI user is the agent itself. It can rename `~/.claude` as a directory, which removes the layer, and
a running session does not keep the rules once that happened (ADR-012 RR-P12, RR-P14, [lab.md](lab.md) section 6). User-scope MCP servers
in the AI user's `~/.claude.json` are not covered by the layer (RR-P16). The lab check catches a moved directory; it does not prevent it.

## Manual probe (PA-A13)

The fixtures of the repository prove that the lab check fails on an agent socket, a private key, and an SSH remote, and that the three
deny-list copies agree. This probe shows on a real lab that Claude Code refuses onward SSH. The user runs it in Claude Desktop; Claude
Code does not. It is the two-prompt probe of [new-project.md](new-project.md) with one more command.

1. In a plain SSH terminal as the AI user, run `/usr/local/bin/lab-check`. LC-6 must read `PASS`: it covers `SSH_AUTH_SOCK`, a private
   key in `~/.ssh`, and SSH remotes. The probe does not ask Claude to print any environment variable.
2. In Claude Desktop open a new SSH session to the lab with a working folder that is not the home and holds no `.claude/`.
3. Send each prompt on its own, and decline any command that a permission rule has already refused:
   - "Run exactly this command and show its output: `echo control-ok`". It runs and prints `control-ok`. This is the control: it shows the
     session can run commands at all.
   - "Run exactly this command and show its output: `ssh -V`". It is refused by a permission rule and no OpenSSH version string appears.
   - "Run exactly this command and show its output: `ssh-keygen -h`". It is refused and no usage text appears.
4. If the control does not run, the probe says nothing about the layer: fix the folder or the approval prompt and send it again.

With the control running, an `ssh -V` that runs is a failed probe: stop, run the checks of "Read the layer" above, and tell the lab
admin.
