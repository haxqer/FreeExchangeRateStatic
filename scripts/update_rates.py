#!/usr/bin/env python3
"""Publish a validated USD snapshot from FreeExchangeRateApi."""

import argparse
from http.client import HTTPException
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_URL = "https://api.exchangerate.fun/latest?base=USD"
MAX_RESPONSE_BYTES = 1_000_000
MAX_AGE_SECONDS = 6 * 60 * 60
MIN_CURRENCIES = 150


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def reject_constant(value: str) -> None:
    raise ValueError(f"Invalid JSON number: {value}")


def validate_snapshot(payload: object, now: float) -> dict[str, object]:
    if not isinstance(payload, dict) or payload.get("base") != "USD":
        raise ValueError("The API must return a USD snapshot")
    timestamp = payload.get("timestamp")
    if type(timestamp) is not int or timestamp <= 0:
        raise ValueError("timestamp must be a positive Unix timestamp in seconds")
    if timestamp > now + 300:
        raise ValueError("The API timestamp is more than 5 minutes in the future")
    if now - timestamp > MAX_AGE_SECONDS:
        raise ValueError("The API snapshot is more than 6 hours old")
    rates = payload.get("rates")
    if not isinstance(rates, dict) or len(rates) < MIN_CURRENCIES:
        raise ValueError(f"Expected at least {MIN_CURRENCIES} currency rates")
    for currency, rate in rates.items():
        if not (
            isinstance(currency, str)
            and len(currency) == 3
            and currency.isascii()
            and currency.isalpha()
            and currency.isupper()
        ):
            raise ValueError(f"Invalid currency code: {currency!r}")
        if type(rate) not in (int, float) or not math.isfinite(rate) or rate <= 0:
            raise ValueError(f"Invalid positive, finite rate for {currency}")
    if rates.get("USD") != 1:
        raise ValueError("The USD rate must equal 1")
    return {"timestamp": timestamp, "base": "USD", "rates": dict(sorted(rates.items()))}


def fetch_snapshot() -> dict[str, object]:
    request = Request(
        API_URL,
        headers={
            "Accept": "application/json",
            "User-Agent": "FreeExchangeRateStatic/1.0 (+https://github.com/haxqer/FreeExchangeRateStatic)",
        },
    )
    for attempt in range(3):
        try:
            with urlopen(request, timeout=30) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
            break
        except (URLError, TimeoutError, OSError, HTTPException) as error:
            retryable = not isinstance(error, HTTPError) or error.code == 429 or error.code >= 500
            if isinstance(error, HTTPError):
                error.close()
            if not retryable or attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("The API response exceeds 1 MB")
    payload = json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant)
    return validate_snapshot(payload, time.time())


def publish_snapshot(snapshot: dict[str, object], output: Path) -> bool:
    # Check the existing source timestamp before replacing the last valid snapshot.
    if output.exists():
        previous = json.loads(output.read_text(encoding="utf-8"))
        previous_timestamp = previous["timestamp"]
        if type(previous_timestamp) is not int:
            raise ValueError("The existing snapshot has an invalid timestamp")
        if snapshot["timestamp"] < previous_timestamp:
            raise ValueError("Refusing to publish a timestamp older than the existing snapshot")
    return write_json(snapshot, output)


def write_json(payload: dict[str, object], output: Path, *, overwrite: bool = True) -> bool:
    """Atomically write JSON, optionally preserving an existing immutable file."""
    content = json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    if not overwrite and output.exists():
        return False
    if output.exists() and output.read_text(encoding="utf-8") == content:
        return False
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=output.parent, prefix=".rates-", delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        temporary_path.chmod(0o644)
        if overwrite:
            os.replace(temporary_path, output)
        else:
            # A hard link creates the destination atomically without replacing it.
            try:
                os.link(temporary_path, output)
            except FileExistsError:
                return False
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("latest.json"))
    args = parser.parse_args()
    try:
        snapshot = fetch_snapshot()
        changed = publish_snapshot(snapshot, args.output)
    except (ValueError, KeyError, TypeError, OverflowError, URLError, OSError, HTTPException) as error:
        print(f"Update failed; the previous snapshot was preserved: {error}", file=sys.stderr)
        return 1
    status = "Updated" if changed else "Unchanged"
    print(f"{status}: {args.output}, timestamp={snapshot['timestamp']}, currencies={len(snapshot['rates'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
