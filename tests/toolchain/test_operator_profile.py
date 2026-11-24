"""The operator profile in the manifest (ADR-005 decision 10, CR-18): allowed profile name and the apt membership."""
import json
import subprocess
import sys
import unittest

import helpers
from helpers import ROOT
from test_manifest import check, good
from toolchain_engine import manifest

OPERATOR_APT = {"python3", "python3-apt", "python3-venv", "ansible-core", "git", "ca-certificates", "nftables", "openssh-server", "sudo",
                "unattended-upgrades", "systemd-timesyncd"}


def engine(*argv):
    return subprocess.run([sys.executable, "-I", "-B", str(ROOT / "scripts" / "toolchain"), *argv], capture_output=True, text=True, check=False)


class ProfileName(unittest.TestCase):
    def errors(self, text):
        return check(text)

    def test_operator_is_an_allowed_profile_name(self):
        self.assertEqual(manifest.PROFILES, ("builder", "lab", "operator"))

    def test_the_message_names_the_profiles_and_the_alias(self):
        text = good().replace('profiles = ["lab"]', 'profiles = ["prod"]')
        self.assertIn("lab, operator (builder is an alias of lab)", " ".join(self.errors(text)))

    def test_operator_alone_and_with_lab_pass(self):
        for value in ('["operator"]', '["lab", "operator"]', '["builder", "operator"]'):
            with self.subTest(value=value):
                self.assertEqual(self.errors(good().replace('profiles = ["lab"]', f"profiles = {value}")), [])


class RealManifest(unittest.TestCase):
    def test_the_operator_apt_packages_are_exactly_the_fixed_list(self):
        done = engine("list", "--profile", "operator", "--source", "apt", "--format", "json")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual({item["package"] for item in json.loads(done.stdout)}, OPERATOR_APT)

    def test_the_operator_profile_has_no_downloads_yet(self):
        done = engine("list", "--profile", "operator", "--source", "download", "--format", "json")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout), [])

    def test_the_lab_profile_is_unchanged_and_builder_lists_the_same_tools(self):
        done = engine("list", "--profile", "lab", "--source", "apt", "--format", "json")
        names = {item["package"] for item in json.loads(done.stdout)}
        self.assertTrue({"python3", "git", "curl", "tmux", "jq", "ansible-core"} <= names)
        self.assertFalse(names & {"nftables", "openssh-server", "sudo", "unattended-upgrades", "systemd-timesyncd"})
        alias = engine("list", "--profile", "builder", "--source", "apt", "--format", "json")
        self.assertEqual(alias.returncode, 0, alias.stderr)
        self.assertEqual(alias.stdout, done.stdout)

    def test_builder_alias_selects_every_lab_tool_of_the_real_manifest(self):
        lab = engine("list", "--profile", "lab", "--format", "json")
        builder = engine("list", "--profile", "builder", "--format", "json")
        self.assertEqual((lab.returncode, builder.returncode), (0, 0), lab.stderr + builder.stderr)
        self.assertGreater(len(json.loads(lab.stdout)), 5)
        self.assertEqual(builder.stdout, lab.stdout)

    def test_every_operator_tool_has_a_version_minimum_and_a_smoke_command(self):
        import tomllib
        raw = tomllib.loads((ROOT / "toolchain" / "manifest.toml").read_text())["tools"]
        done = engine("list", "--profile", "operator", "--source", "apt", "--format", "json")
        for item in json.loads(done.stdout):
            with self.subTest(package=item["package"]):
                self.assertTrue(item.get("version_min"))
                self.assertTrue(raw[item["name"]].get("smoke"))

    def test_the_manifest_check_passes(self):
        self.assertEqual(engine("check").returncode, 0)


if __name__ == "__main__":
    unittest.main()
