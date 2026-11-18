import unittest
import urllib.error

import helpers  # noqa: F401
from operator_lib import download


class Response:
    def __init__(self, chunks):
        self.chunks = list(chunks)

    def read(self, size=-1):
        return self.chunks.pop(0) if self.chunks else b""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class Opener:
    def __init__(self, chunks=(), error=None):
        self.chunks, self.error, self.requests = chunks, error, []

    def open(self, request, timeout=None):
        self.requests.append((request, timeout))
        if self.error:
            raise self.error
        return Response(self.chunks)


class Clock:
    def __init__(self, *times):
        self.times = list(times)

    def __call__(self):
        return self.times.pop(0)


class TimedDownload(unittest.TestCase):
    URL = "https://downloads.example.invalid/tool.tar.gz"

    def test_bytes_and_seconds_are_returned_and_nothing_is_kept(self):
        opener = Opener([b"a" * 1000, b"b" * 1000])
        result = download.timed_download(self.URL, max_bytes=10_000, timeout=5, opener=opener, clock=Clock(10.0, 12.0))
        self.assertEqual((result.bytes, result.seconds), (2000, 2.0))
        self.assertEqual(opener.requests[0][0].get_method(), "GET")
        self.assertIsNone(opener.requests[0][0].get_header("Authorization"))
        self.assertEqual(opener.requests[0][1], 5)

    def test_the_download_stops_at_the_cap(self):
        opener = Opener([b"a" * 600] * 10)
        result = download.timed_download(self.URL, max_bytes=1000, timeout=5, opener=opener, clock=Clock(0.0, 1.0))
        self.assertLessEqual(result.bytes, 1000 + 600)
        self.assertTrue(result.capped)

    def test_only_https_urls_are_accepted(self):
        for url in ("http://downloads.example.invalid/x", "file:///etc/passwd", "ftp://x.example.invalid/x", "https://", "x", ""):
            with self.subTest(url=url), self.assertRaises(ValueError):
                download.timed_download(url, max_bytes=10, timeout=1, opener=Opener())

    def test_errors_become_a_fixed_message(self):
        with self.assertRaises(download.DownloadError) as caught:
            download.timed_download(self.URL, max_bytes=10, timeout=1, opener=Opener(error=urllib.error.URLError("secret detail")))
        self.assertNotIn("secret", str(caught.exception))

    def test_megabits_per_second_is_a_bounded_integer(self):
        self.assertEqual(download.megabits_per_second(download.Timing(bytes=12_500_000, seconds=1.0, capped=False)), 100)
        self.assertEqual(download.megabits_per_second(download.Timing(bytes=1, seconds=100.0, capped=False)), 1)
        self.assertEqual(download.megabits_per_second(download.Timing(bytes=0, seconds=0.0, capped=False)), None)
        self.assertEqual(download.megabits_per_second(download.Timing(bytes=10**12, seconds=0.001, capped=False)), 100000)


class ManifestUrl(unittest.TestCase):
    def test_the_repository_manifest_gives_an_https_amd64_artifact(self):
        url = download.manifest_artifact_url(helpers.ROOT / "toolchain" / "manifest.toml")
        self.assertTrue(url.startswith("https://"))
        self.assertIn("amd64", url)

    def test_a_manifest_without_a_download_is_an_error(self):
        import pathlib
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "m.toml"
            path.write_text('schema_version = 1\n[tools.x]\nsource = "apt"\n')
            with self.assertRaises(download.DownloadError):
                download.manifest_artifact_url(path)


if __name__ == "__main__":
    unittest.main()
