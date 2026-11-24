"""CR-57 plan PR 4: the operator profile (Debian 13, ADR-012 decision 7, PA-20) and its shared roles (PA-A27).

Static checks over the playbook and roles, plus real playbook runs that must be refused before any role runs, as the current user in a
throw-away git clone. What needs root, sshd, and a second user (the real run, the second run, the dry run, the operator check on the
machine it set up) is the PA-28 job (tests/ansible/pa28-operator.sh, job `operator-profile`). Nothing here changes this machine.
"""
import getpass
import pathlib
import re
import shutil
import unittest

from test_profiles import ACCOUNTS as LAB_ACCOUNTS, clone_of_this_tree, host_facts, run

ROOT = pathlib.Path(__file__).resolve().parents[2]
ANSIBLE = ROOT / "ansible"
HAVE_ANSIBLE = shutil.which("ansible-playbook") is not None and shutil.which("git") is not None
OPERATOR_ROLES = ("operator_user", "operator_tools", "operator_projects", "operator_checks")
SHARED_ROLES = ("ssh_hardening", "release_check", "unattended_upgrades")
# The roles of the CR-18 Ubuntu profile that no profile applies any more; plan PR 7 deletes them.
LEFTOVERS = ("operator_firewall", "operator_lock", "operator_sudo", "operator_system", "operator_ssh")
ORDER = ["apt_base", "toolchain", "shell_env", "verify", "unattended_upgrades", "operator_user", "operator_tools", "operator_projects",
         "ssh_hardening", "operator_checks"]
ME = getpass.getuser()
# The operator admin is the account that runs the test (the profile refuses any other); the operator user does not exist, so the key audit
# is the first thing that fails once every gate before it has passed.
ACCOUNTS = {"operator_user": "ghost-op", "operator_admin_user": ME}


def tasks(role, name="main.yml"):
    return (ANSIBLE / "roles" / role / "tasks" / name).read_text()


def everything(ansible=ANSIBLE):
    return {p.relative_to(ansible).as_posix(): p.read_text() for p in ansible.rglob("*.yml") if "operator" in p.relative_to(ansible).as_posix()}


def operator_yml():
    return (ANSIBLE / "operator.yml").read_text()


