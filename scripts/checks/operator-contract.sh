#!/usr/bin/env bash
# tool: python3
# order: 96
# class: platform
# Operator scripts follow the contract (CR-18 acceptance S-6, S-11): no eval, exec, shell=True, os.system, sudo outside
# setup and facts, Terraform, OCI call with a verb other than list, get, or inspect, or download piped to a shell.
set -euo pipefail
# shellcheck source=../lib/gate-lib.sh source-path=SCRIPTDIR
. "$(dirname "${BASH_SOURCE[0]}")/../lib/gate-lib.sh"

gate_require_tool python3
exec python3 -I -B "$(dirname "${BASH_SOURCE[0]}")/operator_contract.py"
