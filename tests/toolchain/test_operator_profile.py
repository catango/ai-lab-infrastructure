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

    def test_the_message_names_all_three(self):
        text = good().replace('profiles = ["builder", "lab"]', 'profiles = ["prod"]')
        self.assertIn("builder, lab, operator", " ".join(self.errors(text)))

    def test_operator_alone_and_with_builder_pass(self):
        for value in ('["operator"]', '["builder", "operator"]', '["builder", "lab", "operator"]'):
            with self.subTest(value=value):
                self.assertEqual(self.errors(good().replace('profiles = ["builder", "lab"]', f"profiles = {value}")), [])


class RealManifest(unittest.TestCase):
    def test_the_operator_apt_packages_are_exactly_the_fixed_list(self):
        done = engine("list", "--profile", "operator", "--source", "apt", "--format", "json")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual({item["package"] for item in json.loads(done.stdout)}, OPERATOR_APT)

    def test_the_operator_profile_has_no_downloads_yet(self):
        done = engine("list", "--profile", "operator", "--source", "download", "--format", "json")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout), [])

    def test_the_builder_profile_is_unchanged(self):
        done = engine("list", "--profile", "builder", "--source", "apt", "--format", "json")
        names = {item["package"] for item in json.loads(done.stdout)}
        self.assertTrue({"python3", "git", "curl", "tmux", "jq", "ansible-core"} <= names)
        self.assertFalse(names & {"nftables", "openssh-server", "sudo", "unattended-upgrades", "systemd-timesyncd"})

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
