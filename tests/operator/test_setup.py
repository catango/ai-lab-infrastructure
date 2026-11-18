"""scripts/operator/setup (acceptance P-1, P-2): run in a sandbox with stub commands; nothing real is installed or changed."""
import os
import pathlib
import shutil
import stat
import subprocess
import tempfile
import unittest

import helpers

REAL = helpers.OPERATOR_DIR / "setup"
ROOT_USER = os.geteuid() == 0


class Sandbox(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = pathlib.Path(self.tmp.name)
        self.root = base / "repo"
        (self.root / "scripts" / "operator").mkdir(parents=True)
        (self.root / "ansible" / "inventory").mkdir(parents=True)
        shutil.copy(REAL, self.root / "scripts" / "operator" / "setup")
        (self.root / "ansible" / "operator.yml").write_text("---\n")
        self.bin = base / "bin"
        self.bin.mkdir()
        self.log = base / "calls.log"
        self.log.write_text("")
        self.stub("python3", 'echo "python3 $*" >> "$STUB_LOG"; exit "${STUB_RELEASE_RC:-0}"')
        self.stub("sudo", 'echo "sudo $*" >> "$STUB_LOG"; exec "$@"')
        self.stub("apt-get", f'echo "apt-get $*" >> "$STUB_LOG"; if [ "$1" = install ]; then cp "{self.bin}/ansible-playbook.real" "{self.bin}/ansible-playbook"; fi')
        self.write("ansible-playbook.real", 'echo "ansible-playbook $*" >> "$STUB_LOG"; env | grep -E "^ANSIBLE_" | sort >> "$STUB_LOG" || true')
        # Only the basic tools the script and the stubs need are linked in, so that a real ansible-playbook, apt-get, or sudo on the
        # machine running the tests can never be reached.
        for name in ("dirname", "grep", "cat", "env", "sort", "cp", "touch", "sh", "bash"):
            real = shutil.which(name)
            self.assertIsNotNone(real, name)
            os.symlink(real, self.bin / name)
        self.env = {"PATH": str(self.bin), "HOME": str(base), "STUB_LOG": str(self.log)}

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, body):
        path = self.bin / name
        path.write_text(f"#!/bin/sh\n{body}\n")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def stub(self, name, body):
        self.write(name, body)

    def have_ansible(self):
        shutil.copy(self.bin / "ansible-playbook.real", self.bin / "ansible-playbook")

    def setup(self, *args, env=None):
        merged = dict(self.env)
        merged.update(env or {})
        return subprocess.run([str(self.root / "scripts" / "operator" / "setup"), *args], capture_output=True, text=True, env=merged,
                              stdin=subprocess.DEVNULL, timeout=60)

    def calls(self):
        return [line for line in self.log.read_text().splitlines() if not line.startswith("ANSIBLE_")]

    def ansible_env(self):
        return [line for line in self.log.read_text().splitlines() if line.startswith("ANSIBLE_")]


BECOME = [] if ROOT_USER else ["--ask-become-pass"]
SUDO = "" if ROOT_USER else "sudo "


class DryRun(Sandbox):
    def test_the_default_is_a_dry_run_that_checks_the_playbook_in_check_mode(self):
        self.have_ansible()
        result = self.setup()
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls()
        self.assertTrue(calls[0].startswith("python3 -I -B -c"), calls)  # the release check comes first
        playbook = [c for c in calls if c.startswith("ansible-playbook")]
        self.assertEqual(len(playbook), 1)
        self.assertIn("--check --diff", playbook[0])
        self.assertNotIn("operator_apply", playbook[0])
        self.assertEqual("--ask-become-pass" in playbook[0], not ROOT_USER)
        self.assertFalse([c for c in calls if c.startswith(("apt-get", "sudo"))])

    def test_the_explicit_dry_run_flag_is_the_same(self):
        self.have_ansible()
        self.assertEqual(self.setup("--dry-run").returncode, 0)
        self.assertTrue(any("--check" in c for c in self.calls()))

    def test_without_ansible_it_installs_nothing_and_prints_the_apt_command(self):
        result = self.setup()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([c for c in self.calls() if not c.startswith("python3")], [])
        self.assertIn("apt-get install -y ansible-core", result.stdout)

    def test_the_paths_come_from_the_script_location(self):
        self.have_ansible()
        self.setup()
        playbook = next(c for c in self.calls() if c.startswith("ansible-playbook"))
        self.assertIn(str(self.root / "ansible" / "operator.yml"), playbook)
        self.assertIn(str(self.root / "ansible" / "inventory" / "localhost.yml"), playbook)


