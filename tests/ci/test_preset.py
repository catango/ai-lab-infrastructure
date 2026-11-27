"""CR-57 plan PR 10 (`preset`): this platform's preset for the template (ADR-008 decision 14): `docs/PLATFORM.md`, the deny list source
`.claude/deny.platform.txt`, and the preset configuration `config/preset.yaml` (PA-A9, PA-A10, PA-A1 final run, ADR-010 size budget,
design interactions I-8 and I-12).

Text checks over this repository only. The template repository has no built files to read (O-13, U-9), so nothing here claims a check
against it. The words the removal PRs search for are built from parts, so this file does not itself match the PA-A1 command.
"""
import importlib.machinery
import importlib.util
import pathlib
import re
import shlex
import shutil
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLATFORM = "docs/PLATFORM.md"
DENY = ".claude/deny.platform.txt"
CONFIG = "config/preset.yaml"
PRESET_FILES = (PLATFORM, DENY, CONFIG)


def read(rel):
    return (ROOT / rel).read_text()


def parts(*pieces):
    return "".join(pieces)


A, B, C, LABVM, OPVM, LABOP = (parts("o", "ci"), parts("terra", "form"), parts("to", "fu"), parts("lab", " vm"),
                               parts("operator", " vm"), parts("lab", " operator"))
STALE_TERMS = re.compile(rf"\b({A}|{B}|{C}|open{C}|{LABVM}|{OPVM}|{LABOP})\b", re.I)
FIXED_WINDOW = re.compile(r"\b[0-9]{1,3}(\.[0-9]{1,3}){3}\b|[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z]{2,}|SHA256:[A-Za-z0-9+/]{20,}")


def project_value(section, key):
    """One scalar of `config/project.yaml` under a top-level section (the file is flat enough for this; no YAML library is assumed)."""
    block = re.search(rf"^{section}:\n((?:[ \t]+.*\n|[ \t]*\n|#.*\n)+)", read("config/project.yaml"), re.M)
    value = re.search(rf"^[ \t]+{key}:[ \t]*\"?([^\"#\n]*?)\"?[ \t]*(?:#.*)?$", block.group(1), re.M)
    return value.group(1).strip()


def preset_value(key):
    value = re.search(rf"^[ \t]*{key}:[ \t]*\"?([^\"#\n]*?)\"?[ \t]*(?:#.*)?$", read(CONFIG), re.M)
    return value.group(1).strip() if value else None


def rules(rel):
    return [l for l in read(rel).splitlines() if l.strip() and not l.lstrip().startswith("#")]


class Files(unittest.TestCase):
    def test_the_preset_files_exist(self):
        for rel in PRESET_FILES:
            self.assertTrue((ROOT / rel).is_file(), rel)


class Pa9NoRemovedSubjects(unittest.TestCase):
    """PA-A9: none of the removed subjects (the cloud CLI, the infrastructure tools, the lab-hosted operator machine) is in the preset."""

    def test_no_preset_file_names_a_removed_subject(self):
        for rel in PRESET_FILES:
            hits = [m.group(0) for m in STALE_TERMS.finditer(read(rel))]
            self.assertEqual(hits, [], rel)

    @unittest.skipUnless(shutil.which("rg"), "ripgrep is required")
    def test_the_recorded_pa_a9_command_prints_nothing(self):
        command = ["rg", "-n", "-i", "-w", "-e", A, "-e", B, "-e", LABOP, PLATFORM, DENY]
        run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        self.assertEqual((run.stdout, run.stderr, run.returncode), ("", "", 1))

    def test_no_preset_file_names_an_address_an_email_or_a_fingerprint(self):
        for rel in PRESET_FILES:
            self.assertEqual(FIXED_WINDOW.findall(read(rel)), [], rel)

    def test_no_preset_file_names_an_account_but_the_owner_of_the_repository_path(self):
        """The machine account is named nowhere. The owner login of the platform repository (the approver's account at this revision) is
        only the owner part of a public repository path: inside a qualified reference of PLATFORM.md and on the `owner:` line of the
        configuration."""
        owner, repo = project_value("github", "owner"), project_value("project", "name")
        for rel in PRESET_FILES:
            text = read(rel)
            self.assertNotIn(project_value("github", "machine_login"), text, rel)
            text = re.sub(rf"{re.escape(owner)}/{re.escape(repo)}:ADR-[0-9]+", "", text)
            text = re.sub(rf"^[ \t]*owner:[ \t]*{re.escape(owner)}[ \t]*$", "", text, flags=re.M)
            self.assertNotIn(project_value("github", "approver_login"), text, rel)
            self.assertNotIn(owner, text, rel)


