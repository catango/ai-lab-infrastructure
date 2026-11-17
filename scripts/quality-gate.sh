#!/usr/bin/env bash
# Quality gate: runs scripts/checks/*.sh over the tracked files. Design: CR-2 design.md section 5.
# Never writes to the repository; needs no network and no credentials.
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)
CHECK_DIR="$ROOT/scripts/checks"
MAX_FINDINGS=20

usage() {
  cat <<'USAGE'
Usage: scripts/quality-gate.sh [--list] [--only ID[,ID...]] [--skip ID[,ID...]]
                               [--base REF] [--strict] [--verbose]

  --list       print check IDs and the tool each needs
  --only/--skip  select checks (comma-separated, repeatable)
  --base REF   only files changed since the merge base with REF (default: all tracked files)
  --strict     a missing tool is an error (exit 3); CI always passes this
  --verbose    print every finding instead of the first 20 per check

Exit codes: 0 all selected checks passed, 1 a check failed, 2 usage error,
            3 --strict and a required tool is missing.
USAGE
}

usage_error() {
  printf 'quality-gate: %s\n' "$1" >&2
  usage >&2
  exit 2
}

LIST=0 STRICT=0 VERBOSE=0 BASE=''
ONLY=() SKIP=()
while [[ $# -gt 0 ]]; do
  case $1 in
    --list) LIST=1 ;;
    --strict) STRICT=1 ;;
    --verbose) VERBOSE=1 ;;
    --only | --skip | --base)
      [[ $# -ge 2 && -n $2 ]] || usage_error "$1 needs a value"
      case $1 in
        --only) IFS=, read -r -a _ids <<<"$2" && ONLY+=("${_ids[@]}") ;;
        --skip) IFS=, read -r -a _ids <<<"$2" && SKIP+=("${_ids[@]}") ;;
        --base) BASE=$2 ;;
      esac
      shift
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *) usage_error "unknown argument: $1" ;;
  esac
  shift
done

# header FILE KEY: value of a "# KEY: value" line in the first 12 lines of a check.
header() { awk -v k="$2" 'NR<=12 && $1=="#" && $2==k":" {print $3; exit}' "$1"; }

# Discover checks, ordered by their "# order:" header.
IDS=() TOOLS=()
while read -r _ id tool; do
  IDS+=("$id")
  TOOLS+=("$tool")
