import unittest

import helpers  # noqa: F401
from operator_lib import modes, steps


class Recorder:
    def __init__(self, needed=True):
        self.needed_value = needed
        self.applied = 0

    def needed(self):
        return self.needed_value

    def apply(self):
        self.applied += 1
        self.needed_value = False


def mode(apply):
    return modes.Mode(apply=apply)


class Steps(unittest.TestCase):
    def test_dry_run_never_applies_and_lists_the_steps(self):
        rec, lines = Recorder(), []
        result = steps.run_steps([steps.Step("write the file", rec.needed, rec.apply)], mode(False), out=lines.append)
        self.assertEqual(rec.applied, 0)
        self.assertEqual((result.would, result.changed), (1, 0))
        self.assertEqual(lines, ["would: write the file"])

    def test_apply_runs_needed_steps(self):
        rec, lines = Recorder(), []
        result = steps.run_steps([steps.Step("write the file", rec.needed, rec.apply)], mode(True), out=lines.append)
        self.assertEqual((rec.applied, result.changed), (1, 1))
        self.assertEqual(lines, ["done: write the file"])

    def test_a_second_apply_changes_nothing(self):
        rec = Recorder()
        plan = [steps.Step("write the file", rec.needed, rec.apply)]
        steps.run_steps(plan, mode(True), out=lambda _: None)
        second = steps.run_steps(plan, mode(True), out=lambda _: None)
        self.assertEqual((rec.applied, second.changed), (1, 0))

    def test_steps_that_are_not_needed_are_skipped_in_both_modes(self):
        rec = Recorder(needed=False)
        for apply in (False, True):
            with self.subTest(apply=apply):
                result = steps.run_steps([steps.Step("noop", rec.needed, rec.apply)], mode(apply), out=lambda _: None)
                self.assertEqual((rec.applied, result.changed, result.would), (0, 0, 0))

    def test_destructive_step_needs_confirmation(self):
        rec = Recorder()
        plan = [steps.Step("overwrite", rec.needed, rec.apply, destructive=True)]
        declined = steps.run_steps(plan, mode(True), out=lambda _: None, confirm_fn=lambda _: False)
        self.assertEqual((rec.applied, declined.declined, declined.changed), (0, 1, 0))
        confirmed = steps.run_steps(plan, mode(True), out=lambda _: None, confirm_fn=lambda _: True)
        self.assertEqual((rec.applied, confirmed.changed), (1, 1))

    def test_dry_run_does_not_ask_for_confirmation(self):
        rec = Recorder()
        asked = []
        steps.run_steps([steps.Step("overwrite", rec.needed, rec.apply, destructive=True)], mode(False),
                        out=lambda _: None, confirm_fn=lambda q: asked.append(q) or True)
        self.assertEqual(asked, [])

    def test_step_names_are_sanitised_in_output(self):
        lines = []
        steps.run_steps([steps.Step("reach 192.0.2.1 for a" + helpers.AT + "b.example", lambda: True, lambda: None)], mode(False), out=lines.append)
        self.assertNotIn("192.0.2.1", lines[0])
        self.assertNotIn("a" + helpers.AT + "b.example", lines[0])


if __name__ == "__main__":
    unittest.main()
