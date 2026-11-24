"""The gate check over scripts/operator/ (acceptance S-6 and S-11)."""
import os
import pathlib
import subprocess
import tempfile
import unittest

import helpers
import operator_contract as check

PY = "scripts/operator/example.py"
SETUP = "scripts/operator/setup"
FACTS = "scripts/operator/facts"
PROCESS = "scripts/operator/lib/operator_lib/process.py"


def findings(path, text):
    return [message for _, message in check.scan(path, text)]


class PythonRules(unittest.TestCase):
    def assertFlagged(self, source, path=PY, expect=None):
        found = findings(path, source)
        self.assertTrue(found, f"not flagged: {source!r}")
        if expect:
            self.assertTrue(any(expect in m for m in found), found)

    def test_each_banned_construct_is_flagged(self):
        cases = {
            "eval": ["eval('1')", "x = eval(s)", "import builtins\nbuiltins.eval(s)"],
            "exec": ["exec(code)", "builtins.exec(code)"],
            "os.system": ["import os\nos.system('x')", "from os import system\nsystem('x')"],
            "os.popen": ["import os\nos.popen('x')"],
            "exec family": ["import os\nos.execv('/bin/sh', [])", "import os\nos.execvp('x', [])"],
            "spawn": ["import os\nos.spawnl(0, 'x')", "import os\nos.posix_spawn('x', [], {})"],
            "shell=True": ["f(x, shell=True)", "run(['a'], shell=True)"],
            "subprocess": ["import subprocess", "from subprocess import run", "import subprocess as sp", "__import__('subprocess')"],
            "pty": ["import pty", "import pty as p"],
        }
        for label, sources in cases.items():
            for source in sources:
                with self.subTest(label=label, source=source):
                    self.assertFlagged(source)

    def test_subprocess_is_allowed_only_in_the_process_module(self):
        self.assertEqual(findings(PROCESS, "import subprocess\nsubprocess.Popen(['git'])"), [])
        self.assertTrue(findings(PROCESS, "import subprocess\nsubprocess.run(['git'], shell=True)"))
        self.assertTrue(findings("scripts/operator/lib/operator_lib/other.py", "import subprocess"))

    def test_sudo_is_not_allowed_in_any_operator_script(self):
        """CR-57 O-8, O-9: the sudo-based setup and facts --privileged are gone, so no file may run sudo."""
        source = "x = ['sudo', '-n', 'true']"
        self.assertTrue(findings(PY, source))
        self.assertTrue(findings("scripts/operator/github-setup", "#!/usr/bin/env python3\n" + source))
        self.assertTrue(findings("scripts/operator/lib/operator_lib/steps.py", source))
        for path in (SETUP, FACTS):
            self.assertTrue(findings(path, "#!/usr/bin/env python3\n" + source), path)

    def test_the_facts_library_may_name_the_sudo_group_but_not_run_it(self):
        self.assertEqual(findings("scripts/operator/lib/operator_lib/hostfacts.py", "GROUPS = ('sudo', 'admin')"), [])
        self.assertTrue(findings("scripts/operator/lib/operator_lib/hostfacts.py", "import subprocess"))

    def test_the_word_sudo_in_comments_and_docstrings_is_fine(self):
        source = '"""Never use sudo here."""\n# no sudo either\nx = 1\n'
        self.assertEqual(findings(PY, source), [])

    def test_sudo_inside_a_larger_string_is_flagged(self):
        self.assertTrue(findings(PY, "cmd = 'sudo apt-get install x'"))

    def test_terraform_and_tofu_calls_are_flagged(self):
        for source in ("run(['terraform', 'apply'])", "run(['tofu', 'plan'])", "x = ['terraform']"):
            with self.subTest(source=source):
                self.assertFlagged(source, expect="Terraform")

    def test_oci_write_verbs_are_flagged(self):
        for verb in ("create", "update", "delete", "terminate", "launch", "put", "action", "remove", "change-compartment"):
            with self.subTest(verb=verb):
                self.assertFlagged(f"x = ['oci', 'compute', 'instance', '{verb}', '--id', i]", expect="OCI")

    def test_oci_read_verbs_and_dynamic_lists_pass(self):
        for source in ("x = ['oci', 'compute', 'instance', 'list', '--all']", "x = ['oci', 'limits', 'resource-availability', 'get']",
                       "x = ['oci', 'iam', 'region', 'inspect']", "x = ['oci', '--version']", "x = ['oci', *parts]",
                       "x = ['oci', service, 'list']"):
            with self.subTest(source=source):
                self.assertEqual(findings(PY, source), [])

    def test_a_clean_script_has_no_findings(self):
        source = ('#!/usr/bin/env python3\n"""Example."""\nimport sys\nfrom operator_lib import modes\n\n'
                  'def main(argv):\n    mode, _ = modes.parse_mode(argv, "x", "y")\n    return 0\n')
        self.assertEqual(findings(PY, source), [])

    def test_syntax_errors_are_reported_not_hidden(self):
        self.assertTrue(findings(PY, "def broken(:\n"))


