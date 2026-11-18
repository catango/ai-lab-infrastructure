"""The GitHub REST API as a client for operator scripts: the pr-contract safeguards (httpclient), the API version header, and
validation of the logins and repository names that arrive on the command line."""
import re

from .httpclient import HttpClient

BASE = "https://api.github.com"
HEADERS = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
_LOGIN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?")
_REPO = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}")


def make_client(token, *, read_only, opener=None):
    return HttpClient(BASE, token, read_only=read_only, opener=opener, headers=HEADERS)


def valid_login(value):
    return isinstance(value, str) and _LOGIN.fullmatch(value) is not None and "--" not in value


def valid_repo(value):
    return isinstance(value, str) and _REPO.fullmatch(value) is not None and value not in (".", "..")
