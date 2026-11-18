#!/usr/bin/env bash
# Runs the operator tests under the memory and CPU limits of the strictest machine profile
# (CR-18 acceptance S-10; limits come from scripts/operator/machine-profiles.toml). Used by the CI job
# `operator-limits`; the quality gate runs the same tests without limits.
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)
read -r memory_mb cpu_threads < <(python3 -I -B - "$ROOT" <<'PY'
import sys
sys.path.insert(0, sys.argv[1] + "/scripts/operator/lib")
from operator_lib import profiles
limits = profiles.strictest(profiles.load_profiles(sys.argv[1] + "/scripts/operator/machine-profiles.toml"))
print(limits["memory_mb"], limits.get("cpu_threads", 1))
PY
)
printf 'limits: memory %s MB, cpu threads %s\n' "$memory_mb" "$cpu_threads"

ulimit -v $((memory_mb * 1024))
cd "$ROOT"
exec taskset -c "0-$((cpu_threads - 1))" timeout 600 python3 -I -B -m unittest discover -s tests/operator -p 'test_*.py'
