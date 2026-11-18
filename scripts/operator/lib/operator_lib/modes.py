"""Dry run is the default; --apply executes (ADR-011 decision 2, design section 4 rule 1)."""
import argparse
import sys
from dataclasses import dataclass

from . import exitcodes


@dataclass(frozen=True)
class Mode:
    apply: bool

    @property
    def dry_run(self):
        return not self.apply


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(exitcodes.USAGE, f"{self.prog}: error: {message}\n")


def parse_mode(argv, prog, description, add_arguments=None):
    """Return (Mode, namespace). Both flags together, an unknown argument, or an abbreviation is a usage error (exit 2)."""
    parser = _Parser(prog=prog, description=description, allow_abbrev=False)
    parser.add_argument("--dry-run", action="store_true", help="show what would happen and change nothing (the default)")
    parser.add_argument("--apply", action="store_true", help="execute the changes")
    if add_arguments is not None:
        add_arguments(parser)
    args = parser.parse_args(argv)
    if args.dry_run and args.apply:
        parser.error("--dry-run and --apply cannot be used together")
    return Mode(apply=bool(args.apply)), args


def confirm(question, input_fn=input):
    """True only for the exact answer 'yes'. End of input declines."""
    try:
        return input_fn(f"{question} Type 'yes' to continue: ") == "yes"
    except EOFError:
        return False
