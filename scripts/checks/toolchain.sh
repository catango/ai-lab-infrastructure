#!/usr/bin/env bash
# tool: python3
# order: 93
# class: generic
# Static validation of toolchain/manifest.toml and its lock file (scripts/toolchain check; no network).
set -euo pipefail
# shellcheck source=../lib/gate-lib.sh source-path=SCRIPTDIR
. "$(dirname "${BASH_SOURCE[0]}")/../lib/gate-lib.sh"

engine="$(dirname "${BASH_SOURCE[0]}")/../toolchain"
files=$(cat)
if ! gate_select '^toolchain/(manifest\.toml|python/[^/]+\.(lock|in))$' <<<"$files" | grep -q .; then exit 77; fi
gate_require_tool python3

rc=0
out=$(python3 -I -B "$engine" --manifest toolchain/manifest.toml --root . check 2>&1) || rc=$?
if [[ $rc -eq 0 ]]; then exit 0; fi
if [[ $rc -eq 2 ]]; then
  printf 'toolchain/manifest.toml:1: manifest could not be checked (usage or file error)\n'
  exit 1
fi
grep -v '^toolchain: ' <<<"$out" | sed -E 's|^|toolchain/manifest.toml:1: |' || true
exit 1
