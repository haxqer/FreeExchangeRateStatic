from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import archive_rates, update_rates
from tests.test_update_rates import NOW, sample_snapshot


class ArchiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.history = Path(self.directory.name) / "history"
        self.collected_at = datetime.fromtimestamp(NOW, timezone.utc)

    def test_timezone_conversion_and_midnight_use_utc_collection_time(self) -> None:
        local = datetime(2026, 10, 3, 0, 17, 8, tzinfo=timezone(timedelta(hours=8)))
        snapshot = {**sample_snapshot(), "timestamp": int(local.timestamp()) - 60}
        self.assertTrue(archive_rates.archive_snapshot(snapshot, self.history, local))
        output = self.history / "2026/10/02/16.json"
        data = json.loads(output.read_text())
        self.assertEqual(data["collected_at"], "2026-10-02T16:17:08Z")
        self.assertEqual(data["timestamp"], snapshot["timestamp"])
        self.assertEqual(data["rates"], snapshot["rates"])
        day_index = json.loads((output.parent / "index.json").read_text())
        self.assertEqual(day_index, {"date": "2026-10-02", "timezone": "UTC", "hours": ["16"]})
        root_index = json.loads((self.history / "index.json").read_text())
        self.assertEqual(root_index["days"][0]["path"], "2026/10/02/index.json")
        self.assertEqual(root_index["days"][0]["sha256"], hashlib.sha256((output.parent / "index.json").read_bytes()).hexdigest())

    def test_first_success_wins_and_unchanged_rates_are_saved_next_hour(self) -> None:
        snapshot = sample_snapshot()
        archive_rates.archive_snapshot(snapshot, self.history, self.collected_at)
        output = archive_rates.snapshot_path(self.history, self.collected_at)
        original = output.read_bytes()
        modified = {**snapshot, "rates": {**snapshot["rates"], "CNY": 7}}
        self.assertFalse(archive_rates.archive_snapshot(modified, self.history, self.collected_at))
        self.assertEqual(output.read_bytes(), original)
        later = self.collected_at + timedelta(hours=1)
        self.assertTrue(archive_rates.archive_snapshot(snapshot, self.history, later))
        self.assertEqual(json.loads(archive_rates.snapshot_path(self.history, later).read_text())["timestamp"], snapshot["timestamp"])
        index = json.loads((output.parent / "index.json").read_text())
        self.assertEqual(index["hours"], sorted([self.collected_at.strftime("%H"), later.strftime("%H")]))

    def test_invalid_snapshot_and_naive_time_create_no_history(self) -> None:
        cases = [
            ({**sample_snapshot(), "timestamp": NOW - 21601}, self.collected_at),
            (sample_snapshot(), self.collected_at.replace(tzinfo=None)),
        ]
        for snapshot, collected_at in cases:
            with self.subTest(collected_at=collected_at):
                with self.assertRaises(ValueError):
                    archive_rates.archive_snapshot(snapshot, self.history, collected_at)
                self.assertFalse(self.history.exists())

    def test_failed_snapshot_write_creates_no_record_or_indexes(self) -> None:
        with patch("scripts.update_rates.os.link", side_effect=OSError("disk error")):
            with self.assertRaises(OSError):
                archive_rates.archive_snapshot(sample_snapshot(), self.history, self.collected_at)
        self.assertEqual(list(self.history.rglob("*.json")), [])
        self.assertEqual(list(self.history.rglob(".rates-*")), [])

    def test_concurrent_creation_never_overwrites_first_record(self) -> None:
        output = archive_rates.snapshot_path(self.history, self.collected_at)

        def competing_writer(source, destination):
            destination.write_text("first record")
            raise FileExistsError("another writer won")

        with patch("scripts.update_rates.os.link", side_effect=competing_writer):
            self.assertFalse(update_rates.write_json(sample_snapshot(), output, overwrite=False))
        self.assertEqual(output.read_text(), "first record")
        self.assertEqual(list(output.parent.glob(".rates-*")), [])

    def test_indexes_recover_an_unindexed_previous_day_without_filling_gaps(self) -> None:
        first = datetime(2026, 10, 2, 23, 17, tzinfo=timezone.utc)
        snapshot = {**sample_snapshot(), "timestamp": int(first.timestamp()) - 60}
        with patch("scripts.archive_rates.update_indexes", side_effect=OSError("disk error")):
            with self.assertRaises(OSError):
                archive_rates.archive_snapshot(snapshot, self.history, first)
        later = first + timedelta(hours=2)
        archive_rates.archive_snapshot(snapshot, self.history, later)
        previous_day = json.loads((self.history / "2026/10/02/index.json").read_text())
        current_day = json.loads((self.history / "2026/10/03/index.json").read_text())
        self.assertEqual(previous_day["hours"], ["23"])
        self.assertEqual(current_day["hours"], ["01"])
        self.assertEqual(len(json.loads((self.history / "index.json").read_text())["days"]), 2)

    def test_same_hour_retry_repairs_indexes_without_requesting_upstream(self) -> None:
        with patch("scripts.archive_rates.update_indexes", side_effect=OSError("disk error")):
            with self.assertRaises(OSError):
                archive_rates.archive_snapshot(sample_snapshot(), self.history, self.collected_at)
        with (
            patch("scripts.archive_rates.datetime") as clock,
            patch("scripts.archive_rates.fetch_snapshot") as fetch,
            patch("sys.argv", ["archive_rates.py", "--history", str(self.history)]),
            patch("sys.stdout", new_callable=io.StringIO),
        ):
            clock.now.return_value = self.collected_at
            self.assertEqual(archive_rates.main(), 0)
            fetch.assert_not_called()
        self.assertTrue((self.history / "index.json").exists())

    def test_fetch_failure_leaves_existing_history_unchanged(self) -> None:
        archive_rates.archive_snapshot(sample_snapshot(), self.history, self.collected_at)
        original = {path: path.read_bytes() for path in self.history.rglob("*.json")}
        with (
            patch("scripts.archive_rates.datetime") as clock,
            patch("scripts.archive_rates.fetch_snapshot", side_effect=ValueError("invalid response")),
            patch("sys.argv", ["archive_rates.py", "--history", str(self.history)]),
            patch("sys.stderr", new_callable=io.StringIO),
        ):
            clock.now.return_value = self.collected_at + timedelta(hours=1)
            self.assertEqual(archive_rates.main(), 1)
        self.assertEqual({path: path.read_bytes() for path in self.history.rglob("*.json")}, original)

    def test_fetch_finishing_after_midnight_archives_in_the_new_utc_day(self) -> None:
        before = datetime(2026, 10, 2, 23, 59, 59, tzinfo=timezone.utc)
        after = before + timedelta(seconds=2)
        snapshot = {**sample_snapshot(), "timestamp": int(after.timestamp()) - 60}
        with (
            patch("scripts.archive_rates.datetime") as clock,
            patch("scripts.archive_rates.fetch_snapshot", return_value=snapshot),
            patch("sys.argv", ["archive_rates.py", "--history", str(self.history)]),
            patch("sys.stdout", new_callable=io.StringIO),
        ):
            clock.now.side_effect = [before, after]
            self.assertEqual(archive_rates.main(), 0)
        self.assertTrue((self.history / "2026/10/03/00.json").exists())
        self.assertFalse((self.history / "2026/10/02").exists())


if __name__ == "__main__":
    unittest.main()
