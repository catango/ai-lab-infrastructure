#!/usr/bin/env bash
# Tests for workspace/restore.sh and workspace/verify.sh (CR-2: R-1 to R-10, D-1), run against a
# temporary HOME with stubbed sudo, gh, ansible-playbook, apt-get, and curl. Nothing touches the real
# home, the network, or the system. Usage: tests/workspace/run.sh [name-fragment]
set -euo pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
ROOT=$(cd "$HERE/../.." && pwd -P)
STUBS="$HERE/stubs"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
FILTER=${1:-}

export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null
PASSED=0
FAILED=0
ok() {
  PASSED=$((PASSED + 1))
  printf 'ok   %s\n' "$1"
}
fail() {
  FAILED=$((FAILED + 1))
  printf 'FAIL %s\n' "$1"
  if [[ -n ${2:-} ]]; then printf '     %s\n' "${2:0:300}"; fi
}
selected() { [[ -z $FILTER || $1 == *"$FILTER"* ]]; }
has() { grep -qF -- "$2" <<<"$1"; }
# check NAME STATUS [DETAIL]: STATUS 0 is a pass
check() {
  if [[ $2 -eq 0 ]]; then ok "$1"; else fail "$1" "${3:-}"; fi
}
# when_ok CONDITION...: prints 0 when the command succeeds, else 1 (for use inside check)
when_ok() {
  if "$@"; then echo 0; else echo 1; fi
}

config_get() { sed -n "s/^[[:space:]]*$1:[[:space:]]*\"\{0,1\}\([A-Za-z0-9-]*\).*/\1/p" "$ROOT/config/project.yaml" | head -n 1; }
OWNER=$(config_get owner)
MACHINE=$(config_get machine_login)
REPO_NAME=ai-lab-infrastructure
TOKEN="canary-token-0123456789abcdef"

# content and layout of a home directory; clones' .git directories are left out (git fetch rewrites them)
snapshot() {
  (
    cd "$1"
    find . -path ./work -prune -o -print 2>/dev/null | LC_ALL=C sort
    find . -path ./work -prune -o -type f -exec sha256sum {} + 2>/dev/null | LC_ALL=C sort
    if [[ -d work ]]; then find work -path '*/.git' -prune -o -print | LC_ALL=C sort; fi
  )
}

# ---------------------------------------------------------------- one isolated case

mkcase() {
  C=$(mktemp -d "$WORK/case.XXXXXX")
  H="$C/home" STATE="$C/state" LOG="$C/calls.log" PFX="$C/prefix" MANIFEST="$C/manifest.toml" OSREL="$C/os-release" ORIGIN="$C/origin.git"
  mkdir -p "$H" "$STATE" "$PFX/bin" "$PFX/tools/alpha/1.2.3/bin"
  : >"$LOG"
  printf '#!/bin/sh\necho alpha 1.2.3\n' >"$PFX/tools/alpha/1.2.3/bin/alpha"
  chmod +x "$PFX/tools/alpha/1.2.3/bin/alpha"
  ln -s ../tools/alpha/1.2.3/bin/alpha "$PFX/bin/alpha"
  cat >"$MANIFEST" <<'TOML'
schema_version = 1

[tools.alpha]
version = "1.2.3"
profiles = ["builder"]
source = "download"
format = "tar.gz"
strip = 1
binaries = ["bin/alpha"]
smoke = ["alpha", "--version"]
smoke_match = "alpha 1.2.3"

[tools.alpha.artifacts.amd64]
url = "https://example.invalid/alpha/1.2.3/alpha-amd64.tar.gz"
sha256 = "0000000000000000000000000000000000000000000000000000000000000001"

[tools.alpha.artifacts.arm64]
url = "https://example.invalid/alpha/1.2.3/alpha-arm64.tar.gz"
sha256 = "0000000000000000000000000000000000000000000000000000000000000002"
TOML
  printf 'ID=debian\nVERSION_ID="13"\n' >"$OSREL"
  # A local origin that stands in for GitHub through url.insteadOf; the clone keeps the https remote.
  local seed="$C/seed"
  git init -q -b main "$seed"
  mkdir -p "$seed/.claude"
  cp "$ROOT/.claude/settings.json" "$seed/.claude/settings.json"
  git -C "$seed" add -A
  git -C "$seed" -c user.name=t -c user.email=noreply commit -q -m seed
  git -C "$seed" branch impl/CR-2-pr
  git clone -q --bare "$seed" "$ORIGIN"
  printf '[url "file://%s"]\n\tinsteadOf = https://github.com/%s/%s.git\n' "$ORIGIN" "$OWNER" "$REPO_NAME" >"$H/.gitconfig"
  RUN_ENV=()
  REPLIES=(--reply "Token T1:=$TOKEN")
}

