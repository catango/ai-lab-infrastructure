#!/usr/bin/env bash
# tool: pymarkdown
# order: 80
# pymarkdownlnt over every Markdown file. Line length, inline HTML, and first-line-heading rules
# are off: the PR templates start with HTML comments and the docs use long table rows.
set -euo pipefail
# shellcheck source=../lib/gate-lib.sh source-path=SCRIPTDIR
. "$(dirname "${BASH_SOURCE[0]}")/../lib/gate-lib.sh"

mapfile -t files < <(gate_select '\.(md|markdown)$')
if [[ ${#files[@]} -eq 0 ]]; then exit 77; fi
gate_require_tool pymarkdown

rc=0
out=$(pymarkdown --disable-rules md013,md033,md041 scan -- "${files[@]}" 2>&1) || rc=$?
if [[ $rc -eq 0 && -z $out ]]; then exit 0; fi
gate_linter_line <<<"$out"
exit 1
