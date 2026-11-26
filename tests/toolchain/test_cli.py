"""CLI behavior: exit codes, arguments, check, list, and the real manifest of this repository."""
import io
import pathlib
import subprocess
import sys
import unittest

import helpers
from helpers import ROOT, manifest_text, sha256, without_arm64, write_config
from test_install import Base
from toolchain_engine import cli, manifest


class Usage(Base):
    def test_an_architecture_the_manifest_has_no_artifact_for_is_a_usage_error(self):
        """CR-57 PA-30: an amd64-only manifest has no artifact for `--arch arm64`; install and verify refuse before any download."""
        self.write_manifest(without_arm64(manifest_text(amd64_sha=sha256(self.good))))
        self.assertEqual(self.install(arch="amd64")[0], 0)
        code, _, err = self.install(arch="arm64")
        self.assertEqual(code, 2)
        self.assertIn("no artifact for architecture arm64", err)

    def test_check_names_the_unlisted_architecture_under_an_amd64_only_configuration(self):
        write_config(self.root, "amd64")
        code, out, _ = self.run_cli("check")
        self.assertEqual(code, 1)
        self.assertIn("unlisted", out)

    def test_usage_errors_exit_2(self):
        cases = [[], ["bogus"], ["install"], ["install", "--profile", "lab"], ["install", "--profile", "prod", "--prefix", "/x"],
                 ["install", "--profile", "lab", "--prefix", "/x", "--arch", "riscv"], ["list"], ["verify", "--profile", "lab"],
                 ["install", "--profile", "lab", "--prefix", "/x", "--unknown"]]
        for argv in cases:
            with self.subTest(argv=argv):
                out, err = io.StringIO(), io.StringIO()
                self.assertEqual(cli.main(argv, out=out, err=err), 2)

    def test_invalid_manifest_is_exit_2_for_install_and_1_for_check(self):
        self.write_manifest("schema_version = 9\n")
        self.assertEqual(self.install()[0], 2)
        code, out, _ = self.run_cli("check")
        self.assertEqual(code, 1)
        self.assertIn("schema_version", out)

    def test_missing_manifest_is_exit_2(self):
        out, err = io.StringIO(), io.StringIO()
        self.assertEqual(cli.main(["--manifest", "/nonexistent/manifest.toml", "check"], out=out, err=err), 2)

    def test_check_ok(self):
        write_config(self.root, "amd64", "arm64")  # the fixture manifest has both artifacts, so the configuration lists both
        code, out, _ = self.run_cli("check")
        self.assertEqual(code, 0)
        self.assertIn("ok", out)

    def test_list(self):
        code, out, _ = self.run_cli("list", "--profile", "lab", "--arch", "amd64")
        self.assertEqual(code, 0)
        self.assertIn("alpha 1.2.3 download", out)
        self.assertIn("gitlike", out)
        code, out, _ = self.run_cli("list", "--profile", "operator")
        self.assertIn("alpha", out)
        self.assertNotIn("gitlike", out)


    def test_list_json_and_source_filter(self):
        import json
        code, out, _ = self.run_cli("list", "--profile", "lab", "--format", "json")
        self.assertEqual(code, 0)
        data = json.loads(out)
        names = {item["name"]: item for item in data}
        self.assertEqual(names["gitlike"]["package"], "git")
        self.assertEqual(names["gitlike"]["source"], "apt")
        self.assertEqual(names["alpha"]["version"], "1.2.3")
        code, out, _ = self.run_cli("list", "--profile", "lab", "--format", "json", "--source", "apt")
        self.assertEqual([item["name"] for item in json.loads(out)], ["gitlike"])
        code, out, _ = self.run_cli("list", "--profile", "lab", "--source", "download")
        self.assertNotIn("gitlike", out)

    def test_bad_format_or_source_is_a_usage_error(self):
        for argv in (["list", "--profile", "lab", "--format", "xml"], ["list", "--profile", "lab", "--source", "snap"],
                     ["install", "--profile", "lab", "--prefix", "/x", "--source", "snap"]):
            with self.subTest(argv=argv):
                self.assertEqual(cli.main(argv, out=io.StringIO(), err=io.StringIO()), 2)


class Arch(unittest.TestCase):
    def test_detect(self):
        self.assertEqual(cli.detect_arch("x86_64"), "amd64")
        self.assertEqual(cli.detect_arch("aarch64"), "arm64")
        for bad in ("armv7l", "i686", "ppc64le", "riscv64", ""):
            with self.subTest(machine=bad), self.assertRaises(Exception):
                cli.detect_arch(bad)


class RealManifest(unittest.TestCase):
    """The manifest shipped in this repository (T-6 static part, T-10)."""

    def setUp(self):
        self.path = ROOT / "toolchain" / "manifest.toml"
        self.raw = manifest.load(self.path)

    def test_check_passes(self):
        self.assertEqual(manifest.check_file(self.path, ROOT), [])

    def test_lab_tools_resolve_under_their_expected_names(self):
        names = set()
        for tool in self.raw["tools"].values():
            names.update(pathlib.PurePosixPath(b).name for b in tool.get("binaries", []))
        for expected in ("fd", "rg", "gh", "yq", "shellcheck", "actionlint", "yamllint", "pymarkdown"):
            self.assertIn(expected, names)

    def test_every_download_has_exactly_the_configured_amd64_artifact(self):
        for name, tool in self.raw["tools"].items():
            if tool["source"] == "download":
                with self.subTest(tool=name):
                    self.assertEqual(set(tool["artifacts"]), {"amd64"})

    def test_lock_file_has_hashes_for_both_architectures_of_native_packages(self):
        text = (ROOT / "toolchain" / "python" / "builder.lock").read_text()
        self.assertIn("yamllint==", text)
        self.assertIn("pymarkdownlnt==", text)
        self.assertNotIn("--index-url", text)

    def test_script_runs_isolated(self):
        done = subprocess.run([sys.executable, "-I", "-B", str(ROOT / "scripts" / "toolchain"), "check"], capture_output=True, text=True, check=False)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)


if __name__ == "__main__":
    unittest.main()