runenv() {
  env -i PATH="$STUBS:/usr/bin:/bin" HOME="$H" LANG=C.UTF-8 TERM=dumb STUB_STATE="$STATE" STUB_LOG="$LOG" STUB_LOGIN="$MACHINE" \
    AI_LAB_PREFIX="$PFX" AI_LAB_MANIFEST="$MANIFEST" AI_LAB_OS_RELEASE="$OSREL" AI_LAB_MACHINE=x86_64 "${RUN_ENV[@]}" "$@"
}
restore_tty() { runenv python3 -I "$HERE/pty_run.py" --timeout 120 "${REPLIES[@]}" -- bash "$ROOT/workspace/restore.sh" "$@"; }
restore_notty() { runenv bash "$ROOT/workspace/restore.sh" "$@" </dev/null; }
verify_run() { runenv bash "$ROOT/workspace/verify.sh" --prefix "$PFX" "$@" </dev/null; }
OUT=""
RC=0
capture() {
  RC=0
  OUT=$("$@" 2>&1) || RC=$?
}
log_has() { grep -qF -- "$1" "$LOG"; }

# ---------------------------------------------------------------- R-1 and R-2

if selected dry-run; then
  mkcase
  before=$(snapshot "$H")
  repo_before=$(git -C "$ROOT" status --porcelain)
  capture restore_notty --dry-run
  check "R-1 dry-run exits 0" "$RC" "$OUT"
  check "R-1 dry-run leaves the home directory unchanged" "$(when_ok test "$before" == "$(snapshot "$H")")"
  check "R-1 dry-run leaves the repository unchanged" "$(when_ok test "$repo_before" == "$(git -C "$ROOT" status --porcelain)")"
  check "R-1 dry-run does not create ~/work" "$(when_ok test ! -e "$H/work")"
  for step in "system and toolchain" "claude user configuration" "git identity" "token" "repositories" "verification"; do
    check "R-1 dry-run announces: $step" "$(when_ok has "$OUT" "[dry-run] $step:")" "$OUT"
  done
  bad=$(grep -E '^(sudo|apt-get|gh) ' "$LOG" || true)
  check "R-1 dry-run runs no sudo, apt, or gh" "$(when_ok test -z "$bad")" "$bad"
  not_check=$(grep -E '^ansible-playbook' "$LOG" | grep -vF -- '--check' || true)
  check "R-1 dry-run only checks the playbook (check mode)" "$(when_ok test -z "$not_check")" "$not_check"
  check "R-1 dry-run never prompts for the token" "$(when_ok test -z "$(grep -F 'Token T1' <<<"$OUT" || true)")"
fi

if selected refuse; then
  mkcase
  before=$(snapshot "$H")
  capture restore_notty
  check "R-2 refuses without a terminal on stdin (exit 2)" "$(when_ok test "$RC" -eq 2)" "rc=$RC $OUT"
  check "R-2 says why" "$(when_ok has "$OUT" "terminal")" "$OUT"
  check "R-2 changed nothing and ran nothing" "$(when_ok test "$before" == "$(snapshot "$H")" -a ! -s "$LOG")"
  for marker in CLAUDECODE=1 CLAUDE_CODE_ENTRYPOINT=cli; do
    mkcase
    RUN_ENV=("$marker")
    capture restore_tty
    check "R-2 refuses inside a Claude Code session ($marker)" "$([[ $RC -eq 2 ]] && has "$OUT" "Claude Code" && echo 0 || echo 1)" "rc=$RC $OUT"
    check "R-2 ($marker) ran nothing" "$(when_ok test ! -s "$LOG")"
  done
  mkcase
  printf 'ID=ubuntu\nVERSION_ID="24.04"\n' >"$OSREL"
  capture restore_tty
  check "preflight refuses another OS (exit 2, nothing run)" "$(when_ok test "$RC" -eq 2 -a ! -s "$LOG")" "rc=$RC $OUT"
  mkcase
  RUN_ENV=(AI_LAB_MACHINE=aarch64)
  capture restore_tty
  check "preflight refuses another architecture" "$(when_ok test "$RC" -eq 2 -a ! -s "$LOG")" "rc=$RC $OUT"
  mkcase
  RUN_ENV=(STUB_CURL_FAIL=1)
  capture restore_tty
  check "preflight refuses when the network is unreachable" "$(when_ok test "$RC" -eq 2)" "rc=$RC $OUT"
  check "preflight stops before any step ran" "$(when_ok test -z "$(grep -E '^(sudo|ansible-playbook|gh)' "$LOG" || true)")"
  mkcase
  capture runenv bash -x "$ROOT/workspace/restore.sh" --dry-run
  check "restore.sh aborts under set -x" "$([[ $RC -eq 2 ]] && has "$OUT" "set -x" && echo 0 || echo 1)" "rc=$RC"
  capture runenv bash "$ROOT/workspace/restore.sh" --bogus
  check "unknown option is a usage error (exit 2)" "$(when_ok test "$RC" -eq 2)"
