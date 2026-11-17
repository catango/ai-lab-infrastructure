"""T-8 (static part), T-9: the playbooks' structure, syntax, and preflight assertions.

Runs ansible-playbook when it is installed (the builder-profile CI job applies the profile for real).
Nothing here needs root, network, or become: only --syntax-check and the preflight/placeholder tasks run.
"""
import os
import pathlib
import platform
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
ANSIBLE = ROOT / "ansible"
ROLES = ("apt_base", "toolchain", "python_tools", "shell_env", "verify", "claude_managed_settings")
HAVE_ANSIBLE = shutil.which("ansible-playbook") is not None


def host_facts():
    release = {}
    for line in pathlib.Path("/etc/os-release").read_text().splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            release[key] = value.strip('"')
    return release.get("ID", "").capitalize(), release.get("VERSION_ID", "").split(".")[0], platform.machine()


def run(playbook, *args, extra_vars=None):
    with tempfile.TemporaryDirectory() as tmp:
        env = {"PATH": os.environ["PATH"], "HOME": tmp, "ANSIBLE_HOME": tmp, "ANSIBLE_LOCAL_TEMP": tmp,
               "ANSIBLE_CONFIG": str(ANSIBLE / "ansible.cfg"), "ANSIBLE_NOCOLOR": "1", "LC_ALL": "C.UTF-8"}
        argv = ["ansible-playbook", "-i", str(ANSIBLE / "inventory" / "localhost.yml"), str(ANSIBLE / playbook), *args]
        for key, value in (extra_vars or {}).items():
            argv += ["-e", f"{key}={value}"]
        done = subprocess.run(argv, capture_output=True, text=True, env=env, cwd=ROOT, timeout=120, check=False)
        return done.returncode, done.stdout + done.stderr


class Structure(unittest.TestCase):
    def test_layout(self):
        for rel in ("ansible.cfg", "inventory/localhost.yml", "group_vars/all.yml", "builder.yml", "lab.yml"):
            self.assertTrue((ANSIBLE / rel).is_file(), rel)
        for role in ROLES:
            self.assertTrue((ANSIBLE / "roles" / role / "tasks" / "main.yml").is_file(), role)

    def test_playbooks_use_local_connection_and_no_remote_hosts(self):
        inventory = (ANSIBLE / "inventory" / "localhost.yml").read_text()
        self.assertIn("ansible_connection: local", inventory)
        for path in ANSIBLE.rglob("*.yml"):
            text = path.read_text()
            self.assertNotRegex(text, r"ansible_host|ansible_ssh|ansible_user", path.name)

    def test_builder_role_order(self):
        text = (ANSIBLE / "builder.yml").read_text()
        order = [text.index(f"- {role}") for role in ("apt_base", "toolchain", "python_tools", "shell_env", "verify")]
        self.assertEqual(order, sorted(order))

    def test_privilege_only_where_the_design_allows(self):
        allowed = {"apt_base", "toolchain", "python_tools", "shell_env", "claude_managed_settings"}
        for role in ROLES:
            text = (ANSIBLE / "roles" / role / "tasks" / "main.yml").read_text()
            if "become" in text:
                self.assertIn(role, allowed)
                self.assertIn("ai_lab_become", text, "become must go through the root check")
        self.assertNotIn("become: true", "".join(p.read_text() for p in ANSIBLE.rglob("*.yml")), "blanket become")

    def test_no_shell_or_raw_modules_and_no_downloads_in_ansible(self):
        for path in ANSIBLE.rglob("*.yml"):
            text = path.read_text()
            for banned in ("ansible.builtin.shell", "ansible.builtin.raw", "get_url", "ansible.builtin.uri", "unarchive", "curl ", "wget "):
                self.assertNotIn(banned, text, f"{path.name}: {banned}")

    def test_engine_is_called_through_isolated_python(self):
        for role in ("toolchain", "python_tools", "verify"):
            text = (ANSIBLE / "roles" / role / "tasks" / "main.yml").read_text()
            self.assertIn("- -I", text, role)
            self.assertIn("{{ toolchain_engine }}", text, role)
        self.assertIn('toolchain_engine: "{{ repo_root }}/scripts/toolchain"', (ANSIBLE / "group_vars" / "all.yml").read_text())

    def test_managed_settings_role_is_off_by_default(self):
        self.assertRegex((ANSIBLE / "group_vars" / "all.yml").read_text(), r"claude_managed_settings_enabled:\s*false")


@unittest.skipUnless(HAVE_ANSIBLE, "ansible-playbook is not installed")
class SyntaxAndPreflight(unittest.TestCase):
    def test_syntax_check_both_profiles(self):
        for playbook in ("builder.yml", "lab.yml"):
            with self.subTest(playbook=playbook):
                code, out = run(playbook, "--syntax-check")
                self.assertEqual(code, 0, out)

    def test_builder_preflight_passes_with_matching_expectations(self):
        name, major, arch = host_facts()
        code, out = run("builder.yml", "--tags", "preflight",
                        extra_vars={"builder_expected_os": name, "builder_expected_major": major, "builder_expected_arch": arch})
        self.assertEqual(code, 0, out)

    def test_builder_preflight_aborts_with_one_message_on_any_other_host(self):
        name, major, arch = host_facts()
        good = {"builder_expected_os": name, "builder_expected_major": major, "builder_expected_arch": arch}
        for key, bad in (("builder_expected_os", "NoSuchOS"), ("builder_expected_major", "99"), ("builder_expected_arch", "riscv64")):
            with self.subTest(wrong=key):
                code, out = run("builder.yml", "--tags", "preflight", extra_vars={**good, key: bad})
                self.assertNotEqual(code, 0)
                self.assertIn("builder profile requires", out)
                self.assertEqual(out.count("FAILED!"), 1, out)

    def test_lab_placeholder_fails_with_the_stage_3_message_after_its_preflight(self):
        name, major, arch = host_facts()
        code, out = run("lab.yml", extra_vars={"lab_expected_os": name, "lab_expected_major": major, "lab_expected_arch": arch})
        self.assertNotEqual(code, 0)
        self.assertIn("lab profile is implemented in Stage 3", out)
        self.assertEqual(out.count("FAILED!"), 1, out)

    def test_lab_placeholder_aborts_with_one_message_on_the_wrong_host(self):
        code, out = run("lab.yml", extra_vars={"lab_expected_os": "NoSuchOS"})
        self.assertNotEqual(code, 0)
        self.assertIn("lab profile requires", out)
        self.assertEqual(out.count("FAILED!"), 1, out)
        self.assertNotIn("Stage 3", out)


if __name__ == "__main__":
    unittest.main()
