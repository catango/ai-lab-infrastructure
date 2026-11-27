"""CR-57 plan PR 8, PA-34, PA-A23, PA-A31 (O-18, O-22): the project input channel of lab setup.

`ansible/roles/lab_project/files/lab-project-input` reads three files of a project (the CI manifest, the package list, the seeded
`.claude/deny.platform.txt`) from a merged commit or tag of an anonymous clone, or from a commit SHA the user supplies, and nothing
else: the project's own `scripts/toolchain` is never extracted, so it is never run. These tests run the helper against real git
repositories in temporary directories; the anonymous clone is a seam (no network) and apt is answered by a fake.
Nothing here needs root. The PA-28 job runs the real thing as root with two accounts (tests/ansible/pa28-lab.sh, step `project`).
"""
import io
import json
import os
import pathlib
import subprocess
import tempfile
import unittest

import helpers
from helpers import ROOT, load

HELPER = ROOT / "ansible" / "roles" / "lab_project" / "files" / "lab-project-input"
GIT_ENV = {"PATH": "/usr/bin:/bin", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null", "GIT_AUTHOR_NAME": "t",
           "GIT_AUTHOR_EMAIL": "noreply", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "noreply"}
AT = "@"  # kept apart so that no line of this file looks like an email address to the public-repository hygiene check
CORE = "# the core list\nBash(ssh *)\nRead(~/.ssh/**)\n"
MANIFEST = ('schema_version = 1\n[tools.demo]\nversion = "1.0.0"\nprofiles = ["lab"]\nsource = "download"\nformat = "binary"\n'
            'binaries = ["demo"]\nsmoke = ["demo"]\nsmoke_match = "1.0.0"\n[tools.demo.artifacts.amd64]\n'
            'url = "https://example.org/demo-1.0.0"\nsha256 = "' + "0" * 64 + '"\n')
APT_PLAN = (
    "Reading package lists...\nInst libdemo1 (1.2-3 Debian:13.1/stable [amd64])\n"
    "Inst demo (2.0-1 Debian:13.1/stable, Debian-Security:13/stable-security [amd64])\nConf libdemo1 (1.2-3 Debian:13.1/stable [amd64])\n")


def git(path, *args, check=True):
    done = subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True, env=GIT_ENV, check=False)
    if check:
        assert done.returncode == 0, done.stderr
    return done.stdout.strip()