fi

# ---------------------------------------------------------------- full restore, R-3 to R-7

if selected restore; then
  mkcase
  mkdir -p "$H/.claude/remote/engine" "$H/.claude/projects" "$H/.claude/rules"
  printf '{"old": true}\n' >"$H/.claude/settings.json"
  printf 'canary-credential\n' >"$H/.claude/.credentials.json"
  printf 'engine\n' >"$H/.claude/remote/engine/x"
  printf 'session\n' >"$H/.claude/projects/p.json"
  printf 'unrelated\n' >"$H/.claude/rules/mine-not-ours.txt"
  untouched() { (cd "$H/.claude" && sha256sum .credentials.json remote/engine/x projects/p.json rules/mine-not-ours.txt); }
  untouched_before=$(untouched)
  RUN_ENV=("STUB_PRS=$(printf 'impl/CR-2-pr\nx/../y\n')")
  capture restore_tty
  check "R-4 restore exits 0 with a verified workspace" "$RC" "$OUT"
  for n in 1 2 3 4 5 6; do check "R-4 step $n/6 is reported with its time" "$(when_ok has "$OUT" "$n/6")"; done
  check "R-4 reports total time against the 15-minute target" "$([[ $OUT == *target* && $OUT == *900* ]] && echo 0 || echo 1)"
  check "R-4 ends with the verification summary" "$(when_ok has "$OUT" "verify: 6 passed, 0 failed")" "$OUT"
  order=$(grep -nE '^(sudo -v|ansible-playbook|gh auth login|gh auth setup-git|gh pr list)' "$LOG" | sed -E 's/^[0-9]+://; s/ .*//' | tr '\n' ' ')
  check "R-4 steps run in the documented order" "$([[ $order == "sudo ansible-playbook gh gh gh "* ]] && echo 0 || echo 1)" "$order"
  check "R-3 login goes through stdin with --with-token" "$(when_ok log_has 'gh auth login --hostname github.com --with-token')"
  check "R-3 the token is not in the terminal output (no echo)" "$([[ $OUT != *"$TOKEN"* ]] && echo 0 || echo 1)"
  check "R-3 the token is not in any recorded argument" "$([[ -z $(grep -F -- "$TOKEN" "$LOG" || true) ]] && echo 0 || echo 1)"
  check "R-3 gh auth token is never called" "$([[ -z $(grep -F 'auth token' "$LOG" || true) ]] && echo 0 || echo 1)"
  check "R-3 gh received the token on stdin" "$([[ $(cat "$STATE/token_stdin") == "$TOKEN" ]] && echo 0 || echo 1)"
  leak=$(grep -rlF -- "$TOKEN" "$H" "$ROOT/workspace" "$ROOT/docs" 2>/dev/null || true)
  check "R-3 the token is in no file under HOME or the repository" "$(when_ok test -z "$leak")" "$leak"
  check "R-3 no shell history is written" "$(when_ok test -z "$(find "$H" -name '*history*' 2>/dev/null)")"
  backup=$(find "$H/.claude" -maxdepth 1 -name 'settings.json.bak.*' | head -n 1)
  check "R-6 differing settings were backed up with the old content" "$([[ -n $backup ]] && grep -q old "$backup" && echo 0 || echo 1)"
  check "R-6 settings.json is restored from workspace/claude-user" "$(when_ok cmp -s "$H/.claude/settings.json" "$ROOT/workspace/claude-user/settings.json")"
  check "R-6 user instructions are restored" "$(when_ok cmp -s "$H/.claude/CLAUDE.md" "$ROOT/workspace/claude-user/CLAUDE.md")"
  check "R-6 credential, remote, session, and unrelated files are untouched" "$(when_ok test "$untouched_before" == "$(untouched)")"
  check "git identity: name is the machine login" "$([[ $(git config --file "$H/.gitconfig" user.name) == "$MACHINE" ]] && echo 0 || echo 1)"
  check "git identity: email is the noreply address from the profile lookup" "$([[ $(git config --file "$H/.gitconfig" user.email) == "424242+$MACHINE@users.noreply.github.com" ]] && echo 0 || echo 1)"
  clone="$H/work/$REPO_NAME"
  check "step 5 cloned the repository" "$(when_ok test -d "$clone/.git")"
  check "R-7 a local tracking branch exists for the open PR" "$(when_ok git -C "$clone" show-ref --verify -q refs/heads/impl/CR-2-pr)"
  check "R-7 the checked-out branch is unchanged" "$([[ $(git -C "$clone" symbolic-ref --short HEAD) == main ]] && echo 0 || echo 1)"
  check "R-7 an invalid branch name from the API is skipped" "$([[ $OUT == *skipping* && -z $(git -C "$clone" for-each-ref 'refs/heads/x*') ]] && echo 0 || echo 1)" "$OUT"
  check "R-7 prints a git switch hint" "$(when_ok has "$OUT" "git switch impl/CR-2-pr")"

  # R-5: a second run changes nothing, does not prompt, and does not reset a dirty clone
  printf 'work in progress\n' >"$clone/dirty.txt"
  : >"$LOG"
  snap=$(snapshot "$H")
  capture restore_tty
  check "R-5 second run exits 0" "$RC" "$OUT"
  check "R-5 second run does not prompt for the token" "$([[ $OUT != *"Token T1"* && -z $(grep -F 'auth login' "$LOG" || true) ]] && echo 0 || echo 1)"
  check "R-5 second run changes nothing outside the clones' .git" "$(when_ok test "$snap" == "$(snapshot "$H")")"
  check "R-5 a dirty clone is reported and left alone" "$([[ -f $clone/dirty.txt && $OUT == *uncommitted* ]] && echo 0 || echo 1)"
  check "R-5 no second backup was made" "$([[ $(find "$H/.claude" -maxdepth 1 -name 'settings.json.bak.*' | wc -l) -eq 1 ]] && echo 0 || echo 1)"
  : >"$LOG"
  capture restore_tty --reauth
  check "--reauth asks for the token again" "$([[ $OUT == *"Token T1"* && -n $(grep -F 'auth login' "$LOG" || true) ]] && echo 0 || echo 1)" "$OUT"
  capture restore_tty --skip-clone
  check "--skip-clone run exits 0" "$RC" "$OUT"
