#!/usr/bin/env bash
# Shared helpers of the two halves of the PA-28 job (pa28-lab.sh and pa28-operator.sh). Sourced, never run directly.
# The caller sets TREE_ROOTS (an array: the directories its profile may touch) before it calls tree_list or tree_hash.
set -euo pipefail

fail() {
  printf 'PA-28: %s\n' "$*" >&2
  exit 1
}
ok() { printf 'ok: %s\n' "$*"; }

# tree_list: the names, types, modes, owners, link targets, and file contents under TREE_ROOTS, outside what the container itself
# rewrites. A refusal and a dry run must leave tree_hash unchanged; tree_list shows what changed when two hashes differ.
tree_list() {
  local roots=() root
  for root in "${TREE_ROOTS[@]}"; do
    if [[ -e $root ]]; then roots+=("$root"); fi
  done
  {
    find "${roots[@]}" -xdev -not -path /etc/resolv.conf -not -path /etc/hosts -not -path /etc/hostname -printf '%p %y %m %U %G %l\n'
    find "${roots[@]}" -xdev -type f -not -path /etc/resolv.conf -not -path /etc/hosts -not -path /etc/hostname -print0 | xargs -0 -r sha256sum
  } | LC_ALL=C sort
}
tree_hash() { tree_list | sha256sum | cut -d' ' -f1; }

# mentions FILE TEXT...: the file has every text
mentions() {
  local text
  for text in "${@:2}"; do grep -qF -- "$text" "$1" || return 1; done
}
