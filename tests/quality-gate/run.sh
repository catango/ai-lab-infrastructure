#!/usr/bin/env bash
# Tests for scripts/quality-gate.sh and scripts/checks/*.sh (CR-2: Q-1..Q-9, C-1, C-2, C-6, C-7).
# Usage: tests/quality-gate/run.sh [check-id | dispatcher ...]   (no arguments: everything)
# Fixtures live in tests/quality-gate/fixtures/<check-id>/<pass-*|fail-*>/. A fail case may hold
# an EXPECT file (substring that must appear in the findings). Fixtures that would contain
# forbidden patterns (public-repo-hygiene) are generated here from fragments.
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)
FIXTURES="$ROOT/tests/quality-gate/fixtures"
CHECKS="$ROOT/scripts/checks"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

# The tests must not depend on, or modify, the caller's git configuration or identity.
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null
export GIT_AUTHOR_NAME=test GIT_AUTHOR_EMAIL=noreply GIT_COMMITTER_NAME=test GIT_COMMITTER_EMAIL=noreply
export GATE_SELFTEST=1

PASSED=0
FAILED=0
SKIPPED=0
ok() {
  PASSED=$((PASSED + 1))
  printf 'ok   %s\n' "$1"
}
fail() {
  FAILED=$((FAILED + 1))
  printf 'FAIL %s\n' "$1"
  if [[ -n ${2:-} ]]; then printf '     %s\n' "$2"; fi
}
skip() {
  SKIPPED=$((SKIPPED + 1))
  printf 'SKIP %s\n' "$1"
}
# expect NAME CONDITION-STATUS DETAIL: record ok/fail from a command status.
assert() {
  if [[ $2 -eq 0 ]]; then ok "$1"; else fail "$1" "${3:-}"; fi
}

