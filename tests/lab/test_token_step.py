"""CR-57 PA-A8, PA-A25, LC-14: the token step refuses without a terminal and inside a Claude session before it reads anything, runs
in a clean environment, reads no startup file of the AI user, and hands the token to gh only on its standard input. The static
checks are the AC1-8 checks of the old workspace restore tests (deleted in plan PR 7), re-created for the token step.
"""
import os
import pathlib
import re
import shutil
import stat
import unittest

import helpers
from helpers import TOKEN_STEP, make_prefix, run, run_pty, scratch

TOKEN = "ghp_" + "T" * 36
ALLOWED = {"PATH", "HOME", "USER", "LOGNAME", "TERM", "LC_ALL", "PWD", "OLDPWD", "SHLVL", "_", "GH_PROMPT_DISABLED",
           "GH_SPINNER_DISABLED", "GH_NO_UPDATE_NOTIFIER", "GH_NO_EXTENSION_UPDATE_NOTIFIER", "NO_COLOR"}


class Fixture:
    def __init__(self, test, **options):
        self.base = scratch(test)
        self.prefix = make_prefix(self.base, **options)
        self.home = self.base / "home"
        self.home.mkdir()
        os.chmod(self.home, 0o777)
        self.env = {"PATH": helpers.PLAIN_PATH, "HOME": str(self.home), "TERM": "xterm"}

    def argv(self, *more):
        return [str(TOKEN_STEP), "--prefix", str(self.prefix), "--home", str(self.home), *more]

    def calls(self):
        path = self.prefix / "calls.log"
        return path.read_text().splitlines() if path.exists() else []

    def login(self, env=None, reply=TOKEN, more=()):
        return run_pty(self.argv(*more), env or self.env, replies=[("Token T1: ", reply)])


class Refusals(unittest.TestCase):
    def test_without_a_terminal_it_refuses_before_reading_input(self):
        fixture = Fixture(self)
        data = fixture.base / "input.txt"
        data.write_text(TOKEN + "\n")
        with open(data, "rb") as handle:
            code, out = run(fixture.argv(), env=fixture.env, stdin=handle)
            self.assertEqual(handle.tell(), 0, "the step read its input")
        self.assertEqual(code, 2, out)
        self.assertIn("not a terminal", out)
        self.assertEqual(fixture.calls(), [], "gh was called")
        self.assertNotIn(TOKEN, out)

    def test_inside_a_claude_session_it_refuses_before_prompting(self):
        for name in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SSE_PORT"):
            with self.subTest(marker=name):
                fixture = Fixture(self)
                code, out = fixture.login(env={**fixture.env, name: "1"})
                self.assertEqual(code, 2, out)
                self.assertIn("Claude Code session", out)
                self.assertNotIn("Token T1", out, "it prompted inside a session")
                self.assertEqual(fixture.calls(), [])

    def test_a_claude_process_among_the_ancestors_refuses(self):
        fixture = Fixture(self)
        fake = fixture.base / "claude"
        shutil.copy2("/bin/bash", fake)
        argv = [str(fake), "-c", '"$@"; exit $?', "_", *fixture.argv()]
        code, out = run_pty(argv, fixture.env, replies=[("Token T1: ", TOKEN)])
        self.assertEqual(code, 2, out)
        self.assertIn("Claude Code process", out)
        self.assertNotIn("Token T1", out)
        self.assertEqual(fixture.calls(), [])

    def test_a_trace_is_refused_and_the_token_is_never_printed(self):
        fixture = Fixture(self)
        code, out = run_pty(["/bin/bash", "-x", *fixture.argv()], fixture.env, replies=[("Token T1: ", TOKEN)])
        self.assertEqual(code, 2, out)
        self.assertNotIn(TOKEN, out)

    @unittest.skipUnless(os.getuid() == 0 and not helpers.RUN_AS, "needs root")
    def test_root_is_refused(self):
        fixture = Fixture(self)
        code, out = fixture.login()
        self.assertEqual(code, 2, out)
        self.assertIn("not as root", out)

    def test_stage_two_alone_refuses_an_unclean_environment(self):
        """Starting the second stage by hand, with a polluted environment, does not get around the first stage."""
        fixture = Fixture(self)
        code, out = run_pty([str(TOKEN_STEP), "--clean-stage", "--prefix", str(fixture.prefix), "--home", str(fixture.home)],
                            {**fixture.env, "PLANTED_CANARY": "1"}, replies=[("Token T1: ", TOKEN)])
        self.assertEqual(code, 2, out)
        self.assertIn("not clean", out)
        self.assertNotIn("Token T1", out)

    def test_an_unknown_argument_is_a_usage_error(self):
        fixture = Fixture(self)
        code, out = run(fixture.argv("--token", TOKEN), env=fixture.env)
        self.assertEqual(code, 2, out)
        self.assertIn("usage", out)

    def test_without_the_lab_configuration_it_refuses(self):
        fixture = Fixture(self, conf=False)
        code, out = fixture.login()
        self.assertEqual(code, 2, out)
        self.assertIn("lab.conf", out)
        self.assertNotIn("Token T1", out)


