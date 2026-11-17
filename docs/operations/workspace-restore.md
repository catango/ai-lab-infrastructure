# Workspace restore runbook

Rebuilds the platform workspace (Debian 13, x86-64) after the home directory is reset. Target: a verified workspace within 15 minutes, with token T1 as the only manual input (ADR-001 section 4a, AC1-7). Design: [CR-2 design, section 4](../cr/CR-2/design.md).

**Run every command here yourself, in a plain SSH terminal.** Never from a Claude Code session: the script refuses to run in one, and token T1 must never reach a session (AC1-8). Placeholders in angle brackets are yours to fill in.

## What survives and what does not

Survives: everything pushed to GitHub, and `/opt/ai-lab` if the disk persists (the profile reapplies either way). Lost by design: uncommitted work, the local `gh` login, Claude Code session state, caches. The rule in each repository's CLAUDE.md is to commit and push after each completed checklist item.

## One-time: cut the first release tag (you)

The restore clones the latest release tag anonymously. Claude never creates tags. After the restore PR is merged and before the first reset test:

```bash
git switch main && git pull --ff-only
git tag -a v0.1.0 -m "Stage 1: workspace foundation"
git push origin v0.1.0
```

## Restore

1. Open a plain SSH terminal to the workspace.
2. Clone the repository at the latest release tag, anonymously over HTTPS, outside `~/work` (so the working clone stays on `main`):

   ```bash
   git clone --depth 1 --branch v0.1.0 https://github.com/<owner>/ai-lab-infrastructure.git ~/restore-v0.1.0
   cd ~/restore-v0.1.0
   ```

3. Read the plan. This changes nothing (no sudo, no apt, no writes, no token prompt, no clone); it runs the playbook in check mode when Ansible is already installed:

   ```bash
   workspace/restore.sh --dry-run
   ```

4. Run it:

   ```bash
   workspace/restore.sh
   ```

   - It calls `sudo -v` first. The sudo password prompt belongs to `sudo`; the script never reads a password. If Ansible still needs the password afterwards (a per-terminal sudo ticket), it asks Ansible to prompt for it.
   - If `ansible-core` is missing it installs it with `sudo apt-get install -y --no-install-recommends ansible-core python3-apt`, then applies `ansible/builder.yml` (the `builder` profile) with local Ansible.
   - It restores `~/.claude/settings.json` and `~/.claude/CLAUDE.md` from `workspace/claude-user/`. A differing file is backed up as `<name>.bak.<timestamp>` first. Credentials, `~/.claude/remote/`, and session state are never touched.
   - It sets the git identity to the machine account and its GitHub noreply address, built from the public profile lookup (no address is stored in the repository).
   - **It then prompts `Token T1:`.** Paste the token from your password manager. Nothing is echoed. The token goes to `gh auth login --with-token` on stdin only: never an argument, an environment variable, a file, or the shell history. A token for another account, or without the `repo` and `workflow` scopes, is refused and removed.
   - It clones the repositories in `workspace/repos.txt` into `~/work/`, creates local tracking branches for the open PRs of the machine account (it prints `git switch <branch>` for each), and runs the verification.

5. Read the summary line (`restore: complete in <n>s (target 900s)`) and the `verify:` lines. Each step prints its own time.
6. Connect the Claude Desktop SSH session. It redeploys its engine under `~/.claude/remote/` by itself. Then run `resume-work` on the relevant PR.

Exit codes: `0` restored and verified; `1` restored but verification failed; `2` usage or preflight error (nothing changed); `3` a step failed.

Options: `--dry-run`, `--reauth` (ask for the token even when `gh` is logged in), `--skip-clone` (only re-run verification).

Running it again on a restored workspace changes nothing, does not ask for the token, and never resets a clone with uncommitted changes (it reports them).

## Verification

`workspace/verify.sh` runs at the end and can be run alone (it is read-only):

| ID | Checks |
|---|---|
| V-1 | Every `builder` tool answers its smoke command with the manifest version |
| V-2 | Every clone in `~/work/` has the required deny rules, bypass-permissions mode disabled, project MCP servers not enabled, and no `.mcp.json` (static check) |
| V-3 | The token belongs to the machine account and has the `repo` and `workflow` scopes; warns under 14 days to expiry; warns when it is stored in a file, and fails when that file is not mode 0600 |
| V-4 | No OCI credentials: no `~/.oci/`, no `oci` binary, no `OCI_` variable |
| V-5 | Git identity is the machine account's noreply address |
| V-6 | Every repository in `repos.txt` is cloned with the expected origin |

Where the system has no keyring, `gh` stores the token in `~/.config/gh/`; the home directory is ephemeral by design, so this is accepted and reported as a warning.

## Guardrail probe (manual, once per reset)

The static check cannot prove Claude Code enforces the rules. In a new Claude Code session in `~/work/ai-lab-infrastructure`, ask Claude to run each of these harmless commands and confirm every one is refused by a permission rule: `git push --dry-run origin HEAD:main`, `gh pr merge 1`, `sudo true`, `printenv`.

## Reset test (R-4, AC1-7)

You run this once after the restore PR is merged and the tag exists. It resets the home directory, so make sure everything you want is pushed.

1. Push or discard all work. Note the time.
2. Simulate the reset (keeps `~/restore-v0.1.0` if you already cloned it; adjust to taste):

   ```bash
   mkdir -p ~/reset-backup && mv ~/work ~/.claude ~/.config/gh ~/.gitconfig ~/reset-backup/ 2>/dev/null || true
   ```

3. Follow **Restore** above from step 2, timing the run (the script prints per-step times).
4. Record in the PR: total time, any step over its expected time, any prompt other than token T1 and sudo, and the `verify:` lines. Then remove `~/reset-backup` after you have checked nothing is missing.

## Notes for maintainers

- The test seams `AI_LAB_PREFIX`, `AI_LAB_MANIFEST`, `AI_LAB_OS_RELEASE`, and `AI_LAB_MACHINE` exist so the tests can run against a temporary home; do not set them in normal use.
- `workspace/claude-user/required-deny.txt` must equal the deny list in `.claude/settings.json`; a test fails when they drift.
- Rotation of token T1 follows ADR-001 section 4 (90-day expiry): [ADR-001](../adr/ADR-001-trust-model-and-execution.md).
