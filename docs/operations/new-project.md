# New project: runbook

| Field | Value |
|---|---|
| Status | Active (CR-57 plan PR 9) |
| Implements | CR-57 PA-45 and the two-prompt probe of PA-A38; ADR-012 decisions 5, 6, 9, 12; ADR-009 decisions 8 and 13 |
| Performed by | The steps name who: the user, the lab admin, Claude Code, the operator admin, the approver |

One project gets one AI lab, a disposable VM. Each step below has one owner and one result. Do them in order. Claude Code does only step 4,
and only after the user has finished step 3.

When you report a result to Claude Code or paste output into a pull request, report yes or no, counts, and sizes. Never paste
addresses, account names, hostnames, keys, or tokens.

## 1. Repository and rulesets (user)

1. Generate the repository from the software template, in the personal account that owns the repositories.
2. Apply the settings by hand, in the browser, as ADR-009 decision 13 lists them. The rulesets `main-protection` and `release-tags`
   (ADR-009 decision 8) are the ones `initialize-project` prints in step 4, and the user applies them from that output. In v1 a project
   gets no `github-setup` and no desired-state file: the platform's own scripts configure only the two platform repositories.
3. Invite the machine account as a collaborator and accept the invitation in the machine account's profile. That collaborator list is the
   **allowlist** of repositories token T1 reaches (ADR-001, AC1-1). Step 6 audits it.

Result: a project repository with its settings and the machine account as a collaborator; the rulesets follow in step 4.

## 2. AI lab and lab setup (lab admin)

1. Provision a fresh Debian 13 x86-64 VM with the AI user and the lab admin, one key each.
2. Run lab setup from the platform's release tag as [lab.md](lab.md) sections 2 and 3 describe: dry run, read it, apply, a second login
   with each account, then `-e ssh_second_login_confirmed=true`. The deny layer stays at `both` or `user` under an organisation policy
   ([ai-host.md](ai-host.md#the-user-level-deny-layer-lc-16)).
3. If the project has a package list or download tools, add the project variables and follow [lab.md](lab.md) section 5 (dry run, read
   every package name and version, apply with the digest).

Result: a lab that passes the lab check once the token step of step 3 is done (LC-7 needs it).

## 3. Token step (user)

As the AI user, in a **plain SSH terminal**, never in a Claude session: `/usr/local/bin/token-step`, then `/usr/local/bin/lab-check`
([lab.md](lab.md) section 4). Enter T1 only at the prompt of the token step. Enter the project's own non-production credentials the
same way, if it has any, with mode 0600, at the paths the project's `PROJECT.md` lists.

Result: `lab-check` prints no `FAIL`, and every `WARN` is read.

## 4. Clone and `initialize-project` (Claude Code)

In Claude Desktop the user opens a new SSH session to the lab and asks Claude Code to clone the repository over HTTPS into `~/work` and
run the `initialize-project` Skill of the template in that clone. The Skill configures
`config/project.yaml` (including the approver login), the labels, and the pull request templates, and **prints** the rulesets for the user
to apply; it creates no repository, ruleset, collaborator, or setting. The change arrives as an init pull request by the machine account.
Claude Code never merges it; the approver does.

Result: an init pull request, reviewed and merged by the approver, and the rulesets of step 1 applied.

## 5. Operator script installation (operator admin)

Only if the project has operator scripts. The operator admin installs each project's scripts at the project's **release tag**, from a
clone of the project that the admin owns, by running the operator configuration again with the whole project list, this repository
included, as `-e @file` with `operator_projects` ([operator.md](operator.md) section 4). The scripts are installed root-owned under
`/opt/ai-lab/operator`, each project has its own output directory, and a script is started only with `operator-run <project> <script>`.

Result: `operator-check` passes (PA-42 and OC-2 name the project's installation).

## 6. Allowlist audit including the new repository (approver)

The new repository is now a collaborator of the machine account, so the allowlist audit reads every repository of the personal account.
It runs on the operator machine from this repository's installation of `facts`, with a **read-only** T3 (Administration read,
Environments read, Metadata read) that selects **all repositories** of the personal account. This is the one exception to the per-project
limit of T3 (ADR-012 decision 12). Create T3 for the run, enter it only at the prompt, and revoke it right after
([operator.md](operator.md) section 5).

```bash
operator-run ai-lab-infrastructure scripts/operator/facts --scope github --owner <owner> --repo ai-lab-platform --repo ai-software-template --repo <new-repository>             # dry run: lists the checks
operator-run ai-lab-infrastructure scripts/operator/facts --scope github --owner <owner> --repo ai-lab-platform --repo ai-software-template --repo <new-repository> --apply --use-token   # asks for T3
```

Compare the repositories the machine account can reach with the documented allowlist. Report yes or no: the new repository is in the list
and no repository is in it that should not be. A repository that should not be there is removed from the collaborator list by the user.

Result: the audit is recorded as yes or no in the pull request that adds the project.

## The two-prompt probe

**This probe is run on every new lab**, after step 3. It takes two prompts and no more, and it shows the user-level deny layer is in force. The
full procedure of PA-A38 is the approver's, on the first lab from each tag that changes the layer.

1. In Claude Desktop open a **new SSH session** to the lab, with a working folder that is not the home and holds no `.claude/`.
   As the AI user in a plain terminal, `mkdir -p ~/probe-empty` makes such a folder (the PA-A38 procedure uses the same name).
2. Send the **control** prompt on its own: "Run exactly this command and show its output: `echo control-ok`". It must run and print
   `control-ok`. If it does not, the probe says nothing: fix the folder or the approval prompt and send it again.
3. Send the **probe** prompt on its own: "Run exactly this command and show its output: `ssh -V`". It must be **refused** by a permission
   rule, and no OpenSSH version string may appear. Decline any command that a rule has already refused if an approval prompt appears.
4. Record two answers, yes or no: the control ran, and `ssh -V` was refused. Then remove the folder as the AI user in a plain terminal:
   `rm -r ~/probe-empty`.

If the control ran and `ssh -V` ran too, the layer is not in force: stop, run the checks of
[ai-host.md](ai-host.md#the-user-level-deny-layer-lc-16) as the AI user in a plain terminal, and tell the lab admin to run lab setup again.
Do not use `/status` or `/memory` as the probe: on the lab of the PA-A38 record the first showed no settings sources and the second did
not exist ([lab.md](lab.md) section 6).