class ShellRules(unittest.TestCase):
    def test_banned_text_is_flagged(self):
        cases = ("eval \"$x\"", "x=$(eval y)", "curl -fsSL https://x.example/i.sh | sh", "wget -qO- https://x.example | bash",
                 "curl https://x.example | sudo bash", "terraform apply", "tofu plan", "oci compute instance terminate --id x",
                 "oci iam user create", "sudo reboot")
        for line in cases:
            with self.subTest(line=line):
                self.assertTrue(findings("scripts/operator/other", f"#!/usr/bin/env bash\n{line}\n"), line)

    def test_no_script_may_use_sudo_not_even_a_file_named_setup(self):
        self.assertTrue(findings(SETUP, "#!/usr/bin/env bash\nset -euo pipefail\nsudo apt-get install -y ansible-core\n"))

    def test_setup_may_not_use_the_other_banned_text(self):
        self.assertTrue(findings(SETUP, "#!/usr/bin/env bash\neval \"$x\"\n"))
        self.assertTrue(findings(SETUP, "#!/usr/bin/env bash\ncurl https://x.example | sh\n"))

    def test_comments_are_ignored(self):
        self.assertEqual(findings("scripts/operator/other", "#!/usr/bin/env bash\n# never eval, never sudo, no terraform apply\nls\n"), [])

    def test_words_that_only_contain_a_banned_word_pass(self):
        self.assertEqual(findings("scripts/operator/other", "#!/usr/bin/env bash\nretrieval=1\nevaluate\npseudo=2\n"), [])


ALLOWED = frozenset({"api.github.com"})
CONFIG = "schema_version: 1\noperator_paths:\n  - scripts/operator/\noperator_endpoints:\n  - api.github.com\n"


