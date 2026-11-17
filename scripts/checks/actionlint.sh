#!/usr/bin/env bash
# tool: actionlint
# order: 90
# actionlint over the workflow files. The custom format omits the source snippet.
set -euo pipefail
# shellcheck source=../lib/gate-lib.sh source-path=SCRIPTDIR
. "$(dirname "${BASH_SOURCE[0]}")/../lib/gate-lib.sh"

mapfile -t files < <(gate_workflow_files)
if [[ ${#files[@]} -eq 0 ]]; then exit 77; fi
gate_require_tool actionlint

# shellcheck disable=SC2016  # Go template, not shell expansion
readonly FORMAT='{{range $err := .}}{{$err.Filepath}}:{{$err.Line}}: {{$err.Message}}
{{end}}'
rc=0
out=$(actionlint -no-color -format "$FORMAT" -- "${files[@]}" 2>&1) || rc=$?
if [[ $rc -eq 0 && -z $out ]]; then exit 0; fi
printf '%s\n' "$out" | grep -v '^$'
exit 1
