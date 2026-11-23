# GitHub Configuration: Stage 0 Runbook

| Field | Value |
|---|---|
| Status | **Executed** 2026-11-17 (Stage 0 complete). Since CR-18, repository settings, security features, rulesets, and the collaborator are applied by `scripts/operator/github-setup`; the manual steps it replaced are in Appendix A |
| Date | 2026-11-17 |
| Updated | 2026-11-19 (CR-18, PR 7a) |
| Target location | `ai-lab-infrastructure/docs/operations/github-setup.md` |
| Implements | ADR-001 (D8/D13, D14, D16, D17), ADR-003, ADR-011, preparation for ADR-002 |
| Performed by | You, in the browser and in one plain SSH terminal to the workspace; the scripted parts on the platform operator VM |

> Executing this runbook is your explicit authorization of the actions it describes:
> account creation, repository creation, settings, token creation, and connecting the chat GitHub Integration.
> GitHub's menus change over time. If a label differs from what is written here, use the closest
> equivalent and note the difference in the results summary (Part 14).

## Placeholders

| Placeholder | Meaning | Example |
|---|---|---|
| `<you>` | Your personal GitHub username | `jdoe` |
| `<bot>` | Machine account username | `jdoe-ai-bot` |
| `<bot-id>` | Numeric user ID of the machine account (shown in Part 2.6) | `123456789` |

---

## What is scripted and what stays manual

| Part | Now |
|---|---|
| 0, 1, 2 (preparation, account hardening, machine account) | **Manual**, below |
| 3 (create the repositories) | **Manual**, below. The script configures repositories that exist |
| 4, 5, 6 (settings, Actions, security features) | **Script**: `github-setup`. Manual steps in Appendix A.1 to A.3 |
| 7.1 (`main-protection`) | **Script**. Manual steps in Appendix A.4 |
| 7.2 (`release-tags`) | **Manual the first time** (the first release tag needs it, and the approver applies it), below. The script keeps it in the wanted state afterwards |
| 8 (environments) | Declared, deferred to Stage 4. Appendix A.5 |
| 9 (collaborator) | **Script** sends the invitation; **accepting it stays manual**, below. Appendix A.6 |
| 10, 11, 12 (token T1, chat integration, first login) | **Manual**, below |
| 13 (verification) | V3, V7, V8, V9 are covered by the script's dry run and `facts --scope github`; the others stay manual, below |

Run the scripted parts on the platform operator VM, as described in [operator.md](operator.md) (sections 3 and 4). The dry run
needs token T3 and the apply needs T2; both are created for the run and revoked after it. The wanted state is the data file
`scripts/operator/github-desired-state.toml` (its comments name the Parts it implements).

```bash
scripts/operator/github-setup --owner <you> --collaborator <bot>            # dry run (T3): current against wanted, no write call
scripts/operator/github-setup --owner <you> --collaborator <bot> --apply    # apply (T2)
scripts/operator/facts --scope github --owner <you> --repo ai-lab-infrastructure --repo ai-software-template --apply --use-token   # facts (T3)
```

The script cannot set Dependabot grouped updates, discussions, sponsorships, LFS in archives, or the chat integration. Those stay
manual (Appendix A.1 and A.3 list the Console steps).

---

## Part 0: Preparation (5 min)