want() {
  local a
  if [[ ${#WANTED[@]} -eq 0 ]]; then return 0; fi
  for a in "${WANTED[@]}"; do
    if [[ $a == "$1" ]]; then return 0; fi
  done
  return 1
}
WANTED=("$@")

header() { awk -v k="$2" 'NR<=12 && $1=="#" && $2==k":" {print $3; exit}' "$CHECKS/$1.sh"; }
has_tool() { [[ -z $1 || $1 == none ]] || command -v "$1" >/dev/null 2>&1; }
rep() { # rep N STRING: STRING repeated N times
  local n=$1 s=''
  while ((n > 0)); do
    s+=$2
    n=$((n - 1))
  done
  printf '%s' "$s"
}
contains() { grep -qF -- "$2" <<<"$1"; }

# ---------------------------------------------------------------- check fixtures

list_files() { (cd "$1" && find . -type f ! -name EXPECT ! -name SECRET | sed 's|^\./||' | LC_ALL=C sort); }

run_dir() { # id name dir
  local id=$1 name=$2 dir=$3 tool tmp files out rc expect
  tool=$(header "$id" tool)
  if ! has_tool "$tool"; then
    skip "$id/$name (tool not installed: $tool)"
    return
  fi
  tmp=$(mktemp -d "$WORK/case.XXXXXX")
  cp -R "$dir/." "$tmp/"
  find "$tmp" -type f -name '*.sh' ! -name 'noexec*' -exec chmod 755 {} +
  find "$tmp" -type f -name 'noexec*' -exec chmod 644 {} +
  files=$(list_files "$tmp")
  rc=0
  out=$(cd "$tmp" && "$BASH" "$CHECKS/$id.sh" <<<"$files" 2>&1) || rc=$?
  case $name in
    pass-*)
      if [[ $rc -eq 0 ]]; then ok "$id/$name"; else fail "$id/$name" "expected exit 0, got $rc"; fi
      ;;
    fail-*)
      if [[ $rc -ne 1 ]]; then
        fail "$id/$name" "expected exit 1, got $rc"
        return
      fi
      if grep -qvE '^[^:]+:[0-9]+: .+' <<<"$out"; then
        fail "$id/$name" "a finding does not match path:line: message"
        return
      fi
      expect=''
      if [[ -f $dir/EXPECT ]]; then expect=$(<"$dir/EXPECT"); fi
      if [[ -n $expect ]] && ! contains "$out" "$expect"; then
        fail "$id/$name" "findings do not mention: $expect"
        return
      fi
      if [[ -f $dir/SECRET ]] && contains "$out" "$(<"$dir/SECRET")"; then
        fail "$id/$name" "a finding echoes file content"
        return
      fi
      ok "$id/$name"
      ;;
  esac
}

gen_hygiene_cases() {
  local d="$WORK/gen/public-repo-hygiene" at='@' secret
  mk() { # name expect content
    mkdir -p "$d/$1"
    printf '%s\n' "$3" >"$d/$1/file.txt"
    printf '%s\n' "$2" >"$d/$1/EXPECT"
    printf '%s\n' "$3" >"$d/$1/SECRET"
  }
  mk fail-ocid "identifier" "$(printf '%s%s.%s.%s.%s.%s' ocid 1 instance oc1 uk-london-1 "$(rep 20 a)")"
  mk fail-private-ipv4 "IPv4" "$(printf '%s.%s.%s.%s' 10 0 0 7)"
  mk fail-public-ipv4 "IPv4" "$(printf '%s.%s.%s.%s' 8 8 8 8)"
  mk fail-email "email" "$(printf '%s%s%s' user "$at" example.com)"
  mk fail-fingerprint-sha256 "fingerprint" "$(printf '%s:%s' SHA256 "$(rep 43 A)")"
  mk fail-fingerprint-md5 "fingerprint" "$(rep 15 'ab:')ab"
  mk fail-private-key "private key" "$(printf -- '-----BEGIN %s-----' 'OPENSSH PRIVATE KEY')"
  mk fail-token-ghp "token" "$(printf '%s_%s' ghp "$(rep 36 x)")"
  mk fail-token-fine-grained "token" "$(printf 'github_pat_%s' "$(rep 30 x)")"
  secret=$(printf '%s.%s.%s.%s' 192 0 2 1)
  mkdir -p "$d/pass-doc-range-and-noreply"
  printf '%s\n%s\n' "$secret" "1234+bot${at}users.noreply.github.com" >"$d/pass-doc-range-and-noreply/file.txt"
}

run_check_fixtures() {
  local id name dir
  gen_hygiene_cases
  for dir in "$FIXTURES"/*/ "$WORK"/gen/*/; do
    [[ -d $dir ]] || continue
    id=$(basename "$dir")
    want "$id" || continue
    if [[ ! -f $CHECKS/$id.sh ]]; then
      fail "$id" "fixtures exist but scripts/checks/$id.sh does not"
      continue
    fi
    for c in "$dir"*/; do
      name=$(basename "$c")
      run_dir "$id" "$name" "${c%/}"
    done
  done
}

run_notool() { # a check whose tool is missing must exit 78 (SKIP), not fake a result
  local id=$1 tool tmp bin files rc
  tool=$(header "$id" tool)
  [[ -n $tool && $tool != none ]] || return 0
  bin=$(restricted_bin)
  tmp=$(mktemp -d "$WORK/notool.XXXXXX")
  cp -R "$FIXTURES/$id/pass-"*/. "$tmp/" 2>/dev/null || cp -R "$FIXTURES/$id/"*/. "$tmp/"
  files=$(list_files "$tmp")
  rc=0
  (cd "$tmp" && PATH="$bin" "$BASH" "$CHECKS/$id.sh" <<<"$files" >/dev/null 2>&1) || rc=$?
  if [[ $rc -eq 78 ]]; then ok "$id: exits 78 without $tool"; else fail "$id: exits 78 without $tool" "got $rc"; fi
}

restricted_bin() { # a PATH with the basics but none of the linters
  local d="$WORK/bin" t p
  if [[ -d $d ]]; then
    printf '%s' "$d"
    return
  fi
  mkdir -p "$d"
  for t in git awk sed grep sort cat head tail tr cut wc uniq find xargs mktemp rm cp chmod mkdir dirname basename realpath env ls date; do
    if p=$(command -v "$t" 2>/dev/null); then ln -sf "$p" "$d/$t"; fi
  done
  printf '%s' "$d"
}

run_adapters() { # normalisation of linter output, tested with stand-in tools (no verdicts are faked)
  local id=$1 tool=$2 raw=$3 want_line=$4 file=$5 tmp bin out rc
  bin="$WORK/stub-$id"
  mkdir -p "$bin"
  cp -P "$(restricted_bin)"/* "$bin/"
  # shellcheck disable=SC2016  # the stand-in tool must expand these variables itself
  printf '#!/bin/sh\n[ -z "$STUB_OUTPUT" ] || printf "%%s\\n" "$STUB_OUTPUT"\nexit "$STUB_RC"\n' >"$bin/$tool"
  chmod +x "$bin/$tool"
  tmp=$(mktemp -d "$WORK/adapter.XXXXXX")
  printf 'x\n' >"$tmp/$file"
  rc=0
  out=$(cd "$tmp" && STUB_OUTPUT="$raw" STUB_RC=1 PATH="$bin" "$BASH" "$CHECKS/$id.sh" <<<"$file" 2>&1) || rc=$?
  if [[ $rc -eq 1 ]] && contains "$out" "$want_line"; then ok "$id: adapter normalises $tool output"; else fail "$id: adapter normalises $tool output" "rc=$rc"; fi
  rc=0
  out=$(cd "$tmp" && STUB_OUTPUT="$tmp/$raw" STUB_RC=1 PATH="$bin" "$BASH" "$CHECKS/$id.sh" <<<"$file" 2>&1) || rc=$?
  if [[ $rc -eq 1 ]] && contains "$out" "$want_line" && ! contains "$out" "$tmp"; then ok "$id: adapter makes absolute paths relative"; else fail "$id: adapter makes absolute paths relative" "rc=$rc"; fi
  rc=0
  out=$(cd "$tmp" && STUB_OUTPUT="" STUB_RC=0 PATH="$bin" "$BASH" "$CHECKS/$id.sh" <<<"$file" 2>&1) || rc=$?
  if [[ $rc -eq 0 && -z $out ]]; then ok "$id: adapter passes clean $tool run"; else fail "$id: adapter passes clean $tool run" "rc=$rc"; fi
}

# ---------------------------------------------------------------- dispatcher

new_repo() {
  local d
  d=$(mktemp -d "$WORK/repo.XXXXXX")
  git -C "$d" init -q -b main
  cp -R "$ROOT/scripts" "$d/scripts"
  printf '%s\n' "$d"
}
commit_all() {
  git -C "$1" add -A
  git -C "$1" commit -q -m "${2:-test}"
}
good_script() { printf '#!/usr/bin/env bash\nset -euo pipefail\necho ok\n' >"$1/$2" && chmod 755 "$1/$2"; }
bad_script() { printf '#!/usr/bin/env bash\necho no strict mode\n' >"$1/$2" && chmod 755 "$1/$2"; }
gate() { # repo args...: sets OUT and RC
  local repo=$1
  shift
  RC=0
  OUT=$("$BASH" "$repo/scripts/quality-gate.sh" "$@" 2>&1) || RC=$?
}
# rc_is NAME EXPECTED: compares RC from the last gate call
rc_is() { if [[ $RC -eq $2 ]]; then ok "$1"; else fail "$1" "expected exit $2, got $RC"; fi; }
out_has() { if contains "$OUT" "$2"; then ok "$1"; else fail "$1" "output lacks: $2"; fi; }
out_lacks() { if contains "$OUT" "$2"; then fail "$1" "output unexpectedly has: $2"; else ok "$1"; fi; }

test_dispatcher() {
  local repo bin i n expected

  # Q-1 exit 0 and 1, Q-4 summary line
  repo=$(new_repo)
  good_script "$repo" good.sh
  commit_all "$repo"
  gate "$repo" --only bash-hygiene
  rc_is "Q-1 exit 0 when all selected checks pass" 0
  out_has "Q-1 PASS line" "PASS bash-hygiene"
  out_has "Q-4 summary line" "quality-gate: 0 failed, 1 passed, 0 skipped"
  bad_script "$repo" bad.sh
  commit_all "$repo"
  gate "$repo" --only bash-hygiene
  rc_is "Q-1 exit 1 when a check fails" 1
  out_has "Q-1 FAIL line with count" "FAIL bash-hygiene (1)"
  out_has "Q-1 finding is path:line: message" "  bad.sh:1: "
  out_has "Q-4 summary counts the failure" "quality-gate: 1 failed, 0 passed, 0 skipped"

  # Q-1 exit 2
  gate "$repo" --no-such-option
  rc_is "Q-1 exit 2 on unknown option" 2
  gate "$repo" --only no-such-check
  rc_is "Q-1 exit 2 on unknown check id" 2
  gate "$repo" --base
  rc_is "Q-1 exit 2 on --base without value" 2
  gate "$repo" --base no-such-ref --only bash-hygiene
  rc_is "Q-1 exit 2 on unresolvable --base" 2
  gate "$repo" stray-argument
  rc_is "Q-1 exit 2 on a positional argument" 2

  # Q-2 --list, --only, --skip, --base
  gate "$repo" --list
  rc_is "Q-2 --list exits 0" 0
  expected="bash-hygiene shellcheck public-repo-hygiene workflow-policy no-claude-in-workflows links yaml markdown actionlint toolchain python gate-tests"
  n=$(awk '{print $1}' <<<"$OUT" | grep -Ev '^(ID|CHECK)$' | tr '\n' ' ' | sed 's/ $//')
  if [[ $n == "$expected" ]]; then ok "Q-2 --list shows check ids in order"; else fail "Q-2 --list shows check ids in order" "got: $n"; fi
  out_has "Q-2 --list shows the tool" "shellcheck"
  gate "$repo" --only bash-hygiene,links
  out_has "Q-2 --only runs the selected checks" "bash-hygiene"
  out_has "Q-2 --only runs the selected checks (second id)" "links"
  out_lacks "Q-2 --only leaves the others out" "shellcheck"
  gate "$repo" --only bash-hygiene,links --skip links
  out_has "Q-2 --skip keeps the rest" "bash-hygiene"
  out_lacks "Q-2 --skip removes the check" " links"
  good_script "$repo" newer.sh
  commit_all "$repo"
  gate "$repo" --only bash-hygiene --base HEAD~1
  rc_is "Q-2 --base limits to changed files (bad file unchanged since base)" 0
  bad_script "$repo" newest-bad.sh
  commit_all "$repo"
  gate "$repo" --only bash-hygiene --base HEAD~1
  rc_is "Q-2 --base sees files added since the base" 1
  out_lacks "Q-2 --base does not report unchanged files" "  bad.sh:"

  # fixtures are test inputs, not repository content
  repo=$(new_repo)
  mkdir -p "$repo/tests/demo/fixtures"
  bad_script "$repo/tests/demo/fixtures" bad.sh
  good_script "$repo" good.sh
  commit_all "$repo"
  gate "$repo" --only bash-hygiene
  rc_is "files under tests/*/fixtures/ are not checked" 0

  # Q-3 missing tool: SKIP locally, exit 3 under --strict (a failure takes priority)
  bin=$(restricted_bin)
  RC=0
  OUT=$(PATH="$bin" "$BASH" "$repo/scripts/quality-gate.sh" --only shellcheck 2>&1) || RC=$?
  rc_is "Q-3 missing tool is not an error without --strict" 0
  out_has "Q-3 SKIP names the tool" "SKIP shellcheck (tool missing: shellcheck)"
  RC=0
  OUT=$(PATH="$bin" "$BASH" "$repo/scripts/quality-gate.sh" --strict --only shellcheck 2>&1) || RC=$?
  rc_is "Q-3 missing tool is exit 3 with --strict" 3
  bad_script "$repo" bad.sh
  commit_all "$repo"
  RC=0
  OUT=$(PATH="$bin" "$BASH" "$repo/scripts/quality-gate.sh" --strict --only shellcheck,bash-hygiene 2>&1) || RC=$?
  rc_is "Q-3 a failing check outranks a missing tool (exit 1)" 1
  gate "$repo" --only links
  out_has "no applicable files is SKIP (no files)" "SKIP links (no files)"
  rc_is "no applicable files is not an error" 0
  gate "$repo" --strict --only links
  rc_is "no applicable files is allowed under --strict" 0

  # Q-4 at most 20 findings per check plus a count; --verbose shows all
  repo=$(new_repo)
  for i in $(seq 1 30); do bad_script "$repo" "bad$i.sh"; done
  commit_all "$repo"
  gate "$repo" --only bash-hygiene
  n=$(grep -cE '^  bad[0-9]+\.sh:' <<<"$OUT" || true)
  if [[ $n -eq 20 ]]; then ok "Q-4 shows 20 of 30 findings"; else fail "Q-4 shows 20 of 30 findings" "got $n"; fi
  out_has "Q-4 states how many are hidden" "... 10 more (use --verbose)"
  out_has "Q-4 FAIL line carries the total" "FAIL bash-hygiene (30)"
  n=$(grep -c '^quality-gate:' <<<"$OUT" || true)
  if [[ $n -eq 1 ]]; then ok "Q-4 exactly one summary line"; else fail "Q-4 exactly one summary line" "got $n"; fi
  gate "$repo" --only bash-hygiene --verbose
  n=$(grep -cE '^  bad[0-9]+\.sh:' <<<"$OUT" || true)
  if [[ $n -eq 30 ]]; then ok "Q-4 --verbose shows all findings"; else fail "Q-4 --verbose shows all findings" "got $n"; fi
  out_lacks "Q-4 --verbose has no truncation note" "more (use --verbose)"

  # Q-8 writes nothing to the repository; needs no network, credentials, or environment
  repo=$(new_repo)
  good_script "$repo" good.sh
  printf '# T\n\n[a](good.sh)\n' >"$repo/README.md"
  mkdir -p "$repo/.github/workflows"
  printf 'name: x\non: push\npermissions: {}\njobs:\n  a:\n    runs-on: ubuntu-24.04\n    steps:\n      - run: echo hi\n' >"$repo/.github/workflows/ci.yml"
  commit_all "$repo"
  RC=0
  OUT=$(cd "$repo" && env -i PATH="$PATH" HOME="$WORK/no-home" "$BASH" scripts/quality-gate.sh 2>&1) || RC=$?
  n=$(git -C "$repo" status --porcelain | wc -l)
  if [[ $n -eq 0 ]]; then ok "Q-8 repository is clean after a run"; else fail "Q-8 repository is clean after a run" "$n paths changed"; fi
  if [[ $RC -eq 0 ]]; then ok "Q-8 runs with an empty environment (no credentials)"; else fail "Q-8 runs with an empty environment (no credentials)" "exit $RC: $OUT"; fi
  if command -v unshare >/dev/null 2>&1 && unshare -rn true 2>/dev/null; then
    RC=0
    OUT=$(unshare -rn "$BASH" "$repo/scripts/quality-gate.sh" 2>&1) || RC=$?
    if [[ $RC -eq 0 ]]; then ok "Q-8 runs without network"; else fail "Q-8 runs without network" "exit $RC"; fi
  else
    skip "Q-8 runs without network (unshare -rn unavailable; static scan below)"
  fi
  if grep -rEn '(^|[^A-Za-z_-])(curl|wget|ssh|scp|nc)[[:space:]]|git[[:space:]]+(fetch|pull|push|clone)' \
    "$ROOT/scripts" --include='*.sh' --exclude='workflow-policy.sh' | grep -v ':[[:space:]]*#' >"$WORK/net.txt"; then
    fail "Q-8 no network commands in scripts/" "$(head -n 3 "$WORK/net.txt")"
  else
    ok "Q-8 no network commands in scripts/"
  fi

  # Q-9 step summary
  RC=0
  OUT=$(GITHUB_STEP_SUMMARY="$WORK/summary.md" "$BASH" "$repo/scripts/quality-gate.sh" --only bash-hygiene,links 2>&1) || RC=$?
  if [[ -f $WORK/summary.md ]] && grep -q '^| Check | Result |' "$WORK/summary.md" && grep -q '^| bash-hygiene | PASS |' "$WORK/summary.md"; then
    ok "Q-9 summary table appended to GITHUB_STEP_SUMMARY"
  else
    fail "Q-9 summary table appended to GITHUB_STEP_SUMMARY"
  fi
  bad_script "$repo" bad.sh
  commit_all "$repo"
  GITHUB_STEP_SUMMARY="$WORK/summary.md" "$BASH" "$repo/scripts/quality-gate.sh" --only bash-hygiene >/dev/null 2>&1 || true
  if grep -q '^| bash-hygiene | FAIL |' "$WORK/summary.md" && grep -q 'bad.sh:1:' "$WORK/summary.md"; then
    ok "Q-9 summary appends (does not overwrite) and lists findings"
  else
    fail "Q-9 summary appends (does not overwrite) and lists findings"
  fi

  # robustness: a crashing check is a failure; output cannot forge workflow commands
  repo=$(new_repo)
  printf '#!/usr/bin/env bash\n# tool: none\n# order: 999\nset -euo pipefail\nexit 5\n' >"$repo/scripts/checks/zz-crash.sh"
  chmod 755 "$repo/scripts/checks/zz-crash.sh"
  commit_all "$repo"
  gate "$repo" --only zz-crash
  rc_is "a crashing check fails the gate" 1
  out_has "a crashing check is reported" "crashed (exit 5)"
  repo=$(new_repo)
  bad_script "$repo" '::notice::x.sh'
  commit_all "$repo"
  gate "$repo" --only bash-hygiene
  if grep -q '^::' <<<"$OUT" || contains "$OUT" '::notice::'; then
    fail "workflow-command sequences in findings are neutralised"
  else
    ok "workflow-command sequences in findings are neutralised"
  fi
}

# ---------------------------------------------------------------- main

if want dispatcher; then test_dispatcher; fi
run_check_fixtures
for f in "$CHECKS"/*.sh; do
  id=$(basename "$f" .sh)
  if want "$id" && [[ -d $FIXTURES/$id ]]; then run_notool "$id"; fi
done
if want python; then
  tmp=$(mktemp -d "$WORK/bytecode.XXXXXX")
  cp -R "$FIXTURES/python/pass-ok/." "$tmp/"
  files=$(list_files "$tmp")
  (cd "$tmp" && "$BASH" "$CHECKS/python.sh" <<<"$files" >/dev/null 2>&1) || true
  if [[ -z $(find "$tmp" -name '__pycache__' -o -name '*.pyc') ]]; then ok "python: writes no bytecode"; else fail "python: writes no bytecode"; fi
fi
if want yaml; then
  run_adapters yaml yamllint 'a.yml:3:1: [error] too many blank lines (1 > 0) (empty-lines)' \
    'a.yml:3: [error] too many blank lines (1 > 0) (empty-lines)' a.yml
fi
if want markdown; then
  run_adapters markdown pymarkdown 'a.md:3:1: MD018: No space present after the hash character (no-missing-space-atx)' \
    'a.md:3: MD018: No space present after the hash character (no-missing-space-atx)' a.md
fi

printf 'tests: %d passed, %d failed, %d skipped\n' "$PASSED" "$FAILED" "$SKIPPED"
if [[ $FAILED -gt 0 ]]; then exit 1; fi
