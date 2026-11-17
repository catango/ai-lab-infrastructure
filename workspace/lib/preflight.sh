#!/usr/bin/env bash
# Preflight checks for workspace/restore.sh (design 4.3). Sourced, never run. Each check prints one
# reason and returns 1 when it fails. AI_LAB_OS_RELEASE and AI_LAB_MACHINE are test seams (a file with
# ID and VERSION_ID, and a machine name); they do not weaken the checks, they only let the tests lie.
set -euo pipefail

pf_platform() {
  local release=${AI_LAB_OS_RELEASE:-/etc/os-release} machine=${AI_LAB_MACHINE:-} id version
  if [[ -z $machine ]]; then machine=$(uname -m); fi
  id=$(sed -n 's/^ID="\{0,1\}\([A-Za-z0-9._-]*\)"\{0,1\}$/\1/p;T;q' "$release" 2>/dev/null || true)
  version=$(sed -n 's/^VERSION_ID="\{0,1\}\([0-9.]*\)"\{0,1\}$/\1/p;T;q' "$release" 2>/dev/null || true)
  if [[ $id != debian || ${version%%.*} != 13 || $machine != x86_64 ]]; then
    printf 'this workspace profile needs Debian 13 on x86_64\n'
    return 1
  fi
}

pf_not_root() {
  if [[ $(id -u) -eq 0 ]]; then
    printf 'run as your normal user, not root (the script calls sudo only where needed)\n'
    return 1
  fi
}

# A Claude Code session shell carries CLAUDECODE and CLAUDE_CODE_* variables (names only are inspected).
pf_no_claude_session() {
  if compgen -e | grep -qE '^(CLAUDECODE|CLAUDE_CODE_[A-Z0-9_]*)$'; then
    printf 'this looks like a Claude Code session; run the restore from a plain SSH terminal (the token must never reach a session)\n'
    return 1
  fi
}

pf_terminal() {
  if [[ ! -t 0 ]]; then
    printf 'stdin is not a terminal; the token prompt needs one (run this from a plain SSH terminal)\n'
    return 1
  fi
}

pf_network() {
  local url
  for url in https://deb.debian.org/ https://github.com/ https://api.github.com/; do
    if ! curl -fsSI --max-time 15 -o /dev/null "$url"; then
      printf 'cannot reach %s\n' "${url#https://}"
      return 1
    fi
  done
}
