from http.client import IncompleteRead
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from scripts.check_site import needs_deployment, public_files


class SiteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.snapshot = Path(self.directory.name) / "latest.json"
        self.index = Path(self.directory.name) / "index.html"
        self.snapshot.write_bytes(b'{"timestamp":123}')
        self.index.write_bytes(b"<h1>Exchange rates</h1>")
        self.files = (self.snapshot, self.index)

    @patch("scripts.check_site.urlopen")
    def test_unchanged_snapshot_and_homepage_skip_deployment(self, urlopen) -> None:
        urlopen.side_effect = [io.BytesIO(file.read_bytes()) for file in self.files]
        self.assertFalse(needs_deployment("https://example.com/rates/", self.files))
        self.assertEqual(urlopen.call_count, 2)
        self.assertEqual(urlopen.call_args.args[0].full_url, "https://example.com/rates/index.html")

    @patch("scripts.check_site.urlopen")
    def test_old_snapshot_retries_previous_failed_deployment(self, urlopen) -> None:
        urlopen.return_value = io.BytesIO(b'{"timestamp":122}')
        self.assertTrue(needs_deployment("https://example.com/rates", self.files))
        self.assertEqual(urlopen.call_count, 1)

    @patch("scripts.check_site.urlopen")
    def test_changed_homepage_requires_deployment(self, urlopen) -> None:
        urlopen.side_effect = [io.BytesIO(self.snapshot.read_bytes()), io.BytesIO(b"old homepage")]
        self.assertTrue(needs_deployment("https://example.com/rates", self.files))

    @patch("scripts.check_site.urlopen")
    def test_unreachable_or_missing_site_requires_deployment(self, urlopen) -> None:
        for error in [
            URLError("offline"),
            TimeoutError("timed out"),
            HTTPError("https://example.com", 404, "Not found", {}, None),
            IncompleteRead(b"partial"),
        ]:
            with self.subTest(error=error):
                urlopen.side_effect = error
                self.assertTrue(needs_deployment("https://example.com/rates", self.files))

    @patch("scripts.check_site.urlopen")
    def test_remote_file_with_extra_bytes_requires_deployment(self, urlopen) -> None:
        urlopen.return_value = io.BytesIO(self.snapshot.read_bytes() + b"extra")
        self.assertTrue(needs_deployment("https://example.com/rates", self.files))

    @patch("scripts.check_site.urlopen")
    def test_missing_local_file_fails_instead_of_deploying_incomplete_site(self, urlopen) -> None:
        missing_file = Path(self.directory.name) / "missing.json"
        with self.assertRaises(FileNotFoundError):
            needs_deployment("https://example.com/rates", (missing_file,))
        urlopen.assert_not_called()

    @patch("scripts.check_site.urlopen")
    def test_new_history_requires_deployment_even_when_latest_is_unchanged(self, urlopen) -> None:
        root = Path(self.directory.name)
        history = root / "history"
        history.mkdir()
        (history / "index.json").write_bytes(b'{"timezone":"UTC","days":["2026-10-03"]}')
        urlopen.side_effect = [
            io.BytesIO(self.snapshot.read_bytes()), io.BytesIO(self.index.read_bytes()),
            io.BytesIO(b'{"timezone":"UTC","days":[]}'),
        ]
        self.assertTrue(needs_deployment("https://example.com/rates", public_files(root), root))
        self.assertEqual(urlopen.call_args.args[0].full_url, "https://example.com/rates/history/index.json")

    @patch("scripts.check_site.urlopen")
    def test_complete_unchanged_site_skips_deployment(self, urlopen) -> None:
        root = Path(self.directory.name)
        history = root / "history"
        history.mkdir()
        (history / "index.json").write_bytes(b'{"timezone":"UTC","days":[]}')
        files = public_files(root)
        urlopen.side_effect = [io.BytesIO(file.read_bytes()) for file in files]
        self.assertFalse(needs_deployment("https://example.com/rates", files, root))
        self.assertEqual(urlopen.call_count, 3)

    def test_missing_history_index_fails_instead_of_silently_skipping_history(self) -> None:
        root = Path(self.directory.name)
        (root / "history").mkdir()
        with patch("scripts.check_site.urlopen") as urlopen:
            urlopen.side_effect = [io.BytesIO(file.read_bytes()) for file in self.files]
            with self.assertRaises(FileNotFoundError):
                needs_deployment("https://example.com/rates", public_files(root), root)


if __name__ == "__main__":
    unittest.main()