class Budget(unittest.TestCase):
    """ADR-010 decision 2: `docs/PLATFORM.md` 80 lines and 6 KiB, read from the ADR so the value is not copied here."""

    def limits(self):
        adr = next((ROOT / "docs" / "adr").glob("ADR-010-*.md")).read_text()
        match = re.search(r"`docs/PLATFORM\.md` and `docs/PROJECT\.md` ([0-9]+) lines and ([0-9]+) KiB each", adr)
        return int(match.group(1)), int(match.group(2)) * 1024

    def test_platform_md_is_within_the_line_and_byte_budget(self):
        lines, size = self.limits()
        self.assertEqual((lines, size), (80, 6144))
        raw = (ROOT / PLATFORM).read_bytes()
        self.assertLessEqual(len(raw.splitlines()), lines)
        self.assertLessEqual(len(raw), size)


class PlatformMd(unittest.TestCase):
    def setUp(self):
        self.text = read(PLATFORM)
        self.owner, self.repo = project_value("github", "owner"), project_value("project", "name")

    def test_it_holds_no_import_and_no_front_matter(self):
        """ADR-008 decision 5: the imported files contain no import."""
        for number, line in enumerate(self.text.splitlines(), 1):
            self.assertFalse(line.lstrip().startswith("@"), f"line {number}")
        self.assertFalse(self.text.startswith("---"))

    def test_every_record_reference_is_qualified_by_owner_and_repository(self):
        """I-8, ADR-008 decision 13: `<owner>/<repo>:ADR-<n>`, never a relative link that would break in the template."""
        references = [m for m in re.finditer(r"ADR-[0-9]+", self.text)]
        self.assertTrue(references)
        for match in references:
            before = self.text[max(0, match.start() - len(self.owner) - len(self.repo) - 2):match.start()]
            self.assertEqual(before, f"{self.owner}/{self.repo}:", match.group(0))

    def test_it_points_to_both_adr_011_and_adr_012(self):
        for number in ("011", "012"):
            self.assertIn(f"{self.owner}/{self.repo}:ADR-{number}", self.text)

    def test_it_has_no_relative_link_and_no_path_into_the_records(self):
        self.assertEqual(re.findall(r"\]\([^)]*\)", self.text), [])
        for fragment in ("docs/adr", "docs/cr", "docs/architecture", "../"):
            self.assertNotIn(fragment, self.text)

    def test_the_repository_name_appears_only_inside_the_qualified_references(self):
        """I-12: the name comes from the configuration; outside the references it is not in the prose."""
        outside = re.sub(rf"{re.escape(self.owner)}/{re.escape(self.repo)}:ADR-[0-9]+", "", self.text)
        self.assertNotIn(self.repo, outside)
        self.assertNotIn(self.owner, outside)

    def test_it_describes_the_multi_project_operator_machine(self):
        """PA-42 and ADR-012 decision 12."""
        text = " ".join(self.text.split())
        for fragment in ("operator machine", "release tag", "root-owned", "output directory", "one at a time", "T2", "T3",
                         "this project's repositories", "operator_paths"):
            self.assertIn(fragment, text)

    def test_it_states_where_claude_code_runs_and_what_it_never_reaches(self):
        text = " ".join(self.text.split())
        for fragment in ("AI lab", "Debian 13", "x86-64", "ephemeral", "AI user", "docs/PROJECT.md", ".claude/deny.platform.txt", "amd64"):
            self.assertIn(fragment, text)

    def test_it_does_not_reach_for_an_older_term(self):
        self.assertNotIn("workspace", self.text.lower())