class Structure(unittest.TestCase):
    def test_layout(self):
        self.assertTrue((ANSIBLE / "operator.yml").is_file())
        for role in OPERATOR_ROLES + SHARED_ROLES:
            self.assertTrue((ANSIBLE / "roles" / role / "tasks" / "main.yml").is_file(), role)
        for rel in ("operator_tools/files/operator-check", "operator_tools/files/operator-run", "operator_projects/tasks/one.yml",
                    "operator_projects/defaults/main.yml", "operator_tools/defaults/main.yml"):
            self.assertTrue((ANSIBLE / "roles" / rel).is_file(), rel)

    def test_role_names_match_the_pc8_path_rule(self):
        config = (ROOT / "config" / "project.yaml").read_text()
        self.assertIn("  - ansible/roles/operator_*/\n", config)
        self.assertIn("  - ansible/operator.yml\n", config)
        for role in OPERATOR_ROLES:
            self.assertTrue(role.startswith("operator_"))
        for role in SHARED_ROLES + ("git_identity",):
            self.assertIn(f"  - ansible/roles/{role}/\n", config, role)

    def test_the_roles_are_applied_in_a_fixed_order_and_sshd_comes_before_the_check(self):
        text = operator_yml()
        roles = re.findall(r"^    - (?:role: )?([a-z_]+)$", text[text.index("  roles:"):], re.M)
        self.assertEqual(roles, ORDER)

    def test_no_role_of_the_ubuntu_profile_is_applied_and_no_lock_play_remains(self):
        code = "\n".join(line for line in operator_yml().splitlines() if not line.lstrip().startswith("#"))
        for role in LEFTOVERS:
            self.assertNotIn(role, code, role)
        self.assertNotRegex(code, r"tags:\s*\[[^\]]*never")
        self.assertEqual(code.count("- name: Apply the operator profile"), 1)
        self.assertEqual(len(re.findall(r"^- name:", code, re.M)), 1, "one play only")

    def test_the_toolchain_profile_is_operator_and_it_takes_python_3_and_git_only(self):
        self.assertIn("toolchain_profile: operator", operator_yml())
        self.assertNotIn("python_tools", operator_yml())

    def test_the_pre_tasks_run_the_gates_first_and_the_key_audit_before_any_role(self):
        text = operator_yml()
        pre = text[text.index("  pre_tasks:"):text.index("  roles:")]
        names = re.findall(r"^    - name: (.+)$", pre, re.M)
        self.assertEqual([n.split(",")[0] for n in names], [
            "Refuse a real run without the explicit apply variable", "Release check", "Preflight",
            "The two managed accounts are named and differ", "Only the operator admin runs the operator configuration", "Key audit",
            "The project list is valid and every project's clone is a release"])
        self.assertIn("name: release_check", pre)
        self.assertIn("tasks_from: audit", pre)
        self.assertIn("operator_apply", pre[:pre.index("Release check")])
        self.assertIn("always", pre[:pre.index("Release check")])

    def test_the_release_check_is_the_shared_role_and_has_no_bypass(self):
        """C-4: the same role as the lab playbook, imported without a `when`, tag skip, or variable."""
        text = operator_yml()
        block = text[text.index("- name: Release check"):text.index("- name: Preflight")]
        self.assertIn("name: release_check", block)
        self.assertNotIn("when:", block)
        self.assertIn("tags: [always]", block)
        for path in ANSIBLE.rglob("*.yml"):
            self.assertNotRegex(path.read_text(), r"release_check_skip|skip_release|ignore_release|release_bypass", path.name)

    def test_the_preflight_names_the_one_supported_platform(self):
        group = (ANSIBLE / "group_vars" / "all.yml").read_text()
        for line in ("operator_expected_os: Debian", 'operator_expected_major: "13"', "operator_expected_arch: x86_64"):
            self.assertIn(line, group)
        self.assertNotIn("Ubuntu\n", group.split("# Used only by the roles")[0])
        self.assertIn("operator_apply: false", group)

    def test_the_names_of_the_two_accounts_are_not_in_the_repository(self):
        for name, text in everything().items():
            self.assertNotRegex(text, r"operator_user: \S", name + " must not name an account")


class SharedRoles(unittest.TestCase):
    """PA-A27 (design PA-31): the lab and the operator profile use the same SSH hardening role, which has one defaults file."""

    def test_both_playbooks_include_the_one_role_by_the_same_name(self):
        for playbook in ("lab.yml", "operator.yml"):
            text = (ANSIBLE / playbook).read_text()
            self.assertIn("name: ssh_hardening\n        tasks_from: audit", text, playbook)
            self.assertRegex(text, r"- role: ssh_hardening\n      tags: \[ssh_hardening\]", playbook)
            self.assertIn("name: release_check", text, playbook)
            self.assertRegex(text, r"- role: unattended_upgrades", playbook)

    def test_the_role_has_one_defaults_file_and_no_profile_copies_the_sshd_settings(self):
        defaults = sorted(p.relative_to(ANSIBLE).as_posix() for p in (ANSIBLE / "roles").rglob("*") if p.is_file()
                          and p.parent.name == "defaults" and p.parent.parent.name == "ssh_hardening")
        self.assertEqual(defaults, ["roles/ssh_hardening/defaults/main.yml"])
        for playbook in ("lab.yml", "operator.yml"):
            text = (ANSIBLE / playbook).read_text()
            for setting in ("PasswordAuthentication", "PermitRootLogin", "AllowUsers", "AuthorizedKeysFile", "KexAlgorithms"):
                self.assertNotIn(setting, text, f"{playbook} must not copy {setting}")
        for role in OPERATOR_ROLES:
            for path in (ANSIBLE / "roles" / role).rglob("*.yml"):
                self.assertNotIn("sshd_config", path.read_text(), path.as_posix())

    def test_each_profile_sets_only_the_accounts_and_the_key_options(self):
        for playbook, accounts, private in (("lab.yml", ("lab_ai_user", "lab_admin_user"), "lab_ai_user"),
                                            ("operator.yml", ("operator_user", "operator_admin_user"), "operator_user")):
            text = (ANSIBLE / playbook).read_text()
            self.assertRegex(text, rf"ssh_hardening_accounts: \[\"{{{{ {accounts[0]} \| default\(''\) }}}}\", \"{{{{ {accounts[1]} \| default\(''\) }}}}\"\]")
            self.assertIn(f'ssh_hardening_private_key_accounts: ["{{{{ {private} | default(\'\') }}}}"]', text)
        self.assertIn("ssh_hardening_key_options: []", operator_yml(), "restrict,pty is the AI user's option only (LC-11)")

    def test_the_operator_profile_gets_no_git_identity_and_no_claude_settings(self):
        for role in ("git_identity", "claude_managed_settings", "lab_tools"):
            self.assertNotIn(role, operator_yml(), role)


