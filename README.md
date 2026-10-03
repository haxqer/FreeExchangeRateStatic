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