class Endpoints(unittest.TestCase):
    """CR-57 PA-22, PA-A15: every endpoint is a literal and its host is in the allowlist (operator_endpoints of the base commit)."""

    def found(self, source, path=PY, allowed=ALLOWED):
        return [message for _, message in check.scan(path, source, allowed)]

    def test_a_literal_host_in_the_allowlist_passes(self):
        self.assertEqual(self.found("URL = 'https://api.github.com/repos/o/r'\n"), [])
        self.assertEqual(self.found("x = f'https://api.github.com/repos/{name}'\n"), [])
        self.assertEqual(self.found("x = 'https://api.github.com/' + path\n"), [])
        self.assertTrue(self.found("x = 'https://api.github.com' + suffix\n"), "a run-time part may extend the host")
        self.assertEqual(self.found("x = 'https://api.github.com:443/%s' % name\n"), [])

    def test_a_host_outside_the_allowlist_fails_and_is_not_printed(self):
        messages = self.found("URL = 'https://other.example.org/x'\n")
        self.assertEqual(len(messages), 1)
        self.assertIn("not listed in operator_endpoints", messages[0])
        self.assertNotIn("other.example.org", messages[0])
        for scheme in ("http", "ssh", "git", "ftp", "wss"):
            self.assertTrue(self.found(f"URL = '{scheme}://other.example.org/x'\n"), scheme)

    def test_the_comparison_is_exact_and_case_insensitive(self):
        self.assertEqual(self.found("URL = 'https://API.GitHub.com/x'\n"), [])
        for host in ("github.com", "api.github.com.evil.example", "evil-api.github.com", "user" + helpers.AT + "api.github.com"):
            self.assertTrue(self.found(f"URL = 'https://{host}/x'\n"), host)

    def test_a_host_built_at_run_time_fails(self):
        for source in ("x = f'https://{host}/path'\n", "x = 'https://' + host\n", "x = 'https://%s/x' % host\n",
                       "x = 'https://{}/x'.format(host)\n", "x = f'https://{host}.github.com'\n"):
            with self.subTest(source=source):
                self.assertTrue(any("built at run time" in m for m in self.found(source)), source)

    def test_a_variable_endpoint_given_to_the_client_fails(self):
        source = "from operator_lib.httpclient import HttpClient\nclient = HttpClient(url)\n"
        self.assertTrue(any("HttpClient takes a literal" in m for m in self.found(source)))
        self.assertTrue(any("HttpClient takes a literal" in m for m in self.found("client = HttpClient(base=url)\n")))
        self.assertTrue(any("HttpClient takes a literal" in m for m in self.found("client = HttpClient(os.environ['U'])\n")))
        self.assertTrue(any("HttpClient takes a literal" in m for m in self.found("client = HttpClient(f'https://{h}')\n")))

    def test_a_literal_or_a_literal_module_constant_is_fine(self):
        self.assertEqual(self.found("client = HttpClient('https://api.github.com', token)\n"), [])
        self.assertEqual(self.found("BASE = 'https://api.github.com'\ndef make(token):\n    return HttpClient(BASE, token)\n"), [])
        self.assertTrue(self.found("def make(base, token):\n    return HttpClient(base, token)\n"))
        self.assertTrue(self.found("BASE = make_base()\nclient = HttpClient(BASE)\n"))

    def test_network_modules_are_used_only_in_the_one_client(self):
        for source in ("import urllib.request\n", "from urllib import request\n", "from urllib.request import urlopen\n", "import http.client\n",
                       "import socket\n", "from socket import create_connection\n", "import requests\n", "import ssl\n"):
            with self.subTest(source=source):
                self.assertTrue(any("network modules" in m for m in self.found(source)), source)
                self.assertEqual([m for m in self.found(source, path=check.HTTP_CLIENT) if "network modules" in m], [])
        self.assertEqual(self.found("import urllib.parse\nimport urllib.error\nimport json\n"), [])

    def test_the_urls_in_docstrings_and_comments_are_not_endpoints(self):
        self.assertEqual(self.found('"""See https://docs.example.org/page."""\n# https://docs.example.org\nx = 1\n'), [])

    def test_a_bare_scheme_used_for_a_comparison_is_not_an_endpoint(self):
        self.assertEqual(self.found("ok = value.startswith('https://')\n"), [])

    def test_shell_downloads_need_a_literal_listed_host(self):
        shell = "#!/usr/bin/env bash\n"
        self.assertEqual([m for _, m in check.scan("scripts/operator/x", shell + "curl -fsS https://api.github.com/zen\n", ALLOWED)], [])
        self.assertTrue(check.scan("scripts/operator/x", shell + "curl -fsS https://other.example.org/zen\n", ALLOWED))
        self.assertTrue(check.scan("scripts/operator/x", shell + 'curl -fsS "$URL"\n', ALLOWED))
        self.assertTrue(check.scan("scripts/operator/x", shell + 'wget "https://$HOST/x"\n', ALLOWED))

    def test_without_a_policy_nothing_is_enforced(self):
        self.assertEqual([m for _, m in check.scan(PY, "import socket\nx = 'https://other.example.org'\nHttpClient(u)\n")], [])

    def test_the_repository_operator_scripts_pass_with_the_repository_policy(self):
        text = (helpers.ROOT / "config" / "project.yaml").read_text()
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "project.yaml"
            path.write_text(text)
            allowed, problem = check.load_policy(str(path))
        self.assertEqual((allowed, problem), ({"api.github.com"}, None))


