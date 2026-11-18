"""facts, host scope (acceptance F-1). The script is loaded as a module and run with a fake system, a fake runner, and a temporary home."""
import importlib.machinery
import importlib.util
import os
import pathlib
import stat
import tempfile
import unittest

import io
from contextlib import redirect_stderr

import helpers
import fakes
from operator_lib import download, exitcodes, process, profiles, release

SCRIPT = helpers.OPERATOR_DIR / "facts"


def load_facts():
    loader = importlib.machinery.SourceFileLoader("operator_facts_script", str(SCRIPT))
    spec = importlib.util.spec_from_loader("operator_facts_script", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


facts = load_facts()
OK_RELEASE = lambda repo, out=print: release.ReleaseCheck(True, "a" * 40, "v0.1.0")  # noqa: E731


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = pathlib.Path(self.tmp.name)
        self.system = fakes.FakeSystem()
        self.runner = fakes.FakeRunner()
        self.lines = []
        self.downloads = []
        self.environ = {"HOME": str(self.home), "SSH_CLIENT": f"{fakes.ADDRESS} 50000 22"}

    def tearDown(self):
        self.tmp.cleanup()

    def downloader(self, url, **kw):
        self.downloads.append(url)
        return download.Timing(bytes=12_500_000, seconds=1.0, capped=False)

    def run_facts(self, *argv, environ=None, system=None, runner=None):
        self.lines = []
        code = facts.main(list(argv), system=system or self.system, environ=environ if environ is not None else self.environ,
                          out=self.lines.append, require_release=lambda repo, out=print: self.lines.append("release ok"),
                          runner=runner or self.runner, downloader=self.downloader)
        return code

    @property
    def text(self):
        return "\n".join(self.lines)

    def values(self):
        found = {}
        for line in self.lines:
            if ": " in line and not line.startswith(("manual", "would", "==")):
                key, value = line.split(": ", 1)
                found[key] = value
        return found

    def tree(self):
        return sorted(str(p.relative_to(self.home)) for p in self.home.rglob("*"))

    def assertNoCanary(self):
        everything = self.text + "\n".join(self.tree())
        for canary in (fakes.ADDRESS, fakes.ACCOUNT, fakes.OTHER_ACCOUNT, fakes.HOSTNAME, "ssh-ed25519", "BEGIN"):
            self.assertNotIn(canary, everything)


class DryRun(Base):
    def test_a_dry_run_runs_no_check_and_writes_nothing(self):
        self.assertEqual(self.run_facts(), 0)
        self.assertEqual(self.system.reads, [])
        self.assertEqual(self.runner.calls, [])
        self.assertEqual(self.tree(), [])
        self.assertEqual(self.downloads, [])

    def test_the_dry_run_lists_the_checks_and_says_how_to_apply(self):
        self.run_facts()
        self.assertIn("release ok", self.lines[0])
        self.assertTrue(any(line.startswith("would: ") for line in self.lines))
        self.assertIn("--apply", self.text)

    def test_both_flags_and_other_scopes_are_usage_errors(self):
        for argv in (["--dry-run", "--apply"], ["--scope", "oci"], ["--scope", "github"], ["--bogus"], ["--privileged", "x"]):
            with self.subTest(argv=argv), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                self.run_facts(*argv)
            self.assertEqual(caught.exception.code, exitcodes.USAGE)

    def test_the_release_check_runs_first_and_a_refusal_stops_everything(self):
        def refuse(repo, out=print):
            raise SystemExit(exitcodes.FAILED)
        with self.assertRaises(SystemExit) as caught:
            facts.main(["--apply"], system=self.system, environ=self.environ, out=self.lines.append, require_release=refuse,
                       runner=self.runner, downloader=self.downloader)
        self.assertEqual(caught.exception.code, 1)
        self.assertEqual((self.system.reads, self.runner.calls, self.tree()), ([], [], []))

    def test_privileged_and_allowlist_and_bandwidth_dry_runs_only_list(self):
        self.run_facts("--privileged", "--write-allowlist", "--measure-bandwidth")
        self.assertEqual(self.runner.calls, [])
        self.assertEqual(self.downloads, [])
        self.assertEqual(self.tree(), [])
        for word in ("sshd -T", "nft list ruleset", "/etc/sudoers.d", "sudo -n true", "allowlist", "download"):
            self.assertIn(word, self.text)
        self.assertNotIn(fakes.ADDRESS, self.text)


class Apply(Base):
    def test_apply_reports_safe_values(self):
        self.assertEqual(self.run_facts("--apply"), 0)
        v = self.values()
        expected = {"python_version": "3.13", "kernel_version": "6.8", "git_version": "2.43.0", "memory_mb": "983", "swap_mb": "512",
                    "cpu_threads": "2", "disk_gb_total": "50", "disk_gb_free": "30", "ntp_synchronized": "yes", "login_accounts": "2",
                    "sudo_group_members": "2", "listening_tcp_ports": "2", "ssh_listening": "yes", "firewall_ufw_enabled": "yes",
                    "firewall_nftables_enabled": "no", "installed_packages": "7", "home_persists": "unknown", "egress_known": "yes",
                    "egress_stable": "unknown", "egress_distinct": "1"}
        for key, value in expected.items():
            self.assertEqual(v.get(key), value, key)
        self.assertNoCanary()

    def test_only_the_state_file_is_written_and_with_private_modes(self):
        self.run_facts("--apply")
        state_dir = self.home / ".local" / "state" / "operator" / "facts"
        self.assertEqual(self.tree(), [".local", ".local/state", ".local/state/operator", ".local/state/operator/facts",
                                       ".local/state/operator/facts/state.json"])
        self.assertEqual(stat.S_IMODE(os.stat(state_dir).st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(os.stat(state_dir / "state.json").st_mode), 0o600)
        self.assertNotIn(fakes.ADDRESS, (state_dir / "state.json").read_text())

    def test_without_privileged_sudo_is_never_called_and_only_git_runs(self):
        self.run_facts("--apply")
        self.assertEqual([c for c, _ in self.runner.calls], [("git", "--version")])

    def test_only_python_and_git_are_needed(self):
        runner = fakes.FakeRunner(git_version="")
        runner.canned.pop(("git", "--version"))
        self.assertEqual(self.run_facts("--apply", runner=runner), 0)
        self.assertEqual(self.values()["git_present"], "no")

    def test_repeated_runs_make_the_egress_stable_and_a_new_address_does_not(self):
        self.run_facts("--apply")
        self.run_facts("--apply")
        self.assertEqual((self.values()["egress_stable"], self.values()["egress_distinct"], self.values()["runs"]), ("yes", "1", "2"))
        self.run_facts("--apply", environ={**self.environ, "SSH_CLIENT": "198.51.100.9 1 22"})
        self.assertEqual((self.values()["egress_stable"], self.values()["egress_distinct"]), ("no", "2"))
        self.assertNoCanary()
        self.assertNotIn("198.51.100.9", self.text)

    def test_no_ssh_client_means_no_egress_fact(self):
        self.run_facts("--apply", environ={"HOME": str(self.home)})
        self.assertEqual((self.values()["egress_known"], self.values()["egress_stable"], self.values()["egress_distinct"]), ("no", "unknown", "0"))

    def test_a_malformed_ssh_client_is_ignored(self):
        for value in ("", "not-an-address 1 22", "999.1.1.1 1 22", "x" * 500):
            with self.subTest(value=value[:20]):
                self.run_facts("--apply", environ={"HOME": str(self.home), "SSH_CLIENT": value})
                self.assertEqual(self.values()["egress_known"], "no")

    def test_the_home_persists_after_a_restart(self):
        self.run_facts("--apply")
        self.assertEqual(self.values()["home_persists"], "unknown")
        self.run_facts("--apply")
        self.assertEqual(self.values()["home_persists"], "unknown")  # same boot: cannot tell
        self.system.boot_id = "99999999-2222-3333-4444-555555555555"
        self.run_facts("--apply")
        self.assertEqual(self.values()["home_persists"], "yes")

    def test_unreadable_system_files_give_unknown_not_a_crash(self):
        self.assertEqual(self.run_facts("--apply", system=fakes.FakeSystem(files={}, dirs=())), 0)
        self.assertEqual(self.values()["ntp_synchronized"], "unknown")

    def test_a_corrupt_state_file_is_replaced(self):
        self.run_facts("--apply")
        state = self.home / ".local" / "state" / "operator" / "facts" / "state.json"
        state.write_text("{not json")
        self.assertEqual(self.run_facts("--apply"), 0)
        self.assertEqual(self.values()["runs"], "1")

    def test_the_machine_profile_entry_is_valid_and_has_safe_values_only(self):
        self.run_facts("--apply", "--measure-bandwidth")
        start = self.lines.index("== machine profile entry ==")
        block = self.lines[start + 1:]
        end = next(i for i, line in enumerate(block) if line.startswith("=="))
        toml = "\n".join(["[machines.example]"] + block[:end])
        path = self.home / "entry.toml"
        path.write_text(toml)
        entry = profiles.load_profiles(path)["example"]
        self.assertEqual(entry, {"arch": "x86-64", "os": "ubuntu-24.04", "memory_mb": 983, "cpu_threads": 2, "disk_gb": 50, "bandwidth_mbit": 100})
        self.assertNoCanary()

    def test_off_host_facts_are_manual_lines(self):
        self.run_facts("--apply")
        manual = [line for line in self.lines if line.startswith("manual: ")]
        joined = " ".join(manual)
        for topic in ("provider firewall", "SSH path from Z0", "corporate approval"):
            self.assertIn(topic, joined)

    def test_bandwidth_downloads_one_manifest_artifact_once(self):
        self.run_facts("--apply", "--measure-bandwidth")
        self.assertEqual(len(self.downloads), 1)
        self.assertTrue(self.downloads[0].startswith("https://"))
        self.assertEqual(self.values()["bandwidth_mbit"], "100")
        self.run_facts("--apply")
        self.assertNotIn("bandwidth_mbit", self.values())

    def test_a_failed_download_is_reported_as_unknown(self):
        def broken(url, **kw):
            raise download.DownloadError("download failed")
        self.lines = []
        facts.main(["--apply", "--measure-bandwidth"], system=self.system, environ=self.environ, out=self.lines.append,
                   require_release=lambda repo, out=print: None, runner=self.runner, downloader=broken)
        self.assertEqual(self.values()["bandwidth_mbit"], "unknown")


class Allowlist(Base):
    PATH = ".config/operator/ssh-allowlist"

    def test_the_address_goes_to_the_file_and_never_to_the_output(self):
        self.run_facts("--apply", "--write-allowlist")
        path = self.home / self.PATH
        self.assertEqual(path.read_text().split(), [fakes.ADDRESS])
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(os.stat(path.parent).st_mode), 0o700)
        self.assertNotIn(fakes.ADDRESS, self.text)
        self.assertEqual(self.values()["allowlist_entries"], "1")

    def test_a_second_run_does_not_duplicate_and_a_new_address_is_added(self):
        self.run_facts("--apply", "--write-allowlist")
        self.run_facts("--apply", "--write-allowlist")
        self.assertEqual((self.home / self.PATH).read_text().split(), [fakes.ADDRESS])
        self.run_facts("--apply", "--write-allowlist", environ={**self.environ, "SSH_CLIENT": "198.51.100.9 1 22"})
        self.assertEqual(sorted((self.home / self.PATH).read_text().split()), ["192.0.2.77", "198.51.100.9"])

    def test_without_an_address_nothing_is_written_and_the_run_fails(self):
        code = self.run_facts("--apply", "--write-allowlist", environ={"HOME": str(self.home)})
        self.assertEqual(code, exitcodes.FAILED)
        self.assertFalse((self.home / self.PATH).exists())

    def test_the_allowlist_is_not_written_without_the_flag(self):
        self.run_facts("--apply")
        self.assertFalse((self.home / self.PATH).exists())


class Privileged(Base):
    def test_exactly_the_listed_commands_run_and_each_asks_for_the_password(self):
        self.run_facts("--apply", "--privileged")
        self.assertEqual(self.runner.privileged(), [("sudo", "sshd", "-T"), ("sudo", "nft", "list", "ruleset"),
                                                    ("sudo", "find", "/etc/sudoers.d", "-maxdepth", "1", "-type", "f"), ("sudo", "-n", "true")])
        for argv, kw in self.runner.calls:
            if argv[0] == "sudo":
                self.assertTrue(kw.get("interactive") or argv == ("sudo", "-n", "true"), argv)
                self.assertEqual(kw["allow_exact"], facts.ALLOW_EXACT)

    def test_the_results_are_yes_no_and_counts(self):
        self.run_facts("--apply", "--privileged")
        v = self.values()
        expected = {"sshd_password_auth_off": "yes", "sshd_root_login_off": "no", "sshd_pubkey_auth_on": "yes", "sshd_port_count": "1",
                    "nft_tables": "2", "nft_chains": "3", "nft_input_policy_drop": "yes", "sudoers_d_files": "2", "sudo_passwordless": "no"}
        for key, value in expected.items():
            self.assertEqual(v.get(key), value, key)
        self.assertNoCanary()

    def test_a_refused_or_failing_command_gives_unknown(self):
        runner = fakes.FakeRunner(canned={("sudo", "sshd", "-T"): (1, ""), ("sudo", "nft", "list", "ruleset"): (1, "")})
        self.assertEqual(self.run_facts("--apply", "--privileged", runner=runner), 0)
        v = self.values()
        self.assertEqual((v["sshd_password_auth_off"], v["nft_tables"]), ("unknown", "unknown"))

    def test_a_missing_sudo_gives_unknown(self):
        runner = fakes.FakeRunner()
        for key in list(runner.canned):
            if key[0] == "sudo":
                del runner.canned[key]
        self.assertEqual(self.run_facts("--apply", "--privileged", runner=runner), 0)
        self.assertEqual(self.values()["sudo_passwordless"], "unknown")

    def test_passwordless_sudo_is_reported(self):
        runner = fakes.FakeRunner(canned={("sudo", "-n", "true"): (0, "")})
        self.run_facts("--apply", "--privileged", runner=runner)
        self.assertEqual(self.values()["sudo_passwordless"], "yes")

    def test_the_fixed_list_matches_the_design(self):
        self.assertEqual(facts.PRIVILEGED, (("sshd", "-T"), ("nft", "list", "ruleset"), ("find", "/etc/sudoers.d", "-maxdepth", "1", "-type", "f")))
        self.assertEqual(facts.PROBE, ("sudo", "-n", "true"))
        self.assertEqual(len(facts.ALLOW_EXACT), 4)

    def test_every_allowed_tuple_passes_the_process_policy_and_nothing_else_does(self):
        for argv in facts.ALLOW_EXACT:
            process._check(list(argv), process.DEFAULT_ALLOW, facts.ALLOW_EXACT, (), None)
        for argv in (["sudo", "sh"], ["sudo", "-n", "true", "x"], ["sudo", "sshd", "-T", "-f", "x"], ["sudo", "find", "/", "-delete"]):
            with self.assertRaises(process.PolicyViolation):
                process._check(argv, process.DEFAULT_ALLOW, facts.ALLOW_EXACT, (), None)


class Script(unittest.TestCase):
    def test_the_script_is_executable_and_uses_the_shared_library(self):
        self.assertTrue(os.access(SCRIPT, os.X_OK))
        text = SCRIPT.read_text()
        self.assertIn("parse_mode", text)
        self.assertIn("require_release_commit", text)

    def test_the_real_script_refuses_both_flags_without_running_anything(self):
        import subprocess
        result = subprocess.run([str(SCRIPT), "--dry-run", "--apply"], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                                env={"PATH": "/usr/bin:/bin", "HOME": "/nonexistent"})
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
