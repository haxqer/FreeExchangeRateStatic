#!/usr/bin/env python3
"""Collect once per UTC hour and recover partial latest/history writes on retry."""

import argparse
from datetime import datetime, timezone
from http.client import HTTPException
import json
from pathlib import Path
import sys
from urllib.error import URLError

if __package__:
    from .archive_rates import archive_snapshot, snapshot_path, update_indexes
    from .update_rates import fetch_snapshot, publish_snapshot, validate_snapshot
else:
    from archive_rates import archive_snapshot, snapshot_path, update_indexes
    from update_rates import fetch_snapshot, publish_snapshot, validate_snapshot


def update_latest(snapshot: dict[str, object], latest: Path) -> bool:
    """Keep a newer latest snapshot when retrying an immutable hourly record."""
    if latest.exists():
        previous = json.loads(latest.read_text(encoding="utf-8"))
        timestamp = previous["timestamp"]
        if type(timestamp) is not int:
            raise ValueError("The existing latest snapshot has an invalid timestamp")
        if snapshot["timestamp"] < timestamp:
            return False
    return publish_snapshot(snapshot, latest)


def collect_rates(site_root: Path) -> tuple[Path, bool, bool]:
    history = site_root / "history"
    latest = site_root / "latest.json"
    now = datetime.now(timezone.utc)
    output = snapshot_path(history, now)
    if output.exists():
        record = json.loads(output.read_text(encoding="utf-8"))
        collection_time = record["collected_at"]
        if not isinstance(collection_time, str):
            raise ValueError("The archived collection time must be an ISO 8601 string")
        collected_at = datetime.fromisoformat(collection_time.replace("Z", "+00:00"))
        if snapshot_path(history, collected_at) != output:
            raise ValueError("The archived collection time does not match its hourly path")
        if collected_at > now:
            raise ValueError("The archived collection time is in the future")
        snapshot = validate_snapshot(record, collected_at.timestamp())
        update_indexes(history)
        archived = False
    else:
        snapshot = fetch_snapshot()
        # A request crossing the hour belongs to its actual collection hour.
        collected_at = datetime.now(timezone.utc)
        snapshot = validate_snapshot(snapshot, collected_at.timestamp())
        output = snapshot_path(history, collected_at)
        archived = archive_snapshot(snapshot, history, collected_at)
    # Save history first: a later write failure can be repaired without a new fetch.
    updated = update_latest(snapshot, latest)
    return output, archived, updated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-root", type=Path, default=Path("."))
    args = parser.parse_args()
    try:
        output, archived, updated = collect_rates(args.site_root)
    except (ValueError, KeyError, TypeError, OverflowError, URLError, OSError, HTTPException) as error:
        print(f"Collection failed; retry will recover saved hourly data: {error}", file=sys.stderr)
        return 1
    print(f"Hour: {output}; archived={archived}; latest_updated={updated}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
