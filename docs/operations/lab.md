# AI lab: runbook for the lab admin and the user

| Field | Value |
|---|---|
| Status | Active (CR-57 plan PR 9) |
| Implements | ADR-012 decisions 5, 6, 9, 11, 13, 14 (CR-57 PA-16, PA-17, PA-34, PA-44, PA-47 to PA-57; criteria PA-A8, PA-A23, PA-A31, PA-A38) |
| Performed by | The **lab admin** (lab setup, section 3 and 5), the **user** as the AI user in a plain SSH terminal (section 4), the approver (the PA-A38 check, section 6) |
| Reference | [ai-host.md](ai-host.md): the contract items LC-1 to LC-16, the hosts, the deny layer. [new-project.md](new-project.md): where this runbook sits in a new project |

Claude Code never runs, reaches, or probes an AI lab from the platform workspace, and never runs lab setup. The lab admin and the user do.
When you report a result to Claude Code or paste output into a pull request, report yes or no, counts, and sizes. Never paste addresses,
account names, hostnames, keys, or tokens.

## Placeholders

| Placeholder | Meaning |
|---|---|
| `<owner>` | The GitHub account that owns the repositories |
| `<release-tag>` | The release tag to set up from, for example the latest `v0.x.y` |
| `<ai-user>`, `<admin-user>` | The two managed accounts of the lab (the repository does not name them) |
| `<plan_sha256>` | The digest that the dry run of a project package list prints (section 5) |

## 1. Who does what

| Account | Does | Never |
|---|---|---|
| Lab admin | Clones this repository at a release tag, runs lab setup and the project toolchain step | Is a Claude Desktop target (LC-3); holds a credential |
| AI user | Runs Claude Code through Claude Desktop sessions; in a plain SSH terminal runs the token step and the lab check | Has sudo (LC-2) |
| User | Enters T1 in a plain terminal as the AI user; reads the lab check | Types a token into a Claude session |

## 2. Before lab setup

1. A fresh Debian 13 x86-64 VM with the two accounts provisioned, **one key each**, and no other key on the machine. Lab setup refuses
   (and changes nothing) when a managed account has no key or more than one, a key is shared, root or another account has a key, the AI
   user's `~/.ssh` holds a private key, or sshd uses `AuthorizedKeysCommand`, `TrustedUserCAKeys`, or `AuthorizedPrincipalsFile`.
2. As the lab admin: git and `ansible-playbook` are installed (the Debian archive packages `git` and `ansible-core`; the lab admin
   installs them once, before the first run).
3. An anonymous clone at the release tag, owned by the lab admin:

   ```bash
   git -c advice.detachedHead=false clone --branch <release-tag> https://github.com/<owner>/ai-lab-infrastructure.git
   cd ai-lab-infrastructure
   ```

   Lab setup refuses to run unless HEAD is a release tag contained in `origin/main` and the clone has no local changes. Nothing skips
   this check. Never edit files in the clone; check out a new tag after the approver has cut it.
4. `config/project.yaml` at that tag names the machine account and its numeric id. Lab setup refuses while the id is missing, and
   nothing in the repository guesses it.

## 3. Lab setup

Run from the root of the clone, as the lab admin (Ansible uses `become` when it is not root, so the account needs sudo rights for the
run). Dry run first; read it:

```bash
ansible-playbook -i ansible/inventory/localhost.yml ansible/lab.yml --check --diff -e lab_ai_user=<ai-user> -e lab_admin_user=<admin-user>
```

Apply with the same command without `--check` and with `-e lab_apply=true`. A real run without that variable stops at the first task.

```bash
ansible-playbook -i ansible/inventory/localhost.yml ansible/lab.yml --diff -e lab_ai_user=<ai-user> -e lab_admin_user=<admin-user> -e lab_apply=true
```

- **sshd is switched last, and only on your word.** Open a **second** login with each of the two accounts while the first session stays
  open. Only when both worked, add `-e ssh_second_login_confirmed=true` and run again. Without it everything else is applied and sshd
  keeps its settings. Do not close the first session before the second login worked.