class Fixture(unittest.TestCase):
    """A project repository: `main` has commit A (tagged v1.0.0), a branch `feature` has an unmerged commit B on top of it."""

    def setUp(self):
        self.mod = load("lab_project_input", HELPER)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = pathlib.Path(tmp.name)
        self.repo = self.base / "project"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        self.put("toolchain/manifest.toml", MANIFEST)
        self.put("toolchain/lab-packages.txt", "# packages\nhello\n")
        self.put(".claude/deny.platform.txt", "# platform\nRead(~/.config/svc/**)\n")
        self.put("scripts/toolchain", "#!/bin/sh\ntouch \"$SENTINEL\"\n", 0o755)
        self.put("docs/PROJECT.md", "project\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "A")
        self.a = git(self.repo, "rev-parse", "HEAD")
        git(self.repo, "tag", "v1.0.0")
        git(self.repo, "checkout", "-q", "-b", "feature")
        self.put(".claude/deny.platform.txt", "# platform\nRead(~/.config/svc/**)\nRead(~/.config/other/**)\n")
        git(self.repo, "commit", "-q", "-am", "B")
        self.b = git(self.repo, "rev-parse", "HEAD")
        git(self.repo, "checkout", "-q", "main")
        self.work = self.base / "work"
        self.work.mkdir(mode=0o700)

    def put(self, relative, text, mode=0o644):
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        path.chmod(mode)

    def clone(self, url, dest):
        """The seam of the anonymous clone: a bare clone of the local fixture repository (no network)."""
        done = subprocess.run(["git", "clone", "-q", "--bare", str(self.repo), str(dest)], capture_output=True, env=GIT_ENV, check=False)
        assert done.returncode == 0, done.stderr

    def anonymous(self, ref, url="https://github.com/owner/project"):
        return self.mod.fetch_anonymous(url, ref, self.work, clone=self.clone)

    def supplied(self, sha):
        return self.mod.fetch_supplied(str(self.repo), sha, None)


class Packages(unittest.TestCase):
    """PA-A23: a package list names Debian archive packages and nothing else; a third-party apt source is refused."""

    def setUp(self):
        self.mod = load("lab_project_input", HELPER)

    def refused(self, text, fragment):
        with self.assertRaises(self.mod.Refusal) as caught:
            self.mod.parse_packages(text)
        self.assertIn(fragment, str(caught.exception))

    def test_names_comments_and_blank_lines(self):
        self.assertEqual(self.mod.parse_packages("# a list\n\nhello\n  libstdc++6  \ng++\n"), ["hello", "libstdc++6", "g++"])

    def test_an_empty_list_is_no_package(self):
        self.assertEqual(self.mod.parse_packages("# nothing\n"), [])

    def test_a_third_party_apt_source_line_is_refused(self):
        for line in ("deb http://example.org/debian trixie main", "deb-src https://example.org/debian trixie main",
                     "deb [signed-by=/etc/key.gpg] https://example.org/apt stable main", "ppa:someone/tools",
                     "https://example.org/pkg.deb", "Types: deb", "URIs: https://example.org/apt"):
            self.refused(line + "\n", "third-party apt source")

    def test_a_package_from_another_release_or_a_pinned_version_is_refused(self):
        for line in ("hello/unstable", "hello=2.10-5", "hello:i386", "hello-", "Hello", "hello world", "-hello", "hello*", "../x"):
            self.refused(line + "\n", "not a plain Debian package name")

    def test_a_name_twice_and_too_long_a_list_are_refused(self):
        self.refused("hello\nhello\n", "twice")
        self.refused("\n".join(f"pkg{n}x" for n in range(201)) + "\n", "at most")


class DenyEntries(unittest.TestCase):
    """PA-A31, I-7: the project's deny.platform.txt entries join the lab-wide list after the core entries, none repeated."""

    def setUp(self):
        self.mod = load("lab_project_input", HELPER)

    def test_the_core_stays_first_and_byte_for_byte_and_the_project_entries_follow(self):
        text, entries, added = self.mod.merge_deny(CORE, "# platform\nRead(~/.config/svc/**)\nRead(~/.config/svc2/**)\n", "owner/project", "a" * 40)
        self.assertTrue(text.startswith(CORE))
        self.assertEqual(entries, ["Bash(ssh *)", "Read(~/.ssh/**)", "Read(~/.config/svc/**)", "Read(~/.config/svc2/**)"])
        self.assertEqual(added, ["Read(~/.config/svc/**)", "Read(~/.config/svc2/**)"])
        self.assertEqual(self.mod.parse_deny(text), entries)

    def test_an_entry_the_core_has_is_not_listed_twice(self):
        text, entries, added = self.mod.merge_deny(CORE, "Bash(ssh *)\nRead(~/.config/svc/**)\nRead(~/.config/svc/**)\n", "owner/project", "a" * 40)
        self.assertEqual(entries.count("Bash(ssh *)"), 1)
        self.assertEqual(entries.count("Read(~/.config/svc/**)"), 1)
        self.assertEqual(added, ["Read(~/.config/svc/**)"])

    def test_no_project_file_or_nothing_new_leaves_the_core_untouched(self):
        self.assertEqual(self.mod.merge_deny(CORE, None, None, None), (CORE, ["Bash(ssh *)", "Read(~/.ssh/**)"], []))
        self.assertEqual(self.mod.merge_deny(CORE, "# only\nBash(ssh *)\n", "owner/project", "a" * 40)[0], CORE)

    def test_an_entry_that_is_not_a_rule_is_refused(self):
        for bad in ("Read(", "has space", "Bash(x)\x00", "x" * 400, "{json}", "Bash(a)) trailing"):
            with self.assertRaises(self.mod.Refusal, msg=bad):
                self.mod.parse_deny(bad + "\n")

    def test_no_core_entry_is_removed_and_the_core_is_the_source(self):
        """PA-A10: a project file only adds. The merge never drops, reorders, or rewrites a core entry."""
        core = (ROOT / "workspace" / "claude-user" / "required-deny.txt").read_text()
        text, entries, added = self.mod.merge_deny(core, "Read(~/.config/svc/**)\n", "owner/project", "b" * 40)
        self.assertEqual(entries[:90], self.mod.parse_deny(core))
        self.assertEqual(entries[90:], ["Read(~/.config/svc/**)"])
        self.assertTrue(text.startswith(core))


APT_TOOL = '[tools.git]\nprofiles = ["lab"]\nsource = "apt"\nversion_min = "2.0"\npackage = "git"\nsmoke = ["git", "--version"]\n'
PIP_TOOL = ('# a pip tool\n[tools.lint]\nprofiles = ["lab"]\nsource = "pip"\nlockfile = "x.lock"\nbinaries = ["lint"]\nsmoke = ["lint"]\n'
            'smoke_match = "1"\n')


class ManifestFilter(unittest.TestCase):
    """The project's CI manifest is "the tools CI uses": a template-seeded one lists the gate tools, apt and pip entries included. The
    engine installs download tools only in v1, so the manifest that is staged and recorded holds those, and the rest is reported."""

    def setUp(self):
        self.mod = load("lab_project_input", HELPER)

    def test_a_download_manifest_is_kept_as_it_is(self):
        self.assertEqual(self.mod.filter_manifest(MANIFEST), (MANIFEST, []))

    def test_apt_and_pip_entries_are_left_out_and_reported_and_the_rest_stays_valid(self):
        text, skipped = self.mod.filter_manifest("schema_version = 1\n" + PIP_TOOL + APT_TOOL + MANIFEST[len("schema_version = 1\n"):])
        self.assertEqual(sorted(skipped), [("git", "apt"), ("lint", "pip")])
        import tomllib
        parsed = tomllib.loads(text)
        self.assertEqual(sorted(parsed["tools"]), ["demo"])
        self.assertEqual(parsed["tools"]["demo"]["artifacts"]["amd64"]["sha256"], "0" * 64)
        self.assertNotIn("lockfile", text)
        self.assertNotIn('source = "apt"', text)
        self.assertNotIn('source = "pip"', text)

    def test_the_real_manifest_of_this_repository_is_filtered_to_its_download_tools(self):
        import tomllib
        original = (ROOT / "toolchain" / "manifest.toml").read_text()
        text, skipped = self.mod.filter_manifest(original)
        kept = tomllib.loads(text)["tools"]
        expected = {name for name, tool in tomllib.loads(original)["tools"].items() if tool["source"] == "download"}
        self.assertEqual(set(kept), expected)
        self.assertEqual({name for name, _ in skipped}, set(tomllib.loads(original)["tools"]) - expected)
        for name in kept:
            self.assertEqual(kept[name], tomllib.loads(original)["tools"][name])

    def test_a_manifest_with_no_download_tool_has_nothing_to_install(self):
        self.assertEqual(self.mod.filter_manifest("schema_version = 1\n" + APT_TOOL)[0], None)

    def test_a_layout_that_cannot_be_filtered_is_refused_and_not_guessed(self):
        dotted = 'schema_version = 1\ntools.demo.version = "1.0.0"\ntools.demo.source = "download"\ntools.git.source = "apt"\n'
        with self.assertRaises(self.mod.Refusal):
            self.mod.filter_manifest(dotted)

    def test_invalid_toml_and_a_manifest_without_tools_are_refused(self):
        for text in ("tools = [", "schema_version = 1\n"):
            with self.assertRaises(self.mod.Refusal, msg=text):
                self.mod.filter_manifest(text)


class Archive(unittest.TestCase):
    """The only bytes of a project that reach root are three regular files of known names, read from a tar of git archive."""

    def setUp(self):
        self.mod = load("lab_project_input", HELPER)

    def tar(self, members):
        import tarfile
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w") as archive:
            for name, kind, payload in members:
                info = tarfile.TarInfo(name)
                if kind == "dir":
                    info.type = tarfile.DIRTYPE
                    archive.addfile(info)
                elif kind == "link":
                    info.type, info.linkname = tarfile.SYMTYPE, payload
                    archive.addfile(info)
                else:
                    data = payload.encode()
                    info.size = len(data)
                    archive.addfile(info, io.BytesIO(data))
        return buffer.getvalue()

    def test_the_three_files_come_out_by_their_staged_names(self):
        data = self.tar([("toolchain/", "dir", ""), ("toolchain/manifest.toml", "file", "m"), (".claude/", "dir", ""),
                         (".claude/deny.platform.txt", "file", "d")])
        self.assertEqual(self.mod.extract_tar(data), {"manifest.toml": "m", "deny.platform.txt": "d"})

    def test_a_symbolic_link_in_place_of_a_file_is_refused(self):
        with self.assertRaises(self.mod.Refusal):
            self.mod.extract_tar(self.tar([("toolchain/manifest.toml", "link", "/etc/shadow")]))

    def test_the_projects_scripts_toolchain_is_refused_and_never_staged(self):
        with self.assertRaises(self.mod.Refusal) as caught:
            self.mod.extract_tar(self.tar([("scripts/toolchain", "file", "#!/bin/sh\n")]))
        self.assertIn("scripts/toolchain", str(caught.exception))

    def test_a_file_over_the_size_cap_is_refused(self):
        with self.assertRaises(self.mod.Refusal):
            self.mod.extract_tar(self.tar([("toolchain/lab-packages.txt", "file", "x" * (1 << 20 + 1))]))

    def test_a_tar_that_is_not_a_tar_is_refused(self):
        with self.assertRaises(self.mod.Refusal):
            self.mod.extract_tar(b"not a tar")


class Sources(Fixture):
    """PA-A23: merged commit or tag from an anonymous clone, or a SHA the user supplies; nothing else."""

    def test_a_tag_on_a_merged_commit_is_accepted(self):
        commit, data = self.anonymous("v1.0.0")
        self.assertEqual(commit, self.a)
        self.assertEqual(set(self.mod.extract_tar(data)), {"manifest.toml", "packages.txt", "deny.platform.txt"})

    def test_a_merged_commit_is_accepted_by_its_full_sha(self):
        self.assertEqual(self.anonymous(self.a)[0], self.a)

    def test_an_unmerged_commit_is_refused(self):
        git(self.repo, "branch", "-f", "reachable", self.b)
        with self.assertRaises(self.mod.Refusal) as caught:
            self.anonymous(self.b)
        self.assertIn("not merged", str(caught.exception))

    def test_a_tag_on_an_unmerged_commit_is_refused(self):
        git(self.repo, "tag", "v2.0.0", self.b)
        with self.assertRaises(self.mod.Refusal) as caught:
            self.anonymous("v2.0.0")
        self.assertIn("not merged", str(caught.exception))

    def test_a_branch_name_is_not_a_reference(self):
        for ref in ("main", "feature", "HEAD", "--upload-pack=x", "a b", "", "v1.0.0^{commit}", self.a[:12]):
            with self.assertRaises(self.mod.Refusal, msg=ref):
                self.anonymous(ref)

    def test_only_an_anonymous_https_address_of_github_is_accepted(self):
        for url in ("file:///tmp/x", "http://github.com/o/p", "git" + AT + "github.com:o/p.git", "https://user:token" + AT + "github.com/o/p",
                    "https://example.org/o/p", "https://github.com/o", "https://github.com/o/p/extra", "ssh://github.com/o/p", "/tmp/x"):
            with self.assertRaises(self.mod.Refusal, msg=url):
                self.anonymous("v1.0.0", url=url)

    def test_a_supplied_sha_is_accepted_even_when_it_is_not_merged(self):
        commit, data = self.supplied(self.b)
        self.assertEqual(commit, self.b)
        self.assertIn("Read(~/.config/other/**)", self.mod.extract_tar(data)["deny.platform.txt"])

    def test_a_supplied_value_that_is_not_a_full_sha_is_refused(self):
        for value in ("v1.0.0", "main", self.a[:12], self.a.upper(), self.a + "0", "--all", ""):
            with self.assertRaises(self.mod.Refusal, msg=value):
                self.supplied(value)

    def test_a_supplied_sha_that_the_clone_does_not_have_is_refused(self):
        with self.assertRaises(self.mod.Refusal):
            self.supplied("0" * 40)

    def test_the_project_scripts_toolchain_is_in_the_commit_and_is_never_staged_or_run(self):
        sentinel = self.base / "sentinel"
        os.environ["SENTINEL"] = str(sentinel)
        self.addCleanup(os.environ.pop, "SENTINEL", None)
        _, data = self.supplied(self.a)
        files = self.mod.extract_tar(data)
        self.assertNotIn("scripts/toolchain", files)
        self.assertEqual(sorted(files), ["deny.platform.txt", "manifest.toml", "packages.txt"])
        self.assertFalse(sentinel.exists())

    def test_a_project_without_the_files_stages_nothing(self):
        git(self.repo, "rm", "-q", "-r", "toolchain", ".claude")
        git(self.repo, "commit", "-q", "-m", "C")
        _, data = self.supplied(git(self.repo, "rev-parse", "HEAD"))
        self.assertEqual(self.mod.extract_tar(data), {})


class Stage(Fixture):
    def args(self, *extra):
        core = self.base / "core.txt"
        core.write_text(CORE)
        return ["stage", "--out", str(self.work), "--core", str(core), *extra]

    def run_cli(self, argv):
        out, err = io.StringIO(), io.StringIO()
        code = self.mod.main(argv, out=out, err=err, clone=self.clone)
        return code, out.getvalue(), err.getvalue()

    def test_without_a_project_the_result_is_the_core_list_and_nothing_is_staged(self):
        code, out, _ = self.run_cli(self.args())
        result = json.loads(out)
        self.assertEqual((code, result["source"], result["deny_entries"], result["added"], result["packages"]),
                         (0, None, ["Bash(ssh *)", "Read(~/.ssh/**)"], [], []))
        self.assertEqual(list(self.work.iterdir()), [])

    def test_a_supplied_sha_stages_the_three_files_and_reports_the_source(self):
        code, out, _ = self.run_cli(self.args("--clone", str(self.repo), "--sha", self.a))
        result = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual(result["source"], {"kind": "supplied-sha", "commit": self.a, "repo": None, "ref": None})
        self.assertEqual(result["packages"], ["hello"])
        self.assertEqual(result["added"], ["Read(~/.config/svc/**)"])
        self.assertEqual(result["deny_entries"], ["Bash(ssh *)", "Read(~/.ssh/**)", "Read(~/.config/svc/**)"])
        self.assertEqual(sorted(p.name for p in self.work.iterdir()), ["deny.platform.txt", "manifest.toml", "packages.txt"])
        for path in self.work.iterdir():
            self.assertEqual(path.stat().st_mode & 0o077, 0, path.name)
        self.assertIn("Read(~/.config/svc/**)", result["deny_text"])
        self.assertEqual(result["manifest_present"], True)
        self.assertEqual(result["manifest_skipped"], [])

    def test_an_anonymous_tag_reports_repo_ref_and_commit(self):
        code, out, _ = self.run_cli(self.args("--repo", "https://github.com/owner/project", "--ref", "v1.0.0"))
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["source"], {"kind": "anonymous", "commit": self.a, "repo": "https://github.com/owner/project", "ref": "v1.0.0"})

    def test_an_unmerged_commit_is_refused_with_exit_1_and_nothing_is_staged(self):
        code, out, err = self.run_cli(self.args("--repo", "https://github.com/owner/project", "--ref", self.b))
        self.assertEqual((code, out), (1, ""))
        self.assertIn("not merged", err)
        self.assertEqual(list(self.work.iterdir()), [])

    def test_the_two_sources_together_or_half_of_one_are_a_usage_error(self):
        for extra in (["--repo", "https://github.com/o/p"], ["--ref", "v1"], ["--sha", self.a], ["--clone", str(self.repo)],
                      ["--repo", "https://github.com/o/p", "--ref", "v1", "--sha", self.a, "--clone", str(self.repo)]):
            code, out, err = self.run_cli(self.args(*extra))
            self.assertEqual((code, out), (2, ""), extra)

    def test_a_bad_package_list_in_the_commit_is_refused_before_anything_is_staged(self):
        self.put("toolchain/lab-packages.txt", "deb http://example.org/debian trixie main\n")
        git(self.repo, "commit", "-q", "-am", "C")
        code, out, err = self.run_cli(self.args("--clone", str(self.repo), "--sha", git(self.repo, "rev-parse", "HEAD")))
        self.assertEqual((code, out), (1, ""))
        self.assertIn("third-party apt source", err)
        self.assertEqual(list(self.work.iterdir()), [])


