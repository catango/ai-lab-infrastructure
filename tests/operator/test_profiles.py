import pathlib
import tempfile
import unittest

import helpers
from operator_lib import profiles

GOOD = """
[machines.alpha]
arch = "x86-64"
os = "ubuntu-24.04-minimal"
memory_mb = 2048
cpu_threads = 2

[machines.beta]
arch = "x86-64"
os = "ubuntu-24.04-minimal"
memory_mb = 1024
cpu_threads = 1
disk_gb = 47
"""


def load(text):
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "profiles.toml"
        path.write_text(text)
        return profiles.load_profiles(path)


class Profiles(unittest.TestCase):
    def test_the_repository_file_is_valid_and_describes_both_machines(self):
        data = profiles.load_profiles(helpers.PROFILES)
        self.assertEqual(set(data), {"platform_operator", "lab_operator"})
        for entry in data.values():
            self.assertEqual(entry["arch"], "x86-64")
            self.assertTrue(entry["os"].startswith("ubuntu-24.04"))

    def test_the_lab_operator_memory_is_the_design_input(self):
        self.assertEqual(profiles.load_profiles(helpers.PROFILES)["lab_operator"]["memory_mb"], 1024)

    def test_strictest_takes_the_smallest_limits(self):
        strictest = profiles.strictest(load(GOOD))
        self.assertEqual((strictest["memory_mb"], strictest["cpu_threads"]), (1024, 1))

    def test_strictest_ignores_machines_without_a_value(self):
        data = load(GOOD.replace("memory_mb = 1024\n", ""))
        self.assertEqual(profiles.strictest(data)["memory_mb"], 2048)

    def test_strictest_without_any_value_is_an_error(self):
        with self.assertRaises(profiles.ProfileError):
            profiles.strictest({"a": {"arch": "x86-64"}})

    def test_unknown_keys_are_refused(self):
        for extra in ('hostname = "x"', 'address = "x"', "owner = 1"):
            with self.subTest(extra=extra), self.assertRaises(profiles.ProfileError):
                load(GOOD + extra + "\n")

    def test_identifiers_in_values_are_refused(self):
        for value in ("192.0.2.1", "2001:db8::1", "a" + helpers.AT + "example.org", helpers.OCID + ".instance.oc1..aaaabbbbccccdddd", "host-01.example.org"):
            with self.subTest(value=value), self.assertRaises(profiles.ProfileError):
                load(GOOD.replace('os = "ubuntu-24.04-minimal"', f'os = "{value}"', 1))

    def test_wrong_types_and_ranges_are_refused(self):
        for old, new in (("memory_mb = 2048", 'memory_mb = "2048"'), ("memory_mb = 2048", "memory_mb = 0"), ("memory_mb = 2048", "memory_mb = -1"),
                         ("cpu_threads = 2", "cpu_threads = 1.5"), ("cpu_threads = 2", "cpu_threads = true"), ("memory_mb = 2048", "memory_mb = 99999999")):
            with self.subTest(new=new), self.assertRaises(profiles.ProfileError):
                load(GOOD.replace(old, new, 1))

    def test_bad_structure_is_refused(self):
        for text in ("", "machines = 1", "[machines]\n", "[machines.a]\n[other]\nx = 1", "not toml ["):
            with self.subTest(text=text), self.assertRaises(profiles.ProfileError):
                load(text)

    def test_a_missing_file_is_an_error(self):
        with self.assertRaises(profiles.ProfileError):
            profiles.load_profiles("/nonexistent/profiles.toml")


if __name__ == "__main__":
    unittest.main()