class Apply(Sandbox):
    def test_apply_runs_the_playbook_with_the_apply_variable(self):
        self.have_ansible()
        result = self.setup("--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        playbook = next(c for c in self.calls() if c.startswith("ansible-playbook"))
        self.assertIn("-e operator_apply=true", playbook)
        self.assertNotIn("--check", playbook)
        self.assertEqual("--ask-become-pass" in playbook, not ROOT_USER)
        self.assertFalse([c for c in self.calls() if c.startswith("apt-get")])

    def test_apply_installs_ansible_core_first_when_it_is_missing(self):
        result = self.setup("--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [c for c in self.calls() if not c.startswith("python3")]
        self.assertEqual([c for c in calls if c.startswith("apt-get")], ["apt-get update -q", "apt-get install -y ansible-core"])
        self.assertTrue(calls[-1].startswith("ansible-playbook"), calls)
        self.assertEqual(sum(1 for c in calls if c.startswith("sudo ")), 0 if ROOT_USER else 2)
        order = [c.split()[0] if not c.startswith("sudo ") else "sudo" for c in calls]
        self.assertLess(max(i for i, c in enumerate(calls) if c.startswith("apt-get")), len(calls) - 1)
        self.assertEqual(order[-1], "ansible-playbook")

    def test_the_environment_cannot_change_the_playbook_or_its_roles(self):
        self.have_ansible()
        hostile = {"ANSIBLE_ROLES_PATH": "/tmp/x", "ANSIBLE_CONFIG": "/tmp/y.cfg", "ANSIBLE_STDOUT_CALLBACK": "z", "ANSIBLE_LIBRARY": "/tmp/m"}
        self.setup("--apply", env=hostile)
        seen = dict(line.split("=", 1) for line in self.ansible_env())
        self.assertNotIn("ANSIBLE_ROLES_PATH", seen)
        self.assertNotIn("ANSIBLE_LIBRARY", seen)
        self.assertNotIn("ANSIBLE_STDOUT_CALLBACK", seen)
        self.assertEqual(seen["ANSIBLE_CONFIG"], str(self.root / "ansible" / "ansible.cfg"))


class Refusals(Sandbox):
    def test_usage_errors_run_nothing(self):
        self.have_ansible()
        for args in (["--dry-run", "--apply"], ["--bogus"], ["apply"], ["--apply=yes"], ["--apply", "extra"], ["-x"], ["--ansible-args", "x"]):
            with self.subTest(args=args):
                result = self.setup(*args)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(self.calls(), [])

    def test_help_exits_cleanly_and_runs_nothing(self):
        result = self.setup("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("--apply", result.stdout)
        self.assertEqual(self.calls(), [])

    def test_outside_a_release_tag_it_stops_before_anything_else(self):
        self.have_ansible()
        for args in ([], ["--apply"]):
            with self.subTest(args=args):
                self.log.write_text("")
                result = self.setup(*args, env={"STUB_RELEASE_RC": "1"})
                self.assertEqual(result.returncode, 1)
                self.assertEqual(len(self.calls()), 1)
                self.assertIn("-c", self.calls()[0])

    def test_the_release_check_uses_the_shared_library(self):
        text = REAL.read_text()
        self.assertIn("require_release_commit", text)
        self.assertIn("python3 -I -B -c", text)


class Script(unittest.TestCase):
    def test_it_is_executable_bash_with_strict_mode(self):
        self.assertTrue(os.access(REAL, os.X_OK))
        lines = REAL.read_text().splitlines()
        self.assertRegex(lines[0], r"^#!.*bash")
        self.assertIn("set -euo pipefail", "\n".join(lines[:15]))

    def test_it_has_no_eval_download_or_command_text_from_input(self):
        text = REAL.read_text()
        for banned in ("eval ", "curl", "wget", "bash -c", "sh -c", "read -p", "$@\"|", "xargs"):
            self.assertNotIn(banned, text)

    def test_sudo_is_used_only_for_the_two_apt_commands(self):
        import re
        uses = [line.strip() for line in REAL.read_text().splitlines() if re.search(r'(^|[^\w-])SUDO\[@\]|(^|[^\w-])sudo\b', line) and not line.strip().startswith("#")]
        for line in uses:
            self.assertTrue("apt-get" in line or "SUDO=" in line or "SUDO[*]" in line, line)


if __name__ == "__main__":
    unittest.main()
