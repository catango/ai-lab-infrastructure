"""P-9: API failure, rate limit, and malformed responses all fail closed; token handling."""
import contextlib
import http.client
import io
import json
import socket
import tempfile
import unittest
import urllib.error
import urllib.request

import helpers
from pr_contract import cli
from pr_contract.api import MAX_FILES, FixtureClient, GitHubClient
from pr_contract.errors import ApiError, InputError, LimitExceeded, NotFound

TOKEN = "tok-SECRET-0123456789"


class Resp:
    def __init__(self, data, status=200):
        self.data, self.status = data, status

    def read(self, n=-1):
        return self.data if n < 0 else self.data[:n]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class Opener:
    """Fake opener: maps URL -> bytes, an exception, or a callable returning one."""

    def __init__(self, routes):
        self.routes, self.requests = routes, []

    def open(self, request, timeout=None):
        self.requests.append(request)
        route = self.routes.get(request.full_url, self.routes.get("*"))
        if callable(route):
            route = route(request)
        if isinstance(route, BaseException):
            raise route
        return Resp(route if isinstance(route, bytes) else json.dumps(route).encode())


def http_error(code, headers=None):
    hdrs = http.client.HTTPMessage()
    for key, value in (headers or {}).items():
        hdrs[key] = value
    return urllib.error.HTTPError("https://api.github.com/x", code, "msg", hdrs, io.BytesIO(b""))


PR_JSON = {"number": 5, "title": "t", "body": None, "state": "open", "draft": True, "merged": False,
           "changed_files": 2, "user": {"login": "u"}, "head": {"ref": "impl/CR-2-x"}, "base": {"ref": "main"}}
URL = "https://api.github.com/repos/o/r"


def client(routes, token=TOKEN):
    opener = Opener(routes)
    return GitHubClient("o/r", token=token, opener=opener), opener


