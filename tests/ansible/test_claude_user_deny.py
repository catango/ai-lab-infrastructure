"""CR-57 plan PR 4a, PA-50, PA-51, PA-A34, PA-A35: the module `claude_user_deny` that writes the user-level deny layer.

The module works on file descriptors and is plain functions with seams for the calls that need root (ownership, the attribute), so
every case runs here as an ordinary user in a temporary home: a fake `Ops` records the ownership and the attribute instead of
changing them, and can run a step between two calls of the module (a seam) to show a rename or a link planted in the middle of a
run. The PA-28 job runs the same module for real, as root, in a Debian 13 container (tests/ansible/pa28-lab.sh).
"""
import contextlib
import errno
import importlib.util
import io
import json
import os
import pathlib
import re
import stat
import sys
import tempfile
import types
import unittest
import unittest.mock

ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE = ROOT / "ansible" / "roles" / "claude_user_deny" / "library" / "claude_user_deny.py"
sys.path.insert(0, str(ROOT / "tests" / "lab"))
from helpers import tree_hash  # noqa: E402  (the same tree hash as the lab fixtures)

spec = importlib.util.spec_from_file_location("claude_user_deny", MODULE)
mod = importlib.util.module_from_spec(spec)
sys.dont_write_bytecode = True
spec.loader.exec_module(mod)

ME, MY_GROUP = os.getuid(), os.getgid()
ACCOUNT = "ai-test"
ENTRIES = ["Bash(ssh *)", "Read(~/.ssh/**)", "Edit(~/.ssh/**)", "Bash(sudo *)"]
IMMUTABLE = 0x10


def pwd_entry(name, uid, home):
    return types.SimpleNamespace(pw_name=name, pw_uid=uid, pw_gid=MY_GROUP, pw_dir=home)


def key(path):
    info = os.lstat(path)
    return info.st_dev, info.st_ino


class FakeOps(mod.Ops):
    """The real descriptor operations, except ownership and the attribute, which are recorded (the test user is not root)."""

    def __init__(self):
        self.owners, self.flags, self.hooks, self.calls = {}, {}, {}, []
        self.set_error = None
        self.devices = {}

    def owner_of(self, info):
        return self.owners.get((info.st_dev, info.st_ino), (info.st_uid, info.st_gid))

    def device_of(self, info):
        return self.devices.get((info.st_dev, info.st_ino), info.st_dev)

    def fchown(self, fd, uid, gid):
        info = os.fstat(fd)
        self.owners[(info.st_dev, info.st_ino)] = (uid, gid)
        self.calls.append(("fchown", uid, gid))

    def get_flags(self, fd):
        info = os.fstat(fd)
        return self.flags.get((info.st_dev, info.st_ino), 0)

    def set_flags(self, fd, flags):
        if flags & IMMUTABLE and self.set_error:
            raise OSError(self.set_error, os.strerror(self.set_error))
        info = os.fstat(fd)
        self.flags[(info.st_dev, info.st_ino)] = flags
        self.calls.append(("flags", bool(flags & IMMUTABLE)))

    def seam(self, name):
        if name in self.hooks:
            self.hooks.pop(name)()


