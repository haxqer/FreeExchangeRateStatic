import copy
import io
import itertools
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from scripts import update_rates

NOW = 1_800_000_000


def sample_snapshot() -> dict[str, object]:
    codes = ("".join(letters) for letters in itertools.product("ABCDEFGHIJKLMNOPQRSTUVWXYZ", repeat=3))
    rates = dict.fromkeys(itertools.islice(codes, 150), 2.5)
    rates.update({"USD": 1, "CNY": 6.7049, "BTC": 0.000011819885})
    return {"timestamp": NOW - 60, "base": "USD", "rates": rates}


class ValidationTests(unittest.TestCase):
    def test_valid_snapshot_preserves_small_rates_and_source_timestamp(self) -> None:
        snapshot = sample_snapshot()
        result = update_rates.validate_snapshot(snapshot, NOW)
        self.assertEqual(result, snapshot)
        self.assertEqual(list(result["rates"]), sorted(result["rates"]))

    def test_rejects_invalid_or_stale_data(self) -> None:
        valid = sample_snapshot()
        cases = [None, [], {"error": "upstream unavailable"}]
        for field, value in [
            ("base", "EUR"),
            ("timestamp", True),
            ("timestamp", 0),
            ("timestamp", NOW * 1000),
            ("timestamp", NOW + 301),
            ("timestamp", NOW - update_rates.MAX_AGE_SECONDS - 1),
            ("rates", {"USD": 1}),
        ]:
            cases.append({**valid, field: value})
        for currency, rate in [
            ("USD", 2), ("CNY", True), ("CNY", "6.7"), ("CNY", 0),
            ("CNY", -1), ("CNY", float("nan")), ("CNY", float("inf")),
            ("../CNY", 1), ("cny", 1), ("€UR", 1),
        ]:
            bad = copy.deepcopy(valid)
            bad["rates"][currency] = rate
            cases.append(bad)
        for payload in cases:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    update_rates.validate_snapshot(payload, NOW)


class FetchTests(unittest.TestCase):
    @patch("scripts.update_rates.time.time", return_value=NOW)
    @patch("scripts.update_rates.urlopen")
    def test_fetches_real_response_shape(self, urlopen, _time) -> None:
        urlopen.return_value = io.BytesIO(json.dumps(sample_snapshot()).encode())
        self.assertEqual(update_rates.fetch_snapshot(), sample_snapshot())
        self.assertEqual(urlopen.call_args.args[0].full_url, update_rates.API_URL)

    @patch("scripts.update_rates.time.time", return_value=NOW)
    @patch("scripts.update_rates.time.sleep")
    @patch("scripts.update_rates.urlopen")
    def test_retries_transient_failures(self, urlopen, sleep, _time) -> None:
        urlopen.side_effect = [
            URLError("connection reset"),
            HTTPError(update_rates.API_URL, 503, "Unavailable", {}, None),
            io.BytesIO(json.dumps(sample_snapshot()).encode()),
        ]
        self.assertEqual(update_rates.fetch_snapshot(), sample_snapshot())
        self.assertEqual(urlopen.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    @patch("scripts.update_rates.time.sleep")
    @patch("scripts.update_rates.urlopen")
    def test_does_not_retry_client_errors(self, urlopen, sleep) -> None:
        urlopen.side_effect = HTTPError(update_rates.API_URL, 404, "Not found", {}, None)
        with self.assertRaises(HTTPError):
            update_rates.fetch_snapshot()
        self.assertEqual(urlopen.call_count, 1)
        sleep.assert_not_called()

    @patch("scripts.update_rates.time.sleep")
    @patch("scripts.update_rates.urlopen", side_effect=URLError("offline"))
    def test_retries_are_bounded(self, urlopen, sleep) -> None:
        with self.assertRaises(URLError):
            update_rates.fetch_snapshot()
        self.assertEqual(urlopen.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    @patch("scripts.update_rates.urlopen")
    def test_rejects_non_json_duplicates_non_finite_and_oversized_responses(self, urlopen) -> None:
        for raw in [
            b"<html>Gateway error</html>",
            b'{"base":"USD","base":"EUR"}',
            b'{"rates":{"USD":1,"USD":2}}',
            b'{"rate":NaN}',
            b"x" * (update_rates.MAX_RESPONSE_BYTES + 1),
        ]:
            with self.subTest(raw=raw[:80]):
                urlopen.return_value = io.BytesIO(raw)
                with self.assertRaises(ValueError):
                    update_rates.fetch_snapshot()


class PublishTests(unittest.TestCase):
    def test_publishes_valid_json_and_skips_unchanged_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "latest.json"
            snapshot = update_rates.validate_snapshot(sample_snapshot(), NOW)
            self.assertTrue(update_rates.publish_snapshot(snapshot, output))
            self.assertEqual(json.loads(output.read_text()), snapshot)
            original_mtime = output.stat().st_mtime_ns
            self.assertFalse(update_rates.publish_snapshot(snapshot, output))
            self.assertEqual(output.stat().st_mtime_ns, original_mtime)

    def test_old_timestamp_preserves_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "latest.json"
            snapshot = sample_snapshot()
            update_rates.publish_snapshot(snapshot, output)
            original = output.read_bytes()
            with self.assertRaises(ValueError):
                update_rates.publish_snapshot({**snapshot, "timestamp": NOW - 120}, output)
            self.assertEqual(output.read_bytes(), original)

    def test_failed_atomic_replace_preserves_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "latest.json"
            snapshot = sample_snapshot()
            update_rates.publish_snapshot(snapshot, output)
            original = output.read_bytes()
            with patch("scripts.update_rates.os.replace", side_effect=OSError("disk error")):
                with self.assertRaises(OSError):
                    update_rates.publish_snapshot({**snapshot, "timestamp": NOW}, output)
            self.assertEqual(output.read_bytes(), original)
            self.assertEqual(list(Path(directory).iterdir()), [output])

    def test_failed_fetch_preserves_existing_file_and_exits_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "latest.json"
            update_rates.publish_snapshot(sample_snapshot(), output)
            original = output.read_bytes()
            with (
                patch("sys.argv", ["update_rates.py", "--output", str(output)]),
                patch("scripts.update_rates.fetch_snapshot", side_effect=ValueError("invalid data")),
                patch("sys.stderr", new_callable=io.StringIO),
            ):
                self.assertEqual(update_rates.main(), 1)
            self.assertEqual(output.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