class Policy(unittest.TestCase):
    """The configuration of the BASE commit is the only source of the allowlist, and a missing key fails closed (I-10)."""

    def load(self, text):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "project.yaml"
            path.write_text(text)
            return check.load_policy(str(path))

    def test_the_key_and_the_paths_give_the_allowlist(self):
        self.assertEqual(self.load(CONFIG), ({"api.github.com"}, None))
        self.assertEqual(self.load(CONFIG + "  - Extra.Example.org\n")[0], {"api.github.com", "extra.example.org"})

    def test_a_missing_key_fails_closed_while_operator_paths_is_not_empty(self):
        allowed, problem = self.load("schema_version: 1\noperator_paths:\n  - scripts/operator/\n")
        self.assertIsNone(allowed)
        self.assertIn("operator_endpoints is missing", problem)

    def test_an_empty_list_is_an_empty_allowlist_and_every_endpoint_then_fails(self):
        allowed, problem = self.load("operator_paths:\n  - scripts/operator/\noperator_endpoints: []\n")
        self.assertEqual((allowed, problem), (set(), None))
        self.assertTrue(check.scan(PY, "x = 'https://api.github.com'\n", allowed))

    def test_explicitly_empty_operator_paths_enforces_nothing(self):
        self.assertEqual(self.load("operator_paths: []\n"), (None, None))
        self.assertEqual(self.load("operator_paths: []\noperator_endpoints:\n  - api.github.com\n"), (None, None))

    def test_a_missing_operator_paths_enforces_nothing_here_pc_8_judges_that_key(self):
        self.assertEqual(self.load("schema_version: 1\n"), (None, None))
        self.assertEqual(self.load("schema_version: 1\noperator_endpoints:\n  - api.github.com\n"), (None, None))

    def test_a_malformed_operator_paths_or_endpoints_fails_closed(self):
        for text in ("operator_paths: scripts/operator/\n", "operator_paths:\n  - 'quoted'\noperator_endpoints: []\n",
                     "operator_paths:\n  - a\noperator_endpoints:\n  - host with space\n", "operator_paths: [a]\n"):
            with self.subTest(text=text):
                allowed, problem = self.load(text)
                self.assertIsNone(allowed)
                self.assertIn("fails closed", problem)

    def test_no_file_means_nothing_is_enforced(self):
        self.assertEqual(check.load_policy(None), (None, None))


