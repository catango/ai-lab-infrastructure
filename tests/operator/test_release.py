import os
import pathlib
import subprocess
import tempfile
import unittest

import helpers  # noqa: F401
from operator_lib import release

GIT_ENV = {"PATH": os.environ.get("PATH", ""), "HOME": "/nonexistent", "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@noreply.invalid",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@noreply.invalid"}


def git(cwd, *args):
    subprocess.run(["git", "-c", "init.defaultBranch=main", "-c", "protocol.file.allow=always", *args], cwd=cwd, env=GIT_ENV,
                   check=True, capture_output=True, text=True)


class Repo(unittest.TestCase):
    """A clone with origin/main, in a temporary directory."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = pathlib.Path(self.tmp.name)
        self.origin = base / "origin.git"
        self.work = base / "work"
        git(base, "init", "-q", "--bare", str(self.origin))
        git(base, "clone", "-q", str(self.origin), str(self.work))
        self.commit("one")
        git(self.work, "push", "-q", "origin", "HEAD:main")
        git(self.work, "fetch", "-q", "origin")

    def tearDown(self):
        self.tmp.cleanup()

    def commit(self, name):
        (self.work / name).write_text(name)
        git(self.work, "add", name)
        git(self.work, "commit", "-q", "-m", name)

    def publish(self):
        git(self.work, "push", "-q", "origin", "HEAD:main")
        git(self.work, "fetch", "-q", "origin")

    def check(self):
        return release.check_release_commit(self.work)


class ReleaseCommit(Repo):
    def test_a_release_tag_contained_in_origin_main_passes(self):
        git(self.work, "tag", "-a", "-m", "release", "v0.1.0")
        result = self.check()
        self.assertTrue(result.ok, result.reason)
        self.assertEqual(result.tag, "v0.1.0")
        self.assertEqual(len(result.commit), 40)

    def test_a_lightweight_tag_passes_too(self):
        git(self.work, "tag", "v0.1.1")
        self.assertTrue(self.check().ok)

    def test_head_without_a_tag_is_refused(self):
        result = self.check()
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, release.NO_TAG)

    def test_tag_on_an_older_commit_is_refused(self):
        git(self.work, "tag", "v0.1.0")
        self.commit("two")
        self.publish()
        self.assertEqual(self.check().reason, release.NO_TAG)

    def test_a_tag_that_is_not_a_release_tag_is_refused(self):
        for name in ("latest", "release-1", "x1.0", "V1.0"):
            with self.subTest(name=name):
                git(self.work, "tag", name)
                self.assertEqual(self.check().reason, release.NO_TAG)
                git(self.work, "tag", "-d", name)

    def test_a_tagged_commit_not_in_origin_main_is_refused(self):
        self.commit("local-only")
        git(self.work, "tag", "v0.2.0")
        result = self.check()
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, release.NOT_IN_MAIN)

    def test_local_changes_are_refused_before_anything_else(self):
        git(self.work, "tag", "v0.1.0")
        (self.work / "one").write_text("edited")
        self.assertEqual(self.check().reason, release.LOCAL_CHANGES)

    def test_an_untracked_file_counts_as_a_local_change(self):
        git(self.work, "tag", "v0.1.0")
        (self.work / "new-file").write_text("x")
        self.assertEqual(self.check().reason, release.LOCAL_CHANGES)

    def test_a_missing_origin_main_is_refused(self):
        git(self.work, "tag", "v0.1.0")
        git(self.work, "update-ref", "-d", "refs/remotes/origin/main")
        self.assertEqual(self.check().reason, release.NOT_IN_MAIN)

    def test_not_a_repository_is_refused(self):
        with tempfile.TemporaryDirectory() as empty:
            self.assertEqual(release.check_release_commit(empty).reason, release.NOT_A_REPO)

    def test_the_result_message_has_no_path_or_output(self):
        git(self.work, "tag", "v0.1.0")
        (self.work / "one").write_text("edited")
        self.assertNotIn(str(self.work), self.check().reason)


class Require(Repo):
    def test_require_prints_commit_and_tag_and_returns_the_result(self):
        git(self.work, "tag", "v0.3.0")
        lines = []
        result = release.require_release_commit(self.work, out=lines.append)
        self.assertTrue(result.ok)
        self.assertIn("v0.3.0", lines[0])
        self.assertIn(result.commit[:12], lines[0])

    def test_require_exits_with_failure_when_refused(self):
        lines = []
        with self.assertRaises(SystemExit) as caught:
            release.require_release_commit(self.work, out=lines.append)
        self.assertEqual(caught.exception.code, 1)
        self.assertIn(release.NO_TAG, lines[0])


if __name__ == "__main__":
    unittest.main()
