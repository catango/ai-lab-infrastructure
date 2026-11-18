"""Release-tag commit check (ADR-011 decision 3, design section 4 rule 4).

HEAD must equal the commit of a release tag (v<number>...) and be contained in origin/main, with no local changes.
Reasons are fixed text: no path, output, or name from the repository is printed.
"""
import re
import sys
from dataclasses import dataclass

from . import exitcodes, process

NOT_A_REPO = "not a git repository"
LOCAL_CHANGES = "local changes in the clone"
NO_TAG = "HEAD is not a release tag"
NOT_IN_MAIN = "the release tag is not contained in origin/main (fetch first)"
FAILED = "the commit check could not run"
_TAG = re.compile(r"v[0-9]+(?:\.[0-9]+)*(?:[-+][0-9A-Za-z.]+)?")
_SHA = re.compile(r"[0-9a-f]{40}")


@dataclass(frozen=True)
class ReleaseCheck:
    ok: bool
    commit: str = ""
    tag: str = ""
    reason: str = ""


def _git(repo, *args):
    return process.run(["git", "-C", str(repo), *args], allow=frozenset({"git"}), timeout=30,
                       extra_env={"GIT_TERMINAL_PROMPT": "0"})


def check_release_commit(repo):
    try:
        if _git(repo, "rev-parse", "--git-dir").returncode != 0:
            return ReleaseCheck(False, reason=NOT_A_REPO)
        status = _git(repo, "status", "--porcelain", "--untracked-files=all")
        if status.returncode != 0 or status.truncated:
            return ReleaseCheck(False, reason=FAILED)
        if status.stdout.strip():
            return ReleaseCheck(False, reason=LOCAL_CHANGES)
        head = _git(repo, "rev-parse", "HEAD")
        commit = head.stdout.strip()
        if head.returncode != 0 or not _SHA.fullmatch(commit):
            return ReleaseCheck(False, reason=FAILED)
        tags = _git(repo, "tag", "--points-at", "HEAD", "--list", "v*")
        names = sorted(t for t in tags.stdout.split() if _TAG.fullmatch(t)) if tags.returncode == 0 else []
        if not names:
            return ReleaseCheck(False, commit, reason=NO_TAG)
        contained = _git(repo, "merge-base", "--is-ancestor", "HEAD", "refs/remotes/origin/main").returncode == 0
        if not contained:
            return ReleaseCheck(False, commit, names[-1], NOT_IN_MAIN)
        return ReleaseCheck(True, commit, names[-1])
    except (process.CommandMissing, process.CommandTimeout, process.PolicyViolation):
        return ReleaseCheck(False, reason=FAILED)


def require_release_commit(repo, out=print):
    """Print the commit and tag and return the check, or print the reason and exit with status 1."""
    result = check_release_commit(repo)
    if not result.ok:
        out(f"refused: {result.reason}")
        sys.exit(exitcodes.FAILED)
    out(f"commit {result.commit[:12]} at release tag {result.tag}")
    return result
