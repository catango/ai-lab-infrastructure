import os
import pathlib
import stat
import tempfile
import unittest

import helpers  # noqa: F401
from operator_lib import process


class Stubs(unittest.TestCase):
    """Stub commands in a temporary directory that is the only PATH entry."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.bin = pathlib.Path(self.tmp.name)
        self.marker = self.bin / "ran-marker"

    def tearDown(self):
        self.tmp.cleanup()

    def stub(self, name, body):
        path = self.bin / name
        path.write_text(f"#!/bin/sh\n{body}\n")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def run_cmd(self, argv, **kw):
        kw.setdefault("allow", process.DEFAULT_ALLOW)
        kw.setdefault("path", f"{self.bin}:/usr/bin:/bin")
        return process.run(argv, **kw)


class Policy(Stubs):
    def test_commands_outside_the_allowlist_are_refused(self):
        for name in ("ls", "bash", "sh", "sudo", "curl", "python3", "terraform"):
            self.stub(name, f"touch {self.marker}")
        for argv in (["ls"], ["bash", "-c", "x"], ["sudo", "true"], ["curl", "x"], ["python3"], ["terraform", "apply"],
                     ["/usr/bin/git", "status"], ["./git", "status"], [""], []):
            with self.subTest(argv=argv), self.assertRaises(process.PolicyViolation):
                self.run_cmd(argv)
        self.assertFalse(self.marker.exists())

    def test_a_command_string_is_refused(self):
        self.stub("git", f"touch {self.marker}")
        for value in ("git status", "git; rm -rf x"):
            with self.subTest(value=value), self.assertRaises(process.PolicyViolation):
                self.run_cmd(value)
        self.assertFalse(self.marker.exists())

    def test_non_string_and_nul_arguments_are_refused(self):
        self.stub("git", "true")
        for argv in (["git", 1], ["git", None], ["git", "a\0b"]):
            with self.subTest(argv=argv), self.assertRaises(process.PolicyViolation):
                self.run_cmd(argv)

    def test_arguments_are_passed_literally_without_a_shell(self):
        self.stub("git", 'for a in "$@"; do echo "[$a]"; done')
        result = self.run_cmd(["git", "a;b", "$HOME", "`x`", "c d"])
        self.assertEqual(result.stdout.split(), ["[a;b]", "[$HOME]", "[`x`]", "[c", "d]"])

    def test_exact_privileged_commands_are_allowed_only_as_listed(self):
        self.stub("sudo", f'echo "$@"; touch {self.marker}')
        allowed = frozenset({("sudo", "-n", "true"), ("sudo", "sshd", "-T")})
        self.assertEqual(self.run_cmd(["sudo", "-n", "true"], allow_exact=allowed).returncode, 0)
        self.assertEqual(self.run_cmd(["sudo", "sshd", "-T"], allow_exact=allowed).stdout.strip(), "sshd -T")
        self.marker.unlink()
        for argv in (["sudo", "-n", "false"], ["sudo", "sshd", "-T", "-f", "x"], ["sudo", "sh"], ["sudo"], ["sudo", "-n", "true", "x"]):
            with self.subTest(argv=argv), self.assertRaises(process.PolicyViolation):
                self.run_cmd(argv, allow_exact=allowed)
        self.assertFalse(self.marker.exists())


class OciVerbs(Stubs):
    def test_read_verbs_pass(self):
        self.stub("oci", "echo ok")
        for argv in (["oci", "iam", "compartment", "list", "--all"], ["oci", "limits", "resource-availability", "get", "--service-name", "compute"],
                     ["oci", "compute", "instance", "list"], ["oci", "iam", "availability-domain", "inspect"], ["oci", "--version"]):
            with self.subTest(argv=argv):
                self.assertEqual(self.run_cmd(argv).returncode, 0)

    def test_everything_else_is_refused(self):
        self.stub("oci", f"touch {self.marker}")
        for argv in (["oci"], ["oci", "compute", "instance", "terminate", "--instance-id", "x"], ["oci", "compute", "instance", "launch"],
                     ["oci", "iam", "user", "create"], ["oci", "iam", "policy", "update"], ["oci", "network", "vcn", "delete"],
                     ["oci", "compute", "instance", "action", "--action", "STOP"], ["oci", "--profile", "x", "iam", "compartment", "list"],
                     ["oci", "setup", "config"], ["oci", "session", "authenticate"], ["oci", "iam", "compartment", "list-all"],
                     ["oci", "os", "object", "put", "--file", "x"], ["oci", "list"]):
            with self.subTest(argv=argv), self.assertRaises(process.PolicyViolation):
                self.run_cmd(argv)
        self.assertFalse(self.marker.exists())


class Environment(Stubs):
    def test_the_child_gets_a_minimal_environment(self):
        self.stub("git", "env")
        os.environ.update({"GH_TOKEN": helpers.PAT + "PARENT_CANARY_1", "OCI_CLI_KEY_CONTENT": "KEY_CANARY", "AWS_SECRET": "SECRET_CANARY",
                           "SSH_AUTH_SOCK": "/tmp/agent-canary", "SSH_CLIENT": "192.0.2.5 1 22"})
        try:
            out = self.run_cmd(["git", "x"]).stdout
        finally:
            for key in ("GH_TOKEN", "OCI_CLI_KEY_CONTENT", "AWS_SECRET", "SSH_AUTH_SOCK", "SSH_CLIENT"):
                del os.environ[key]
        for canary in ("CANARY", "192.0.2.5", "agent"):
            self.assertNotIn(canary, out)
        keys = {line.split("=", 1)[0] for line in out.splitlines()}
        self.assertTrue(keys <= {"PATH", "LANG", "LC_ALL", "HOME", "PWD", "SHLVL", "_", "OLDPWD"}, keys)

    def test_extra_environment_is_checked(self):
        self.stub("oci", "env")
        out = self.run_cmd(["oci", "iam", "region", "list"], extra_env={"OCI_CLI_AUTH": "instance_principal"}).stdout
        self.assertIn("OCI_CLI_AUTH=instance_principal", out)
        for env in ({"lower": "x"}, {"BAD-KEY": "x"}, {"A": "x\ny"}, {"A": 1}):
            with self.subTest(env=env), self.assertRaises(process.PolicyViolation):
                self.run_cmd(["oci", "iam", "region", "list"], extra_env=env)

    def test_a_secret_never_reaches_argv_or_the_environment(self):
        self.stub("git", f"touch {self.marker}")
        secret = helpers.PAT + "SECRET_VALUE_1234567890"
        with self.assertRaises(process.PolicyViolation):
            self.run_cmd(["git", "clone", f"https://x:{secret}@example.invalid/r"], secrets=[secret])
        with self.assertRaises(process.PolicyViolation):
            self.run_cmd(["git", "x"], secrets=[secret], extra_env={"GIT_TOKEN": secret})
        self.assertFalse(self.marker.exists())

    def test_nothing_is_written_to_the_working_directory(self):
        self.stub("git", "true")
        with tempfile.TemporaryDirectory() as cwd:
            self.run_cmd(["git", "x"], cwd=cwd)
            self.assertEqual(os.listdir(cwd), [])


class Interactive(Stubs):
    def test_an_interactive_command_keeps_the_session_for_a_password_prompt(self):
        self.stub("sudo", 'cut -d" " -f6 /proc/self/stat')
        allowed = frozenset({("sudo", "-n", "true")})
        quiet = self.run_cmd(["sudo", "-n", "true"], allow_exact=allowed)
        loud = self.run_cmd(["sudo", "-n", "true"], allow_exact=allowed, interactive=True)
        self.assertNotEqual(int(quiet.stdout), os.getsid(0))
        self.assertEqual(int(loud.stdout), os.getsid(0))

    def test_interactive_cannot_be_combined_with_input_text(self):
        self.stub("git", "true")
        with self.assertRaises(process.PolicyViolation):
            self.run_cmd(["git", "x"], interactive=True, input_text="x")

    def test_the_policy_still_applies(self):
        self.stub("sudo", f"touch {self.marker}")
        with self.assertRaises(process.PolicyViolation):
            self.run_cmd(["sudo", "sh"], interactive=True)
        self.assertFalse(self.marker.exists())


class Output(Stubs):
    def test_output_is_capped_and_flagged(self):
        self.stub("git", "head -c 5000000 /dev/zero | tr '\\0' 'a'")
        result = self.run_cmd(["git", "x"], max_output=1024)
        self.assertTrue(result.truncated)
        self.assertEqual(len(result.stdout), 1024)

    def test_exit_status_is_returned_not_raised(self):
        self.stub("git", "echo out; echo err >&2; exit 3")
        result = self.run_cmd(["git", "x"])
        self.assertEqual((result.returncode, result.stdout.strip(), result.stderr.strip(), result.truncated), (3, "out", "err", False))

    def test_timeout_raises(self):
        self.stub("git", "sleep 5")
        with self.assertRaises(process.CommandTimeout):
            self.run_cmd(["git", "x"], timeout=0.3)

    def test_stdin_is_closed_by_default(self):
        self.stub("git", "cat; echo done")
        self.assertEqual(self.run_cmd(["git", "x"]).stdout.strip(), "done")

    def test_a_missing_command_is_a_clear_error(self):
        with self.assertRaises(process.CommandMissing):
            self.run_cmd(["git", "x"], path="/nonexistent-directory")


if __name__ == "__main__":
    unittest.main()