class Requests(unittest.TestCase):
    def test_pull_request_url_headers_and_parse(self):
        c, opener = client({f"{URL}/pulls/5": PR_JSON})
        pr = c.pull(5)
        self.assertEqual((pr.number, pr.body, pr.head_ref, pr.base_ref, pr.author), (5, "", "impl/CR-2-x", "main", "u"))
        request = opener.requests[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.get_header("Authorization"), f"Bearer {TOKEN}")
        self.assertTrue(request.full_url.startswith("https://api.github.com/"))

    def test_no_token_means_no_authorization_header(self):
        c, opener = client({f"{URL}/pulls/5": PR_JSON}, token=None)
        c.pull(5)
        self.assertIsNone(opener.requests[0].get_header("Authorization"))

    def test_issue_kind(self):
        c, _ = client({f"{URL}/issues/2": {"number": 2}, f"{URL}/issues/3": {"number": 3, "pull_request": {}}})
        self.assertEqual(c.issue_kind(2), "issue")
        self.assertEqual(c.issue_kind(3), "pull_request")

    def test_files_are_paginated(self):
        page = [{"filename": f"f{i}", "status": "modified"} for i in range(100)]
        routes = {f"{URL}/pulls/5/files?per_page=100&page=1": page,
                  f"{URL}/pulls/5/files?per_page=100&page=2": [{"filename": "last", "status": "renamed", "previous_filename": "old", "patch": "p"}]}
        c, _ = client(routes)
        files = c.pull_files(5)
        self.assertEqual(len(files), 101)
        self.assertEqual((files[-1].path, files[-1].previous, files[-1].patch, files[-1].status), ("last", "old", "p", "renamed"))

    def test_file_cap_is_an_error(self):
        page = [{"filename": f"f{i}", "status": "modified"} for i in range(100)]
        c, opener = client({"*": page})
        with self.assertRaises(LimitExceeded):
            c.pull_files(5)
        self.assertEqual(len(opener.requests), MAX_FILES // 100)

    def test_bad_repo_and_numbers_are_input_errors(self):
        for repo in ("", "a", "a/b/c", "../x", "a b/c", "a/b?x", "a/" + "b" * 101):
            with self.subTest(repo=repo), self.assertRaises(InputError):
                GitHubClient(repo, token=None)
        c, _ = client({})
        for number in ("5", -1, 0, True, 10**9):
            with self.subTest(number=number), self.assertRaises(InputError):
                c.pull(number)


class Failures(unittest.TestCase):
    def call(self, route):
        c, _ = client({"*": route})
        return c.pull(5)

    def assert_api_error(self, route, fragment=None):
        with self.assertRaises(ApiError) as caught:
            self.call(route)
        self.assertNotIn(TOKEN, str(caught.exception))
        if fragment:
            self.assertIn(fragment, str(caught.exception))

    def test_not_found(self):
        with self.assertRaises(NotFound):
            self.call(http_error(404))

    def test_rate_limits(self):
        self.assert_api_error(http_error(403, {"x-ratelimit-remaining": "0"}), "rate limit")
        self.assert_api_error(http_error(429), "rate limit")

    def test_other_http_errors(self):
        for code in (401, 403, 500, 502, 503):
            with self.subTest(code=code):
                self.assert_api_error(http_error(code), str(code))

    def test_redirects_are_not_followed(self):
        self.assert_api_error(http_error(302, {"location": "https://elsewhere.example/x"}), "redirect")

    def test_network_errors_and_timeouts(self):
        self.assert_api_error(urllib.error.URLError("unreachable"))
        self.assert_api_error(socket.timeout("slow"))
        self.assert_api_error(ConnectionResetError("reset"))

    def test_malformed_responses(self):
        for route in (b"", b"not json", b"[1, 2]", b"null", b"{", b'{"number": "5"}', b"\xff\xfe",
                      json.dumps({**PR_JSON, "head": None}).encode(),
                      json.dumps({**PR_JSON, "title": 5}).encode(),
                      json.dumps({**PR_JSON, "draft": "yes"}).encode(),
                      json.dumps({k: v for k, v in PR_JSON.items() if k != "user"}).encode()):
            with self.subTest(route=route[:30]):
                self.assert_api_error(route)

    def test_oversized_response(self):
        self.assert_api_error(b"{" + b" " * (11 * 1024 * 1024) + b"}", "too large")

    def test_files_response_must_be_a_list_of_objects(self):
        for route in ({"a": 1}, [1], [{"status": "added"}], [{"filename": "x"}], [{"filename": 3, "status": "added"}]):
            with self.subTest(route=route):
                c, _ = client({"*": route})
                with self.assertRaises(ApiError):
                    c.pull_files(5)

    def test_issue_response_must_be_an_object(self):
        c, _ = client({"*": [1]})
        with self.assertRaises(ApiError):
            c.issue_kind(2)


class FixtureTests(unittest.TestCase):
    def test_missing_and_malformed_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = FixtureClient(tmp)
            with self.assertRaises(NotFound):
                c.pull(1)
            with open(f"{tmp}/pr-1.json", "w") as handle:
                handle.write("{broken")
            with self.assertRaises(ApiError):
                c.pull(1)

    def test_files_default_to_an_empty_list_only_when_missing_is_not_ambiguous(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(NotFound):
                FixtureClient(tmp).pull_files(1)


class ExitCodes(unittest.TestCase):
    def run_main(self, routes):
        c, _ = client(routes)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = cli.main(["--repo", "o/r", "--pr", "5", "--templates", str(helpers.TEMPLATES)], client=c)
        return code, out.getvalue()

    def test_every_api_failure_exits_3_and_never_leaks_the_token(self):
        for name, route in (("rate limit", http_error(429)), ("500", http_error(500)), ("network", urllib.error.URLError("x")),
                            ("malformed", b"not json"), ("404 on the PR itself", http_error(404))):
            with self.subTest(name=name):
                code, output = self.run_main({"*": route})
                self.assertEqual(code, 3)
                self.assertNotIn(TOKEN, output)
                self.assertNotIn("pr-contract: pass", output)


if __name__ == "__main__":
    unittest.main()