done < <(
  for f in "$CHECK_DIR"/*.sh; do
    [[ -e $f ]] || continue
    id=$(basename "$f" .sh)
    printf '%s %s %s\n' "$(header "$f" order || true)" "$id" "$(header "$f" tool || true)"
  done | awk '{ printf "%s %s %s\n", ($1 == "" ? 999 : $1), $2, ($3 == "" ? "none" : $3) }' | LC_ALL=C sort -k1,1n -k2,2
)

if [[ $LIST -eq 1 ]]; then
  for i in "${!IDS[@]}"; do printf '%-26s %s\n' "${IDS[$i]}" "${TOOLS[$i]}"; done
  exit 0
fi

known() {
  local i
  for i in "${IDS[@]}"; do
    if [[ $i == "$1" ]]; then return 0; fi
  done
  return 1
}
for i in "${ONLY[@]}" "${SKIP[@]}"; do
  known "$i" || usage_error "unknown check id: $i (see --list)"
done
listed() { # listed ID ARRAY-ELEMENTS...
  local id=$1 e
  shift
  for e in "$@"; do
    if [[ $e == "$id" ]]; then return 0; fi
  done
  return 1
}

# File list: tracked files (or changed since BASE), regular files only. Fixtures under
# tests/*/fixtures/ are inputs to the tests, not repository content.
git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1 || usage_error "not a git work tree: $ROOT"
FILES=()
if [[ -n $BASE ]]; then
  merge_base=$(git -C "$ROOT" merge-base "$BASE" HEAD 2>/dev/null) || usage_error "cannot resolve --base $BASE"
  list_cmd=(git -C "$ROOT" -c core.quotepath=off diff --name-only --no-ext-diff --diff-filter=ACMR -z "$merge_base" --)
else
  list_cmd=(git -C "$ROOT" -c core.quotepath=off ls-files -z)
fi
while IFS= read -r -d '' path; do
  case $path in *$'\n'*) continue ;; tests/*/fixtures/*) continue ;; esac
  if [[ -f $ROOT/$path ]]; then FILES+=("$path"); fi
done < <("${list_cmd[@]}")

emit_files() {
  if [[ ${#FILES[@]} -gt 0 ]]; then printf '%s\n' "${FILES[@]}"; fi
}

# Findings are untrusted text (paths, tool messages): drop control characters and neutralise
# the "::" sequence so a finding cannot forge a GitHub Actions workflow command.
sanitize() { LC_ALL=C sed -e 's/[[:cntrl:]]//g' -e 's/::/: :/g'; }

FAILED=0 PASSED=0 SKIPPED=0
MISSING=()
ROWS=() DETAILS=()
for i in "${!IDS[@]}"; do
  id=${IDS[$i]}
  if [[ ${#ONLY[@]} -gt 0 ]] && ! listed "$id" "${ONLY[@]}"; then continue; fi
  if [[ ${#SKIP[@]} -gt 0 ]] && listed "$id" "${SKIP[@]}"; then continue; fi
  rc=0
  out=$(cd "$ROOT" && "$BASH" "$CHECK_DIR/$id.sh" < <(emit_files)) || rc=$?
  case $rc in
    0)
      PASSED=$((PASSED + 1))
      printf 'PASS %s\n' "$id"
      ROWS+=("| $id | PASS | 0 |")
      ;;
    77)
      SKIPPED=$((SKIPPED + 1))
      printf 'SKIP %s (no files)\n' "$id"
      ROWS+=("| $id | SKIP (no files) | 0 |")
      ;;
    78)
      SKIPPED=$((SKIPPED + 1))
      MISSING+=("$id")
      printf 'SKIP %s (tool missing: %s)\n' "$id" "${TOOLS[$i]}"
      ROWS+=("| $id | SKIP (tool missing: ${TOOLS[$i]}) | 0 |")
      ;;
    *)
      FAILED=$((FAILED + 1))
      if [[ $rc -eq 1 ]]; then
        mapfile -t found < <(sanitize <<<"$out" | grep -v '^[[:space:]]*$' || true)
      else
        found=("check crashed (exit $rc)")
      fi
      if [[ ${#found[@]} -eq 0 ]]; then found=("check failed without findings"); fi
      total=${#found[@]}
      printf 'FAIL %s (%d)\n' "$id" "$total"
      ROWS+=("| $id | FAIL | $total |")
      shown=$total
      if [[ $VERBOSE -eq 0 && $total -gt $MAX_FINDINGS ]]; then shown=$MAX_FINDINGS; fi
      DETAILS+=("FAIL $id ($total)")
      for ((n = 0; n < shown; n++)); do
        printf '  %s\n' "${found[$n]}"
        DETAILS+=("    ${found[$n]}")
      done
      if [[ $shown -lt $total ]]; then
        printf '  ... %d more (use --verbose)\n' "$((total - shown))"
        DETAILS+=("    ... $((total - shown)) more (use --verbose)")
      fi
      ;;
  esac
done

summary=$(printf 'quality-gate: %d failed, %d passed, %d skipped' "$FAILED" "$PASSED" "$SKIPPED")
printf '%s\n' "$summary"

if [[ -n ${GITHUB_STEP_SUMMARY:-} ]]; then
  {
    printf '### quality-gate\n\n%s\n\n| Check | Result | Findings |\n|---|---|---|\n' "$summary"
    printf '%s\n' "${ROWS[@]}"
    if [[ ${#DETAILS[@]} -gt 0 ]]; then
      printf '\n~~~~text\n'
      printf '%s\n' "${DETAILS[@]}"
      printf '~~~~\n'
    fi
  } >>"$GITHUB_STEP_SUMMARY"
fi

if [[ $FAILED -gt 0 ]]; then exit 1; fi
if [[ $STRICT -eq 1 && ${#MISSING[@]} -gt 0 ]]; then
  printf 'quality-gate: --strict: required tool missing for: %s\n' "${MISSING[*]}"
  exit 3
fi
exit 0