class Recorded(Fixture):
    """A run that selects no project keeps the deny entries that an earlier run recorded: a routine re-run (a key change, a tag
    update) must never silently drop a project's credential-path rule from the layer. The record is the root-owned directory that
    lab setup wrote; one lab is one project (design PA-8), and a new selection replaces it."""

    def setUp(self):
        super().setUp()
        self.record = self.base / "record"
        self.record.mkdir()
        (self.record / "deny.platform.txt").write_text("# recorded\nRead(~/.config/recorded/**)\n")
        (self.record / "SOURCE").write_text(f"kind=supplied-sha\ncommit={self.a}\n")
        core = self.base / "core.txt"
        core.write_text(CORE)
        self.base_args = ["stage", "--out", str(self.work), "--core", str(core), "--recorded", str(self.record)]

    def run_cli(self, *extra):
        out, err = io.StringIO(), io.StringIO()
        code = self.mod.main([*self.base_args, *extra], out=out, err=err, clone=self.clone)
        return code, out.getvalue(), err.getvalue()

    def test_no_selection_keeps_the_recorded_entries_after_the_core(self):
        code, out, _ = self.run_cli()
        result = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual(result["deny_entries"], ["Bash(ssh *)", "Read(~/.ssh/**)", "Read(~/.config/recorded/**)"])
        self.assertEqual(result["source"], {"kind": "recorded", "commit": self.a, "repo": None, "ref": None})
        self.assertEqual((result["packages"], result["manifest_present"]), ([], False))
        self.assertEqual(list(self.work.iterdir()), [], "nothing is staged and nothing is installed again")

    def test_a_new_selection_replaces_the_recorded_entries(self):
        code, out, _ = self.run_cli("--clone", str(self.repo), "--sha", self.a)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["deny_entries"][-1], "Read(~/.config/svc/**)")
        self.assertNotIn("Read(~/.config/recorded/**)", json.loads(out)["deny_entries"])

    def test_a_missing_record_is_no_record(self):
        (self.record / "deny.platform.txt").unlink()
        code, out, _ = self.run_cli()
        self.assertEqual((code, json.loads(out)["source"]), (0, None))

    def test_a_record_that_is_a_link_or_not_a_rule_list_is_refused(self):
        (self.record / "deny.platform.txt").unlink()
        (self.record / "deny.platform.txt").symlink_to("/etc/passwd")
        code, out, err = self.run_cli()
        self.assertEqual((code, out), (1, ""))
        (self.record / "deny.platform.txt").unlink()
        (self.record / "deny.platform.txt").write_text("not a rule\n")
        self.assertEqual(self.run_cli()[0], 1)


