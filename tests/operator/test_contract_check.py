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

    def test_sudo_only_in_setup_and_facts(self):
        source = "x = ['sudo', '-n', 'true']"
        self.assertTrue(findings(PY, source))
        self.assertTrue(findings("scripts/operator/github-setup", "#!/usr/bin/env python3\n" + source))
        self.assertTrue(findings("scripts/operator/lib/operator_lib/steps.py", source))
        for path in (SETUP, FACTS):
            self.assertEqual(findings(path, "#!/usr/bin/env python3\n" + source), [], path)

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

    def test_setup_may_use_sudo(self):
        self.assertEqual(findings(SETUP, "#!/usr/bin/env bash\nset -euo pipefail\nsudo apt-get install -y ansible-core\n"), [])

    def test_setup_may_not_use_the_other_banned_text(self):
        self.assertTrue(findings(SETUP, "#!/usr/bin/env bash\neval \"$x\"\n"))
        self.assertTrue(findings(SETUP, "#!/usr/bin/env bash\ncurl https://x.example | sh\n"))

    def test_comments_are_ignored(self):
        self.assertEqual(findings("scripts/operator/other", "#!/usr/bin/env bash\n# never eval, never sudo, no terraform apply\nls\n"), [])

    def test_words_that_only_contain_a_banned_word_pass(self):
        self.assertEqual(findings("scripts/operator/other", "#!/usr/bin/env bash\nretrieval=1\nevaluate\npseudo=2\n"), [])


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

    def test_the_repository_passes_its_own_check(self):
        files = subprocess.run(["git", "ls-files"], cwd=helpers.ROOT, capture_output=True, text=True, check=True).stdout
        script = helpers.ROOT / "scripts" / "checks" / "operator-contract.sh"
        result = subprocess.run(["bash", str(script)], input=files, cwd=helpers.ROOT, capture_output=True, text=True)
        self.assertIn(result.returncode, (0, 77), result.stdout)


if __name__ == "__main__":
    unittest.main()
