import json
import unittest
import urllib.error

import helpers  # noqa: F401
from operator_lib import httpclient
from pr_contract.errors import ApiError, NotFound


class Response:
    def __init__(self, data=b"{}", status=200):
        self._data, self.status = data, status

    def read(self, limit=-1):
        return self._data if limit < 0 else self._data[:limit]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class Opener:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.requests = response or Response(), error, []

    def open(self, request, timeout=None):
        self.requests.append((request, timeout))
        if self.error is not None:
            raise self.error
        return self.response


def client(**kw):
    kw.setdefault("opener", Opener())
    return httpclient.HttpClient("https://api.example.invalid", **kw)


class ReadOnly(unittest.TestCase):
    def test_get_is_sent(self):
        c = client()
        self.assertEqual(c.get("/repos/x/y"), {})
        self.assertEqual(c._opener.requests[0][0].get_method(), "GET")

    def test_every_other_method_raises_before_a_request_is_sent(self):
        for method in ("POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "get", "TRACE", "", "GET "):
            with self.subTest(method=method):
                c = client()
                with self.assertRaises(httpclient.ReadOnlyViolation):
                    c.request(method, "/repos/x/y", body={"a": 1})
                self.assertEqual(c._opener.requests, [])

    def test_read_only_is_the_default(self):
        self.assertTrue(client().read_only)

    def test_a_write_client_must_be_asked_for_explicitly(self):
        c = client(read_only=False)
        c.request("PATCH", "/repos/x/y", body={"a": 1})
        request = c._opener.requests[0][0]
        self.assertEqual(request.get_method(), "PATCH")
        self.assertEqual(json.loads(request.data), {"a": 1})

    def test_unknown_methods_are_refused_even_for_a_write_client(self):
        c = client(read_only=False)
        for method in ("TRACE", "CONNECT", "FOO", "post"):
            with self.subTest(method=method), self.assertRaises(httpclient.ReadOnlyViolation):
                c.request(method, "/x")
        self.assertEqual(c._opener.requests, [])


class Safety(unittest.TestCase):
    def test_token_is_only_in_the_authorization_header(self):
        c = client(token=helpers.PAT + "CANARY1234567890")
        c.get("/x")
        request = c._opener.requests[0][0]
        self.assertEqual(request.get_header("Authorization"), "Bearer " + helpers.PAT + "CANARY1234567890")
        self.assertNotIn("CANARY", request.full_url)
        self.assertNotIn("CANARY", repr(c))
        self.assertNotIn("CANARY", str(c.__dict__.get("base", "")))

    def test_no_token_means_no_header(self):
        c = client()
        c.get("/x")
        self.assertIsNone(c._opener.requests[0][0].get_header("Authorization"))

    def test_paths_must_be_absolute_and_plain(self):
        for path in ("x", "//evil.example/x", "https://evil.example/x", "/x\r\nHost: evil", "/a b", ""):
            with self.subTest(path=path), self.assertRaises(ValueError):
                client().get(path)

    def test_base_must_be_https(self):
        with self.assertRaises(ValueError):
            httpclient.HttpClient("http://api.example.invalid")

    def test_timeout_is_set(self):
        c = client()
        c.get("/x")
        self.assertEqual(c._opener.requests[0][1], httpclient.TIMEOUT_SECONDS)

    def test_oversized_and_malformed_responses_fail(self):
        with self.assertRaises(ApiError):
            client(opener=Opener(Response(b"x" * (httpclient.MAX_RESPONSE_BYTES + 5)))).get("/x")
        with self.assertRaises(ApiError):
            client(opener=Opener(Response(b"not json"))).get("/x")

    def test_http_errors_become_fixed_messages(self):
        def err(code):
            return urllib.error.HTTPError("https://api.example.invalid/x", code, "secret body text", {}, None)
        with self.assertRaises(NotFound):
            client(opener=Opener(error=err(404))).get("/x")
        with self.assertRaises(ApiError) as caught:
            client(opener=Opener(error=err(500))).get("/x")
        self.assertNotIn("secret", str(caught.exception))

    def test_network_errors_do_not_leak_the_url_or_token(self):
        c = client(token=helpers.PAT + "CANARY1234567890", opener=Opener(error=urllib.error.URLError("boom " + helpers.PAT + "CANARY1234567890")))
        with self.assertRaises(ApiError) as caught:
            c.get("/x")
        self.assertNotIn("CANARY", str(caught.exception))

    def test_empty_body_is_none(self):
        self.assertIsNone(client(opener=Opener(Response(b""))).get("/x"))


if __name__ == "__main__":
    unittest.main()
