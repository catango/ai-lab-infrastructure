"""The lock helper of CR-18 PR 5: fake wheel files in, lock text out, and every refusal."""
import hashlib
import importlib.util
import os
import pathlib
import tempfile
import unittest

import helpers
from toolchain_engine import manifest

SPEC = importlib.util.spec_from_file_location("lock_from_wheels", helpers.ROOT / "toolchain" / "python" / "lock_from_wheels.py")
lock = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lock)
MANY = "manylinux_2_17_x86_64.manylinux2014_x86_64"
WHEELS = {"oci_cli-1.2.3-py3-none-any.whl": b"one", "click-8.1.0-py3-none-any.whl": b"two",
          f"cryptography-44.0.0-cp39-abi3-{MANY}.whl": b"three", f"cffi-1.17.1-cp312-cp312-{MANY}.whl": b"four"}


class LockFromWheels(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, wheels):
        for name, data in wheels.items():
            (self.dir / name).write_bytes(data)

    def test_the_lock_lists_the_top_level_pin_first_with_the_right_hashes(self):
        self.put(WHEELS)
        text = lock.build(self.dir, "# comment\noci-cli==1.2.3\n")
        self.assertIn("oci-cli==1.2.3 \\\n    --hash=sha256:" + hashlib.sha256(b"one").hexdigest(), text)
        self.assertLess(text.index("oci-cli=="), text.index("cffi=="))
        self.assertEqual([line.split("==")[0] for line in text.splitlines() if "==" in line and not line.startswith("#")],
                         ["oci-cli", "cffi", "click", "cryptography"])

    def test_the_text_passes_the_manifest_lock_check(self):
        self.put(WHEELS)
        path = self.dir.parent / (self.dir.name + ".lock")
        path.write_text(lock.build(self.dir, "oci-cli==1.2.3\n"))
        try:
            self.assertEqual(manifest.check_lock(path), [])
        finally:
            os.unlink(path)

    def refused(self, wheels, requirements="oci-cli==1.2.3\n"):
        self.put(wheels)
        with self.assertRaises(lock.LockError):
            lock.build(self.dir, requirements)

    def test_a_wheel_for_another_platform_or_python_is_refused(self):
        for name in ("x-1.0-cp311-cp311-manylinux_2_17_x86_64.whl", f"x-1.0-cp312-cp312-manylinux_2_17_aarch64.whl",
                     "x-1.0-cp312-cp312-win_amd64.whl", "x-1.0-cp312-cp312-macosx_11_0_arm64.whl"):
            for old in self.dir.iterdir():
                old.unlink()
            self.refused({**{"oci_cli-1.2.3-py3-none-any.whl": b"one"}, name: b"x"})

    def test_a_missing_or_different_top_level_pin_is_refused(self):
        self.refused({"click-8.1.0-py3-none-any.whl": b"two"})
        for old in self.dir.iterdir():
            old.unlink()
        self.refused({"oci_cli-1.2.4-py3-none-any.whl": b"one"})

    def test_a_source_archive_or_other_file_is_refused(self):
        self.refused({"oci_cli-1.2.3-py3-none-any.whl": b"one", "x-1.0.tar.gz": b"x"})

    def test_a_requirement_that_is_not_an_exact_pin_is_refused(self):
        self.refused({"oci_cli-1.2.3-py3-none-any.whl": b"one"}, "oci-cli>=1.2\n")

    def test_two_wheels_of_one_project_are_refused(self):
        self.refused({"oci_cli-1.2.3-py3-none-any.whl": b"one", "oci-cli-1.2.3-py3-none-any.whl": b"two"})

    def test_it_writes_to_standard_output_only(self):
        import io
        from contextlib import redirect_stderr, redirect_stdout
        self.put(WHEELS)
        (self.dir.parent / "in.txt").write_text("oci-cli==1.2.3\n")
        out, err = io.StringIO(), io.StringIO()
        before = sorted(os.listdir(self.dir))
        try:
            with redirect_stdout(out), redirect_stderr(err):
                self.assertEqual(lock.main([str(self.dir), str(self.dir.parent / "in.txt")]), 0)
        finally:
            os.unlink(self.dir.parent / "in.txt")
        self.assertTrue(out.getvalue().startswith("# Hash-locked"))
        self.assertEqual(sorted(os.listdir(self.dir)), before)


if __name__ == "__main__":
    unittest.main()