class Privilege(unittest.TestCase):
    def test_become_goes_through_the_root_check_and_is_never_blanket(self):
        for name, text in everything().items():
            self.assertNotIn("become: true", text, name)
            for match in re.finditer(r"become:\s*(.+)", text):
                self.assertIn(match.group(1).strip().strip('"'), ("{{ ai_lab_become }}", "false"), name)

    def test_no_shell_raw_download_or_remote_code_in_the_operator_files(self):
        for name, text in everything().items():
            for banned in ("ansible.builtin.shell", "ansible.builtin.raw", "get_url", "ansible.builtin.uri", "unarchive", "curl ", "wget ", "| sh", "| bash", "eval "):
                self.assertNotIn(banned, text, f"{name}: {banned}")

    def test_no_sudoers_rule_is_ever_written_by_a_role_the_profile_applies(self):
        for role in OPERATOR_ROLES + SHARED_ROLES:
            for path in (ANSIBLE / "roles" / role).rglob("*.yml"):
                text = path.read_text()
                self.assertNotIn("sudoers.d/", text.replace("/etc/sudoers.d,", "").replace("/etc/sudoers.d\n", ""), path.as_posix())
                self.assertNotIn("NOPASSWD", text, path.as_posix())
                self.assertNotRegex(text, r"ALL=\(", path.as_posix())

    def test_the_operator_user_is_taken_out_of_root_equivalent_groups_and_no_sudoers_rule_may_name_it(self):
        text = tasks("operator_user")
        self.assertIn("gpasswd", text)
        self.assertIn("-rEls", text)
        self.assertIn("failed_when: operator_user_sudoers.rc == 0", text)
        defaults = (ANSIBLE / "roles" / "operator_user" / "defaults" / "main.yml").read_text()
        for group in ("sudo", "wheel", "admin", "docker", "lxd", "disk"):
            self.assertIn(group, defaults)

    def test_nothing_is_written_into_a_users_home(self):
        for role in OPERATOR_ROLES + ("unattended_upgrades",):
            for path in (ANSIBLE / "roles" / role).rglob("*.yml"):
                self.assertNotRegex(path.read_text(), r"/home/|~/|ansible_env|ansible_user_dir|\.ssh/", path.as_posix())

    def test_the_two_checked_in_scripts_are_not_run_from_a_path_the_user_can_write(self):
        text = tasks("operator_checks")
        self.assertIn("{{ operator_tools_dir }}/operator-check", text)
        self.assertIn("/usr/sbin/runuser", text)


class Selection(unittest.TestCase):
    def test_everything_selects_by_the_path_inside_ansible_not_by_where_the_checkout_is(self):
        import tempfile
        with tempfile.TemporaryDirectory(prefix="operator-") as tmp:  # a checkout whose own path says "operator"
            ansible = pathlib.Path(tmp) / "operator-checkout" / "ansible"
            for name in ("operator.yml", "roles/operator_tools/tasks/main.yml", "group_vars/all.yml", "roles/apt_base/tasks/main.yml"):
                (ansible / name).parent.mkdir(parents=True, exist_ok=True)
                (ansible / name).write_text("---\n")
            self.assertEqual(sorted(everything(ansible)), ["operator.yml", "roles/operator_tools/tasks/main.yml"])