class PresetConfiguration(unittest.TestCase):
    """I-12: the repository name is in `config/project.yaml` and in the preset's configuration, and the rename follow-up (plan row C)
    changes both. The qualified references of PLATFORM.md must follow the same name, so a rename that updates only the configuration fails
    here instead of leaving a dead reference in every generated repository."""

    def test_the_platform_repository_is_the_project_of_the_configuration(self):
        self.assertEqual(preset_value("repository"), project_value("project", "name"))
        self.assertEqual(preset_value("owner"), project_value("github", "owner"))

    def test_the_configuration_names_the_two_seeded_files_it_supplies(self):
        self.assertEqual(preset_value("platform_md"), PLATFORM)
        self.assertEqual(preset_value("deny_platform"), DENY)
        for rel in (PLATFORM, DENY):
            self.assertTrue((ROOT / rel).is_file())

    def test_the_name_is_stated_once_in_the_configuration(self):
        self.assertEqual(len(re.findall(re.escape(project_value("project", "name")), read(CONFIG))), 1)


class DenySource(unittest.TestCase):
    """PA-A10: the preset's deny list source adds no rule and changes nothing this repository's deny files hold."""

    RULE = re.compile(r"[A-Z][A-Za-z]*\(.+\)")

    def test_it_holds_rule_lines_and_comments_only(self):
        self.assertTrue(rules(DENY))
        for line in rules(DENY):
            self.assertRegex(line, self.RULE)

    def test_no_entry_is_listed_twice(self):
        entries = rules(DENY)
        self.assertEqual(len(entries), len(set(entries)))

    def test_every_entry_is_already_in_the_core_list_and_in_the_repository_settings(self):
        """The preset introduces no rule that this repository's own files do not carry, so none of the three files has to change."""
        import json
        core = rules("workspace/claude-user/required-deny.txt")
        settings = json.loads(read(".claude/settings.json"))["permissions"]["deny"]
        for entry in rules(DENY):
            self.assertIn(entry, core, entry)
            self.assertIn(entry, settings, entry)

    def test_lab_setup_adds_nothing_when_this_repository_is_the_project(self):
        """The merge of lab setup (I-7) keeps the core byte for byte and adds only entries the core lacks: none here."""
        loader = importlib.machinery.SourceFileLoader("lab_project_input",
                                                      str(ROOT / "ansible" / "roles" / "lab_project" / "files" / "lab-project-input"))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
        core_text = read("workspace/claude-user/required-deny.txt")
        text, entries, added = module.merge_deny(core_text, read(DENY), "this repository", "0" * 40)
        self.assertEqual((text, added), (core_text, []))

    def test_it_names_no_credential_path_of_a_project(self):
        """Credential paths are the project's (I-7, PA-43); the preset lists none of its own beyond what the core lists."""
        self.assertNotRegex(read(DENY), r"~/\.config/(?!gh/)")


class Pa1(unittest.TestCase):
    """PA-A1 with the recorded command as the acceptance file holds it (amended by design PR 75): it prints nothing."""

    @staticmethod
    def command():
        text = read("docs/cr/CR-57/acceptance-criteria.md")
        block = text.split("## The PA-A1 command", 1)[1].split("```bash\n", 1)[1].split("```", 1)[0]
        return shlex.split(block.replace("\\\n", " "))

    @unittest.skipUnless(shutil.which("rg"), "ripgrep is required")
    def test_the_recorded_command_prints_nothing(self):
        command = self.command()
        self.assertEqual(command[0], "rg")
        run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        self.assertEqual((run.stdout, run.returncode), ("", 1))


if __name__ == "__main__":
    unittest.main()