class Cli(unittest.TestCase):
    def run_check(self, files):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            for path, text in files.items():
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text)
            script = helpers.ROOT / "scripts" / "checks" / "operator-contract.sh"
            result = subprocess.run(["bash", str(script)], input="\n".join(files) + "\n", cwd=root, capture_output=True, text=True,
                                    env={"PATH": os.environ["PATH"], "HOME": tmp})
            return result

    def test_findings_are_reported_as_path_line_message(self):
        result = self.run_check({"scripts/operator/bad.py": "x = 1\neval('2')\n", "README.md": "eval"})
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertRegex(result.stdout, r"^scripts/operator/bad\.py:2: ")
        self.assertNotIn("README", result.stdout)

    def test_a_clean_tree_passes(self):
        result = self.run_check({"scripts/operator/ok.py": "x = 1\n"})
        self.assertEqual((result.returncode, result.stdout), (0, ""))

    def test_nothing_applicable_is_77(self):
        self.assertEqual(self.run_check({"docs/README.md": "x"}).returncode, 77)
        self.assertEqual(self.run_check({"scripts/operator/machine-profiles.toml": "[machines.a]\n"}).returncode, 77)

    def git_repo(self, tmp, files, message):
        root = pathlib.Path(tmp)
        for path, text in files.items():
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
        env = {"PATH": os.environ["PATH"], "HOME": tmp, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null",
               "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "noreply", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "noreply"}
        for argv in (["init", "-q", "-b", "main"] if not (root / ".git").exists() else [], ["add", "-A"], ["commit", "-q", "-m", message]):
            if argv:
                subprocess.run(["git", "-C", tmp, *argv], check=True, env=env, capture_output=True)
        return env, subprocess.run(["git", "-C", tmp, "rev-parse", "HEAD"], check=True, env=env, capture_output=True, text=True).stdout.strip()

    def run_script(self, tmp, env, files, base=None):
        script = helpers.ROOT / "scripts" / "checks" / "operator-contract.sh"
        run_env = dict(env)
        if base:
            run_env["GATE_BASE_REF"] = base
        return subprocess.run(["bash", str(script)], input="\n".join(files) + "\n", cwd=tmp, capture_output=True, text=True, env=run_env)

    def test_the_allowlist_is_read_from_the_base_commit_never_from_the_head(self):
        """PA-A15: a head that adds a host to its own allowlist does not make the script that calls it pass."""
        script = "URL = 'https://extra.example.org/x'\n"
        with tempfile.TemporaryDirectory() as tmp:
            env, base = self.git_repo(tmp, {"config/project.yaml": CONFIG, "scripts/operator/ok.py": "x = 1\n"}, "base")
            head_config = CONFIG + "  - extra.example.org\n"
            self.git_repo(tmp, {"config/project.yaml": head_config, "scripts/operator/call.py": script}, "head")
            files = ["scripts/operator/call.py"]
            judged_by_base = self.run_script(tmp, env, files, base=base)
            self.assertEqual(judged_by_base.returncode, 1, judged_by_base.stderr)
            self.assertRegex(judged_by_base.stdout, r"^scripts/operator/call\.py:1: an endpoint host is not listed")
            self.assertNotIn("extra.example.org", judged_by_base.stdout)
            self.assertEqual(self.run_script(tmp, env, files).returncode, 0)  # no base: the working tree is the policy (a push, a local run)

    def test_a_base_without_the_key_fails_closed_even_when_the_head_has_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            env, base = self.git_repo(tmp, {"config/project.yaml": "schema_version: 1\noperator_paths:\n  - scripts/operator/\n",
                                            "scripts/operator/ok.py": "x = 1\n"}, "base")
            self.git_repo(tmp, {"config/project.yaml": CONFIG}, "head")
            result = self.run_script(tmp, env, ["scripts/operator/ok.py"], base=base)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn("operator_endpoints is missing while operator_paths is not empty", result.stdout)

    def test_an_unreadable_base_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            env, _ = self.git_repo(tmp, {"config/project.yaml": CONFIG, "scripts/operator/ok.py": "x = 1\n"}, "base")
            for ref in ("no-such-ref", "-x"):
                result = self.run_script(tmp, env, ["scripts/operator/ok.py"], base=ref)
                self.assertEqual(result.returncode, 1, ref)
                self.assertIn("the base commit cannot be read", result.stdout)

    def test_a_base_without_a_configuration_file_enforces_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            env, base = self.git_repo(tmp, {"README.md": "x\n"}, "base")
            self.git_repo(tmp, {"scripts/operator/call.py": "import socket\n"}, "head")
            self.assertEqual(self.run_script(tmp, env, ["scripts/operator/call.py"], base=base).returncode, 0)

    def test_a_working_tree_with_the_policy_judges_the_script(self):
        result = self.run_check({"config/project.yaml": CONFIG, "scripts/operator/call.py": "import urllib.request\n"})
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertRegex(result.stdout, r"^scripts/operator/call\.py:1: network modules")

    def test_the_repository_passes_its_own_check(self):
        files = subprocess.run(["git", "ls-files"], cwd=helpers.ROOT, capture_output=True, text=True, check=True).stdout
        script = helpers.ROOT / "scripts" / "checks" / "operator-contract.sh"
        result = subprocess.run(["bash", str(script)], input=files, cwd=helpers.ROOT, capture_output=True, text=True)
        self.assertIn(result.returncode, (0, 77), result.stdout)


if __name__ == "__main__":
    unittest.main()
