#!/usr/bin/env bash
# tool: none
# order: 40
# Workflow policy (design 5.3; C-1, C-2, C-6, C-7). The scan itself is workflow-policy.awk.
set -euo pipefail
# shellcheck source=../lib/gate-lib.sh source-path=SCRIPTDIR
. "$(dirname "${BASH_SOURCE[0]}")/../lib/gate-lib.sh"

awk_file="$(dirname "${BASH_SOURCE[0]}")/workflow-policy.awk"
mapfile -t files < <(gate_all_workflow_files)
if [[ ${#files[@]} -eq 0 ]]; then exit 77; fi

found=0
for f in "${files[@]}"; do
  [[ -f $f ]] || continue
  out=$(awk -v file="$f" -f "$awk_file" "$f")
  if [[ -n $out ]]; then
    printf '%s\n' "$out"
    found=1
  fi
  if [[ $f == .github/workflows/* ]] && ! grep -Eq '^permissions:' -- "$f"; then
    printf '%s:1: missing top-level permissions: (use permissions: {})\n' "$f"
    found=1
  fi
done
exit "$found"
