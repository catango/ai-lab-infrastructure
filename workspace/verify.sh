#!/usr/bin/env bash
# Workspace verification (design 4.6). Read-only. One line per check: PASS, FAIL, or WARN <id>: <detail>.
# Exit 0 when nothing failed, 1 otherwise. It never prints a token or an environment variable value.
# Usage: workspace/verify.sh [--prefix DIR] [--work-dir DIR]
# AI_LAB_PREFIX and AI_LAB_MANIFEST are test seams for the toolchain prefix and manifest.
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)
# shellcheck source=lib/log.sh source-path=SCRIPTDIR
. "$ROOT/workspace/lib/log.sh"
# shellcheck source=lib/config.sh source-path=SCRIPTDIR
. "$ROOT/workspace/lib/config.sh"

PREFIX=${AI_LAB_PREFIX:-/opt/ai-lab}
WORK_DIR="$HOME/work"
while [[ $# -gt 0 ]]; do
  case $1 in
    --prefix | --work-dir)
      [[ $# -ge 2 ]] || {
        echo "verify: $1 needs a value" >&2
        exit 2
      }
      if [[ $1 == --prefix ]]; then PREFIX=$2; else WORK_DIR=$2; fi
      shift 2
      ;;
    *)
      echo "usage: workspace/verify.sh [--prefix DIR] [--work-dir DIR]" >&2
      exit 2
      ;;
  esac
done
load_config || exit 2

PASSED=0
FAILED=0
WARNED=0
pass() {
  PASSED=$((PASSED + 1))
  printf 'PASS %s: %s\n' "$1" "$2"
}
failed() {
  FAILED=$((FAILED + 1))
  printf 'FAIL %s: %s\n' "$1" "$2"
}
warned() {
  WARNED=$((WARNED + 1))
  printf 'WARN %s: %s\n' "$1" "$2"
}

# ---- V-1 tool versions (the install engine's smoke commands)
check_tools() {
  local manifest_args=() output rc=0
  if [[ -n ${AI_LAB_MANIFEST:-} ]]; then manifest_args=(--manifest "$AI_LAB_MANIFEST"); fi
  output=$(python3 -I -B "$ROOT/scripts/toolchain" "${manifest_args[@]}" verify --profile builder --prefix "$PREFIX" 2>&1) || rc=$?
  if [[ $rc -eq 0 ]]; then
    pass V-1 "$(tail -n 1 <<<"$output")"
  else
    failed V-1 "$(grep -E 'FAILED' <<<"$output" | head -n 3 | tr '\n' ';' | cut -c1-200)"
  fi
}

# ---- V-2 guardrail settings in every clone (static)
check_guardrails() {
  local required="$ROOT/workspace/claude-user/required-deny.txt" repo name settings rule problems=() checked=0
  for repo in "$WORK_DIR"/*/; do
    [[ -d $repo/.git ]] || continue
    checked=$((checked + 1))
    name=$(basename "$repo")
    settings="$repo/.claude/settings.json"
    if [[ ! -f $settings ]] || ! jq -e . "$settings" >/dev/null 2>&1; then
      problems+=("$name: no valid .claude/settings.json")
      continue
    fi
    while IFS= read -r rule; do
      [[ -z $rule || $rule == '#'* ]] && continue
      if ! jq -e --arg rule "$rule" '(.permissions.deny // []) | index($rule) != null' "$settings" >/dev/null; then
        problems+=("$name: a required deny rule is missing")
        break
      fi
    done <"$required"
    jq -e '.permissions.disableBypassPermissionsMode == "disable"' "$settings" >/dev/null || problems+=("$name: bypass-permissions mode is not disabled")
    jq -e '.enableAllProjectMcpServers == false' "$settings" >/dev/null || problems+=("$name: enableAllProjectMcpServers is not false")
    [[ ! -e $repo/.mcp.json ]] || problems+=("$name: .mcp.json exists")
  done
  if [[ ${#problems[@]} -gt 0 ]]; then
    failed V-2 "$(printf '%s; ' "${problems[@]}" | cut -c1-300)"
  else
    pass V-2 "$checked repositories checked (static)"
  fi
}

# ---- V-3 token: login, scopes, expiry, and where it is stored
check_token() {
  local response headers body login scopes expiry now left file mode warnings=0
  if ! gh auth status >/dev/null 2>&1; then
    failed V-3 "gh is not logged in"
    return
  fi
  if ! response=$(gh api -i user 2>/dev/null); then
    failed V-3 "the API call with the stored token failed"
    return
  fi
  headers=$(sed -n '1,/^\r\{0,1\}$/p' <<<"$response")
  body=$(sed '1,/^\r\{0,1\}$/d' <<<"$response")
  login=$(jq -r '.login // empty' <<<"$body" 2>/dev/null || true)
  login=$(sanitize "$login")
  if [[ $login != "$MACHINE_LOGIN" ]]; then
    failed V-3 "the token belongs to another account (expected the machine account)"
    return
  fi
  scopes=$(grep -i '^x-oauth-scopes:' <<<"$headers" | sed 's/^[^:]*:[[:space:]]*//; s/\r$//' || true)
  if ! grep -qE '(^|, )repo(,|$)' <<<"$scopes" || ! grep -qE '(^|, )workflow(,|$)' <<<"$scopes"; then
    failed V-3 "token scopes must include repo and workflow"
    return
  fi
  if ! grep -qE '(^|, )read:org(,|$)' <<<"$scopes"; then
    warned V-3 "token lacks read:org (ADR-001 section 2 asks to verify whether gh needs it)"
    warnings=1
  fi
  expiry=$(grep -i '^github-authentication-token-expiration:' <<<"$headers" | sed 's/^[^:]*:[[:space:]]*//; s/\r$//' || true)
  if [[ -n $expiry ]] && now=$(date -u +%s) && left=$(date -u -d "$expiry" +%s 2>/dev/null); then
    left=$(((left - now) / 86400))
    if [[ $left -lt 14 ]]; then
      warned V-3 "token expires in $left days (rotate it, ADR-001 section 4)"
      warnings=1
    fi
  fi
  file="$HOME/.config/gh/hosts.yml"
  if [[ -f $file ]] && grep -q 'oauth_token' "$file" 2>/dev/null; then
    mode=$(stat -c '%a' "$file")
    if [[ $mode != 600 ]]; then
      failed V-3 "the token is stored in a file that is not mode 0600"
      return
    fi
    warned V-3 "the token is stored in a file under ~/.config/gh (no keyring); the home directory is ephemeral by design"
    warnings=1
  fi
  if [[ $warnings -eq 0 ]]; then pass V-3 "login, scopes, and storage are as expected"; fi
}

# ---- V-4 no OCI credentials (names of variables only, never values)
check_oci() {
  local problems=() names
  # shellcheck disable=SC2088  # a display path, not a path to expand
  [[ ! -e $HOME/.oci ]] || problems+=("~/.oci exists")
  if command -v oci >/dev/null 2>&1; then problems+=("an oci binary is on PATH"); fi
  names=$(compgen -e | grep -E '^OCI_' | tr '\n' ' ' || true)
  [[ -z $names ]] || problems+=("OCI_ variables are set: ${names% }")
  if [[ ${#problems[@]} -gt 0 ]]; then
    failed V-4 "$(printf '%s; ' "${problems[@]}")"
  else
    pass V-4 "no OCI credentials on this host"
  fi
}

# ---- V-5 git identity
check_identity() {
  local name email
  name=$(git config --global --get user.name 2>/dev/null || true)
  email=$(git config --global --get user.email 2>/dev/null || true)
  if [[ $name != "$MACHINE_LOGIN" ]]; then
    failed V-5 "user.name is not the machine account"
  elif [[ $email != *@users.noreply.github.com ]]; then
    failed V-5 "user.email is not a GitHub noreply address"
  else
    pass V-5 "git identity is the machine account's noreply address"
  fi
}

# ---- V-6 clones
check_clones() {
  local name dir url problems=() count=0
  while IFS= read -r name; do
    count=$((count + 1))
    dir="$WORK_DIR/$name"
    if [[ ! -d $dir/.git ]]; then
      problems+=("$name: not cloned")
      continue
    fi
    url=$(git -C "$dir" config --get remote.origin.url 2>/dev/null || true)
    if [[ $url != "https://github.com/$OWNER/$name" && $url != "https://github.com/$OWNER/$name.git" ]]; then
      problems+=("$name: origin is not the expected repository")
    fi
  done < <(repo_names)
  if [[ ${#problems[@]} -gt 0 ]]; then
    failed V-6 "$(printf '%s; ' "${problems[@]}")"
  else
    pass V-6 "$count repositories cloned with the expected origin"
  fi
}

check_tools
check_guardrails
check_token
check_oci
check_identity
check_clones
printf 'verify: %d passed, %d failed, %d warnings\n' "$PASSED" "$FAILED" "$WARNED"
if [[ $FAILED -gt 0 ]]; then exit 1; fi