class Tools(unittest.TestCase):
    def test_every_install_task_is_root_owned_and_uses_the_root_check(self):
        for role, exceptions in (("operator_tools", 5), ("operator_projects", 0)):
            for path in (ANSIBLE / "roles" / role / "tasks").glob("*.yml"):
                for task in re.split(r"^\s*- name: ", path.read_text(), flags=re.M)[1:]:
                    if re.search(r"ansible\.builtin\.(copy|file)\b", task) and "state: directory" not in task and "owner:" in task:
                        if "operator_user }}" in task:
                            continue  # the run lock and the output directories belong to the operator user, by design
                        self.assertIn("owner: root", task, task.splitlines()[0])
                    if re.search(r"ansible\.builtin\.(copy|file)\b", task):
                        self.assertIn('become: "{{ ai_lab_become }}"', task, task.splitlines()[0])

    def test_no_mode_is_writable_by_others(self):
        for role in OPERATOR_ROLES:
            for path in (ANSIBLE / "roles" / role).rglob("*.yml"):
                for mode in re.findall(r'^\s+(?:directory_)?mode: "(\d+)"', path.read_text(), re.M):
                    self.assertEqual(int(mode, 8) & 0o022, 0, f"{path.name}: mode {mode} is writable by others")

    def test_the_run_lock_and_the_output_directories_are_the_operator_users_and_private(self):
        text = tasks("operator_tools")
        lock = text[text.index("- name: The run lock"):text.index("- name: The commands the user types")]
        self.assertIn('owner: "{{ operator_user }}"', lock)
        self.assertIn('mode: "0600"', lock)
        self.assertIn("force: false", lock)
        one = tasks("operator_projects", "one.yml")
        output = one[one.index("- name: The output directory of this project"):]
        self.assertIn('owner: "{{ operator_user }}"', output)
        self.assertIn('mode: "0700"', output)

    def test_every_project_passes_the_release_check_by_itself_as_a_pre_task_with_no_when(self):
        release = tasks("operator_projects", "release.yml")
        self.assertIn("name: release_check", release)
        self.assertIn('repo_root: "{{ operator_project.source }}"', release)
        self.assertNotIn("when:", release)
        check = tasks("operator_projects", "check.yml")
        self.assertIn("include_tasks: release.yml", check)
        self.assertNotIn("when:", check)
        self.assertNotIn("release_check", tasks("operator_projects", "one.yml"))
        text = operator_yml()
        block = text[text.index("- name: The project list is valid"):text.index("  roles:")]
        self.assertIn("tasks_from: check", block)
        self.assertIn("tags: [always]", block)

    def test_an_installation_of_another_release_is_taken_away_and_the_marker_is_written_last(self):
        one = tasks("operator_projects", "one.yml")
        self.assertLess(one.index("Take an installation of another release away"), one.index("Install the operator scripts"))
        self.assertLess(one.index("Install the operator scripts"), one.index("Record the release"))
        self.assertLess(one.index("Record the release"), one.index("The output directory of this project"))
        self.assertIn("contained_in_origin_main=yes", one)

    def test_the_defaults_install_this_repository_and_other_projects_come_from_the_caller(self):
        defaults = (ANSIBLE / "roles" / "operator_projects" / "defaults" / "main.yml").read_text()
        self.assertIn("project.yaml", defaults)
        self.assertIn('source: "{{ repo_root }}"', defaults)
        self.assertIn("-e @file", defaults)

    def test_the_conf_names_the_accounts_and_the_release_and_no_path(self):
        text = tasks("operator_tools")
        for line in ("operator_user={{ operator_user }}", "admin_user={{ operator_admin_user }}", "release_tag=", "release_commit="):
            self.assertIn(line, text)

    def test_the_commands_are_links_to_the_root_owned_files(self):
        text = tasks("operator_tools")
        self.assertIn("state: link", text)
        self.assertIn("loop: [operator-check, operator-run]", text)

    def test_the_check_runs_last_and_fails_the_run_only_once_sshd_is_switched(self):
        text = tasks("operator_checks")
        self.assertIn("when: not ansible_check_mode", text)
        self.assertIn("ssh_second_login_confirmed | bool", text)
        self.assertIn("failed_when: false", text)


