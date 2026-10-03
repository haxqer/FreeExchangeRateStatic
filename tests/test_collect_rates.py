from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError

from scripts import archive_rates, collect_rates, update_rates
from tests.test_update_rates import NOW, sample_snapshot


class CollectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.now = datetime.fromtimestamp(NOW, timezone.utc)
        clock_patch = patch("scripts.collect_rates.datetime")
        self.clock = clock_patch.start()
        self.addCleanup(clock_patch.stop)
        self.clock.now.return_value = self.now
        self.clock.fromisoformat.side_effect = datetime.fromisoformat
        fetch_patch = patch("scripts.collect_rates.fetch_snapshot", return_value=sample_snapshot())
        self.fetch = fetch_patch.start()
        self.addCleanup(fetch_patch.stop)

    def hourly_path(self, at: datetime | None = None) -> Path:
        return archive_rates.snapshot_path(self.root / "history", at or self.now)

    def test_one_fetch_updates_both_outputs_and_same_hour_retry_is_unchanged(self) -> None:
        output, archived, updated = collect_rates.collect_rates(self.root)
        self.assertTrue(archived)
        self.assertTrue(updated)
        record = json.loads(output.read_text())
        latest = json.loads((self.root / "latest.json").read_text())
        self.assertEqual({k: record[k] for k in latest}, latest)
        original = {p: p.read_bytes() for p in self.root.rglob("*.json")}
        self.assertEqual(collect_rates.collect_rates(self.root), (output, False, False))
        self.fetch.assert_called_once()
        self.assertEqual(original, {p: p.read_bytes() for p in self.root.rglob("*.json")})

    def test_latest_write_failure_keeps_history_and_retry_recovers_without_upstream(self) -> None:
        with patch("scripts.collect_rates.publish_snapshot", side_effect=OSError("disk error")):
            with self.assertRaises(OSError):
                collect_rates.collect_rates(self.root)
        record = self.hourly_path().read_bytes()
        self.assertFalse((self.root / "latest.json").exists())
        self.fetch.side_effect = URLError("upstream unavailable")
        self.assertEqual(collect_rates.collect_rates(self.root), (self.hourly_path(), False, True))
        self.fetch.assert_called_once()
        self.assertEqual(record, self.hourly_path().read_bytes())
        self.assertEqual(json.loads((self.root / "latest.json").read_text()), sample_snapshot())

    def test_index_failure_keeps_record_and_retry_repairs_both_outputs(self) -> None:
        with patch("scripts.archive_rates.update_indexes", side_effect=OSError("disk error")):
            with self.assertRaises(OSError):
                collect_rates.collect_rates(self.root)
        self.assertTrue(self.hourly_path().exists())
        self.assertFalse((self.root / "history/index.json").exists())
        collect_rates.collect_rates(self.root)
        self.fetch.assert_called_once()
        self.assertTrue((self.root / "history/index.json").exists())
        self.assertTrue((self.root / "latest.json").exists())

    def test_retry_never_regresses_a_newer_latest_snapshot(self) -> None:
        collect_rates.collect_rates(self.root)
        newer = {**sample_snapshot(), "timestamp": NOW}
        update_rates.publish_snapshot(newer, self.root / "latest.json")
        self.assertFalse(collect_rates.collect_rates(self.root)[2])
        self.assertEqual(json.loads((self.root / "latest.json").read_text()), newer)

    def test_fetch_failure_creates_no_hour_and_preserves_latest(self) -> None:
        update_rates.publish_snapshot(sample_snapshot(), self.root / "latest.json")
        original = (self.root / "latest.json").read_bytes()
        self.fetch.side_effect = URLError("upstream unavailable")
        with self.assertRaises(URLError):
            collect_rates.collect_rates(self.root)
        self.assertFalse(self.hourly_path().exists())
        self.assertEqual((self.root / "latest.json").read_bytes(), original)

    def test_midnight_collection_uses_actual_completion_time(self) -> None:
        before = datetime(2026, 10, 3, 23, 59, 59, tzinfo=timezone.utc)
        after = before + timedelta(seconds=2)
        self.clock.now.side_effect = [before, after]
        self.fetch.return_value = {**sample_snapshot(), "timestamp": int(after.timestamp()) - 60}
        self.assertEqual(collect_rates.collect_rates(self.root)[0], self.hourly_path(after))
        self.assertFalse(self.hourly_path(before).exists())

    def test_unchanged_upstream_is_still_archived_in_the_next_hour(self) -> None:
        collect_rates.collect_rates(self.root)
        later = self.now + timedelta(hours=1)
        self.clock.now.return_value = later
        self.assertEqual(collect_rates.collect_rates(self.root), (self.hourly_path(later), True, False))
        self.assertEqual(self.fetch.call_count, 2)

    def test_invalid_saved_collection_time_does_not_update_latest(self) -> None:
        collect_rates.collect_rates(self.root)
        record = json.loads(self.hourly_path().read_text())
        latest = (self.root / "latest.json").read_bytes()
        for value in [123, "2026-10-03T12:00:00", (self.now + timedelta(hours=1)).isoformat()]:
            with self.subTest(value=value):
                self.hourly_path().write_text(json.dumps({**record, "collected_at": value}))
                with self.assertRaises(ValueError):
                    collect_rates.collect_rates(self.root)
                self.assertEqual((self.root / "latest.json").read_bytes(), latest)
        self.fetch.assert_called_once()


if __name__ == "__main__":
    unittest.main()