fi

# ---------------------------------------------------------------- failures

if selected failure; then
  mkcase
  RUN_ENV=(STUB_ANSIBLE_RC=2)
  capture restore_tty
  check "a failing playbook is exit 3 and stops before the token step" "$([[ $RC -eq 3 && $OUT != *"Token T1"* ]] && echo 0 || echo 1)" "rc=$RC $OUT"
  mkcase
  RUN_ENV=(STUB_LOOKUP_FAIL=1)
  capture restore_tty
  check "a failed profile lookup is exit 3" "$(when_ok test "$RC" -eq 3)" "rc=$RC"
  mkcase
  RUN_ENV=(STUB_LOGIN=someone-else)
  capture restore_tty
  check "a token for another login is rejected and logged out" "$([[ $RC -eq 3 ]] && log_has "auth logout" && echo 0 || echo 1)" "rc=$RC $OUT"
  mkcase
  RUN_ENV=("STUB_SCOPES=repo")
  capture restore_tty
  check "a token without the workflow scope is rejected" "$([[ $RC -eq 3 && $OUT == *workflow* ]] && echo 0 || echo 1)" "rc=$RC $OUT"
  mkcase
  RUN_ENV=(STUB_SUDO_NEEDS_PASSWORD=1)
  capture restore_tty
  check "when the sudo ticket is not shared, Ansible is asked to prompt (the script never reads a password)" "$(when_ok grep -q 'ansible-playbook .*--ask-become-pass' "$LOG")" "$(cat "$LOG")"
fi

# ---------------------------------------------------------------- verify.sh