class Plan(unittest.TestCase):
    """PA-A23, O-22: the dry run prints every package name and version before anything is installed; the apply is bound to it."""

    def setUp(self):
        self.mod = load("lab_project_input", HELPER)
        self.calls = []

    def run_fake(self, plan=APT_PLAN, code=0):
        def run(argv, env=None, input=None):
            self.calls.append(list(argv))
            return code, plan.encode(), b""
        return run

    def test_the_plan_lists_every_name_version_and_origin_including_dependencies(self):
        plan = self.mod.plan_packages(["demo"], run=self.run_fake())
        self.assertEqual(plan, [("demo", "2.0-1", "Debian:13.1/stable,Debian-Security:13/stable-security"),
                                ("libdemo1", "1.2-3", "Debian:13.1/stable")])

    def test_the_plan_is_simulated_with_no_recommends_and_the_names_after_a_double_dash(self):
        self.mod.plan_packages(["demo", "other"], run=self.run_fake())
        argv = self.calls[0]
        self.assertEqual(argv[:2], ["apt-get", "-s"])
        self.assertIn("--no-install-recommends", argv)
        self.assertEqual(argv[-3:], ["--", "demo", "other"])

    def test_an_origin_that_is_not_the_debian_archive_is_refused(self):
        plan = "Inst demo (2.0-1 Example:stable/main [amd64])\n"
        with self.assertRaises(self.mod.Refusal) as caught:
            self.mod.plan_packages(["demo"], run=self.run_fake(plan))
        self.assertIn("not the Debian archive", str(caught.exception))
        self.assertIn("Example", str(caught.exception))

    def test_a_plan_that_removes_a_package_is_refused(self):
        with self.assertRaises(self.mod.Refusal) as caught:
            self.mod.plan_packages(["demo"], run=self.run_fake("Remv old [1.0]\nInst demo (2.0-1 Debian:13/stable [amd64])\n"))
        self.assertIn("remove", str(caught.exception))

    def test_a_package_apt_does_not_know_is_refused_with_its_message(self):
        with self.assertRaises(self.mod.Refusal):
            self.mod.plan_packages(["nope"], run=self.run_fake("E: Unable to locate package nope\n", code=100))

    def test_an_empty_package_index_says_what_to_do(self):
        with self.assertRaises(self.mod.Refusal) as caught:
            self.mod.plan_packages(["demo"], run=self.run_fake("E: Unable to locate package demo\n", code=100))
        self.assertIn("apt-get update", str(caught.exception))

    def test_the_digest_covers_names_and_versions_and_not_the_order(self):
        one = self.mod.plan_digest([("a", "1", "Debian:13/stable"), ("b", "2", "Debian:13/stable")])
        two = self.mod.plan_digest([("b", "2", "Debian:13/stable"), ("a", "1", "Debian:13/stable")])
        self.assertEqual(one, two)
        self.assertNotEqual(one, self.mod.plan_digest([("a", "1", "Debian:13/stable"), ("b", "3", "Debian:13/stable")]))

    def test_the_dry_run_prints_each_name_and_version_and_installs_nothing(self):
        out = io.StringIO()
        code = self.mod.report_packages(["demo"], apply=False, reviewed=None, run=self.run_fake(), out=out)
        text = out.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("demo 2.0-1 ", text)
        self.assertIn("libdemo1 1.2-3 ", text)
        self.assertIn("plan_sha256=", text)
        self.assertIn("changed=2", text.splitlines())
        self.assertTrue(all(call[:2] == ["apt-get", "-s"] for call in self.calls), self.calls)

    def test_a_second_run_has_no_plan_and_changes_nothing(self):
        out = io.StringIO()
        self.mod.report_packages(["demo"], apply=False, reviewed=None, run=self.run_fake("Reading package lists...\n"), out=out)
        self.assertIn("changed=0", out.getvalue().splitlines())

    def test_the_apply_needs_the_digest_of_the_plan_that_was_read(self):
        out = io.StringIO()
        code = self.mod.report_packages(["demo"], apply=True, reviewed=None, run=self.run_fake(), out=out)
        self.assertEqual(code, 1)
        self.assertIn("dry run", out.getvalue())
        self.assertTrue(all(call[:2] == ["apt-get", "-s"] for call in self.calls), "nothing was installed")

    def test_an_empty_plan_needs_no_digest_so_a_second_apply_changes_nothing(self):
        out = io.StringIO()
        code = self.mod.report_packages(["demo"], apply=True, reviewed=None, run=self.run_fake("Reading package lists...\n"), out=out)
        self.assertEqual(code, 0)
        self.assertIn("changed=0", out.getvalue().splitlines())
        self.assertTrue(all(call[:2] == ["apt-get", "-s"] for call in self.calls))

    def test_the_command_reads_the_list_file_and_applies_through_main(self):
        listing = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(listing, ignore_errors=True))
        (listing / "packages.txt").write_text("demo\n")
        digest = self.mod.plan_digest(self.mod.plan_packages(["demo"], run=self.run_fake()))
        out, err = io.StringIO(), io.StringIO()
        code = self.mod.main(["packages", "--file", str(listing / "packages.txt"), "--apply", "--reviewed", digest], out=out, err=err, run=self.run_fake())
        self.assertEqual((code, err.getvalue()), (0, ""))
        self.assertTrue(any(call[:3] == ["apt-get", "install", "-y"] for call in self.calls))

    def test_the_apply_refuses_a_plan_that_changed_since_the_dry_run(self):
        out = io.StringIO()
        code = self.mod.report_packages(["demo"], apply=True, reviewed="0" * 64, run=self.run_fake(), out=out)
        self.assertEqual(code, 1)
        self.assertIn("changed since", out.getvalue())
        self.assertTrue(all(call[:2] == ["apt-get", "-s"] for call in self.calls))

    def test_the_apply_installs_exactly_the_reviewed_plan(self):
        digest = self.mod.plan_digest(self.mod.plan_packages(["demo"], run=self.run_fake()))
        self.calls.clear()
        out = io.StringIO()
        code = self.mod.report_packages(["demo"], apply=True, reviewed=digest, run=self.run_fake(), out=out)
        self.assertEqual(code, 0)
        install = [call for call in self.calls if call[:2] != ["apt-get", "-s"]]
        self.assertEqual(len(install), 1)
        self.assertEqual(install[0][:3], ["apt-get", "install", "-y"])
        self.assertIn("--no-install-recommends", install[0])
        self.assertEqual(install[0][-2:], ["--", "demo"])
        self.assertIn("changed=2", out.getvalue().splitlines())


class Static(unittest.TestCase):
    def test_the_helper_is_a_standard_library_script_run_in_isolated_mode(self):
        text = HELPER.read_text()
        self.assertTrue(text.startswith("#!/usr/bin/python3 -I\n"))
        self.assertTrue(os.access(HELPER, os.X_OK))
        for forbidden in ("import requests", "shell=True", "os.system", "eval(", "exec(", "extractall", ".extract("):
            self.assertNotIn(forbidden, text, forbidden)

    def test_the_helper_never_names_a_credential_or_reads_the_environment_for_one(self):
        text = HELPER.read_text()
        for word in ("GH_TOKEN", "GITHUB_TOKEN", ".config/gh", "hosts.yml", ".ssh"):
            self.assertNotIn(word, text, word)


if __name__ == "__main__":
    unittest.main()
