"""The OCI CLI venv inputs (CR-18 PR 5): operator.in has exact pins only, and the lock and the manifest entry arrive together."""
import re
import unittest

import helpers

PYTHON = helpers.ROOT / "toolchain" / "python"
MANIFEST = helpers.ROOT / "toolchain" / "manifest.toml"
PIN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*==[0-9][A-Za-z0-9.!+_-]*")


class OperatorInputs(unittest.TestCase):
    def pins(self):
        lines = (PYTHON / "operator.in").read_text().splitlines()
        return [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]

    def test_every_top_level_requirement_is_an_exact_pin(self):
        pins = self.pins()
        self.assertTrue(pins)
        self.assertTrue(all(PIN.fullmatch(pin) for pin in pins), pins)

    def test_the_lock_and_the_manifest_entry_arrive_together(self):
        lock = (PYTHON / "operator.lock").exists()
        entry = "toolchain/python/operator.lock" in MANIFEST.read_text()
        self.assertEqual(lock, entry, "operator.lock and its manifest entry must be added in the same commit")

    def test_when_the_lock_exists_it_pins_every_top_level_tool_with_hashes(self):
        lock = PYTHON / "operator.lock"
        if not lock.exists():
            self.skipTest("operator.lock is not generated yet (see the PR description)")
        text = lock.read_text()
        for pin in self.pins():
            self.assertRegex(text, re.escape(pin) + r" \\\n\s+--hash=sha256:[0-9a-f]{64}")


if __name__ == "__main__":
    unittest.main()
