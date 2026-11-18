import os
import pathlib
import stat
import tempfile
import unittest

import helpers  # noqa: F401
from operator_lib import rawdir


def mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


class RawDir(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = pathlib.Path(self.tmp.name) / "raw"

    def tearDown(self):
        self.tmp.cleanup()

    def test_directory_is_private_and_files_are_600(self):
        raw = rawdir.RawDir(self.path, cap_bytes=1000)
        raw.write("a.json", b"{}")
        self.assertEqual(mode(self.path), 0o700)
        self.assertEqual(mode(self.path / "a.json"), 0o600)

    def test_an_existing_loose_directory_is_tightened(self):
        self.path.mkdir(mode=0o755)
        os.chmod(self.path, 0o755)
        rawdir.RawDir(self.path, cap_bytes=1000)
        self.assertEqual(mode(self.path), 0o700)

    def test_a_symlinked_directory_is_refused(self):
        target = pathlib.Path(self.tmp.name) / "elsewhere"
        target.mkdir()
        self.path.symlink_to(target)
        with self.assertRaises(rawdir.RawDirError):
            rawdir.RawDir(self.path, cap_bytes=1000)

    def test_unsafe_names_are_refused(self):
        raw = rawdir.RawDir(self.path, cap_bytes=1000)
        for name in ("../x", "a/b", "", ".", "..", ".hidden", "x" * 200, "a\0b", "a b"):
            with self.subTest(name=name), self.assertRaises(rawdir.RawDirError):
                raw.write(name, b"x")

    def test_the_size_cap_is_enforced(self):
        raw = rawdir.RawDir(self.path, cap_bytes=100)
        raw.write("a", b"x" * 60)
        with self.assertRaises(rawdir.RawDirError):
            raw.write("b", b"x" * 60)
        self.assertFalse((self.path / "b").exists())
        self.assertEqual(raw.size(), 60)

    def test_rewriting_a_name_replaces_it_within_the_cap(self):
        raw = rawdir.RawDir(self.path, cap_bytes=100)
        raw.write("a", b"x" * 80)
        raw.write("a", b"y" * 90)
        self.assertEqual((self.path / "a").read_bytes(), b"y" * 90)

    def test_cleanup_removes_the_oldest_first(self):
        raw = rawdir.RawDir(self.path, cap_bytes=1000)
        for index, name in enumerate(("old", "mid", "new")):
            raw.write(name, b"x" * 100)
            os.utime(self.path / name, (1000 + index, 1000 + index))
        removed = raw.cleanup(keep_bytes=150)
        self.assertEqual(removed, 2)
        self.assertEqual(sorted(os.listdir(self.path)), ["new"])

    def test_no_temporary_files_remain(self):
        raw = rawdir.RawDir(self.path, cap_bytes=1000)
        raw.write("a", b"x")
        self.assertEqual(os.listdir(self.path), ["a"])


if __name__ == "__main__":
    unittest.main()
