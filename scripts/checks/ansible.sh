#!/usr/bin/env bash
# tool: ansible-playbook
# order: 91
# class: platform
# ansible-playbook --syntax-check for every top-level playbook in ansible/ (builder.yml and lab.yml).
# Nothing is executed on any host; the temporary and home directories are outside the repository.
set -euo pipefail
# shellcheck source=../lib/gate-lib.sh source-path=SCRIPTDIR
. "$(dirname "${BASH_SOURCE[0]}")/../lib/gate-lib.sh"

mapfile -t playbooks < <(gate_select '^ansible/[^/]+\.ya?ml$')
if [[ ${#playbooks[@]} -eq 0 ]]; then exit 77; fi
gate_require_tool ansible-playbook

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
: >"$work/ansible.cfg"
export HOME="$work" ANSIBLE_HOME="$work" ANSIBLE_LOCAL_TEMP="$work/tmp" ANSIBLE_CONFIG="$work/ansible.cfg" ANSIBLE_NOCOLOR=1 LC_ALL=C.UTF-8

found=0
for playbook in "${playbooks[@]}"; do
  [[ -f $playbook ]] || continue
  rc=0
  out=$(ansible-playbook -i localhost, --syntax-check "$playbook" 2>&1) || rc=$?
  if [[ $rc -ne 0 ]]; then
    message=$(gate_relative <<<"$out" | grep -m1 -E '^(\[ERROR\]|ERROR!)' | cut -c1-200 || true)
    printf '%s:1: %s\n' "$playbook" "${message:-syntax check failed (exit $rc)}"
    found=1
  fi
done
exit "$found"
