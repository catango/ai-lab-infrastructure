#!/usr/bin/env bash
# Workspace restore (ADR-001 section 4a steps 3 to 5; CR-2 design section 4). Idempotent.
# Usage: workspace/restore.sh [--dry-run] [--reauth] [--skip-clone] [--help]
# Exit codes: 0 restored and verified; 1 restored but verification failed; 2 usage or preflight error
# (nothing changed); 3 a restore step failed. The token is read only from an interactive terminal.
set -euo pipefail

# A trace would print the token as it is read and passed on.
if [[ $- == *x* ]]; then
  echo "restore: refusing to run with set -x (it would trace the token)" >&2
  exit 2
fi
unset HISTFILE
set +o history 2>/dev/null || true

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)
# shellcheck source=lib/log.sh source-path=SCRIPTDIR
. "$ROOT/workspace/lib/log.sh"
# shellcheck source=lib/config.sh source-path=SCRIPTDIR
. "$ROOT/workspace/lib/config.sh"
# shellcheck source=lib/preflight.sh source-path=SCRIPTDIR
. "$ROOT/workspace/lib/preflight.sh"

DRY_RUN=0
REAUTH=0
SKIP_CLONE=0
TARGET_SECONDS=900
PREFIX=${AI_LAB_PREFIX:-/opt/ai-lab}
WORK_DIR="$HOME/work"
CLAUDE_DIR="$HOME/.claude"

usage() { echo "usage: workspace/restore.sh [--dry-run] [--reauth] [--skip-clone] [--help]"; }
for arg in "$@"; do
  case $arg in
    --dry-run) DRY_RUN=1 ;;
    --reauth) REAUTH=1 ;;
    --skip-clone) SKIP_CLONE=1 ;;
    --help | -h)
      usage
      exit 0
      ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
done

load_config || exit 2

# ---------------------------------------------------------------- preflight (nothing changes before it passes)

preflight() {
  local reason check
  local checks=(pf_platform pf_not_root)
  if [[ $DRY_RUN -eq 0 ]]; then checks+=(pf_no_claude_session pf_terminal); fi
  checks+=(pf_network)
  for check in "${checks[@]}"; do
    if ! reason=$("$check"); then
      printf 'restore: preflight failed: %s\n' "$reason" >&2
      exit 2
    fi
  done
}
preflight

# ---------------------------------------------------------------- helpers

START=$(date +%s)
STEP_START=$START
STEP_TOTAL=6
step() { # step N TITLE
  STEP_START=$(date +%s)
  CURRENT_STEP=$1
  printf '==> %s/%s %s\n' "$1" "$STEP_TOTAL" "$2"
}
step_done() { printf '    done in %ss\n' "$(($(date +%s) - STEP_START))"; }
step_fail() { # step_fail MESSAGE
  printf 'restore: step %s/%s failed: %s\n' "$CURRENT_STEP" "$STEP_TOTAL" "$1" >&2
  exit 3
}
plan() { printf '[dry-run] %s: %s\n' "$1" "$2"; }
CURRENT_STEP=0

# ---------------------------------------------------------------- dry run

if [[ $DRY_RUN -eq 1 ]]; then
  plan "system and toolchain" "would run sudo -v, install ansible-core from apt if it is absent, and apply ansible/builder.yml"
  if command -v ansible-playbook >/dev/null 2>&1; then
    # Ansible would create ~/.ansible; a dry run must not touch the home directory, so it works in a temporary one.
    dry_tmp=$(mktemp -d)
    trap 'rm -rf "$dry_tmp"' EXIT
    export ANSIBLE_HOME="$dry_tmp" ANSIBLE_LOCAL_TEMP="$dry_tmp/local" ANSIBLE_REMOTE_TEMP="$dry_tmp/remote"
    if ANSIBLE_CONFIG="$ROOT/ansible/ansible.cfg" ansible-playbook -i "$ROOT/ansible/inventory/localhost.yml" --check --diff \
      -e ai_lab_become=false -e "toolchain_prefix=$PREFIX" "$ROOT/ansible/builder.yml"; then
      plan "system and toolchain" "the playbook check finished (nothing was applied)"
    else
      plan "system and toolchain" "the playbook check did not finish without privileges; that is expected before the first restore"
    fi
  fi
  for rel in settings.json CLAUDE.md; do
    if [[ -f $ROOT/workspace/claude-user/$rel ]]; then
      if [[ ! -e $CLAUDE_DIR/$rel ]]; then
        plan "claude user configuration" "would create ~/.claude/$rel"
      elif ! cmp -s "$ROOT/workspace/claude-user/$rel" "$CLAUDE_DIR/$rel"; then
        plan "claude user configuration" "would back up and replace ~/.claude/$rel"
      fi
    fi
  done
  plan "claude user configuration" "files outside the allowlist, ~/.claude/remote/, and credentials are never touched"
  plan "git identity" "would set user.name to $MACHINE_LOGIN and user.email to the account's noreply address (public profile lookup)"
  plan "token" "would ask for token T1 on this terminal unless gh is already logged in (never in dry-run)"
  while IFS= read -r name; do
    plan "repositories" "would clone or fetch $OWNER/$name into ~/work/$name and create local branches for the open PRs of $MACHINE_LOGIN"
  done < <(repo_names)
  plan "verification" "would run workspace/verify.sh"
  exit 0
