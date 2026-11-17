"""Shared builders for the pr-contract tests (standard library only)."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "scripts"))

from pr_contract.errors import ApiError, NotFound  # noqa: E402
from pr_contract.model import FileChange, PullRequest  # noqa: E402

TEMPLATES = ROOT / ".github" / "PULL_REQUEST_TEMPLATE"
FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"
TYPES = ("design", "implementation", "change", "infra", "toolchain")


def template_lines(kind):
    return (TEMPLATES / f"{kind}.md").read_text().splitlines()


def headings(kind):
    return [line[3:].strip() for line in template_lines(kind) if line.startswith("## ")]


def body(kind, *, omit=(), empty=(), comment_only=(), sections=None, top="", marker=True,
         extra="", newline="\n"):
    """A PR body built from the real template: marker comment, then every section filled in."""
    sections = sections or {}
    out = []
    if marker:
        out.append(template_lines(kind)[0])
    if top:
        out.extend(top.rstrip("\n").split("\n"))
        out.append("")
    for heading in headings(kind):
        if heading in omit:
            continue
        out.append(f"## {heading}")
        if heading in comment_only:
            out.append("<!-- Restates the template comment only. -->")
        elif heading in empty:
            out.append("")
        else:
            default = {"Change request": "CR: #2", "Checkpoint": "- [ ] item"}.get(heading, "Filled in for the test.")
            out.append(sections.get(heading, default))
        out.append("")
    if extra:
        out.append(extra)
    return newline.join(out)


IMPL_TOP = "Implements: #2\nDesign: #3\n"


def make_pr(kind="implementation", **over):
    base = dict(
        number=10, title="A title", body="", state="open", draft=True, merged=False,
        author="example-author", head_ref="impl/CR-2-thing", base_ref="main", changed_files=1,
    )
    if kind == "design":
        base.update(head_ref="design/CR-2-thing", body=body("design"))
    elif kind == "implementation":
        base.update(body=body("implementation", top=IMPL_TOP))
    elif kind == "change":
        base.update(head_ref="change/1-thing", body=body("change"))
    elif kind == "infra":
        base.update(head_ref="infra/thing", body=body("infra"))
    elif kind == "toolchain":
        base.update(head_ref="toolchain/thing", body=body("toolchain"))
    base.update(over)
    return PullRequest(**base)


def fc(path, status="modified", previous=None, patch=None):
    return FileChange(path=path, status=status, previous=previous, patch=patch)


class MemClient:
    """In-memory stand-in for the GitHub client: PRs, files, and issue kinds by number."""

    def __init__(self, prs=None, files=None, issues=None, fail=None):
        design = make_pr("design", number=3, state="closed", draft=False, merged=True)
        self.prs = {3: design}
        self.prs.update(prs or {})
        self.files = files or {}
        self.issues = {2: "issue"}
        self.issues.update(issues or {})
        self.fail = fail
        self.calls = []

    def _check(self, name, number):
        self.calls.append((name, number))
        if self.fail is not None:
            raise self.fail

    def pull(self, number):
        self._check("pull", number)
        if number not in self.prs:
            raise NotFound(f"pull {number}")
        return self.prs[number]

    def pull_files(self, number):
        self._check("pull_files", number)
        return list(self.files.get(number, []))

    def issue_kind(self, number):
        self._check("issue_kind", number)
        if number not in self.issues:
            raise NotFound(f"issue {number}")
        return self.issues[number]


__all__ = ["ApiError", "NotFound", "ROOT", "TEMPLATES", "FIXTURES", "TYPES", "headings", "body",
           "make_pr", "fc", "MemClient", "IMPL_TOP", "template_lines"]
