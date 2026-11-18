"""A plan of steps, run as a dry run or applied (design section 4 rules 1 to 3 and 6)."""
from dataclasses import dataclass
from typing import Callable

from . import modes
from .sanitize import scrub


@dataclass(frozen=True)
class Step:
    name: str
    needed: Callable[[], bool]
    apply: Callable[[], None]
    destructive: bool = False


@dataclass
class StepResult:
    would: int = 0
    changed: int = 0
    declined: int = 0


def run_steps(plan, mode, out=print, confirm_fn=modes.confirm):
    """Dry run: list the steps that are needed and call nothing that changes state. Apply: run the needed steps,
    asking first for a destructive one. A step that is not needed in either mode is skipped, so a second apply changes nothing."""
    result = StepResult()
    for step in plan:
        if not step.needed():
            continue
        name = scrub(step.name)
        if mode.dry_run:
            result.would += 1
            out(f"would: {name}")
            continue
        if step.destructive and not confirm_fn(f"{name} deletes or overwrites data."):
            result.declined += 1
            out(f"declined: {name}")
            continue
        step.apply()
        result.changed += 1
        out(f"done: {name}")
    return result