class Case(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = pathlib.Path(tmp.name)
        (self.base / "home").mkdir()
        self.home = self.base / "home" / "ai"
        self.home.mkdir(mode=0o750)
        self.outside = self.base / "outside"
        (self.outside / "dir").mkdir(parents=True)
        (self.outside / "file").write_text("outside\n")
        self.ops = FakeOps()
        self.content = mod.canonical_content(ENTRIES)
        self.claude = self.home / ".claude"
        self.settings = self.claude / "settings.json"

    def place(self, check_mode=False, home=None, content=None):
        return mod.place_layer(self.ops, ACCOUNT, ME, MY_GROUP, str(home or self.home), content or self.content, check_mode)

    def make_layer(self, content=None, flags=IMMUTABLE, mode=0o644):
        """A layer as lab setup leaves it: root:root, immutable, in a directory the account owns."""
        self.claude.mkdir(mode=0o700, exist_ok=True)
        self.settings.write_bytes(content or self.content)
        self.settings.chmod(mode)
        self.ops.owners[key(self.settings)] = (0, 0)
        self.ops.flags[key(self.settings)] = flags

    def refused(self, *needles, command=False):
        with self.assertRaises(mod.Refusal) as caught:
            self.place()
        text = str(caught.exception)
        self.assertIn(ACCOUNT, text)
        for needle in needles:
            self.assertIn(needle, text)
        self.assertEqual("mv ~/.claude/settings.json ~/.claude/settings.json.pre-lab" in text, command, text)
        return text

    def assertUntouched(self, before):
        self.assertEqual(tree_hash(self.base), before)


class Content(unittest.TestCase):
    def test_the_canonical_object_has_the_two_settings_and_the_entries_in_order(self):
        text = mod.canonical_content(ENTRIES).decode()
        self.assertEqual(json.loads(text), {"enableAllProjectMcpServers": False,
                                            "permissions": {"deny": ENTRIES, "disableBypassPermissionsMode": "disable"}})
        self.assertEqual(text, json.dumps({"enableAllProjectMcpServers": False,
                                           "permissions": {"deny": ENTRIES, "disableBypassPermissionsMode": "disable"}}, indent=2) + "\n")
        self.assertEqual(list(json.loads(text)), ["enableAllProjectMcpServers", "permissions"])
        self.assertEqual(list(json.loads(text)["permissions"]), ["deny", "disableBypassPermissionsMode"])

    def test_the_deny_list_is_read_like_required_deny_txt(self):
        self.assertEqual(mod.parse_deny_list("# comment\n\nBash(ssh *)\n  # indented comment\nRead(~/.ssh/**)\n"), ["Bash(ssh *)", "Read(~/.ssh/**)"])

    def test_an_empty_list_and_a_repeated_entry_are_refused(self):
        for text in ("# only a comment\n", "Bash(ssh *)\nBash(ssh *)\n"):
            with self.assertRaises(mod.Refusal, msg=text):
                mod.parse_deny_list(text)

    def test_the_real_list_gives_ninety_entries_that_equal_required_deny_txt(self):
        text = (ROOT / "workspace" / "claude-user" / "required-deny.txt").read_text()
        entries = mod.parse_deny_list(text)
        self.assertEqual(len(entries), 90)
        self.assertEqual(json.loads(mod.canonical_content(entries))["permissions"]["deny"], entries)


class Write(Case):
    def test_a_missing_claude_directory_is_created_for_the_account_and_the_file_is_root_owned_immutable(self):
        result = self.place()
        self.assertTrue(result["changed"])
        self.assertEqual(stat.S_IMODE(os.lstat(self.claude).st_mode), 0o700)
        self.assertEqual(self.ops.owners[key(self.claude)], (ME, MY_GROUP))
        self.assertEqual(self.settings.read_bytes(), self.content)
        self.assertEqual(stat.S_IMODE(os.lstat(self.settings).st_mode), 0o644)
        self.assertEqual(self.ops.owners[key(self.settings)], (0, 0))
        self.assertTrue(self.ops.flags[key(self.settings)] & IMMUTABLE)
        self.assertEqual(sorted(os.listdir(self.claude)), ["settings.json"], "no temporary name is left")
        self.assertEqual(sorted(os.listdir(self.home)), [".claude"])

    def test_a_second_run_changes_nothing(self):
        self.place()
        before, inode = tree_hash(self.base), os.lstat(self.settings).st_ino
        self.ops.calls.clear()
        self.assertFalse(self.place()["changed"])
        self.assertEqual(tree_hash(self.base), before)
        self.assertEqual(os.lstat(self.settings).st_ino, inode)
        self.assertEqual(self.ops.calls, [])

    def test_a_dry_run_writes_nothing_and_reports_the_change(self):
        before = tree_hash(self.base)
        self.assertTrue(self.place(check_mode=True)["changed"])
        self.assertUntouched(before)
        self.assertEqual(self.ops.calls, [])

    def test_a_dry_run_on_a_complete_layer_reports_no_change(self):
        self.place()
        before = tree_hash(self.base)
        self.assertFalse(self.place(check_mode=True)["changed"])
        self.assertUntouched(before)

    def test_an_existing_claude_directory_of_the_account_is_kept_as_it_is(self):
        self.claude.mkdir(mode=0o755)
        (self.claude / "remote").mkdir()
        (self.claude / "state.json").write_text("{}")
        self.assertTrue(self.place()["changed"])
        self.assertEqual(stat.S_IMODE(os.lstat(self.claude).st_mode), 0o755)
        self.assertEqual(sorted(os.listdir(self.claude)), ["remote", "settings.json", "state.json"])

    def test_nothing_else_in_the_home_is_touched(self):
        (self.home / ".bashrc").write_text("x\n")
        (self.home / "work").mkdir()
        self.place()
        self.assertEqual(sorted(os.listdir(self.home)), [".bashrc", ".claude", "work"])
        self.assertEqual((self.home / ".bashrc").read_text(), "x\n")

    def test_changed_content_replaces_the_file_after_clearing_the_attribute_and_sets_it_again(self):
        self.make_layer(mod.canonical_content(ENTRIES[:2]))
        old = os.lstat(self.settings).st_ino
        self.assertTrue(self.place()["changed"])
        self.assertEqual(self.settings.read_bytes(), self.content)
        self.assertNotEqual(os.lstat(self.settings).st_ino, old)
        flags = [call for call in self.ops.calls if call[0] == "flags"]
        self.assertEqual(flags, [("flags", False), ("flags", True)], "cleared before the replacement, set after it")
        self.assertTrue(self.ops.flags[key(self.settings)] & IMMUTABLE)
        self.assertEqual(self.ops.owners[key(self.settings)], (0, 0))
        self.assertEqual(sorted(os.listdir(self.claude)), ["settings.json"])

    def test_a_root_file_without_the_attribute_or_with_another_mode_is_replaced(self):
        for flags, mode in ((0, 0o644), (IMMUTABLE, 0o664)):
            with self.subTest(flags=flags, mode=oct(mode)):
                self.make_layer(flags=flags, mode=mode)
                self.assertTrue(self.place()["changed"])
                self.assertEqual(stat.S_IMODE(os.lstat(self.settings).st_mode), 0o644)
                self.assertTrue(self.ops.flags[key(self.settings)] & IMMUTABLE)
                self.assertFalse(self.place()["changed"])
                self.ops.owners.clear()
                self.ops.flags.clear()


class Refusals(Case):
    """PA-A35: each refusal names the account and the path and changes nothing, link targets included."""

    def test_claude_a_symbolic_link_to_a_directory(self):
        (self.outside / "dir" / "settings.json").write_text("keep\n")
        self.claude.symlink_to(self.outside / "dir")
        before = tree_hash(self.base)
        self.refused(str(self.claude))
        self.assertUntouched(before)
        self.assertEqual((self.outside / "dir" / "settings.json").read_text(), "keep\n")

    def test_claude_a_dangling_link_and_a_regular_file(self):
        self.claude.symlink_to(self.base / "missing")
        before = tree_hash(self.base)
        self.refused(str(self.claude))
        self.assertUntouched(before)
        self.claude.unlink()
        self.claude.write_text("a file\n")
        before = tree_hash(self.base)
        self.refused(str(self.claude))
        self.assertUntouched(before)

    def test_claude_not_owned_by_the_account(self):
        self.claude.mkdir(mode=0o700)
        self.ops.owners[key(self.claude)] = (0, 0)
        before = tree_hash(self.base)
        self.refused(str(self.claude), "not owned by")
        self.assertUntouched(before)

    def test_settings_a_symbolic_link(self):
        self.claude.mkdir(mode=0o700)
        self.settings.symlink_to(self.outside / "file")
        before = tree_hash(self.base)
        self.refused(str(self.settings), "link")
        self.assertUntouched(before)
        self.assertEqual((self.outside / "file").read_text(), "outside\n")

    def test_settings_a_hard_link_prints_no_command(self):
        self.make_layer()
        os.link(self.settings, self.outside / "hard")
        before = tree_hash(self.base)
        self.refused(str(self.settings), "hard")
        self.assertUntouched(before)

    def test_settings_a_directory_a_fifo_and_a_symlink_loop(self):
        self.claude.mkdir(mode=0o700)
        self.settings.mkdir()
        before = tree_hash(self.base)
        self.refused(str(self.settings), "not a regular file")
        self.assertUntouched(before)
        self.settings.rmdir()
        os.mkfifo(self.settings)
        before = tree_hash(self.base)
        self.refused(str(self.settings), "not a regular file")
        self.assertUntouched(before)

    def test_settings_owned_by_the_account_names_the_move_aside_command_and_a_second_run_succeeds_after_it(self):
        self.claude.mkdir(mode=0o700)
        self.settings.write_text('{"mine": true}\n')
        before = tree_hash(self.base)
        text = self.refused(str(self.settings), "owned by", command=True)
        self.assertUntouched(before)
        self.assertEqual(self.settings.read_text(), '{"mine": true}\n', "nothing is removed or moved")
        os.rename(self.settings, self.claude / "settings.json.pre-lab")  # what the account runs, in its own terminal
        self.assertTrue(self.place()["changed"])
        self.assertEqual(self.settings.read_bytes(), self.content)
        self.assertEqual((self.claude / "settings.json.pre-lab").read_text(), '{"mine": true}\n')
        self.assertIn("lab setup", text)

    def test_settings_owned_by_another_account_prints_no_command(self):
        self.make_layer()
        self.ops.owners[key(self.settings)] = (ME + 1, MY_GROUP)
        before = tree_hash(self.base)
        self.refused(str(self.settings), "not owned by root")
        self.assertUntouched(before)

    def test_the_home_a_link_or_not_owned_by_the_account_or_not_a_directory(self):
        link = self.base / "home" / "link"
        link.symlink_to(self.home)
        plain = self.base / "home" / "plain"
        plain.write_text("x")
        before = tree_hash(self.base)
        with self.assertRaises(mod.Refusal) as caught:
            self.place(home=link)
        self.assertIn(ACCOUNT, str(caught.exception))
        self.assertIn(str(link), str(caught.exception))
        self.assertUntouched(before)
        self.ops.owners[key(self.home)] = (0, 0)
        with self.assertRaises(mod.Refusal) as caught:
            self.place()
        self.assertIn("not owned by", str(caught.exception))
        self.assertUntouched(before)
        with self.assertRaises(mod.Refusal):
            self.place(home=plain)
        with self.assertRaises(mod.Refusal):
            self.place(home=self.base / "home" / "nobody")
        self.assertUntouched(before)

    def test_a_relative_home_is_refused(self):
        with self.assertRaises(mod.Refusal):
            mod.place_layer(self.ops, ACCOUNT, ME, MY_GROUP, "home/ai", self.content, False)

    def test_a_dry_run_refuses_too(self):
        self.claude.symlink_to(self.outside / "dir")
        before = tree_hash(self.base)
        with self.assertRaises(mod.Refusal):
            self.place(check_mode=True)
        self.assertUntouched(before)


class Seams(Case):
    """PA-A35: a rename or a link planted between two steps of the module cannot redirect the write."""

    def test_claude_renamed_and_replaced_by_a_link_after_it_was_checked_leaves_every_other_path_unchanged(self):
        outside_before = tree_hash(self.outside)

        def swap():
            os.rename(self.claude, self.home / ".claude.moved")
            self.claude.symlink_to(self.outside / "dir")

        self.claude.mkdir(mode=0o700)
        self.ops.hooks["after-claude-open"] = swap
        self.place()
        self.assertEqual(tree_hash(self.outside), outside_before)
        self.assertTrue(self.claude.is_symlink())
        self.assertEqual((self.home / ".claude.moved" / "settings.json").read_bytes(), self.content, "the write landed in the checked directory")

    def test_the_directory_created_by_the_module_swapped_for_a_link_leaves_outside_paths_unchanged(self):
        outside_before = tree_hash(self.outside)

        def swap():
            os.rename(self.claude, self.home / ".claude.moved")
            self.claude.symlink_to(self.outside / "dir")

        self.ops.hooks["after-claude-open"] = swap
        self.place()
        self.assertEqual(tree_hash(self.outside), outside_before)

    def test_the_home_swapped_for_a_link_after_it_was_checked_leaves_every_other_path_unchanged(self):
        outside_before = tree_hash(self.outside)

        def swap():
            os.rename(self.home, self.base / "home" / "ai.moved")
            self.home.symlink_to(self.outside / "dir")

        self.ops.hooks["after-home-open"] = swap
        self.place()
        self.assertEqual(tree_hash(self.outside), outside_before)
        self.assertTrue((self.base / "home" / "ai.moved" / ".claude" / "settings.json").is_file())

    def test_settings_renamed_after_the_rename_clears_the_attribute_removes_the_stray_file_and_fails(self):
        moved = self.claude / "settings.moved"

        def swap():
            os.rename(self.settings, moved)

        self.ops.hooks["before-attr"] = swap
        with self.assertRaises(mod.Refusal) as caught:
            self.place()
        self.assertIn(ACCOUNT, str(caught.exception))
        self.assertIn(str(self.settings), str(caught.exception))
        self.assertEqual(os.listdir(self.claude), [], "the stray file is removed")
        self.assertFalse(any(flags & IMMUTABLE for flags in self.ops.flags.values()), "the attribute is cleared again")

    def test_settings_replaced_by_the_accounts_own_file_after_the_rename_fails_and_clears_the_attribute(self):
        moved = self.claude / "settings.moved"

        def swap():
            os.rename(self.settings, moved)
            self.settings.write_text("mine\n")

        self.ops.hooks["before-attr"] = swap
        with self.assertRaises(mod.Refusal):
            self.place()
        self.assertFalse(moved.exists(), "the file lab setup wrote is removed")
        self.assertFalse(any(flags & IMMUTABLE for flags in self.ops.flags.values()))
        self.assertEqual(self.settings.read_text(), "mine\n", "the account's own file is not touched")


class AttributeFailure(Case):
    def test_a_failed_attribute_call_removes_the_new_file_and_a_directory_it_created_and_names_the_errno(self):
        self.ops.set_error = errno.ENOTSUP
        before = tree_hash(self.base)
        with self.assertRaises(mod.Refusal) as caught:
            self.place()
        text = str(caught.exception)
        self.assertIn(ACCOUNT, text)
        self.assertIn("ENOTSUP", text)
        self.assertIn("does not support", text)
        self.assertUntouched(before)

    def test_a_failed_attribute_call_keeps_a_directory_that_was_already_there(self):
        self.claude.mkdir(mode=0o700)
        (self.claude / "state.json").write_text("{}")
        self.ops.set_error = errno.EPERM
        before = tree_hash(self.base)
        with self.assertRaises(mod.Refusal) as caught:
            self.place()
        self.assertIn("EPERM", str(caught.exception))
        self.assertIn("CAP_LINUX_IMMUTABLE", str(caught.exception))
        self.assertUntouched(before)

    def test_a_failed_attribute_call_on_a_replacement_leaves_no_file_that_looks_protected(self):
        self.make_layer(mod.canonical_content(ENTRIES[:1]))
        self.ops.set_error = errno.ENOTTY
        with self.assertRaises(mod.Refusal):
            self.place()
        self.assertFalse(self.settings.exists(), "no root-owned file the account could delete is left looking protected")
        self.assertEqual(os.listdir(self.claude), [])


class Probe(Case):
    """PA-51: the probe runs before any change, on the filesystem of the home, in a root-owned directory, and leaves nothing."""

    def root_parent(self):
        self.ops.owners[key(self.home.parent)] = (0, 0)
        os.chmod(self.home.parent, 0o755)  # the umask of the test run must not make it group-writable

    def test_it_sets_and_clears_the_attribute_on_a_scratch_file_and_leaves_nothing(self):
        self.root_parent()
        before = tree_hash(self.base)
        message = mod.probe_attribute(self.ops, ACCOUNT, str(self.home))
        self.assertIn("immutable attribute", message)
        self.assertUntouched(before)
        self.assertEqual([call for call in self.ops.calls if call[0] == "flags"], [("flags", True), ("flags", False)])

    def test_an_unsupported_filesystem_fails_naming_the_errno_and_leaves_nothing(self):
        self.root_parent()
        self.ops.set_error = errno.ENOTTY
        before = tree_hash(self.base)
        with self.assertRaises(mod.Refusal) as caught:
            mod.probe_attribute(self.ops, ACCOUNT, str(self.home))
        self.assertIn("ENOTTY", str(caught.exception))
        self.assertIn("lab_deny_layer=managed", str(caught.exception))
        self.assertUntouched(before)

    def test_a_missing_capability_names_it(self):
        self.root_parent()
        self.ops.set_error = errno.EPERM
        with self.assertRaises(mod.Refusal) as caught:
            mod.probe_attribute(self.ops, ACCOUNT, str(self.home))
        self.assertIn("CAP_LINUX_IMMUTABLE", str(caught.exception))

    def test_a_parent_that_root_does_not_own_is_no_place_for_the_scratch_file(self):
        with self.assertRaises(mod.Refusal) as caught:
            mod.probe_attribute(self.ops, ACCOUNT, str(self.home))
        self.assertIn("root-owned directory", str(caught.exception))
        self.assertEqual(os.listdir(self.home.parent), ["ai"])

    def test_a_home_on_a_filesystem_of_its_own_has_no_root_owned_directory_beside_it(self):
        self.root_parent()
        self.ops.devices[key(self.home)] = -1
        with self.assertRaises(mod.Refusal) as caught:
            mod.probe_attribute(self.ops, ACCOUNT, str(self.home))
        self.assertIn("same filesystem", str(caught.exception))

    def test_a_parent_the_account_can_write_is_refused(self):
        self.root_parent()
        os.chmod(self.home.parent, 0o777)
        with self.assertRaises(mod.Refusal):
            mod.probe_attribute(self.ops, ACCOUNT, str(self.home))
        os.chmod(self.home.parent, 0o755)


class Main(Case):
    """The Ansible entry point: the home comes from the account database; a dry run writes nothing; a refusal is a failed task."""

    def run_module(self, params, check_mode=False, name=ACCOUNT, home=None, uid=ME):
        """Run main() with a stand-in for AnsibleModule (the real class differs between ansible-core releases, and its argument
        parsing is not what is tested): it fills the defaults of the argument spec, prints what the module returns, and exits."""
        entry = pwd_entry(name, uid, str(home or self.home))

        def lookup(user):
            if user != name:
                raise KeyError(user)
            return entry

        class FakeModule:
            def __init__(self, argument_spec, supports_check_mode=False):
                self.params = {key: params.get(key, spec.get("default")) for key, spec in argument_spec.items()}
                self.check_mode = check_mode and supports_check_mode

            def exit_json(self, **result):
                print(json.dumps(result))
                raise SystemExit(0)

            def fail_json(self, **result):
                print(json.dumps({**result, "failed": True}))
                raise SystemExit(1)

        fake = types.SimpleNamespace(AnsibleModule=FakeModule)
        modules = {"ansible": types.ModuleType("ansible"), "ansible.module_utils": types.ModuleType("ansible.module_utils"),
                   "ansible.module_utils.basic": fake}
        with unittest.mock.patch.dict(sys.modules, modules), unittest.mock.patch.object(mod.pwd, "getpwnam", lookup):
            with self.assertRaises(SystemExit):
                mod.main()

    def result(self, params, **kwargs):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.run_module(params, **kwargs)
        return json.loads(out.getvalue())

    def deny_file(self):
        path = self.base / "deny.txt"
        path.write_text("# list\n" + "\n".join(ENTRIES) + "\n")
        return str(path)

    def test_a_dry_run_reports_the_change_and_writes_nothing(self):
        deny = self.deny_file()
        before = tree_hash(self.base)
        out = self.result({"user": ACCOUNT, "action": "write", "deny_list": deny}, check_mode=True)
        self.assertTrue(out["changed"])
        self.assertEqual(out["entries"], len(ENTRIES))
        self.assertEqual(tree_hash(self.base), before)
        self.assertEqual(os.listdir(self.home), [])

    def test_a_refusal_is_a_failed_task_that_names_the_account_and_the_path(self):
        self.claude.symlink_to(self.outside / "dir")
        out = self.result({"user": ACCOUNT, "action": "write", "deny_list": self.deny_file()}, check_mode=True)
        self.assertTrue(out["failed"])
        self.assertIn(ACCOUNT, out["msg"])
        self.assertIn(str(self.claude), out["msg"])

    def test_root_and_an_unknown_account_are_refused(self):
        out = self.result({"user": "root", "action": "probe"}, name="root", uid=0)
        self.assertTrue(out["failed"])
        out = self.result({"user": "nobody-here", "action": "probe"})
        self.assertTrue(out["failed"])

    def test_a_write_needs_the_list_and_an_empty_list_is_refused(self):
        out = self.result({"user": ACCOUNT, "action": "write"})
        self.assertTrue(out["failed"])
        empty = self.base / "empty.txt"
        empty.write_text("# nothing\n")
        out = self.result({"user": ACCOUNT, "action": "write", "deny_list": str(empty)})
        self.assertTrue(out["failed"])
        self.assertEqual(os.listdir(self.home), [])


class Static(unittest.TestCase):
    text = MODULE.read_text()

    def test_the_module_is_standard_library_python_without_a_shell_or_a_chattr_command(self):
        for banned in ("subprocess", "os.system", "os.popen", "shell=True", "chattr", "shutil", "pathlib"):
            self.assertNotIn(banned, self.text, banned)
        self.assertIsNone(re.search(r"(?<![\w.])open\(", self.text), "the builtin open() follows links; use os.open")
        imports = set(re.findall(r"^(?:import|from) ([a-z_.]+)", self.text, re.M))
        self.assertLessEqual(imports, {"errno", "fcntl", "json", "os", "pwd", "stat", "struct"},
                             imports)

    def test_the_module_works_on_descriptors_and_never_follows_a_link(self):
        for needed in ("O_NOFOLLOW", "O_DIRECTORY", "dir_fd=", "follow_symlinks=False", "O_EXCL", "FS_IOC_SETFLAGS", "os.fsync",
                       "supports_check_mode=True"):
            self.assertIn(needed, self.text, needed)

    def test_the_documentation_names_the_parameters(self):
        for name in ("user", "action", "deny_list"):
            self.assertRegex(self.text, rf"(?m)^  {name}:", name)

    def test_the_home_comes_from_the_account_database_not_the_environment(self):
        self.assertIn("pwd.getpwnam", self.text)
        self.assertNotIn("os.environ", self.text)
        self.assertNotIn("expanduser", self.text)


if __name__ == "__main__":
    unittest.main()
