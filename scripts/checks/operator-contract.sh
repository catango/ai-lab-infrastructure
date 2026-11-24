#!/usr/bin/env bash
# tool: python3
# order: 96
# class: platform
# Operator scripts follow the contract (CR-18 acceptance S-6, S-11): no eval, exec, shell=True, os.system, sudo, Terraform,
# OCI call with a verb other than list, get, or inspect, or download piped to a shell. And (CR-57 PA-22, PA-A15) every endpoint is
# a literal listed in `operator_endpoints` of config/project.yaml, read from the BASE commit GATE_BASE_REF (set by quality-gate.sh
# --base), never from the head that is judged (SC-20); without GATE_BASE_REF the working tree is read (a push, or a local run).
set -euo pipefail
# shellcheck source=../lib/gate-lib.sh source-path=SCRIPTDIR
. "$(dirname "${BASH_SOURCE[0]}")/../lib/gate-lib.sh"

gate_require_tool python3

config=config/project.yaml
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
args=()
if [[ -n ${GATE_BASE_REF:-} ]]; then
  if [[ $GATE_BASE_REF == -* ]] || ! commit=$(git rev-parse --verify --quiet "${GATE_BASE_REF}^{commit}" 2>/dev/null); then
    args=(--config-unreadable)
  elif git cat-file -e "$commit:$config" 2>/dev/null; then
    git show "$commit:$config" >"$tmp/config.yaml"
    args=(--config "$tmp/config.yaml")
  fi
elif [[ -f $config ]]; then
  args=(--config "$config")
fi
rc=0
python3 -I -B "$(dirname "${BASH_SOURCE[0]}")/operator_contract.py" "${args[@]}" || rc=$?
exit "$rc"
