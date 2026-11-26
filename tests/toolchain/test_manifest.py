"""T-1: `check` rejects each malformed manifest; plus the structural rules in design 3.2."""
import pathlib
import tempfile
import unittest

import helpers
from helpers import ARM64_URL, AMD64_URL, manifest_text, without_arm64, write_config
from toolchain_engine import manifest

GOOD = "a" * 64
LOCK = (
    "# comment\nyamllint==1.0.0 \\\n    --hash=sha256:" + GOOD + " \\\n    --hash=sha256:" + "b" * 64 + "\n\n"
    "pyyaml==6.0 \\\n    --hash=sha256:" + "c" * 64 + "\n"
)
PIP = '''
[tools.pylint]
profiles = ["lab"]
source = "pip"
lockfile = "toolchain/python/builder.lock"
binaries = ["yamllint"]
smoke = ["yamllint", "--version"]
smoke_match = "yamllint"
'''


def check(text, lock=LOCK, arches=("amd64", "arm64")):
    """Validation errors of TEXT under a root whose config/project.yaml lists ARCHES (None: no configuration file)."""
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        (root / "toolchain" / "python").mkdir(parents=True)
        if arches is not None:
            write_config(root, *arches)
        if lock is not None:
            (root / "toolchain" / "python" / "builder.lock").write_text(lock)
        (root / "toolchain" / "manifest.toml").write_text(text)
        return manifest.check_file(root / "toolchain" / "manifest.toml", root)


def good(**kw):
    kw.setdefault("amd64_sha", GOOD)
    kw.setdefault("arm64_sha", "b" * 64)
    return manifest_text(**kw)


class Accepts(unittest.TestCase):
    def test_a_good_manifest_has_no_errors(self):
        self.assertEqual(check(good()), [])

    def test_pip_and_apt_sources(self):
        self.assertEqual(check(good(extra_tools=PIP)), [])

    def test_binary_format(self):
        text = good().replace('format = "tar.gz"', 'format = "binary"').replace("strip = 1\n", "strip = 0\n") \
            .replace('binaries = ["bin/alpha"]', 'binaries = ["alpha"]')
        self.assertEqual(check(text), [])


class ConfiguredArchitectures(unittest.TestCase):
    """CR-57 PA-30, O-4, PA-A7, PA-A19: `check` requires artifacts for exactly the architectures of config/project.yaml."""

    def errors(self, text, arches):
        return check(text, arches=arches)

    def test_amd64_only_configuration_passes_with_amd64_artifacts(self):
        self.assertEqual(self.errors(without_arm64(good()), ("amd64",)), [])

    def test_an_arm64_artifact_fails_under_an_amd64_only_configuration(self):
        errors = self.errors(good(), ("amd64",))
        self.assertTrue(any("tools.alpha.artifacts.arm64" in e and "unlisted" in e for e in errors), errors)

    def test_amd64_and_arm64_configuration_still_requires_both(self):
        self.assertEqual(self.errors(good(), ("amd64", "arm64")), [])
        errors = self.errors(without_arm64(good()), ("amd64", "arm64"))
        self.assertTrue(any("tools.alpha.artifacts.arm64" in e and "missing" in e for e in errors), errors)

    def test_a_missing_configuration_file_means_the_default_which_is_amd64_only(self):
        self.assertEqual(self.errors(without_arm64(good()), None), [])
        self.assertTrue(any("unlisted" in e for e in self.errors(good(), None)))

    def test_a_configuration_naming_an_unknown_architecture_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "toolchain" / "python").mkdir(parents=True)
            (root / "toolchain" / "python" / "builder.lock").write_text(LOCK)
            (root / "config").mkdir()
            (root / "config" / "project.yaml").write_text("architectures:\n  - name: riscv64\n")
            (root / "toolchain" / "manifest.toml").write_text(without_arm64(good()))
            errors = manifest.check_file(root / "toolchain" / "manifest.toml", root)
        self.assertTrue(any("riscv64" in e for e in errors), errors)

    def test_an_unreadable_configuration_is_an_error_and_not_a_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "toolchain" / "python").mkdir(parents=True)
            (root / "toolchain" / "python" / "builder.lock").write_text(LOCK)
            (root / "config").mkdir()
            (root / "config" / "project.yaml").write_text("architectures: {amd64: {}}\n")
            (root / "toolchain" / "manifest.toml").write_text(without_arm64(good()))
            errors = manifest.check_file(root / "toolchain" / "manifest.toml", root)
        self.assertTrue(any("config/project.yaml" in e for e in errors), errors)


