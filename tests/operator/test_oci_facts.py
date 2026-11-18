"""facts, OCI scope (acceptance F-2, G-5, S-6, S-11). The script runs against a recording stub `oci` command that is started through
process.run (so the allowlist, the verb check, the child environment, and the output cap are the real ones)."""
import functools
import importlib.machinery
import importlib.util
import io
import json
import os
import pathlib
import re
import stat
import tempfile
import unittest
from contextlib import redirect_stderr

import helpers
import fakes_oci as oci
from operator_lib import exitcodes, ocifacts, process

SCRIPT = helpers.OPERATOR_DIR / "facts"


def load_facts():
    loader = importlib.machinery.SourceFileLoader("operator_facts_oci_tests", str(SCRIPT))
    spec = importlib.util.spec_from_loader("operator_facts_oci_tests", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


facts = load_facts()
CLOUD_SHELL = ["--scope", "oci", "--oci-auth", "instance_obo_user"]
LINE = re.compile(r"[a-z0-9_]+: (?:yes|no|unknown|[0-9]+|[0-9]+\.[0-9]+\.[0-9]+)")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = pathlib.Path(self.tmp.name)
        self.home = base / "home"
        self.home.mkdir()
        (base / "bin").mkdir()
        self.stub = oci.Stub(base / "bin")
        self.runner = functools.partial(process.run, path=str(base / "bin"))
        self.environ = {"HOME": str(self.home)}
        self.lines = []

    def tearDown(self):
        self.tmp.cleanup()

    def run_facts(self, *argv, environ=None, runner=None, require_release=None):
        self.lines = []
        release = require_release or (lambda repo, out=print: self.lines.append("release ok"))
        return facts.main(list(argv), environ=self.environ if environ is None else environ, out=self.lines.append,
                          require_release=release, runner=runner or self.runner)

    def apply(self, *extra, **kw):
        return self.run_facts("--scope", "oci", "--apply", *extra, **kw)

    @property
    def text(self):
        return "\n".join(self.lines)

    def values(self):
        found = {}
        for line in self.lines:
            if LINE.fullmatch(line):
                key, value = line.split(": ", 1)
                found[key] = value
        return found

    def raw_dir(self):
        return self.home / ".local" / "state" / "operator" / "oci-raw"

    def assertNoCanary(self, text=None):
        everything = self.text if text is None else text
        for canary in oci.CANARIES:
            self.assertNotIn(canary, everything)


class DryRun(Base):
    def test_a_dry_run_runs_nothing_and_writes_nothing(self):
        self.assertEqual(self.run_facts("--scope", "oci"), exitcodes.OK)
        self.assertEqual(self.stub.calls(), [])
        self.assertEqual(sorted(self.home.iterdir()), [])
        self.assertIn("dry run: nothing was checked", self.text)

    def test_the_dry_run_prints_every_command_as_an_argument_list(self):
        self.run_facts("--scope", "oci")
        commands = [line for line in self.lines if line.startswith("would: [")]
        self.assertGreaterEqual(len(commands), 15)
        for line in commands:
            argv = json.loads(line[len("would: "):])
            self.assertEqual(argv[0], "oci")
            self.assertTrue(process.oci_verb_allowed(argv), line)
            if argv != ["oci", "--version"]:
                self.assertEqual(argv[argv.index("--auth") + 1], "instance_principal")

    def test_the_dry_run_uses_placeholders_not_identifiers(self):
        self.run_facts("--scope", "oci")
        self.assertIn("<tenancy>", self.text)
        self.assertIn("<compartment>", self.text)
        self.assertIn("<availability-domain>", self.text)
        self.assertNotIn(helpers.OCID, self.text)

    def test_the_cloud_shell_choice_is_printed_in_every_command(self):
        self.run_facts(*CLOUD_SHELL)
        commands = [line for line in self.lines if line.startswith("would: [")]
        self.assertTrue(commands)
        self.assertTrue(all('"instance_obo_user"' in line for line in commands if "--version" not in line))

    def test_the_dry_run_names_the_forwarded_variables_without_their_values(self):
        self.environ["OCI_CLI_PROFILE"] = "canary-profile"
        self.run_facts(*CLOUD_SHELL)
        self.assertIn("OCI_CLI_CONFIG_FILE", self.text)
        self.assertIn("OCI_CLI_PROFILE", self.text)
        self.assertNotIn("canary-profile", self.text)

    def test_a_dry_run_still_needs_the_release_tag(self):
        def refuse(repo, out=print):
            raise SystemExit(exitcodes.FAILED)

        with self.assertRaises(SystemExit) as caught:
            self.run_facts("--scope", "oci", require_release=refuse)
        self.assertEqual(caught.exception.code, exitcodes.FAILED)
        self.assertEqual(self.stub.calls(), [])


class Usage(Base):
    def usage_error(self, *argv):
        err = io.StringIO()
        with redirect_stderr(err), self.assertRaises(SystemExit) as caught:
            self.run_facts(*argv)
        self.assertEqual(caught.exception.code, exitcodes.USAGE)
        self.assertEqual(self.stub.calls(), [])
        return err.getvalue()

    def test_only_the_two_documented_auth_values_exist(self):
        for value in ("api_key", "security_token", "resource_principal", ""):
            self.usage_error("--scope", "oci", "--oci-auth", value)

    def test_the_auth_choice_belongs_to_the_oci_scope(self):
        self.usage_error("--oci-auth", "instance_principal")
        self.usage_error("--scope", "github", "--owner", "a", "--repo", "b", "--oci-auth", "instance_principal")

    def test_other_scopes_flags_are_refused_with_the_oci_scope(self):
        for extra in (["--privileged"], ["--measure-bandwidth"], ["--write-allowlist"], ["--owner", "x"], ["--repo", "x"], ["--use-token"]):
            self.assertIn("oci", self.usage_error("--scope", "oci", *extra))


class Apply(Base):
    def test_every_call_is_a_read_only_oci_call_with_the_chosen_auth(self):
        self.assertEqual(self.apply(), exitcodes.OK)
        argvs = self.stub.argvs()
        self.assertGreater(len(argvs), 15)
        for argv in argvs:
            self.assertTrue(process.oci_verb_allowed(argv), argv)
            if argv != ["oci", "--version"]:
                self.assertEqual(argv[argv.index("--auth") + 1], "instance_principal")
                self.assertIn("--connection-timeout", argv)
                self.assertIn("--read-timeout", argv)
                self.assertEqual(argv[argv.index("--output") + 1], "json")
        words = {w for argv in argvs for w in argv}
        for write in ("create", "update", "delete", "terminate", "launch", "change-compartment", "structured-search"):
            self.assertNotIn(write, words)

    def test_calls_are_sequential_and_bounded(self):
        self.apply()
        self.assertLessEqual(len(self.stub.calls()), ocifacts.MAX_CALLS)
        self.assertTrue(all("--limit" in a or "--version" in a or "availability-domain" in a or "resource-availability" in a
                            for a in (c["argv"] for c in self.stub.calls())))

    def test_the_default_scenario_gives_these_facts(self):
        self.assertEqual(self.apply(), exitcodes.OK)
        found = self.values()
        expected = {
            "oci_cli_version": "3.96.3", "compartments_total": "2", "compartments_readable": "2", "compartments_unreadable": "0",
            "compartments_truncated": "no", "availability_domains": "3",
            "a1_ocpu_limit_per_ad": "16", "a1_ocpu_used": "2", "a1_ocpu_available_best_ad": "16",
            "a1_memory_gb_limit_per_ad": "96", "a1_memory_gb_used": "12", "a1_memory_gb_available_best_ad": "96",
            "micro_core_limit_per_ad": "2", "micro_core_used": "1", "micro_core_available_best_ad": "2", "a1_over_free_allowance": "no",
            "instances_total": "2", "instances_a1": "1", "instances_micro": "1", "instances_other": "0",
            "a1_ocpu_in_instances": "2", "a1_memory_gb_in_instances": "12",
            "block_volumes": "1", "boot_volumes": "2", "block_storage_gb_total": "144", "block_storage_over_free_allowance": "no",
            "volume_backups": "2", "volume_backups_over_free_allowance": "no",
            "public_ip_ephemeral": "1", "public_ip_reserved": "2", "public_ip_reserved_assigned": "1", "public_ip_reserved_unassigned": "1",
            "alarms": "3", "alarms_enabled": "2", "absence_alarms": "1", "instances_with_absence_alarm": "1", "instances_without_absence_alarm": "1",
            "topics": "1", "subscriptions": "2", "subscriptions_active": "1", "subscriptions_pending": "1", "subscriptions_email": "2",
            "calls_denied": "0", "calls_failed": "0", "raw_saved": "yes", "tenancy_resolved": "yes",
        }
        for key, value in expected.items():
            self.assertEqual(found.get(key), value, key)

    def test_the_output_is_counts_and_yes_no_only(self):
        self.apply()
        body = [line for line in self.lines if line.startswith(("a1_", "instances_", "public_ip", "alarms", "topics"))]
        self.assertTrue(body)
        start, end = self.lines.index("== facts (oci) =="), self.lines.index("== manual (off-host) ==")
        facts_lines = self.lines[start + 1:end]
        self.assertTrue(all(LINE.fullmatch(line) for line in facts_lines), [l for l in facts_lines if not LINE.fullmatch(l)])
        self.assertNoCanary()
        self.assertNotIn("ocid", self.text.lower())

    def test_raw_output_goes_only_to_a_private_directory(self):
        self.apply()
        raw = self.raw_dir()
        self.assertEqual(stat.S_IMODE(os.stat(raw).st_mode), 0o700)
        files = sorted(raw.iterdir())
        self.assertGreater(len(files), 15)
        self.assertTrue(all(stat.S_IMODE(os.stat(p).st_mode) == 0o600 for p in files))
        joined = "".join(p.read_text() for p in files)
        self.assertIn(oci.TENANCY, joined)
        self.assertNoCanary()
        outside = [p for p in self.home.rglob("*") if p.is_file() and raw not in p.parents]
        self.assertEqual(outside, [])

    def test_a_second_run_gives_the_same_facts_and_the_same_files(self):
        self.apply()
        first, names = self.values(), sorted(p.name for p in self.raw_dir().iterdir())
        self.apply()
        self.assertEqual(self.values(), first)
        self.assertEqual(sorted(p.name for p in self.raw_dir().iterdir()), names)

    def test_the_raw_directory_is_cleaned_to_its_cap(self):
        raw = self.raw_dir()
        raw.mkdir(parents=True, mode=0o700)
        for number in range(5):
            (raw / f"old-{number}.json").write_bytes(b"x" * 1000)
        ocifacts_cap = ocifacts.RAW_CAP
        try:
            ocifacts.RAW_CAP = 4000
            self.apply()
        finally:
            ocifacts.RAW_CAP = ocifacts_cap
        self.assertLessEqual(sum(p.stat().st_size for p in raw.iterdir()), 4000)

    def test_camel_case_keys_are_understood_too(self):
        responses = oci.default_responses()
        responses["instances"] = oci.entry(["compute", "instance", "list", oci.LAB], [
            {"id": oci.INST_A1, "shape": "VM.Standard.A1.Flex", "lifecycleState": "RUNNING", "shapeConfig": {"ocpus": 2, "memoryInGBs": 12}}])
        self.stub.set(responses)
        self.apply()
        self.assertEqual(self.values()["instances_a1"], "1")
        self.assertEqual(self.values()["a1_memory_gb_in_instances"], "12")


class Unknowns(Base):
    def test_a_denied_limits_call_makes_only_those_facts_unknown(self):
        responses = oci.default_responses()
        responses["value-standard-a1-core-count"] = dict(oci.DENIED, match=["limits", "value", "list", "standard-a1-core-count"])
        self.stub.set(responses)
        self.assertEqual(self.apply(), exitcodes.OK)
        found = self.values()
        for key in ("a1_ocpu_limit_per_ad", "a1_ocpu_used", "a1_ocpu_available_best_ad"):
            self.assertEqual(found[key], "unknown")
        self.assertEqual(found["a1_memory_gb_used"], "12")
        self.assertEqual(found["instances_total"], "2")
        self.assertEqual(found["a1_over_free_allowance"], "unknown")
        self.assertEqual(found["calls_denied"], "1")

    def test_over_the_free_allowance_is_yes_even_when_the_other_value_is_unknown(self):
        responses = oci.default_responses()
        for ad, used in zip(oci.ADS, (3, 0, 0)):
            responses[f"avail-standard-a1-core-count-{ad}"] = oci.entry(["limits", "resource-availability", "get", "standard-a1-core-count", ad], {"available": 13, "used": used})
        responses["value-standard-a1-memory-count"] = dict(oci.DENIED, match=["limits", "value", "list", "standard-a1-memory-count"])
        self.stub.set(responses)
        self.apply()
        self.assertEqual(self.values()["a1_over_free_allowance"], "yes")

    def test_an_unreadable_compartment_is_skipped_and_counted(self):
        responses = oci.default_responses()
        responses["instances"] = dict(oci.DENIED, match=["compute", "instance", "list", oci.LAB])
        self.stub.set(responses)
        self.apply()
        found = self.values()
        self.assertEqual((found["compartments_readable"], found["compartments_unreadable"]), ("1", "1"))
        self.assertEqual(found["instances_total"], "0")
        self.assertEqual(found["block_volumes"], "0")
        self.assertFalse(any(oci.LAB in " ".join(a) and "volume" in " ".join(a) for a in self.stub.argvs()), "no further call for an unreadable compartment")

    def test_when_no_compartment_is_readable_the_resource_facts_are_unknown(self):
        responses = oci.default_responses()
        for key in ("instances", "instances-any"):
            responses[key] = dict(oci.DENIED, match=["compute", "instance", "list"])
        self.stub.set(responses)
        self.apply()
        found = self.values()
        for key in ("instances_total", "block_storage_gb_total", "alarms", "public_ip_ephemeral", "instances_without_absence_alarm"):
            self.assertEqual(found[key], "unknown", key)
        self.assertEqual(found["a1_ocpu_used"], "2")

    def test_a_listing_with_another_page_is_unknown_not_a_wrong_count(self):
        responses = oci.default_responses()
        responses["topics"] = {"match": ["ons", "topic", "list", oci.LAB], "out": {"data": [{"lifecycle-state": "ACTIVE"}], "opc-next-page": "token"}}
        self.stub.set(responses)
        self.apply()
        self.assertEqual(self.values()["topics"], "unknown")
        self.assertEqual(self.values()["subscriptions"], "2")

    def test_a_full_page_is_unknown_even_without_a_paging_key(self):
        responses = oci.default_responses()
        responses["topics"] = oci.entry(["ons", "topic", "list", oci.LAB], [{"lifecycle-state": "ACTIVE"}] * int(ocifacts.PAGE))
        self.stub.set(responses)
        self.apply()
        self.assertEqual(self.values()["topics"], "unknown")

    def test_output_that_is_not_json_is_a_failed_call(self):
        responses = oci.default_responses()
        responses["volumes"] = {"match": ["bv", "volume", "list", oci.LAB], "raw": "not json"}
        self.stub.set(responses)
        self.apply()
        self.assertEqual(self.values()["block_volumes"], "unknown")
        self.assertEqual(self.values()["block_storage_gb_total"], "unknown")
        self.assertEqual(self.values()["calls_failed"], "1")

    def test_a_response_over_the_output_cap_is_unknown(self):
        responses = oci.default_responses()
        responses["alarms"] = {"match": ["monitoring", "alarm", "list", oci.LAB], "big": 5000}
        self.stub.set(responses)
        cap = ocifacts.MAX_OUTPUT
        try:
            ocifacts.MAX_OUTPUT = 1000
            self.apply()
        finally:
            ocifacts.MAX_OUTPUT = cap
        self.assertEqual(self.values()["alarms"], "unknown")
        self.assertEqual(self.values()["instances_total"], "2")

    def test_a_call_over_its_timeout_is_unknown_and_does_not_hang(self):
        responses = oci.default_responses()
        responses["topics"] = dict(oci.entry(["ons", "topic", "list", oci.LAB]), sleep=5)
        self.stub.set(responses)
        timeout = ocifacts.CALL_TIMEOUT
        try:
            ocifacts.CALL_TIMEOUT = 1
            self.apply()
        finally:
            ocifacts.CALL_TIMEOUT = timeout
        self.assertEqual(self.values()["topics"], "unknown")
        self.assertEqual(self.values()["calls_failed"], "1")

    def test_the_total_time_is_bounded(self):
        ticks = iter(range(0, 10_000, 400))
        client_clock = ocifacts.CLOCK
        try:
            ocifacts.CLOCK = lambda: next(ticks)
            self.assertEqual(self.apply(), exitcodes.OK)
        finally:
            ocifacts.CLOCK = client_clock
        self.assertLess(len(self.stub.calls()), 10)
        self.assertEqual(self.values()["alarms"], "unknown")

    def test_a_missing_tenancy_stops_the_run(self):
        responses = oci.default_responses()
        responses["compartments"] = oci.entry(["iam", "compartment", "list"], [oci.compartment(oci.LAB, "not-an-id")])
        self.stub.set(responses)
        self.assertEqual(self.apply(), exitcodes.FAILED)
        self.assertEqual(self.values()["tenancy_resolved"], "no")
        self.assertFalse(any("limits" in a for a in self.stub.argvs()))

    def test_the_tenancy_can_come_from_the_parent_of_a_top_level_compartment(self):
        responses = oci.default_responses()
        responses["compartments"] = oci.entry(["iam", "compartment", "list"], [oci.compartment(oci.LAB, oci.TENANCY)])
        self.stub.set(responses)
        self.assertEqual(self.apply(), exitcodes.OK)
        self.assertEqual(self.values()["compartments_total"], "2")

    def test_a_missing_oci_command_is_a_skip(self):
        self.assertEqual(self.apply(runner=functools.partial(process.run, path=self.tmp.name)), exitcodes.SKIPPED)
        self.assertIn("skipped", self.text)

    def test_many_compartments_are_capped(self):
        responses = oci.default_responses()
        many = [oci.compartment(oci.TENANCY, None)] + [oci.compartment(oci.ident("compartment", f"c{n}"), oci.TENANCY) for n in range(30)]
        responses["compartments"] = oci.entry(["iam", "compartment", "list"], many)
        self.stub.set(responses)
        self.apply()
        found = self.values()
        self.assertEqual(found["compartments_truncated"], "yes")
        self.assertEqual(found["compartments_total"], "31")
        self.assertEqual(int(found["compartments_readable"]) + int(found["compartments_unreadable"]), ocifacts.MAX_COMPARTMENTS)
        self.assertLessEqual(len(self.stub.calls()), ocifacts.MAX_CALLS)


class Credentials(Base):
    SECRETS = {"OCI_CLI_KEY_CONTENT": "canarykey", "OCI_CLI_USER": "canaryuser", "OCI_CLI_FINGERPRINT": "canaryprint",
               "OCI_CLI_SECURITY_TOKEN_FILE": "/canary/token", "OCI_CLI_TENANCY": "canarytenancyvalue", "AWS_SECRET": "canaryaws"}

    def child_environments(self):
        return [call["env"] for call in self.stub.calls()]

    def test_no_credential_variable_reaches_a_child_in_either_auth_mode(self):
        self.environ.update(self.SECRETS)
        self.environ.update({"OCI_CLI_CONFIG_FILE": "/etc/oci/config", "OCI_CLI_PROFILE": "uk-london-1"})
        for argv in (["--scope", "oci", "--apply"], [*CLOUD_SHELL, "--apply"]):
            self.run_facts(*argv)
        self.assertTrue(self.stub.calls())
        for call in self.stub.calls():
            for name, value in self.SECRETS.items():
                self.assertNotIn(name, call["env"])
                self.assertFalse([v for v in call["env"].values() if value in v])
                self.assertFalse([a for a in call["argv"] if value in a])

    def test_the_instance_principal_mode_forwards_nothing(self):
        self.environ.update({"OCI_CLI_CONFIG_FILE": "/etc/oci/config", "OCI_CLI_PROFILE": "uk-london-1", "OCI_CLI_AUTH": "api_key"})
        self.apply()
        for env in self.child_environments():
            self.assertFalse([k for k in env if k.startswith("OCI_")])

    def test_the_cloud_shell_mode_forwards_only_the_config_path_and_the_profile(self):
        self.environ.update({"OCI_CLI_CONFIG_FILE": "/etc/oci/config", "OCI_CLI_PROFILE": "uk-london-1", "OCI_CLI_AUTH": "api_key", "OCI_CLI_REGION": "x-y-1"})
        self.run_facts(*CLOUD_SHELL, "--apply")
        for env in self.child_environments():
            self.assertEqual(sorted(k for k in env if k.startswith("OCI_")), ["OCI_CLI_CONFIG_FILE", "OCI_CLI_PROFILE"])
            self.assertEqual(env["OCI_CLI_CONFIG_FILE"], "/etc/oci/config")
        for argv in self.stub.argvs():
            if argv != ["oci", "--version"]:
                self.assertEqual(argv[argv.index("--auth") + 1], "instance_obo_user")

    def test_a_forwarded_value_that_is_not_plain_is_refused(self):
        for name, value in (("OCI_CLI_CONFIG_FILE", "relative/config"), ("OCI_CLI_CONFIG_FILE", "/etc/oci/co nfig"), ("OCI_CLI_PROFILE", "bad profile!"),
                            ("OCI_CLI_PROFILE", "x" * 100), ("OCI_CLI_CONFIG_FILE", "/etc/oci/config\nOCI_X=1")):
            self.environ.update({"OCI_CLI_CONFIG_FILE": "/etc/oci/config", "OCI_CLI_PROFILE": "uk-london-1"})
            self.environ[name] = value
            self.assertEqual(self.run_facts(*CLOUD_SHELL, "--apply"), exitcodes.FAILED)
            self.assertIn("refused", self.text)
        self.assertEqual(self.stub.calls(), [])

    def test_an_unset_cloud_shell_variable_is_simply_not_forwarded(self):
        self.assertEqual(self.run_facts(*CLOUD_SHELL, "--apply"), exitcodes.OK)
        for env in self.child_environments():
            self.assertFalse([k for k in env if k.startswith("OCI_")])

    def test_the_process_runner_refuses_a_write_verb_before_starting_anything(self):
        with self.assertRaises(process.PolicyViolation):
            self.runner(["oci", "compute", "instance", "terminate", "--instance-id", "x"])
        with self.assertRaises(process.PolicyViolation):
            self.runner(["oci", "search", "resource", "structured-search", "--query-text", "x"])
        self.assertEqual(self.stub.calls(), [])

    def test_the_script_has_no_credential_prompt_or_token_option(self):
        text = SCRIPT.read_text()
        module = (helpers.ROOT / "scripts" / "operator" / "lib" / "operator_lib" / "ocifacts.py").read_text()
        for word in ("getpass", "api_key", "security_token", "key_file", "fingerprint", "--config-file", "--profile"):
            self.assertNotIn(word, module)
        self.assertNotIn("getpass(", text.split("def run_oci")[1].split("def main")[0])


if __name__ == "__main__":
    unittest.main()