# a workspace that passes every check
good_state() {
  mkcase
  RUN_ENV=()
  # shellcheck disable=SC2016  # the inner shell expands these
  runenv bash -c '
    git config --global user.name "$0"
    git config --global user.email "424242+$0@users.noreply.github.com"
    mkdir -p "$HOME/work" && git clone -q "https://github.com/$1/$2.git" "$HOME/work/$2"
  ' "$MACHINE" "$OWNER" "$REPO_NAME"
  : >"$STATE/loggedin"
  CLONE="$H/work/$REPO_NAME"
}
v_out() { capture verify_run; }
# expect_fail NAME ID: the last verify run failed with that check
expect_fail() {
  check "$1" "$([[ $RC -eq 1 ]] && grep -qE "^FAIL $2:" <<<"$OUT" && echo 0 || echo 1)" "rc=$RC $OUT"
}
edit_settings() { jq "$1" "$CLONE/.claude/settings.json" >"$C/s.json" && mv "$C/s.json" "$CLONE/.claude/settings.json"; }
gh_login_with_file() { printf 'x\n' | runenv gh auth login --hostname github.com --with-token; }

if selected verify; then
  good_state
  v_out
  check "verify passes a good workspace (exit 0)" "$RC" "$OUT"
  for id in V-1 V-2 V-3 V-4 V-5 V-6; do check "verify reports $id as PASS" "$([[ -n $(grep -E "^PASS $id:" <<<"$OUT" || true) ]] && echo 0 || echo 1)" "$OUT"; done
  check "verify ends with a summary line" "$(when_ok has "$OUT" "verify: 6 passed, 0 failed")"

  good_state
  printf '#!/bin/sh\necho alpha 9.9.9\n' >"$PFX/tools/alpha/1.2.3/bin/alpha"
  v_out
  expect_fail "R-8 a tool version that differs fails V-1" V-1

  good_state
  edit_settings 'del(.permissions.deny[0])'
  v_out
  expect_fail "R-8 a missing deny rule fails V-2" V-2
  good_state
  edit_settings 'del(.permissions.disableBypassPermissionsMode)'
  v_out
  expect_fail "V-2 fails when bypass-permissions mode is not disabled" V-2
  good_state
  edit_settings '.enableAllProjectMcpServers = true'
  v_out
  expect_fail "V-2 fails when project MCP servers are enabled" V-2
  good_state
  printf '{}\n' >"$CLONE/.mcp.json"
  v_out
  expect_fail "V-2 fails when .mcp.json exists" V-2

  good_state
  RUN_ENV=("STUB_SCOPES=repo, read:org")
  v_out
  expect_fail "R-8 token scopes without workflow fail V-3" V-3
  good_state
  RUN_ENV=("STUB_SCOPES=workflow")
  v_out
  expect_fail "R-8 token scopes without repo fail V-3" V-3
  good_state
  RUN_ENV=(STUB_LOGIN=someone-else)
  v_out
  expect_fail "V-3 fails for another login" V-3
  good_state
  RUN_ENV=("STUB_EXPIRY=$(date -u -d '+3 days' '+%Y-%m-%d %H:%M:%S UTC')")
  v_out
  check "V-3 warns when the token expires within 14 days" "$([[ $RC -eq 0 && -n $(grep -E '^WARN V-3:.*expir' <<<"$OUT" || true) ]] && echo 0 || echo 1)" "rc=$RC $OUT"
  good_state
  RUN_ENV=(STUB_TOKEN_FILE=1 STUB_TOKEN_FILE_MODE=600)
  gh_login_with_file
  v_out
  check "R-10 a token stored in a file (mode 0600) is a warning, not a failure" "$([[ $RC -eq 0 && -n $(grep -E '^WARN V-3:.*file' <<<"$OUT" || true) ]] && echo 0 || echo 1)" "rc=$RC $OUT"
  good_state
  RUN_ENV=(STUB_TOKEN_FILE=1 STUB_TOKEN_FILE_MODE=644)
  gh_login_with_file
  v_out
  expect_fail "R-10 a token file that is not mode 0600 fails V-3" V-3

  good_state
  RUN_ENV=(OCI_CANARY=canary-value-should-not-print)
  v_out
  expect_fail "R-8 an OCI_ variable fails V-4" V-4
  check "R-9 the variable name may be shown but never its value" "$([[ $OUT == *OCI_CANARY* && $OUT != *canary-value-should-not-print* ]] && echo 0 || echo 1)" "$OUT"
  good_state
  mkdir "$H/.oci"
  v_out
  expect_fail "R-8 a ~/.oci directory fails V-4" V-4
  good_state
  mkdir "$C/fakebin"
  printf '#!/bin/sh\n' >"$C/fakebin/oci"
  chmod +x "$C/fakebin/oci"
  capture env -i PATH="$C/fakebin:$STUBS:/usr/bin:/bin" HOME="$H" STUB_STATE="$STATE" STUB_LOG="$LOG" STUB_LOGIN="$MACHINE" AI_LAB_MANIFEST="$MANIFEST" bash "$ROOT/workspace/verify.sh" --prefix "$PFX" </dev/null
  expect_fail "an oci binary on PATH fails V-4" V-4

  good_state
  git config --file "$H/.gitconfig" user.name wrong
  v_out
  expect_fail "R-8 a wrong git user.name fails V-5" V-5
  good_state
  git config --file "$H/.gitconfig" user.email someone@example.org
  v_out
  expect_fail "R-8 a non-noreply git email fails V-5" V-5

  good_state
  rm -rf "$CLONE"
  v_out
  expect_fail "a missing clone fails V-6" V-6
  good_state
  git -C "$CLONE" remote set-url origin "https://github.com/$OWNER/other.git"
  v_out
  expect_fail "a clone with the wrong origin fails V-6" V-6

  good_state
  mkdir -p "$H/.config/gh"
  printf 'github.com:\n  oauth_token: %s\n' "$TOKEN" >"$H/.config/gh/hosts.yml"
  chmod 600 "$H/.config/gh/hosts.yml"
  RUN_ENV=(SECRET_CANARY=canary-env-value-should-not-print)
  v_out
  check "R-9 verify never prints a token or an environment value" "$([[ $OUT != *"$TOKEN"* && $OUT != *canary-env-value-should-not-print* ]] && echo 0 || echo 1)" "$OUT"
