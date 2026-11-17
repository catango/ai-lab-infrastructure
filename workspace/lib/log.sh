#!/usr/bin/env bash
# Small output helpers for workspace/restore.sh and workspace/verify.sh (sourced, never run).
# Output carries fixed text, tool names, and logins only: never a token or an environment value.
set -euo pipefail

log() { printf '%s\n' "$*"; }
warn() { printf 'WARN: %s\n' "$*" >&2; }
die() {
  local code=$1
  shift
  printf 'restore: %s\n' "$*" >&2
  exit "$code"
}

# sanitize TEXT: keep printable ASCII only (values that came from an API or a file).
sanitize() { printf '%s' "$1" | LC_ALL=C tr -cd '[:print:]' | cut -c1-120; }
