"""Shared setup for the operator tests (standard library only)."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "scripts" / "operator" / "lib"))
sys.path.insert(0, str(ROOT / "scripts" / "checks"))

OPERATOR_DIR = ROOT / "scripts" / "operator"
PROFILES = OPERATOR_DIR / "machine-profiles.toml"

# Canary values are assembled at run time so that no identifier-shaped text appears in the repository.
AT = "@"
OCID = "ocid" + "1"
PAT = "github" + "_pat_"
