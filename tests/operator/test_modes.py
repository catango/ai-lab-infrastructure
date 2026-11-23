import io
import unittest
from contextlib import redirect_stderr

import helpers  # noqa: F401
from operator_lib import exitcodes, modes


def parse(argv):
    return modes.parse_mode(argv, "example", "An example operator script.")


class Modes(unittest.TestCase):
    def test_no_flag_is_a_dry_run(self):
        mode, _ = parse([])
        self.assertTrue(mode.dry_run)
        self.assertFalse(mode.apply)

    def test_explicit_dry_run(self):
        mode, _ = parse(["--dry-run"])
        self.assertTrue(mode.dry_run)

    def test_apply_is_the_only_way_to_execute(self):
        mode, _ = parse(["--apply"])
        self.assertTrue(mode.apply)
        self.assertFalse(mode.dry_run)

    def test_both_flags_are_a_usage_error(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            parse(["--dry-run", "--apply"])
        self.assertEqual(caught.exception.code, exitcodes.USAGE)

    def test_unknown_arguments_and_abbreviations_are_usage_errors(self):
        for argv in (["--bogus"], ["--app"], ["apply"], ["--apply=yes"], ["--dry"]):
            with self.subTest(argv=argv), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                parse(argv)
            self.assertEqual(caught.exception.code, exitcodes.USAGE)

    def test_extra_arguments_are_added_by_the_script(self):
        mode, args = modes.parse_mode(["--scope", "host"], "example", "x", lambda p: p.add_argument("--scope", choices=["host", "github"]))
        self.assertEqual(args.scope, "host")
        self.assertTrue(mode.dry_run)


class Confirm(unittest.TestCase):
    def test_only_yes_confirms(self):
        self.assertTrue(modes.confirm("Overwrite?", input_fn=lambda _: "yes"))
        for answer in ("", "y", "YES ", "no", "yes please"):
            with self.subTest(answer=answer):
                self.assertFalse(modes.confirm("Overwrite?", input_fn=lambda _: answer))

    def test_end_of_input_declines(self):
        def eof(_):
            raise EOFError
        self.assertFalse(modes.confirm("Overwrite?", input_fn=eof))


class ExitCodes(unittest.TestCase):
    def test_values(self):
        self.assertEqual((exitcodes.OK, exitcodes.FAILED, exitcodes.USAGE, exitcodes.SKIPPED), (0, 1, 2, 77))


if __name__ == "__main__":
    unittest.main()