@unittest.skipUnless(HAVE_ANSIBLE, "ansible-playbook and git are required")
class Gates(unittest.TestCase):
    def test_syntax_check_of_the_profile(self):
        code, out = run("operator.yml", "--syntax-check")
        self.assertEqual(code, 0, out)

    def test_a_real_run_without_the_apply_variable_is_refused_first(self):
        repo = clone_of_this_tree(self, tag="v1.0.0")
        code, out = run("operator.yml", extra_vars=ACCOUNTS, root=repo)
        self.assertNotEqual(code, 0)
        self.assertIn("operator_apply=true", out)
        self.assertEqual(out.count("FAILED!"), 1, out)
        self.assertNotIn("TASK [apt_base", out)

    def refused_by_release_check(self, repo, *args):
        code, out = run("operator.yml", "--check", *args, extra_vars=ACCOUNTS, root=repo)
        self.assertNotEqual(code, 0)
        self.assertIn("refused: this clone is not a release", out)
        self.assertEqual(out.count("FAILED!"), 1, out)
        self.assertNotIn("TASK [Preflight", out, "the release check comes before every other gate")
        self.assertNotIn("TASK [apt_base", out)
        self.assertNotIn("TASK [operator_", out)

    def test_an_untagged_clone_is_refused(self):
        self.refused_by_release_check(clone_of_this_tree(self))

    def test_a_tag_that_is_not_a_release_tag_is_refused(self):
        self.refused_by_release_check(clone_of_this_tree(self, tag="nightly-1"))

    def test_a_tag_not_contained_in_origin_main_is_refused(self):
        self.refused_by_release_check(clone_of_this_tree(self, tag="v1.0.0", contained=False))

    def test_a_tagged_clone_with_a_local_change_is_refused(self):
        repo = clone_of_this_tree(self, tag="v1.0.0")
        (repo / "README.md").write_text("changed\n")
        self.refused_by_release_check(repo)

    def test_selecting_tags_does_not_skip_the_release_check(self):
        self.refused_by_release_check(clone_of_this_tree(self), "--tags", "preflight")

    def test_a_release_passes_the_gate_and_reaches_the_preflight(self):
        repo = clone_of_this_tree(self, tag="v1.0.0")
        name, major, arch = host_facts()
        good = {"operator_expected_os": name, "operator_expected_major": major, "operator_expected_arch": arch}
        for key, bad in (("operator_expected_os", "NoSuchOS"), ("operator_expected_major", "99"), ("operator_expected_arch", "riscv64")):
            with self.subTest(wrong=key):
                code, out = run("operator.yml", "--check", extra_vars={**ACCOUNTS, **good, key: bad}, root=repo)
                self.assertNotEqual(code, 0)
                self.assertIn("operator profile requires", out)
                self.assertEqual(out.count("FAILED!"), 1, out)
                self.assertNotIn("refused: this clone is not a release", out)

    def test_the_account_names_are_required_and_must_differ(self):
        repo = clone_of_this_tree(self, tag="v1.0.0")
        name, major, arch = host_facts()
        host = {"operator_expected_os": name, "operator_expected_major": major, "operator_expected_arch": arch, "ai_lab_become": "false"}
        cases = [{}, {"operator_user": "a"}, {"operator_user": "same", "operator_admin_user": "same"},
                 {"operator_user": "root", "operator_admin_user": "b"}, {"operator_user": "Bad Name", "operator_admin_user": "b"}]
        for accounts in cases:
            with self.subTest(accounts=accounts):
                code, out = run("operator.yml", "--check", extra_vars={**host, **accounts}, root=repo)
                self.assertNotEqual(code, 0)
                self.assertIn("name the two managed accounts", out)
                self.assertEqual(out.count("FAILED!"), 1, out)

    def test_the_key_audit_refuses_before_any_role_runs(self):
        repo = clone_of_this_tree(self, tag="v1.0.0")
        name, major, arch = host_facts()
        host = {"operator_expected_os": name, "operator_expected_major": major, "operator_expected_arch": arch, "ai_lab_become": "false"}
        code, out = run("operator.yml", "--check", extra_vars={**host, **ACCOUNTS}, root=repo)
        self.assertNotEqual(code, 0)
        self.assertIn("refused: ghost-op: the account does not exist", out)
        self.assertNotIn("TASK [apt_base", out)
        self.assertNotIn("TASK [operator_", out)
        self.assertNotIn("TASK [ssh_hardening : Copy the provisioned keys", out)

    def test_only_the_operator_admin_runs_it(self):
        """PA-A21: the wrong user is refused before the key audit or any role; the operator user never runs the configuration."""
        repo = clone_of_this_tree(self, tag="v1.0.0")
        name, major, arch = host_facts()
        host = {"operator_expected_os": name, "operator_expected_major": major, "operator_expected_arch": arch, "ai_lab_become": "false"}
        for admin in ("ghost-opadm", "root-not"):
            with self.subTest(admin=admin):
                code, out = run("operator.yml", "--check", extra_vars={**host, "operator_user": "ghost-op", "operator_admin_user": admin}, root=repo)
                self.assertNotEqual(code, 0)
                self.assertIn("refused: the operator configuration is run by the operator admin", out)
                self.assertEqual(out.count("FAILED!"), 1, out)
                self.assertNotIn("TASK [ssh_hardening", out)
                self.assertNotIn("TASK [apt_base", out)

    def test_the_admin_check_has_no_bypass(self):
        text = operator_yml()
        block = text[text.index("- name: Only the operator admin"):text.index("- name: Key audit")]
        self.assertNotIn("when:", block)
        self.assertIn("tags: [always]", block)
        self.assertNotIn("ignore_errors", block)

    def test_the_lab_accounts_are_not_the_operator_accounts(self):
        """A lab invocation does not satisfy the operator profile: the variable names differ, so a mixed-up call is refused."""
        repo = clone_of_this_tree(self, tag="v1.0.0")
        name, major, arch = host_facts()
        host = {"operator_expected_os": name, "operator_expected_major": major, "operator_expected_arch": arch}
        code, out = run("operator.yml", "--check", extra_vars={**host, **LAB_ACCOUNTS}, root=repo)
        self.assertNotEqual(code, 0)
        self.assertIn("name the two managed accounts", out)