- **The deny layer.** `-e lab_deny_layer=both` is the default. Under an organisation policy the managed file is ignored, so keep `both`
  or `user`; see [ai-host.md](ai-host.md#the-user-level-deny-layer-lc-16) for the modes, the attribute probe, and the move-aside command.
- **A project.** To install a project's toolchain in the same run, add the variables of section 5.
- A second run changes nothing. Run it once more to confirm.
- It also prints the host key fingerprints for information and removes nothing.

After lab setup, as the AI user in a plain terminal, run the token step and the lab check (section 4). The first time a lab is used,
the user also runs the two-prompt probe of [new-project.md](new-project.md#the-two-prompt-probe).

## 4. The token step and the lab check

Both are root-owned commands that lab setup installs under `/opt/ai-lab/lab` and links into `/usr/local/bin`. The AI user runs them by
their absolute paths, in a plain SSH terminal, never inside a Claude session.

```bash
/usr/local/bin/token-step           # enter token T1 at the prompt (echo off)
/usr/local/bin/lab-check            # one PASS, FAIL, or WARN line per item; exit 0 when nothing failed
```

- `token-step` refuses, before it reads anything, without a terminal, as root, with a shell trace on, and inside a Claude Code session.
  It runs again in a clean environment and passes the token to `gh` on its standard input; the token is never an argument, an
  environment variable, a file, or a log line. `--reauth` logs in again. Never run `gh auth login` yourself.
- `lab-check` reads files and runs `git`, `gh`, and the toolchain `verify`; it writes nothing. Fix every `FAIL`. Read every `WARN`.
- Project credentials that the project's `PROJECT.md` lists are entered in the same way, as the AI user in a plain terminal, mode 0600.

## 5. Project toolchains (PA-34)

The lab admin installs the project's download tools and package list from the project's own repository, through lab setup. One lab is
one project. Lab setup reads **three files** of the project and nothing else: `toolchain/manifest.toml` (the tools the project's CI
uses), `toolchain/lab-packages.txt` (Debian archive package names, one per line), and `.claude/deny.platform.txt` (the project's deny
entries). The project's own `scripts/toolchain` is never extracted and never run.

**Name the project with one of two pairs; nothing is chosen by default.**

| Source | Variables |
|---|---|
| An anonymous clone of a public GitHub repository, at a tag or a full 40-character SHA that is **merged** (reachable from the default branch) | `-e lab_project_repo=https://github.com/<owner>/<repository> -e lab_project_ref=<tag or SHA>` |
| The AI user's own clone, at a full 40-character SHA you supply (merged or not; git runs as the AI user and root reads the bytes) | `-e lab_project_clone=<absolute path of the clone> -e lab_project_sha=<40-character SHA>` |

A tag on an unmerged commit is refused. Add the pair to the lab setup commands of section 3.

**Procedure.**

1. **On a fresh VM, refresh the package index first** (the dry run does not): `sudo apt-get update`. Without a current index the dry
   run of a package list refuses and says so.
2. **Dry run** with the project variables and `--check --diff`. It reads the project, changes nothing, and prints the tools it would
   install and, for the package list, **every package name and version it would install** (dependencies included, each with its origin)
   and a `plan_sha256`. It refuses a plan that removes a package, that takes one from an origin other than the Debian archive and the
   Debian security archive, or whose list has a source line, a version or release pin, a duplicate, or more than 200 names.
3. **Read every package name and version.** There is no package allowlist in v1: your reading is the control (ADR-012 RR-P2). If one
   entry is not one you expect, stop and ask the project.
4. **Apply** only with the digest you read: the lab setup command with `-e lab_apply=true` and
   `-e lab_project_packages_reviewed=<plan_sha256>`. A real run without the digest, or with a stale one, stops before anything is written
   (also not the project's deny entries). An empty plan needs no digest, so a second run changes nothing.
5. Run the lab check (LC-4, LC-16, PA-43 read the merged list).

**Where things go.** The tools are installed into `/opt/ai-lab/project/` (root-owned; the AI user cannot change them); the smoke tests
run as the AI user and print its name. The three files and where they came from are recorded in `/opt/ai-lab/lab/project/` (root-owned).
The project's deny entries are merged after the core list into one lab-wide list, and the managed settings, `/opt/ai-lab/lab/deny.txt`,
and the user-level layer are all written from it, so an entry is in every place or in none.

**Later runs.** The recorded deny entries are kept: a lab setup run that names no project reads the recorded `deny.platform.txt`, so a
routine re-run does not drop a project's credential-path rule. Naming a project again replaces the record. There is no command to forget a
project in v1; the lab is disposable.

**Version 1 installs download tools only.** The apt and pip entries of the project's manifest are not installed from the manifest (the dry
run lists what it leaves out): Debian packages come from the package list, and pip needs a lock file that is not one of the three files.

## 6. What the PA-A38 check showed

The approver's PA-A38 check ran on a real lab set up from tag `v0.10.0` under an organisation policy, with Claude Desktop 6.28899.6 and
Claude Code 2.1.330; the record is in the body of pull request 73. The user-level layer passed A, B, and C. What follows is what that
record supports for the people who run a lab, and no more.

- **Moving `~/.claude` removes the layer.** From a plain terminal, `mv ~/.claude ~/.claude.moved` succeeded, LC-16 failed and warned
  while it was moved, and it passed again after moving the directory back. Inside a session the same command ran, and `ssh -V` then
  ran in that same session: a running session no longer has the layer's rules once the directory is gone. A connected Claude Desktop
  app recreates an unprotected `~/.claude` (it did in the record), so moving the directory back is not the way to restore it: the lab
  admin re-runs lab setup (the same command as the first run), and `lab-check` LC-16 detects the state. Tell the users not to move `~/.claude`, and
  run the lab check after any session that may have. If lab setup refuses because the AI user owns a file at the layer path, it prints
  the move-aside command of [ai-host.md](ai-host.md#the-user-level-deny-layer-lc-16).
- **`/status` and `/memory` are not the probe.** In that Desktop and engine, `/status` shows only session information and no settings
  sources (it shows `Managed settings: In effect`, which did not make the managed file refuse `ssh` under the policy), and `/memory` does
  not exist, so the managed CLAUDE.md load was not checked. The probe is the **control command plus `ssh -V`**, in a working folder
  with no `.claude/` (the two-prompt probe of [new-project.md](new-project.md#the-two-prompt-probe)).
- **The Read refusals of `~/.ssh` and `~/.config/gh` come from an instruction rule, not from the layer.** With the home as the working
  folder, Reading `~/.ssh/authorized_keys` and a dummy file under `~/.config/gh/` was refused before and after the layer was removed, and
  the refusal text names an instruction rule. Do not take those refusals as evidence that the layer's `Read` entries work.
- **An allow rule does not override a layer refusal.** With `Bash(ssh *)` allowed in the working folder's `.claude/settings.local.json`,
  `ssh -V` was still refused. In the same run `/usr/bin/ssh -V`, `env ssh -V`, and `sh -c 'ssh -V'` were also refused; that is one
  lab and one version, not a promise.
- **The file itself.** The AI user could not change, move, delete, or link the file (`Operation not permitted`), Claude's Edit tool could
  not change it, and the permission-mode selector reported bypass as not selectable.
- **Not explained.** Root-owned copies of the layer file, identical to each other, were seen outside `~/.claude`; their origin is not
  known. Look at such a file before anything else is done with it.

The full PA-A38 procedure is the approver's, on the first lab from each tag that changes the layer. Every other new lab gets the
two-prompt probe.

## 7. Before a lab is discarded

A lab is rebuilt, not patched in place, when a reboot is not enough. Before it is discarded the user runs, as the AI user in a plain
terminal:

```bash
/usr/local/bin/lab-check --pre-disposal
```

It lists every repository under `~/work` with uncommitted changes or commits that no remote branch has, as of the last fetch, and changes
nothing. The home directory of a lab is ephemeral: push what you need first.

## 8. Failure and recovery

| Symptom | Do |
|---|---|
| Lab setup refuses: not a release tag, or local changes | `git status`, then check out the release tag cleanly. Do not edit the clone |
| Lab setup refuses at the key audit | Provision exactly one key per account and remove any other key; nothing was changed |
| Lab setup fails at the attribute probe | The home filesystem or the container does not take the immutable attribute; use another machine, or `lab_deny_layer=managed` where no organisation policy applies |
| Lab setup refuses a file the AI user owns at `~/.claude/settings.json` | The AI user runs the move-aside command of [ai-host.md](ai-host.md#the-user-level-deny-layer-lc-16) in a plain terminal; run lab setup again |
| The package-list plan refuses, or a real run stops for the digest | `sudo apt-get update`, run the dry run, read it, pass the digest it prints |
| LC-16 fails or warns | Section 6: look at `~/.claude` and any `~/.claude.*` directory, then the lab admin re-runs lab setup at the same tag |
| `token-step` refuses | Run it by its absolute path in a plain SSH terminal as the AI user, not inside a Claude session and not as root |
| A token may have leaked | Revoke it in the browser, tell Claude Code only that it happened |
| A step fails halfway | Repeat the same command; every apply is idempotent |
