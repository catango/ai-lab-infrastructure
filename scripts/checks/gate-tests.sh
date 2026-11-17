#!/usr/bin/env bash
# tool: none
# order: 100
# Runs tests/quality-gate/run.sh (the gate's own fixture tests) when it is part of the file list.
set -euo pipefail
# shellcheck source=../lib/gate-lib.sh source-path=SCRIPTDIR
. "$(dirname "${BASH_SOURCE[0]}")/../lib/gate-lib.sh"

if [[ -n ${GATE_SELFTEST:-} ]]; then exit 77; fi # the tests run the gate; no recursion
if ! gate_select '^tests/quality-gate/run\.sh$' | grep -q .; then exit 77; fi

rc=0
out=$(bash tests/quality-gate/run.sh 2>&1) || rc=$?
if [[ $rc -eq 0 ]]; then exit 0; fi
failed=$(grep -E '^FAIL ' <<<"$out" || true)
if [[ -z $failed ]]; then
  printf 'tests/quality-gate/run.sh:1: test script exited with status %s\n' "$rc"
else
  sed -E 's/^FAIL (.*)$/tests\/quality-gate\/run.sh:1: test failed: \1/' <<<"$failed"
fi
exit 1
