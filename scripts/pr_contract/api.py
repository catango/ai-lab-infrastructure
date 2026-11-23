"""Read-only GitHub REST client (urllib) and an offline fixture client with the same interface.

The API host is fixed, redirects are not followed, every call has a timeout and a size cap,
and the token is only ever placed in one request header. Error messages are fixed text.
"""
import base64
import binascii
import http.client
import json
import re
import urllib.error
import urllib.request
from pathlib import Path

from . import config
from .errors import ApiError, InputError, LimitExceeded, NotFound
from .model import FileChange, PullRequest

API_BASE = "https://api.github.com"
MAX_FILES = 3000
PAGE_SIZE = 100
MAX_PAGES = MAX_FILES // PAGE_SIZE
MAX_RESPONSE_BYTES = 10 * 1024 * 1024
TIMEOUT_SECONDS = 15

MAX_CONFIG_BYTES = config.MAX_TEXT
_SHA = re.compile(r"[0-9a-f]{40}")
_REPO = re.compile(r"[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}")


def check_repo(repo):
    if not isinstance(repo, str) or not _REPO.fullmatch(repo) or any(part in (".", "..") for part in repo.split("/")):
        raise InputError("invalid --repo (expected owner/name)")
    return repo


def check_number(number):
    if not isinstance(number, int) or isinstance(number, bool) or not 1 <= number <= 999_999_999:
        raise InputError("invalid pull request or issue number")
    return number


def parse_files(data):
    if not isinstance(data, list):
        raise ApiError("malformed response")
    return [FileChange.from_api(item) for item in data]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class GitHubClient:
    def __init__(self, repo, token=None, base=API_BASE, opener=None, timeout=TIMEOUT_SECONDS):
        self.repo = check_repo(repo)
        self._token = token or None
        self._base = base.rstrip("/")
        self._opener = opener or urllib.request.build_opener(_NoRedirect)
        self._timeout = timeout

    def _get(self, path):
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "pr-contract"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        request = urllib.request.Request(f"{self._base}{path}", headers=headers, method="GET")
        try:
            with self._opener.open(request, timeout=self._timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as error:
            self._raise_for_status(error)
        except (urllib.error.URLError, OSError, ValueError, http.client.HTTPException) as error:
            raise ApiError(f"network error ({type(error).__name__})") from None
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ApiError("response too large")
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError, RecursionError):
            raise ApiError("malformed response") from None

    @staticmethod
    def _raise_for_status(error):
        code = error.code
        headers = error.headers
        if code == 404:
            raise NotFound("not found") from None
        limited = code == 429 or (code == 403 and headers is not None and (
            headers.get("x-ratelimit-remaining") == "0" or headers.get("retry-after") is not None))
        if limited:
            raise ApiError(f"rate limited (HTTP {code})") from None
        if 300 <= code < 400:
            raise ApiError(f"unexpected redirect (HTTP {code})") from None
        raise ApiError(f"HTTP {code}") from None

    def pull(self, number):
        check_number(number)
        pr = PullRequest.from_api(self._get(f"/repos/{self.repo}/pulls/{number}"))
        if pr.number != number:
            raise ApiError("malformed response")
        return pr

    def pull_files(self, number):
        check_number(number)
        files = []
        for page in range(1, MAX_PAGES + 1):
            batch = parse_files(self._get(f"/repos/{self.repo}/pulls/{number}/files?per_page={PAGE_SIZE}&page={page}"))
            files.extend(batch)
            if len(batch) < PAGE_SIZE:
                return files
        raise LimitExceeded("file limit reached")

    def issue_kind(self, number):
        check_number(number)
        data = self._get(f"/repos/{self.repo}/issues/{number}")
        if not isinstance(data, dict):
            raise ApiError("malformed response")
        return "pull_request" if "pull_request" in data else "issue"


    def repo_private(self):
        data = self._get(f"/repos/{self.repo}")
        return parse_private(data)

    def base_config(self, sha):
        """The configuration file at the base commit, parsed; None when the file does not exist there."""
        if not isinstance(sha, str) or not _SHA.fullmatch(sha):
            raise ApiError("malformed response")
        try:
            data = self._get(f"/repos/{self.repo}/contents/config/project.yaml?ref={sha}")
        except NotFound:
            return None
        return config.parse_yaml(decode_contents(data))


def parse_private(data):
    private = data.get("private") if isinstance(data, dict) else None
    if not isinstance(private, bool):
        raise ApiError("malformed response")
    return private


def decode_contents(data):
    """The text of a file from the contents API; anything but a small base64 file is malformed."""
    if not isinstance(data, dict) or data.get("type") != "file" or data.get("encoding") != "base64":
        raise ApiError("malformed response")
    content, size = data.get("content"), data.get("size", 0)
    if not isinstance(content, str) or not isinstance(size, int) or isinstance(size, bool) or size > MAX_CONFIG_BYTES:
        raise ApiError("malformed response")
    if len(content) > MAX_CONFIG_BYTES * 2:
        raise ApiError("response too large")
    try:
        raw = base64.b64decode(content.replace("\n", ""), validate=True)
        if len(raw) > MAX_CONFIG_BYTES:
            raise ValueError
        return raw.decode("utf-8")
    except (binascii.Error, ValueError, UnicodeDecodeError):
        raise ApiError("malformed response") from None


class FixtureClient:
    """Offline mode: pr-<n>.json, pr-<n>-files.json, and issue-<n>.json in one directory, plus repo.json (the private flag)
    and base-config.yaml (the configuration of the base commit). Any head-config.yaml in the directory is never read."""

    def __init__(self, directory):
        self._dir = Path(directory)
        if not self._dir.is_dir():
            raise InputError("fixtures directory not found")

    def _load(self, name):
        path = self._dir / name
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise NotFound("not found") from None
        except (OSError, UnicodeDecodeError):
            raise ApiError("fixture unreadable") from None
        try:
            return json.loads(text)
        except (ValueError, RecursionError):
            raise ApiError("malformed response") from None

    def pull(self, number):
        check_number(number)
        return PullRequest.from_api(self._load(f"pr-{number}.json"))

    def pull_files(self, number):
        check_number(number)
        files = parse_files(self._load(f"pr-{number}-files.json"))
        if len(files) >= MAX_FILES:
            raise LimitExceeded("file limit reached")
        return files

    def issue_kind(self, number):
        check_number(number)
        data = self._load(f"issue-{number}.json")
        if not isinstance(data, dict):
            raise ApiError("malformed response")
        return "pull_request" if "pull_request" in data else "issue"

    def repo_private(self):
        return parse_private(self._load("repo.json"))

    def base_config(self, sha):
        try:
            text = (self._dir / "base-config.yaml").read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except (OSError, UnicodeDecodeError):
            raise ApiError("fixture unreadable") from None
        return config.parse_yaml(text)
