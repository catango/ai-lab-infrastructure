"""CR-43 S-2 and S-23: the aggregate `quality-gate` of ci.yml needs every other job, always runs, and fails unless each
needed job succeeded.

Text-level checks of the workflow (the standard library has no YAML parser; workflow-policy checks the same rule on a parsed
form) and a fixture test of the commands of the aggregate's step: the script is cut out of the workflow and run with the
`needs` context of a green, a red, a cancelled, and a skipped run.
"""
import json
import os
import pathlib
import re
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
CI = ROOT / ".github" / "workflows" / "ci.yml"
EXPECTED_NEEDS = ["gate", "operator-profile", "operator-limits", "toolchain", "builder-profile"]


def jobs(text):
    """Job id -> its lines (the body at deeper indentation than the id), in file order."""
    result = {}
    current = None
    in_jobs = False
    for line in text.splitlines():
        if re.match(r"^jobs:\s*$", line):
            in_jobs = True
            continue
        if not in_jobs:
            continue
        if line and not line.startswith(" ") and not line.startswith("#"):
            break
        match = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)
        if match:
            current = match.group(1)
            result[current] = []
        elif current:
            result[current].append(line)
    return result


def job_keys(body):
    """The keys at job level (four spaces) of a job body."""
    return {m.group(1): m.group(2) for line in body if (m := re.match(r"^    ([a-z-]+):\s*(.*)$", line))}


def step_script(body, name):
    """The `run: |` block of the step called NAME in a job body, dedented."""
    for index, line in enumerate(body):
        if line.strip() == f"- name: {name}":
            break
    else:
        raise AssertionError(f"no step called {name}")
    run = next(i for i in range(index, len(body)) if body[i].strip() == "run: |")
    lines = []
    for line in body[run + 1:]:
        if line.strip() and not line.startswith(" " * 10):
            break
        lines.append(line[10:])
    return "\n".join(lines).rstrip() + "\n"


class Aggregate(unittest.TestCase):
    def setUp(self):
        self.text = CI.read_text()
        self.jobs = jobs(self.text)
        self.aggregate = self.jobs["quality-gate"]
        self.keys = job_keys(self.aggregate)

    def test_the_jobs_of_the_file(self):
        self.assertEqual(sorted(self.jobs), sorted(EXPECTED_NEEDS + ["quality-gate"]))

    def test_the_aggregate_needs_every_other_job_and_always_runs(self):
        needs = [item.strip() for item in self.keys["needs"].strip("[]").split(",")]
        self.assertEqual(sorted(needs), sorted(EXPECTED_NEEDS))
        self.assertEqual(sorted(needs), sorted(job for job in self.jobs if job != "quality-gate"))
        self.assertEqual(self.keys["if"], "always()")

    def test_no_required_job_is_skipped_or_tolerated(self):
        for job_id, body in self.jobs.items():
            if job_id != "quality-gate":
                self.assertNotIn("if", job_keys(body), job_id)
            self.assertNotIn("continue-on-error", job_keys(body), job_id)
        for banned in ("paths:", "paths-ignore:"):
            self.assertNotIn(banned, self.text)

    def test_the_aggregate_runs_no_repository_code(self):
        self.assertNotIn("uses:", "\n".join(self.aggregate))
        self.assertEqual(self.keys["permissions"], "{}")

    def test_the_aggregate_passes_the_needs_context_through_env(self):
        self.assertIn("NEEDS: ${{ toJSON(needs) }}", "\n".join(self.aggregate))
        self.assertNotIn("${{", step_script(self.aggregate, "Fail unless every needed job succeeded"))


class AggregateCommands(unittest.TestCase):
    """The commands of the aggregate's step, run with the needs context GitHub would give them."""

    def run_script(self, results):
        needs = {name: {"result": result, "outputs": {}} for name, result in results.items()}
        script = step_script(jobs(CI.read_text())["quality-gate"], "Fail unless every needed job succeeded")
        with tempfile.TemporaryDirectory() as tmp:
            summary = pathlib.Path(tmp) / "summary.md"
            env = {"PATH": os.environ["PATH"], "NEEDS": json.dumps(needs), "GITHUB_STEP_SUMMARY": str(summary)}
            proc = subprocess.run(["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", script], env=env,
                                  capture_output=True, text=True, check=False, cwd=tmp)
            return proc.returncode, proc.stdout + proc.stderr, summary.read_text() if summary.exists() else ""

    def green(self):
        return {name: "success" for name in EXPECTED_NEEDS}

    def test_all_green_passes(self):
        code, out, summary = self.run_script(self.green())
        self.assertEqual(code, 0, out)
        for name in EXPECTED_NEEDS:
            self.assertIn(name, summary)

    def test_one_failure_fails_and_is_named(self):
        for result in ("failure", "cancelled", "skipped"):
            for name in EXPECTED_NEEDS:
                with self.subTest(result=result, job=name):
                    results = self.green()
                    results[name] = result
                    code, out, summary = self.run_script(results)
                    self.assertEqual(code, 1, out)
                    self.assertIn(name, out)
                    self.assertIn(result, out)
                    self.assertIn(result, summary)

    def test_an_unknown_result_fails(self):
        results = self.green()
        results["toolchain"] = ""
        self.assertEqual(self.run_script(results)[0], 1)

    def test_no_needed_job_fails(self):
        code, out, _ = self.run_script({})
        self.assertEqual(code, 1, out)

    def test_malformed_needs_fails(self):
        script = step_script(jobs(CI.read_text())["quality-gate"], "Fail unless every needed job succeeded")
        for value in ("", "not json", "[]", "null"):
            with self.subTest(value=value):
                proc = subprocess.run(["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", script],
                                      env={"PATH": os.environ["PATH"], "NEEDS": value}, capture_output=True, text=True,
                                      check=False)
                self.assertNotEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