class Login(unittest.TestCase):
    def test_the_token_reaches_gh_only_on_standard_input(self):
        fixture = Fixture(self)
        code, out = fixture.login()
        self.assertEqual(code, 0, out)
        self.assertEqual((fixture.prefix / "stdin-token.txt").read_text().strip(), TOKEN)
        self.assertNotIn(TOKEN, out, "the terminal echoed the token")
        for line in fixture.calls():
            self.assertNotIn(TOKEN, line, "the token is in an argument")
            self.assertNotIn("ghp_", line)
        self.assertIn("auth login --hostname github.com --with-token", fixture.calls())
        self.assertIn("auth setup-git", fixture.calls())

    def test_the_environment_is_cleared(self):
        fixture = Fixture(self)
        planted = {"PLANTED_CANARY": "x", "GH_TOKEN": "canary-one", "GITHUB_TOKEN": "canary-two", "SSH_AUTH_SOCK": "/nowhere",
                   "BASH_ENV": str(fixture.base / "bash-env"), "ENV": str(fixture.base / "bash-env"), "LD_LIBRARY_PATH": "/nowhere",
                   "SHELLOPTS": "braceexpand", "HISTFILE": str(fixture.base / "history")}
        code, out = fixture.login(env={**fixture.env, **planted})
        self.assertEqual(code, 0, out)
        names = set((fixture.prefix / "env-names.txt").read_text().split())
        self.assertLessEqual(names, ALLOWED, f"unexpected variables reached gh: {sorted(names - ALLOWED)}")
        self.assertNotIn("canary", out)

    def test_a_planted_gh_earlier_on_the_callers_path_is_not_used(self):
        fixture = Fixture(self)
        decoy = fixture.base / "decoy"
        decoy.mkdir()
        os.chmod(decoy, 0o777)
        marker = fixture.base / "decoy-ran"
        gh = decoy / "gh"
        gh.write_text(f"#!/bin/sh\ntouch {marker}\ncat >/dev/null\n")
        gh.chmod(0o755)
        code, out = fixture.login(env={**fixture.env, "PATH": f"{decoy}:{helpers.PLAIN_PATH}"})
        self.assertEqual(code, 0, out)
        self.assertFalse(marker.exists(), "the caller's PATH was used")

    def test_no_shell_startup_file_of_the_ai_user_is_read(self):
        fixture = Fixture(self)
        markers = []
        for index, name in enumerate((".bashrc", ".bash_profile", ".bash_login", ".profile", ".bash_env")):
            marker = fixture.base / f"read-{index}"
            (fixture.home / name).write_text(f"touch {marker}\n")
            markers.append(marker)
        code, out = fixture.login(env={**fixture.env, "BASH_ENV": str(fixture.home / ".bash_env"), "ENV": str(fixture.home / ".profile")})
        self.assertEqual(code, 0, out)
        self.assertEqual([m for m in markers if m.exists()], [], "a startup file was read")

    def test_it_is_started_with_no_profile_files_and_a_fixed_path(self):
        text = TOKEN_STEP.read_text()
        self.assertIn("env -i", text)
        self.assertIn("--noprofile --norc -p", text)
        self.assertIn('"PATH=$PREFIX/bin:/usr/local/bin:/usr/bin:/bin"', text)

    def test_a_token_of_another_account_is_removed(self):
        fixture = Fixture(self, login="someone-else")
        code, out = fixture.login()
        self.assertEqual(code, 3, out)
        self.assertIn("another account", out)
        self.assertIn("auth logout --hostname github.com", fixture.calls())
        self.assertFalse((fixture.prefix / "state" / "logged-in").exists())
        self.assertNotIn(TOKEN, out)

    def test_a_token_without_a_required_scope_is_removed(self):
        for scopes in ("repo", "workflow, read:org"):
            with self.subTest(scopes=scopes):
                fixture = Fixture(self, scopes=scopes)
                code, out = fixture.login()
                self.assertEqual(code, 3, out)
                self.assertIn("scope", out)
                self.assertFalse((fixture.prefix / "state" / "logged-in").exists())

    def test_an_empty_token_is_refused_without_calling_login(self):
        fixture = Fixture(self)
        code, out = fixture.login(reply="")
        self.assertEqual(code, 3, out)
        self.assertNotIn("auth login --hostname github.com --with-token", fixture.calls())

    def test_a_logged_in_gh_is_not_asked_again_unless_reauth(self):
        fixture = Fixture(self)
        logged_in = fixture.prefix / "state" / "logged-in"
        logged_in.write_text("")
        logged_in.chmod(0o666)  # the stub runs as the account under test and replaces it
        code, out = run_pty(fixture.argv(), fixture.env)
        self.assertEqual(code, 0, out)
        self.assertNotIn("Token T1", out)
        code, out = fixture.login(more=("--reauth",))
        self.assertEqual(code, 0, out)
        self.assertIn("Token T1", out)