fi

# ---------------------------------------------------------------- step 1: system and toolchain

step 1 "System and toolchain"
sudo -v || step_fail "sudo is not available to this user"
if ! command -v ansible-playbook >/dev/null 2>&1; then
  sudo apt-get update -q || step_fail "apt-get update failed"
  sudo apt-get install -y --no-install-recommends ansible-core python3-apt || step_fail "could not install ansible-core"
fi
# sudo tickets are per terminal: the `sudo -v` above does not carry over to Ansible's become, which runs in
# its own session and fails with "a password is required". `-k` ignores the cached ticket, so this succeeds
# only when sudo needs no password; otherwise Ansible prompts once ("BECOME password:") and the script never
# reads the password itself.
become_args=()
if ! sudo -n -k true 2>/dev/null; then become_args=(--ask-become-pass); fi
export ANSIBLE_CONFIG="$ROOT/ansible/ansible.cfg"
ansible-playbook -i "$ROOT/ansible/inventory/localhost.yml" "${become_args[@]}" -e "toolchain_prefix=$PREFIX" \
  "$ROOT/ansible/builder.yml" || step_fail "the builder profile did not apply"
step_done

# ---------------------------------------------------------------- step 2: Claude user configuration

# Only these paths are ever written. Anything else in ~/.claude (credentials, remote/, sessions) is never touched.
step 2 "Claude user configuration"
install_user_file() { # install_user_file RELATIVE-PATH
  local rel=$1 src="$ROOT/workspace/claude-user/$1" dest="$CLAUDE_DIR/$1" stamp backup
  [[ -f $src ]] || return 0
  if [[ -L $dest ]]; then
    # shellcheck disable=SC2088  # a display path, not a path to expand
    warn "~/.claude/$rel is a symbolic link; leaving it alone"
    return 0
  fi
  if [[ -f $dest ]] && cmp -s "$src" "$dest"; then
    log "    ~/.claude/$rel: up to date"
    return 0
  fi
  mkdir -p "$(dirname "$dest")"
  chmod 700 "$CLAUDE_DIR"
  if [[ -f $dest ]]; then
    stamp=$(date -u +%Y%m%dT%H%M%SZ)
    backup="$dest.bak.$stamp"
    cp -p "$dest" "$backup"
    log "    ~/.claude/$rel: differed, backed up as $(basename "$backup")"
  fi
  install -m 0644 "$src" "$dest.new"
  mv -f "$dest.new" "$dest"
  log "    ~/.claude/$rel: restored"
}
mkdir -p "$CLAUDE_DIR"
install_user_file settings.json
install_user_file CLAUDE.md
if [[ -d $ROOT/workspace/claude-user/rules ]]; then
  for rule_file in "$ROOT"/workspace/claude-user/rules/*.md; do
    [[ -e $rule_file ]] || continue
    install_user_file "rules/$(basename "$rule_file")"
  done
fi
step_done

# ---------------------------------------------------------------- step 3: git identity

step 3 "Git identity"
account_id=$(curl -fsS --max-time 15 -H 'Accept: application/vnd.github+json' "https://api.github.com/users/$MACHINE_LOGIN" | jq -r '.id // empty') \
  || step_fail "the public profile lookup for the machine account failed"
[[ $account_id =~ ^[0-9]+$ ]] || step_fail "the profile lookup did not return a numeric account id"
email="$account_id+$MACHINE_LOGIN@users.noreply.github.com"
for pair in "user.name=$MACHINE_LOGIN" "user.email=$email"; do
  key=${pair%%=*}
  value=${pair#*=}
  if [[ $(git config --global --get "$key" 2>/dev/null || true) != "$value" ]]; then
    git config --global "$key" "$value"
    log "    $key set"
  else
    log "    $key: up to date"
  fi
done
step_done

# ---------------------------------------------------------------- step 4: token T1

step 4 "GitHub token (T1)"
if [[ $REAUTH -eq 0 ]] && gh auth status >/dev/null 2>&1; then
  log "    gh is already logged in; not asking for the token (use --reauth to replace it)"
else
  # The only input path: a no-echo read from the terminal. The token is never an argument, never in the
  # environment, never written to a file or a log; gh receives it on stdin through a here-string.
  token=""
  IFS= read -rs -p 'Token T1: ' token || true
  printf '\n' >&2
  [[ -n $token ]] || step_fail "no token was entered"
  if ! gh auth login --hostname github.com --with-token <<<"$token" >/dev/null 2>&1; then
    unset token
    step_fail "gh rejected the token"
  fi
  unset token
fi
response=$(gh api -i user 2>/dev/null) || step_fail "the API call with the new token failed"
headers=$(sed -n '1,/^\r\{0,1\}$/p' <<<"$response")
body=$(sed '1,/^\r\{0,1\}$/d' <<<"$response")
login=$(sanitize "$(jq -r '.login // empty' <<<"$body" 2>/dev/null || true)")
scopes=$(grep -i '^x-oauth-scopes:' <<<"$headers" | sed 's/^[^:]*:[[:space:]]*//; s/\r$//' || true)
unset response body
if [[ $login != "$MACHINE_LOGIN" ]]; then
  gh auth logout --hostname github.com >/dev/null 2>&1 || true
  step_fail "the token belongs to another account; it was removed (use the machine account's token)"