class Rejects(unittest.TestCase):
    def assert_error(self, text, fragment, lock=LOCK):
        errors = check(text, lock)
        self.assertTrue(any(fragment in e for e in errors), f"{fragment!r} not in {errors}")

    def test_missing_architecture(self):
        text = good()
        text = text[: text.index("[tools.alpha.artifacts.arm64]")] + text[text.index("[tools.gitlike]"):]
        self.assert_error(text, "arm64")
        text = good()
        start = text.index("[tools.alpha.artifacts.amd64]")
        end = text.index("[tools.alpha.artifacts.arm64]")
        self.assert_error(text[:start] + text[end:], "amd64")

    def test_unknown_architecture(self):
        self.assert_error(good() + '\n[tools.alpha.artifacts.riscv]\nurl = "https://example.invalid/1.2.3"\nsha256 = "' + GOOD + '"\n', "riscv")

    def test_malformed_checksums(self):
        for bad in ("", "abc", "A" * 64, "g" * 64, "a" * 63, "a" * 65, " " + "a" * 63, "sha256:" + "a" * 64):
            with self.subTest(bad=bad):
                self.assert_error(good(amd64_sha=bad), "sha256")

    def test_non_https_urls(self):
        for url in (AMD64_URL.replace("https", "http"), "ftp://example.invalid/alpha-1.2.3", "file:///tmp/alpha-1.2.3", "//example.invalid/1.2.3",
                    "example.invalid/alpha-1.2.3"):
            with self.subTest(url=url):
                self.assert_error(good(amd64_url=url), "https")

    def test_latest_and_version_ranges(self):
        for version in ("latest", "LATEST", "^1.2.3", "~1.2", ">=1.2.3", "1.x", "*", "1.2.3,1.2.4", "", "v 1"):
            with self.subTest(version=version):
                self.assert_error(good(version=version, amd64_url=f"https://example.invalid/{version}", arm64_url=f"https://example.invalid/{version}"), "version")
        self.assert_error(good(amd64_url="https://example.invalid/latest/alpha-1.2.3.tar.gz"), "latest")

    def test_unknown_keys(self):
        self.assert_error(good(alpha_extra='surprise = "x"\n'), "surprise")
        self.assert_error(good(head='schema_version = 1\nsurprise = 1\n'), "surprise")
        self.assert_error(good() + '\n[tools.alpha.artifacts.amd64x]\nurl = "https://x/1.2.3"\nsha256 = "' + GOOD + '"\nextra = 1\n', "alpha")

    def test_version_must_appear_in_every_url(self):
        self.assert_error(good(amd64_url="https://example.invalid/alpha/linux-amd64.tar.gz"), "version")
        self.assert_error(good(arm64_url="https://example.invalid/alpha/9.9.9/linux-arm64.tar.gz"), "version")

    def test_unknown_or_missing_schema_version(self):
        self.assert_error(good(head="schema_version = 2\n"), "schema_version")
        self.assert_error(good(head=""), "schema_version")
        self.assert_error(good(head='schema_version = "1"\n'), "schema_version")

    def test_profiles(self):
        self.assert_error(good().replace('profiles = ["lab"]', "profiles = []"), "profiles")
        self.assert_error(good().replace('profiles = ["lab"]', 'profiles = ["lab", "prod"]'), "profiles")
        self.assert_error(good().replace('profiles = ["lab"]', 'profiles = "lab"'), "profiles")

    def test_builder_is_not_a_profile(self):
        """CR-57 O-19: the alias of plan PR 2 is removed in PR 7; `builder` is an unknown profile like any other name."""
        self.assert_error(good().replace('profiles = ["lab"]', 'profiles = ["builder"]'), "profiles")
        self.assert_error(good().replace('profiles = ["lab"]', 'profiles = ["builder", "lab"]'), "profiles")

    def test_smoke_must_be_an_argument_array(self):
        self.assert_error(good().replace('smoke = ["alpha", "--version"]', 'smoke = "alpha --version"'), "smoke")
        self.assert_error(good().replace('smoke = ["alpha", "--version"]', "smoke = []"), "smoke")
        self.assert_error(good().replace('smoke = ["alpha", "--version"]', 'smoke = ["alpha", 3]'), "smoke")

    def test_smoke_match_required_for_download_and_pip(self):
        self.assert_error(good().replace('smoke_match = "alpha 1.2.3"\n', ""), "smoke_match")
        self.assert_error(good(extra_tools=PIP.replace('smoke_match = "yamllint"\n', "")), "smoke_match")

    def test_duplicate_binary_names_across_tools(self):
        other = PIP.replace('binaries = ["yamllint"]', 'binaries = ["alpha"]')
        self.assert_error(good(extra_tools=other), "alpha")

    def test_shell_metacharacters(self):
        for value in ("a;b", "a|b", "a$(id)", "a`id`", "a b", "a&b", "a>b", "a\\b", 'a"b', "a'b", "a\nb"):
            with self.subTest(value=value):
                escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
                self.assert_error(good().replace('binaries = ["bin/alpha"]', f'binaries = ["{escaped}"]'), "binaries")
        self.assert_error(good(amd64_url=AMD64_URL + "?a=b;rm"), "url")

    def test_download_fields(self):
        self.assert_error(good().replace('format = "tar.gz"', 'format = "rar"'), "format")
        self.assert_error(good().replace("strip = 1", "strip = -1"), "strip")
        self.assert_error(good().replace("strip = 1", 'strip = "1"'), "strip")
        self.assert_error(good().replace('binaries = ["bin/alpha"]', "binaries = []"), "binaries")
        self.assert_error(good().replace('binaries = ["bin/alpha"]', 'binaries = ["../alpha"]'), "binaries")
        self.assert_error(good().replace('binaries = ["bin/alpha"]', 'binaries = ["/bin/alpha"]'), "binaries")
        self.assert_error(good(alpha_extra="max_bytes = 0\n"), "max_bytes")
        self.assert_error(good(alpha_extra='max_bytes = "1"\n'), "max_bytes")

    def test_binary_format_rules(self):
        text = good().replace('format = "tar.gz"', 'format = "binary"')
        self.assert_error(text, "binary")

    def test_unknown_source_and_names(self):
        self.assert_error(good().replace('source = "download"', 'source = "curl"'), "source")
        self.assert_error(good() + '\n[tools."Bad Name"]\nversion = "1"\nprofiles = ["lab"]\nsource = "apt"\npackage = "x"\nversion_min = "1"\nsmoke = ["x"]\n', "Bad Name")

    def test_apt_fields(self):
        self.assert_error(good().replace('version_min = "1:2.0"\n', ""), "version_min")
        self.assert_error(good().replace('package = "git"\n', ""), "package")
        self.assert_error(good().replace('package = "git"', 'package = "git; id"'), "package")

    def test_pip_lockfile_rules(self):
        self.assert_error(good(extra_tools=PIP), "lockfile", lock=None)
        self.assert_error(good(extra_tools=PIP.replace("toolchain/python/builder.lock", "../outside.lock")), "lockfile")
        self.assert_error(good(extra_tools=PIP), "pinned", lock="yamllint>=1.0 \\\n    --hash=sha256:" + GOOD + "\n")
        self.assert_error(good(extra_tools=PIP), "hash", lock="yamllint==1.0\n")
        self.assert_error(good(extra_tools=PIP), "hash", lock="yamllint==1.0 \\\n    --hash=sha256:abc\n")
        self.assert_error(good(extra_tools=PIP), "lockfile", lock="-e git+https://example.invalid/x#egg=x\n")
        self.assert_error(good(extra_tools=PIP), "lockfile", lock="https://example.invalid/x.whl\n")

    def test_toml_syntax_error(self):
        self.assert_error("this is = = not toml", "TOML")

    def test_errors_do_not_echo_values(self):
        marker = "SECRET-MARKER-VALUE"
        errors = check(good(amd64_sha=marker))
        self.assertFalse(any(marker in e for e in errors))


if __name__ == "__main__":
    unittest.main()
