"""Enumerates the operator scripts (acceptance S-1). Scripts run only in a sandbox with stub commands
and only far enough to reach the usage error, so a test never performs an operator action."""
import os
import pathlib
import stat
import subprocess
import tempfile
import unittest

import helpers

SKIP_SUFFIXES = (".toml", ".md", ".txt", ".lock")


def operator_scripts():
    for path in sorted(helpers.OPERATOR_DIR.iterdir()):
        if path.is_file() and path.suffix not in SKIP_SUFFIXES and os.access(path, os.X_OK):
            yield path


class Scripts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = pathlib.Path(self.tmp.name)
        self.bin = base / "bin"
        self.bin.mkdir()
        self.marker = base / "ran"
        for name in ("sudo", "ssh", "git", "curl", "wget", "ansible-playbook", "apt-get", "gh"):
            stub = self.bin / name
            stub.write_text(f"#!/bin/sh\ntouch {self.marker}\nexit 99\n")
            stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
        self.env = {"PATH": f"{self.bin}:/usr/bin:/bin", "HOME": str(base), "LANG": "C.UTF-8"}

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, script, *args):
        return subprocess.run([str(script), *args], cwd=self.tmp.name, env=self.env, capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, timeout=30)

    def test_both_flags_are_a_usage_error_and_run_nothing(self):
        for script in operator_scripts():
            with self.subTest(script=script.name):
                result = self.run_script(script, "--dry-run", "--apply")
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertFalse(self.marker.exists(), "a command ran")

    def test_an_unknown_argument_is_a_usage_error_and_runs_nothing(self):
        for script in operator_scripts():
            with self.subTest(script=script.name):
                self.assertEqual(self.run_script(script, "--no-such-flag").returncode, 2)
                self.assertFalse(self.marker.exists(), "a command ran")

    def test_python_scripts_use_the_shared_modes(self):
        for script in operator_scripts():
            text = script.read_text()
            if text.startswith("#!") and "python" in text.splitlines()[0]:
                with self.subTest(script=script.name):
                    self.assertIn("operator_lib", text)
                    self.assertIn("parse_mode", text)

    def test_a_reference_script_follows_the_contract(self):
        """The contract is exercised even before the first real script exists."""
        reference = helpers.ROOT / "tests" / "operator" / "fixtures" / "reference-script"
        self.assertTrue(os.access(reference, os.X_OK))
        self.assertEqual(self.run_script(reference, "--dry-run", "--apply").returncode, 2)
        dry = self.run_script(reference)
        self.assertEqual((dry.returncode, dry.stdout.strip()), (0, "would: create the marker"))
        self.assertFalse(pathlib.Path(self.tmp.name, "marker").exists())
        apply = self.run_script(reference, "--apply")
        self.assertEqual((apply.returncode, apply.stdout.strip()), (0, "done: create the marker"))
        again = self.run_script(reference, "--apply")
        self.assertEqual((again.returncode, again.stdout.strip()), (0, ""))


if __name__ == "__main__":
    unittest.main()