fi
for scope in repo workflow; do
  if ! grep -qE "(^|, )$scope(,|\$)" <<<"$scopes"; then
    gh auth logout --hostname github.com >/dev/null 2>&1 || true
    step_fail "the token lacks the $scope scope (a classic token with repo and workflow is required); it was removed"
  fi
done
grep -qE '(^|, )read:org(,|$)' <<<"$scopes" || warn "the token lacks read:org (ADR-001 section 2: verify whether gh needs it)"
log "    token accepted for the machine account"
step_done

# ---------------------------------------------------------------- step 5: repositories

step 5 "Repositories"
if [[ $SKIP_CLONE -eq 1 ]]; then
  log "    skipped (--skip-clone)"
else
  gh auth setup-git || step_fail "gh auth setup-git failed"
  mkdir -p "$WORK_DIR"
  while IFS= read -r name; do
    dest="$WORK_DIR/$name"
    if [[ ! -d $dest/.git ]]; then
      git clone -q "https://github.com/$OWNER/$name.git" "$dest" || step_fail "could not clone $name"
      log "    $name: cloned"
    else
      git -C "$dest" fetch -q --prune origin || step_fail "could not fetch $name"
      if [[ -n $(git -C "$dest" status --porcelain) ]]; then
        warn "$name has uncommitted changes (left untouched)"
        log "    $name: fetched; uncommitted changes left untouched"
      else
        log "    $name: fetched"
      fi
    fi
    heads=$(gh pr list -R "$OWNER/$name" --author "$MACHINE_LOGIN" --state open --json headRefName --jq '.[].headRefName' 2>/dev/null || true)
    while IFS= read -r head || [[ -n $head ]]; do
      [[ -n $head ]] || continue
      # A branch name comes from the API: it is data. Only plain, valid names are used.
      if [[ ${#head} -gt 200 || ! $head =~ ^[A-Za-z0-9][A-Za-z0-9._/-]*$ ]] || ! git check-ref-format --branch "$head" >/dev/null 2>&1; then
        warn "skipping a PR branch with an unsafe name"
        continue
      fi
      if git -C "$dest" show-ref --verify -q "refs/heads/$head"; then
        log "    $name: local branch $head exists (git switch $head)"
      elif git -C "$dest" fetch -q origin "+refs/heads/$head:refs/remotes/origin/$head" 2>/dev/null \
        && git -C "$dest" branch --track "$head" "origin/$head" >/dev/null 2>&1; then
        log "    $name: local branch $head created (git switch $head)"
      else
        warn "$name: could not create a local branch for an open PR"
      fi
    done <<<"$heads"
  done < <(repo_names)
fi
step_done

# ---------------------------------------------------------------- step 6: verification

step 6 "Verification"
verify_rc=0
bash "$ROOT/workspace/verify.sh" --prefix "$PREFIX" || verify_rc=$?
step_done

elapsed=$(($(date +%s) - START))
over=""
if [[ $elapsed -gt $TARGET_SECONDS ]]; then over=", over the target"; fi
printf 'restore: complete in %ss (target %ss)%s\n' "$elapsed" "$TARGET_SECONDS" "$over"
if [[ $verify_rc -ne 0 ]]; then
  printf 'restore: the restore finished but verification failed (see the FAIL lines above)\n' >&2
  exit 1
fi
