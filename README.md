# FreeExchangeRateStatic

[中文](README_zh.md)

Free exchange rates as static JSON, with hourly collection and retries within each hour. No API key required. Supports browser requests with CORS.

## Get the latest rates

**[Download latest.json](https://haxqer.github.io/FreeExchangeRateStatic/latest.json)** · [Backup URL](https://raw.githubusercontent.com/haxqer/FreeExchangeRateStatic/main/latest.json)

```bash
curl -fsSL https://haxqer.github.io/FreeExchangeRateStatic/latest.json
```

Example response (partial, for illustration):

```json
{
  "timestamp": 1790992824,
  "base": "USD",
  "rates": {
    "CNY": 6.7049,
    "EUR": 0.888297,
    "JPY": 157.83500891,
    "USD": 1
  }
}
```

| Field | Meaning |
| --- | --- |
| `timestamp` | Source data update time, in Unix seconds. Check this value for freshness. |
| `base` | Always `USD`. |
| `rates` | Currency codes mapped to the amount of each currency per 1 USD. |

## Query historical rates

Snapshots are archived by **UTC collection time**, keeping the first successful record each hour:

```text
history/index.json                # Available dates, daily index paths and SHA-256 hashes
history/2026/10/03/index.json     # Daily index: date, timezone, hours
history/2026/10/03/02.json        # First successful snapshot in UTC hour 02 (example path)
```

[Find available dates](https://haxqer.github.io/FreeExchangeRateStatic/history/index.json), then use each daily index to find available hourly files. For example, `hours: ["02", "03"]` means that day has `02.json` and `03.json`.

Historical files contain the same `timestamp`, `base`, and `rates` as `latest.json`, plus `collected_at` (UTC ISO 8601 collection time, such as `2026-10-03T02:17:08Z`). The source `timestamp` is preserved, so different hours may contain identical rates and source timestamps.

History starts when archiving is enabled; earlier data is not backfilled. Failed collections leave gaps. Scheduled jobs may be delayed or skipped, so 24 records per day are not guaranteed. Rerunning an already archived hour never replaces its snapshot.

One workflow, **Collect and publish exchange rates**, runs at minutes 7, 27, and 47 of every hour (UTC). The first successful collection fetches the public API once and saves both the hourly archive and `latest.json`. Retries use the saved hourly record to repair incomplete writes without fetching again or overwriting history; a newer `latest.json` is preserved. Both outputs are committed together with `Collect hourly exchange rate snapshot`, then the complete site is published. Saved history is also committed if a later collection step fails, so a subsequent run can recover it. An upstream failure before any data is saved leaves the previous files intact.

The workflow serializes collection and publishing. Unchanged files do not create a commit or a deployment; source updates after the first collection are picked up in the next hour. The former archive workflow is retained as a manual compatibility entry calling the same pipeline. Each run's summary records its event type, cron expression (when scheduled), and job start time. [Scheduling investigation](docs/cron-investigation.md) contains the original run timeline and the limits of the diagnosis.

GitHub scheduling remains best effort: retries cannot guarantee hourly execution during a prolonged scheduling outage. This project uses GitHub Actions only; an independent collector would be required to capture data while GitHub cannot start workflows. Runs that never start have no job log, and a snapshot that cannot be pushed may be lost with the temporary runner. Missing hours cannot be reconstructed from the current upstream snapshot. You can manually trigger `update-rates.yml` with `workflow_dispatch` to collect the current hour and retry publishing.

## Convert currencies

```javascript
const response = await fetch('https://haxqer.github.io/FreeExchangeRateStatic/latest.json');
if (!response.ok) throw new Error(`HTTP ${response.status}`);
const { rates } = await response.json();

console.log(`1 USD = ${rates.CNY} CNY`);
console.log(`100 CNY = ${100 * rates.JPY / rates.CNY} JPY`);
```

For any currencies included in `rates`:

```text
converted amount = amount × rates[target] ÷ rates[source]
```

The base is fixed; query parameters such as `?base=CNY` have no effect.

Data: [FreeExchangeRateApi](https://github.com/haxqer/FreeExchangeRateApi) · License: [MIT](LICENSE)