1. In your password manager, create two entries: **GitHub personal** (if it doesn't exist yet) and **GitHub machine account**. Recovery codes and the token (Part 10) go there.
2. Create a **separate browser profile** named "GitHub machine account", for example a separate Edge or Chrome profile. You use it only for the machine account. This prevents linking the wrong account in Part 11.
3. Choose an email address for the machine account. It must be one you control and not already used on GitHub. A plus-address such as `you+gh-bot@yourmail` works with most providers.
4. Choose a license for both platform repositories. **Recommendation: Apache-2.0** (explicit patent grant); MIT is a simpler alternative. The repositories are public, so a license should be present from the start.

## Part 1: Harden your personal account (10 min)

All steps are under your profile picture → **Settings**.

| # | Setting | Path | Value |
|---|---|---|---|
| 1.1 | Plan | Billing and licensing (or "Billing and plans") → Plans | Confirm **GitHub Free** |
| 1.2 | Payment method | Billing and licensing → Payment information | **Leave empty.** Without a payment method, no paid usage can occur. |
| 1.3 | Budgets | Billing and licensing → Budgets and alerts | If budgets are shown, confirm Actions, Codespaces, and Packages are at **$0** with "stop usage" enabled |
| 1.4 | Two-factor authentication | Password and authentication | Enabled. Add a **passkey**; store recovery codes in the password manager. |
| 1.5 | Email privacy | Emails | Enable **Keep my email addresses private** and **Block command line pushes that expose my email** |
| 1.6 | Push protection for yourself | Code security (or "Advanced Security") | **Enabled** (blocks pushing secrets to any public repository) |
| 1.7 | Default branch for new repos | Repositories | `main` |

## Part 2: Create and harden the machine account (15 min)

Do all of Part 2 in the **machine-account browser profile**. GitHub's Terms of Service allow one free machine account in addition to your personal account. It must be used only for automated tasks, and you are responsible for its actions.

| # | Step |
|---|---|
| 2.1 | Sign up at github.com with the machine-account email and username `<bot>`. Choose GitHub Free. |
| 2.2 | Settings → Public profile. Name: "`<you>` AI engineering bot". Bio: "Machine account operated by @`<you>`." This is for transparency only. |
| 2.3 | Settings → Password and authentication. Enable **2FA** (authenticator app or passkey). Store the TOTP seed or passkey and the recovery codes in the "GitHub machine account" entry. |
| 2.4 | Settings → Emails. Enable **Keep my email addresses private** and **Block command line pushes that expose my email**. |
| 2.5 | Settings → Code security. Enable **push protection for yourself**. |
| 2.6 | Settings → Emails. Note the noreply address, `<bot-id>+<bot>@users.noreply.github.com`. It is needed in Part 12. |
| 2.7 | Do **not** add SSH keys, GPG keys, or a payment method to the machine account. |

## Part 3: Create the two repositories (5 min)

In your **personal** browser profile: **+** → **New repository**, once for each repository.

| Field | `ai-lab-infrastructure` | `ai-software-template` |
|---|---|---|
| Owner | `<you>` | `<you>` |
| Visibility | **Public** | **Public** |
| Description | "OCI Always Free AI engineering lab: infrastructure, toolchain, lifecycle" | "Template for AI-assisted, specification-driven projects" |
| Add README | **Yes** (creates `main`, required for rulesets) | **Yes** |
| .gitignore | None (Claude Code adds it) | None |
| License | Your choice from Part 0.4 | Same |

Do **not** add any other files by hand. Everything else arrives through PRs.

## Parts 4 to 6: settings, Actions, security features

By `github-setup`. The Console steps are in Appendix A.1 to A.3.

## Part 7: Rulesets

`main-protection` (7.1) is applied by `github-setup`; the Console steps are in Appendix A.4.

### 7.2 Tag ruleset `release-tags`

Protects release tags. The lab VM and workspace restore pull only reviewed tags.

**New ruleset** → **New tag ruleset**.

| Field | Value |
|---|---|
| Ruleset name | `release-tags` |
| Enforcement status | **Active** |
| Bypass list | **Repository admin** role, mode **Always** (only you can create release tags) |
| Target tags | Include by pattern: `v*` |
| Restrict creations | **On** |
| Restrict updates | **On** |
| Restrict deletions | **On** |
| Block force pushes | **On** |

## Part 8: Environments

Declared and deferred to Stage 4. See Appendix A.5.

## Part 9: Add the machine account as collaborator

`github-setup` sends the invitation (Appendix A.6 has the Console steps). Accepting it stays manual:

1. **Machine-account profile:** open the invitation from the notification or email and accept it for both repositories.
2. **Personal profile:** confirm both repositories list `<bot>` as an active collaborator.

The machine account must never be added to any other repository. Its token reaches every repository it can access (ADR-001 AC1-1).

## Part 10: Create token T1 (5 min)

In the **machine-account profile**: **Settings** → **Developer settings** → **Personal access tokens** → **Tokens (classic)** → **Generate new token** → **Generate new token (classic)**.

| Field | Value |
|---|---|
| Note | `T1 ai-hosts <yyyy-mm-dd>` |
| Expiration | **90 days**. Add a calendar reminder 7 days before expiry. |
| Scopes | **`repo`** (full), **`workflow`**, **`read:org`** (under `admin:org`; read only) |
| All other scopes | **Unchecked** |

Copy the token **once**, directly into the "GitHub machine account" password manager entry. Do not paste it into any chat, document, or file.

## Part 11: Connect Claude chat's read-only GitHub Integration (10 min)

Per D17, chat gets **read-only** access to the public repositories through Claude's built-in GitHub Integration. Do **not** install the Claude GitHub App, and do not configure the GitHub MCP plugin.

1. In your **default browser**, sign out of GitHub and sign in as `<bot>`.
2. In Claude, go to **Customize** → **Connectors** → **GitHub Integration** → **Connect**, and complete the authorization. If GitHub Integration is not listed, your Claude Enterprise admin must enable GitHub for the organization.
   - **If the screen asks you to install the Claude app on an account or repositories, decline.** It is not needed for public repositories.
3. In the machine-account profile, open **Settings** → **Applications** → **Authorized GitHub Apps** and confirm the Claude entry is there.
4. In your personal profile, open **Settings** → **Applications** (all three tabs) and confirm **no** Claude entry exists. Revoke any that does.
5. Switch your default browser back to your personal GitHub session.
6. Create a Claude Enterprise **Project** for the platform. Add `ai-lab-infrastructure` as project knowledge, selecting only `docs/` and `CLAUDE.md` once they exist. Use **Sync now** before each architecture session.

## Part 12: First login on the workspace (10 min)

Use a **plain SSH terminal** (Windows OpenSSH, via your hops), **not** a Claude session. Later restores use `workspace/restore.sh` (D16); this is the one-time manual equivalent.

```bash
# 1. Base tools; the builder profile will later manage versions
sudo apt-get update && sudo apt-get install -y git gh

# 2. Log in as the machine account; the token is read without echo and not stored in shell history
read -rsp 'Paste token T1: ' GH_TOKEN_IN; echo
printf '%s' "$GH_TOKEN_IN" | gh auth login --hostname github.com --git-protocol https --with-token
unset GH_TOKEN_IN

# 3. Let git use gh for HTTPS credentials
gh auth setup-git

# 4. Commit identity = machine account noreply address
git config --global user.name  "<bot>"
git config --global user.email "<bot-id>+<bot>@users.noreply.github.com"
git config --global init.defaultBranch main
git config --global pull.ff only
```

If `gh` is not available from Debian's repositories, install it from the GitHub CLI's official apt repository (instructions at cli.github.com). Do not use any other source.

## Part 13: Verification (10 min)

V3 (rulesets visible and active), V7, V8, and V9 are covered by the script's dry run and by `facts --scope github`. The rest stay
manual. V5 is also the negative test of acceptance U-4 (the machine account cannot create a `v*` tag).

**On the workspace** (a plain terminal). Replace `<you>`.

```bash
# V1  Logged in as the machine account, with the expected scopes
gh auth status
gh api user --jq .login                           # expect: <bot>

# V2  Collaborator with push but no admin rights
for r in ai-lab-infrastructure ai-software-template; do
  gh api "repos/<you>/$r" --jq "\"$r: \" + (.permissions|tostring)"
done                                               # expect: admin:false, push:true

# V4  Direct push to main is rejected (no change results)
cd /tmp && rm -rf v4 && gh repo clone "<you>/ai-lab-infrastructure" v4 && cd v4
git commit --allow-empty -m "verification: must be rejected"
git push origin HEAD:main                          # expect: rejected by ruleset
git reset --hard origin/main

# V5  Release tag creation is rejected
git tag v0.0.0-verify && git push origin v0.0.0-verify   # expect: rejected
git tag -d v0.0.0-verify

# V6  Settings change is rejected (value matches the current setting, so no effect if it wrongly succeeded)
gh api -X PATCH "repos/<you>/ai-lab-infrastructure" -F has_wiki=false   # expect: 403 or 404
cd ~ && rm -rf /tmp/v4
```

**In the browser** (personal profile):

| # | Check | Expected |
|---|---|---|
| V10 | Machine account → Settings → Applications | Claude GitHub Integration authorized here and **not** on your personal account; no Claude app installed on any repository |

## Part 14: Results summary

Parts 4 to 9 and V3, V7 to V9 are covered by the `github-setup` dry run summary: paste its summary line instead of the lines below.

```text
Part 1  Free plan=__ no payment method=__ passkey=__ push protection=__
Part 2  machine account created=__ 2FA=__ email private=__
Part 3  repos created public with README=__ license=__
Part 4  squash-only=__ auto-merge off=__ template flag on ai-software-template=__
Part 5  actions policy restricted=__ SHA pinning option available/on=__ workflow perms read=__
Part 6  PVR=__ dependabot alerts+security updates=__ secret scanning=__ push protection=__
Part 7  main-protection active=__ release-tags active=__ bypass empty=__
Part 9  collaborator accepted on both=__
Part 10 token created, 90 days, scopes repo/workflow/read:org=__ (O-8: gh accepted it=__)
Part 11 GitHub Integration authorized as machine account=__ no Claude app installed=__ project created=__
Part 13 V1=__ V2=__ V3=__ V4=__ V5=__ V6=__ V7=__ V8=__ V9=__ V10=__
Deviations from this runbook: ________
```

---

## Appendix A: Manual steps replaced by `github-setup`

These are the original manual steps. They stay valid. Use them for anything the script cannot set, when the script is unavailable,
and to roll back the script (see [operator.md](operator.md), section 5). Part numbers are the original ones.

### A.1 Part 4: General repository settings (5 min per repo)

Repository → **Settings** → **General**. Apply to **both** repositories.

| Section | Setting | Value | Why |
|---|---|---|---|
| Template repository | "Template repository" | `ai-software-template`: **on**. `ai-lab-infrastructure`: off. | Template use |
| Features | Wikis | Off | Docs live in the repo |
| | Issues | **On** | CR identity (ADR-003) |
| | Sponsorships, Discussions, Projects | Off | Not used in v1 |
| Pull Requests | Allow merge commits | **Off** | ADR-003 |
| | Allow squash merging | **On**. Default message: **Pull request title and description** | ADR-003 traceability |
| | Allow rebase merging | **Off** | ADR-003 |
| | Always suggest updating pull request branches | On | Fewer stale branches |
| | **Allow auto-merge** | **Off** | Collaborators on personal repositories can enable auto-merge on a PR when this setting allows it |
| | Automatically delete head branches | On | Tidy branches |
| Archives | Include Git LFS objects | Off | Not used |

### A.2 Part 5: GitHub Actions settings (5 min per repo)

Repository → **Settings** → **Actions** → **General**. Apply to **both** repositories.

| Setting | Value |
|---|---|
| Actions permissions | **Allow `<you>`, and select non-`<you>`, actions and reusable workflows**. Enable **Allow actions created by GitHub**. Leave the allowlist empty for now; Claude Code proposes entries by PR, and you add them here. |
| Require full-length commit SHA pinning | **On**, if your settings page offers it |
| Approval for running fork pull request workflows | **Require approval for all external contributors** |
| Workflow permissions | **Read repository contents and packages permissions** |
| Allow GitHub Actions to create and approve pull requests | **Off** |
| Artifact and log retention | 30 days (reduces exposure of public logs) |

### A.3 Part 6: Security settings (5 min per repo)

Repository → **Settings** → **Advanced Security** (may be labeled **Code security**). Apply to **both** repositories.

| Setting | Value | Note |
|---|---|---|
| Private vulnerability reporting | **Enable** | Public repos only |
| Dependency graph | **Enabled** | Default for public repos; confirm |
| Dependabot alerts | **Enable** | |
| Dependabot security updates | **Enable** | Creates PRs; never auto-merged |
| Grouped security updates | **Enable** | Fewer PRs |
| Dependabot version updates | Leave as is | Configured later by PR via `.github/dependabot.yml` |
| Secret scanning (Secret Protection) | **Enabled** | Free for public repos; confirm it is on |
| Push protection | **Enabled** | Confirm it is on |
| Code scanning (CodeQL) | **Defer** | Enable "Default setup" after the first code PR is merged (Stage 1); it needs analyzable content |

### A.4 Part 7.1: Branch ruleset `main-protection`

Repository → **Settings** → **Rules** → **Rulesets**. Create both rulesets in **both** repositories.

#### 7.1 Branch ruleset `main-protection`

**New ruleset** → **New branch ruleset**.

| Field | Value |
|---|---|
| Ruleset name | `main-protection` |
| Enforcement status | **Active** |
| Bypass list | **Empty** (no bypass, including you) |
| Target branches | **Include default branch** |
| Restrict deletions | **On** |
| Require linear history | **On** |
| Require a pull request before merging | **On** |
| → Required approvals | **1** |
| → Dismiss stale pull request approvals when new commits are pushed | **On** |
| → Require review from Code Owners | Off |
| → Require approval of the most recent reviewable push | **On** |
| → Require conversation resolution before merging | **On** |
| → Allowed merge methods | **Squash** only |
| Require status checks to pass | **Leave off for now.** Checks can be selected only after they have run once. Add `pr-contract` and `quality-gate` at the end of Stage 1 (a reminder is in the Stage 1 hand-off). |
| Block force pushes | **On** |

**Break-glass:** if you must change `main` without a machine-account PR, temporarily set the ruleset to **Disabled**, make the change, and re-enable it. Record the reason in an issue. Do not add yourself to the bypass list permanently.

### A.5 Part 8: Environments for `ai-lab-infrastructure` (defer to Stage 4)

Do not create them yet. ADR-002 workflows and Spike S2 come first. They are listed here for completeness.

| Environment | Deployment branches | Required reviewers | Prevent self-review | Allow admins to bypass |
|---|---|---|---|---|
| `oci-plan` | Selected branches: `main` | None | — | **Off** |
| `oci-apply` | Selected branches: `main` | **`<you>` only** | **Off** (you merge and approve) | **Off** |

### A.6 Part 9, step 1 and 3: collaborator invitation

1. **Personal profile:** in each repository, go to **Settings** → **Collaborators** → **Add people** → `<bot>` → **Add**. Personal-account repositories have a single collaborator permission level, push access, so there is no role to choose.
2. Accept the invitation in the machine-account profile (Part 9 above).
3. **Personal profile:** confirm both repositories list `<bot>` as an active collaborator.

### A.7 Part 13: the verification steps the script covers

```bash
# V3  Rulesets visible and active
gh api "repos/<you>/ai-lab-infrastructure/rulesets" --jq '.[].name'   # expect: main-protection, release-tags
```

| # | Check | Expected |
|---|---|---|
| V7 | Both repos → Settings → General → Pull Requests | Squash only; auto-merge off |
| V8 | Both repos → Settings → Rules → Rulesets | Two active rulesets; `main-protection` bypass list empty |
| V9 | Both repos → Settings → Advanced Security | Items in Part 6 enabled |
