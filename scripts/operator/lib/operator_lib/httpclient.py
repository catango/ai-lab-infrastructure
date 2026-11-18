"""HTTP client for operator scripts (design section 4 rules 9 and 10). The pr-contract client's safeguards apply: https only,
no redirects, a timeout, a size cap, the token in one header, and fixed error messages. In read-only mode (the default)
any method other than GET raises before a request is built, so a read-only script cannot write through it."""
import http.client
import json
import re
import urllib.error
import urllib.parse
import urllib.request

import operator_lib  # noqa: F401  (puts scripts/ on sys.path)
from pr_contract.api import MAX_RESPONSE_BYTES, TIMEOUT_SECONDS, _NoRedirect
from pr_contract.errors import ApiError, NotFound

METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE"})
_HEADER_NAME = re.compile(r"[A-Za-z][A-Za-z0-9-]{0,40}")
_HEADER_VALUE = re.compile(r"[A-Za-z0-9 ./+;=_-]{1,100}")
_PATH = re.compile(r"/(?!/)[A-Za-z0-9._~%:@!$&'()*+,;=/?-]*")


class ReadOnlyViolation(Exception):
    """A method other than GET on a read-only client, or a method outside the supported set."""


class HttpClient:
    def __init__(self, base, token=None, *, read_only=True, opener=None, timeout=TIMEOUT_SECONDS, headers=None):
        parsed = urllib.parse.urlsplit(base)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("the base URL must be a plain https URL")
        self._base = base.rstrip("/")
        self._token = token or None
        self.read_only = bool(read_only)
        self._opener = opener or urllib.request.build_opener(_NoRedirect)
        self._timeout = timeout
        self._headers = {}
        for name, value in (headers or {}).items():
            if not (isinstance(name, str) and _HEADER_NAME.fullmatch(name) and isinstance(value, str) and _HEADER_VALUE.fullmatch(value)) \
                    or name.lower() in ("authorization", "host", "content-length"):
                raise ValueError("invalid header")
            self._headers[name] = value

    def __repr__(self):
        return f"HttpClient(base={self._base!r}, read_only={self.read_only})"

    def get(self, path):
        return self.request("GET", path)

    def request(self, method, path, body=None):
        if method not in METHODS or (self.read_only and method != "GET"):
            raise ReadOnlyViolation("method not allowed for this client")
        if not isinstance(path, str) or not _PATH.fullmatch(path):
            raise ValueError("invalid request path")
        headers = {"Accept": "application/json", "User-Agent": "operator-script"}
        headers.update(self._headers)
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        request = urllib.request.Request(f"{self._base}{path}", data=data, headers=headers, method=method)
        try:
            with self._opener.open(request, timeout=self._timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as error:
            self._raise_for_status(error)
        except (urllib.error.URLError, OSError, ValueError, http.client.HTTPException) as error:
            raise ApiError(f"network error ({type(error).__name__})") from None
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ApiError("response too large")
        if not raw:
            return None
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError, RecursionError):
            raise ApiError("malformed response") from None

    @staticmethod
    def _raise_for_status(error):
        code = error.code
        if code == 404:
            raise NotFound("not found") from None
        headers = error.headers
        if code == 429 or (code == 403 and headers is not None and (headers.get("x-ratelimit-remaining") == "0" or headers.get("retry-after"))):
            raise ApiError(f"rate limited (HTTP {code})") from None
        if 300 <= code < 400:
            raise ApiError(f"unexpected redirect (HTTP {code})") from None
        raise ApiError(f"HTTP {code}") from None
