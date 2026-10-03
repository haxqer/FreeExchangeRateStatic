# FreeExchangeRateStatic

[中文](README_zh.md)

Free exchange rates as static JSON, updated hourly. No API key required. Supports browser requests with CORS.

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

Separate workflows attempt to fetch the latest rates and archive history at minutes 17 and 27 of every hour (UTC), respectively. Their automated commits use `Update exchange rate snapshot` and `Archive hourly exchange rate snapshot`. Both workflows share a concurrency lock and publish the complete site; changes to the history index also trigger deployment.

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