fi

# ---------------------------------------------------------------- static checks and shipped data

if selected static; then
  for f in workspace/restore.sh workspace/verify.sh workspace/lib/*.sh; do
    bad=$(grep -nE '(^|[^a-z_])eval[[:space:]]|\|[[:space:]]*(ba)?sh([[:space:]]|$)' "$ROOT/$f" || true)
    check "$f exists, has no eval, and no pipe into a shell" "$([[ -f $ROOT/$f && -z $bad ]] && echo 0 || echo 1)" "$bad"
  done
  check "the token only ever travels through a here-string to gh" "$(when_ok grep -q 'with-token <<<' "$ROOT/workspace/restore.sh")"
  forbidden=$(grep -nE 'GH_TOKEN|GITHUB_TOKEN|--token' "$ROOT/workspace/restore.sh" || true)
  check "there is no token argument or environment input" "$(when_ok test -z "$forbidden")" "$forbidden"
  deny_settings=$(jq -r '.permissions.deny[]' "$ROOT/.claude/settings.json" | LC_ALL=C sort)
  deny_required=$(grep -vE '^[[:space:]]*(#|$)' "$ROOT/workspace/claude-user/required-deny.txt" | LC_ALL=C sort)
  deny_user=$(jq -r '.permissions.deny[]' "$ROOT/workspace/claude-user/settings.json" | LC_ALL=C sort)
  check "required-deny.txt equals the deny rules of .claude/settings.json" "$(when_ok test "$deny_settings" == "$deny_required")"
  check "the user-level settings carry the same deny rules" "$(when_ok test "$deny_user" == "$deny_required")"
  check "the user-level settings disable bypass mode and project MCP servers" "$(when_ok jq -e '.permissions.disableBypassPermissionsMode == "disable" and .enableAllProjectMcpServers == false' "$ROOT/workspace/claude-user/settings.json" >/dev/null)"
  names=$(grep -vE '^[[:space:]]*(#|$)' "$ROOT/workspace/repos.txt" || true)
  check "repos.txt lists plain repository names, including this one" "$([[ -n $names && -z $(grep -vE '^[A-Za-z0-9._-]+$' <<<"$names" || true) && -n $(grep -x "$REPO_NAME" <<<"$names" || true) ]] && echo 0 || echo 1)"
  runbook="$ROOT/docs/operations/workspace-restore.md"
  check "D-1 the runbook exists and has the exact commands" "$([[ -f $runbook ]] && grep -q 'restore.sh --dry-run' "$runbook" && grep -q 'v0.1.0' "$runbook" && grep -q 'sudo' "$runbook" && echo 0 || echo 1)"
fi

printf 'tests: %d passed, %d failed, 0 skipped\n' "$PASSED" "$FAILED"
if [[ $FAILED -gt 0 ]]; then exit 1; fi
