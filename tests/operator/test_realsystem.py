import os
import pathlib
import tempfile
import unittest

import helpers  # noqa: F401
from operator_lib import hostfacts


class RealSystemRead(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = pathlib.Path(self.tmp.name)
        self.system = hostfacts.RealSystem()

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_regular_file_is_read(self):
        (self.base / "f").write_text("ID=ubuntu\n")
        self.assertEqual(self.system.read(str(self.base / "f")), "ID=ubuntu\n")

    def test_a_symlink_is_followed_like_etc_os_release_on_ubuntu(self):
        (self.base / "real").write_text('ID=ubuntu\nVERSION_ID="24.04"\n')
        os.symlink("real", self.base / "os-release")
        text = self.system.read(str(self.base / "os-release"))
        self.assertIn("VERSION_ID", text)

    def test_missing_files_and_directories_are_none(self):
        (self.base / "d").mkdir()
        self.assertIsNone(self.system.read(str(self.base / "missing")))
        self.assertIsNone(self.system.read(str(self.base / "d")))

    def test_the_read_is_capped(self):
        (self.base / "big").write_text("x" * 5000)
        self.assertEqual(len(self.system.read(str(self.base / "big"), limit=100)), 100)

    def test_the_os_name_comes_through_a_symlink_end_to_end(self):
        (self.base / "real").write_text('NAME="Ubuntu"\nID=ubuntu\nVERSION_ID="24.04"\n')
        os.symlink("real", self.base / "os-release")

        class Rooted(hostfacts.RealSystem):
            def read(inner, path, limit=hostfacts.READ_LIMIT):  # noqa: N805
                return super().read(str(self.base / "os-release") if path == "/etc/os-release" else path, limit)
        self.assertEqual(hostfacts.os_name(Rooted()), "ubuntu-24.04")

    def test_state_and_allowlist_files_are_still_not_followed(self):
        home = self.base / "home"
        state_dir = pathlib.Path(hostfacts.state_dir(str(home)))
        state_dir.mkdir(parents=True)
        (self.base / "elsewhere").write_text('{"version": 1, "runs": 99}')
        os.symlink(self.base / "elsewhere", state_dir / hostfacts.STATE_NAME)
        state = hostfacts.State(str(state_dir))
        self.assertTrue(state.fresh)
        self.assertEqual(state.data["runs"], 0)


if __name__ == "__main__":
    unittest.main()
