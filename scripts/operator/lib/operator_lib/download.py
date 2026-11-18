"""One timed download that is discarded (design section 5.1, --measure-bandwidth). https only, redirects only to https,
a size cap, a timeout, no credentials, and nothing written to disk."""
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

CHUNK = 64 * 1024
MAX_REDIRECTS = 5


class DownloadError(Exception):
    """The download or the manifest lookup failed. The message is fixed text."""


@dataclass(frozen=True)
class Timing:
    bytes: int
    seconds: float
    capped: bool


class _HttpsRedirect(urllib.request.HTTPRedirectHandler):
    max_redirections = MAX_REDIRECTS

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.lower().startswith("https://"):
            raise urllib.error.HTTPError(newurl, code, "redirect to a non-https URL", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _check_url(url):
    parsed = urllib.parse.urlsplit(url) if isinstance(url, str) else None
    if parsed is None or parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("the URL must be a plain https URL")


def timed_download(url, *, max_bytes, timeout, opener=None, clock=time.monotonic):
    _check_url(url)
    opener = opener or urllib.request.build_opener(_HttpsRedirect)
    request = urllib.request.Request(url, headers={"User-Agent": "operator-script"}, method="GET")
    total = 0
    start = clock()
    try:
        with opener.open(request, timeout=timeout) as response:
            while total < max_bytes:
                chunk = response.read(CHUNK)
                if not chunk:
                    break
                total += len(chunk)
    except (urllib.error.URLError, OSError, ValueError):
        raise DownloadError("download failed") from None
    return Timing(bytes=total, seconds=clock() - start, capped=total >= max_bytes)


def megabits_per_second(timing):
    """A whole number between 1 and 100000, or None when nothing was measured."""
    if timing.bytes <= 0 or timing.seconds <= 0:
        return None
    return max(1, min(100_000, round(timing.bytes * 8 / timing.seconds / 1_000_000)))


def manifest_artifact_url(path):
    """The amd64 URL of the first download entry of the toolchain manifest."""
    try:
        with open(path, "rb") as handle:
            tools = tomllib.load(handle).get("tools", {})
        for tool in tools.values():
            if isinstance(tool, dict) and tool.get("source") == "download":
                url = tool["artifacts"]["amd64"]["url"]
                _check_url(url)
                return url
    except (OSError, tomllib.TOMLDecodeError, KeyError, TypeError, ValueError):
        raise DownloadError("the manifest has no usable download entry") from None
    raise DownloadError("the manifest has no usable download entry")
