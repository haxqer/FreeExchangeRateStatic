#!/usr/bin/env python3
"""Archive the first successful hourly USD snapshot in UTC date directories."""

import argparse
from datetime import datetime, timezone
import hashlib
from http.client import HTTPException
from pathlib import Path
import sys
from urllib.error import URLError

if __package__:
    from .update_rates import fetch_snapshot, validate_snapshot, write_json
else:
    from update_rates import fetch_snapshot, validate_snapshot, write_json


def snapshot_path(history: Path, collected_at: datetime) -> Path:
    if collected_at.tzinfo is None or collected_at.utcoffset() is None:
        raise ValueError("Collection time must include a timezone")
    utc = collected_at.astimezone(timezone.utc)
    return history / utc.strftime("%Y/%m/%d/%H.json")


def update_indexes(history: Path) -> None:
    """Rebuild indexes from saved files, including recovery after a partial write."""
    days = []
    for day in sorted(history.glob("[0-9][0-9][0-9][0-9]/[0-9][0-9]/[0-9][0-9]")):
        if not day.is_dir():
            continue
        hours = sorted(path.stem for path in day.glob("[0-2][0-9].json") if int(path.stem) < 24)
        if not hours:
            continue
        date = "-".join(day.relative_to(history).parts)
        index = day / "index.json"
        write_json({"date": date, "timezone": "UTC", "hours": hours}, index)
        relative = index.relative_to(history)
        days.append({
            "date": "-".join(relative.parts[:3]),
            "path": relative.as_posix(),
            # Include daily index content so repairing an older day triggers deployment.
            "sha256": hashlib.sha256(index.read_bytes()).hexdigest(),
        })
    write_json({"timezone": "UTC", "days": days}, history / "index.json")


def archive_snapshot(snapshot: dict[str, object], history: Path, collected_at: datetime) -> bool:
    output = snapshot_path(history, collected_at)
    utc = collected_at.astimezone(timezone.utc).replace(microsecond=0)
    valid = validate_snapshot(snapshot, collected_at.timestamp())
    changed = write_json(
        {"collected_at": utc.isoformat().replace("+00:00", "Z"), **valid},
        output,
        overwrite=False,
    )
    update_indexes(history)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", type=Path, default=Path("history"))
    args = parser.parse_args()
    try:
        now = datetime.now(timezone.utc)
        output = snapshot_path(args.history, now)
        if output.exists():
            # Retrying an already archived hour needs no upstream request.
            update_indexes(args.history)
            changed = False
        else:
            snapshot = fetch_snapshot()
            now = datetime.now(timezone.utc)
            output = snapshot_path(args.history, now)
            changed = archive_snapshot(snapshot, args.history, now)
    except (ValueError, KeyError, TypeError, OverflowError, URLError, OSError, HTTPException) as error:
        print(f"Archive failed; existing hourly snapshots were preserved: {error}", file=sys.stderr)
        return 1
    print(f"{'Archived' if changed else 'Unchanged'}: {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