class Static(unittest.TestCase):
    """The AC1-8 checks of the old workspace restore tests, for the token step (PA-A25)."""

    def test_no_eval_and_no_pipe_into_a_shell(self):
        bad = [line for line in TOKEN_STEP.read_text().splitlines()
               if re.search(r"(^|[^a-z_])eval\s|\|\s*(ba)?sh(\s|$)", line)]
        self.assertEqual(bad, [])

    def test_the_token_only_ever_travels_through_a_here_string_to_gh(self):
        text = TOKEN_STEP.read_text()
        self.assertIn("with-token <<<", text)
        self.assertEqual(len(re.findall(r"with-token", text)), 1)

    def test_there_is_no_token_argument_or_environment_input(self):
        forbidden = [line for line in TOKEN_STEP.read_text().splitlines() if re.search(r"GH_TOKEN|GITHUB_TOKEN|--token", line)]
        self.assertEqual(forbidden, [])

    def test_the_token_is_not_written_anywhere(self):
        for line in TOKEN_STEP.read_text().splitlines():
            if "$token" in line and "<<<" not in line and "read -rs" not in line and "unset token" not in line and "-n $token" not in line:
                self.fail(f"the token variable is used outside the read, the here-string, and the unset: {line}")

    @unittest.skipUnless(helpers.INSTALLED, "needs the installed file (PA-28 job)")
    def test_the_installed_step_is_root_owned_and_not_writable_by_others(self):
        for path in (TOKEN_STEP, TOKEN_STEP.parent):
            info = path.stat()
            self.assertEqual(info.st_uid, 0, path)
            self.assertEqual(info.st_mode & (stat.S_IWGRP | stat.S_IWOTH), 0, path)


if __name__ == "__main__":
    unittest.main()
