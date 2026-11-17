#!/usr/bin/env bash
# Exercises the opt-in managed-settings role on a disposable host (the builder-profile CI container):
# it writes once, is idempotent, and refuses to replace a file it did not write.
# It changes /etc, so it only runs when AI_LAB_ALLOW_SYSTEM_CHANGES=1 and as root.
set -euo pipefail

if [[ ${AI_LAB_ALLOW_SYSTEM_CHANGES:-} != 1 || $(id -u) -ne 0 ]]; then
  echo "refusing to run: set AI_LAB_ALLOW_SYSTEM_CHANGES=1 and run as root on a disposable host" >&2
  exit 2
fi
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
target=/etc/claude-code/managed-settings.json
apply() { ansible-playbook -i ansible/inventory/localhost.yml ansible/builder.yml -e claude_managed_settings_enabled=true; }

apply
test -s "$target"
apply | tee "$work/second.txt"
grep -Eq 'changed=0 +unreachable=0 +failed=0' "$work/second.txt"

printf '{"foreign": true}\n' >"$target"
if apply >"$work/foreign.txt" 2>&1; then
  echo "the role replaced a file it did not write" >&2
  exit 1
fi
grep -q 'merge it by hand' "$work/foreign.txt"
grep -qx '{"foreign": true}' "$target"
echo "opt-in role: ok"