@unittest.skipUnless(HAVE_ANSIBLE, "ansible-playbook and git are required")
class ProjectList(unittest.TestCase):
    """The project list is validated before anything is installed."""

    def test_a_bad_project_list_is_refused_by_the_first_task(self):
        import json
        import os
        import subprocess
        import tempfile
        bad = [[], [{"name": "a", "source": "/x"}, {"name": "a", "source": "/y"}], [{"name": "Bad_Name", "source": "/x"}],
               [{"name": "ok", "source": "relative/path"}], [{"name": "ok", "source": "/x y"}]]
        for projects in bad:
            with self.subTest(projects=projects):
                tmp = pathlib.Path(tempfile.mkdtemp())
                self.addCleanup(shutil.rmtree, tmp)
                (tmp / "play.yml").write_text("- hosts: all\n  connection: local\n  gather_facts: false\n  tasks:\n    - ansible.builtin.import_role: "
                                              "{name: operator_projects, tasks_from: check}\n")
                (tmp / "vars.json").write_text(json.dumps({"operator_projects": projects}))
                env = {"PATH": os.environ["PATH"], "HOME": str(tmp), "ANSIBLE_HOME": str(tmp), "ANSIBLE_LOCAL_TEMP": str(tmp),
                       "ANSIBLE_ROLES_PATH": str(ANSIBLE / "roles"), "ANSIBLE_NOCOLOR": "1", "LC_ALL": "C.UTF-8"}
                done = subprocess.run(["ansible-playbook", "-i", str(ANSIBLE / "inventory" / "localhost.yml"), str(tmp / "play.yml"),
                                       "-e", f"repo_root={ROOT}", "-e", "ai_lab_become=false", "-e", f"@{tmp / 'vars.json'}", "--check"],
                                      capture_output=True, text=True, env=env, cwd=tmp, timeout=120, check=False)
                out = done.stdout + done.stderr
                self.assertNotEqual(done.returncode, 0, out)
                self.assertIn("operator_projects needs at least one project", out)
                self.assertEqual(out.count("FAILED!"), 1, out)


if __name__ == "__main__":
    unittest.main()
