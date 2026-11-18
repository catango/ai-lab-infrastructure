"""Shared library for operator scripts (ADR-011, CR-18 design section 4). Standard library only.

Scripts add scripts/operator/lib to sys.path and import this package. It also makes scripts/ importable so
that the pr-contract error types and its GitHub client safeguards are reused, not copied.
"""
import os
import sys

sys.dont_write_bytecode = True
_SCRIPTS = os.path.normpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "..", ".."))
if _SCRIPTS not in sys.path:
    sys.path.append(_SCRIPTS)
