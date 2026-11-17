#!/usr/bin/env bash
# Reads config/project.yaml without a YAML parser (yq does not exist before the toolchain is installed).
# Sourced, never run. Requires ROOT to be set to the repository root.
set -euo pipefail

# config_get KEY: the value of a top-level or nested scalar key, restricted to letters, digits, and '-'.
config_get() {
  sed -n "s/^[[:space:]]*$1:[[:space:]]*\"\{0,1\}\([A-Za-z0-9-]*\).*/\1/p;T;q" "$ROOT/config/project.yaml"
}

# load_config: sets OWNER and MACHINE_LOGIN, or stops.
load_config() {
  OWNER=$(config_get owner)
  MACHINE_LOGIN=$(config_get machine_login)
  if [[ -z $OWNER || -z $MACHINE_LOGIN ]]; then
    printf 'restore: config/project.yaml has no owner or machine_login\n' >&2
    return 1
  fi
}

# repo_names: the repository names in workspace/repos.txt (comments and blank lines dropped; plain names only).
repo_names() {
  local line
  while IFS= read -r line || [[ -n $line ]]; do
    line=${line%%#*}
    line=${line//[[:space:]]/}
    if [[ -z $line ]]; then continue; fi
    if [[ ! $line =~ ^[A-Za-z0-9._-]+$ ]]; then
      printf 'restore: invalid repository name in repos.txt\n' >&2
      return 1
    fi
    printf '%s\n' "$line"
  done <"$ROOT/workspace/repos.txt"
}
