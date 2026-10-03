# FreeExchangeRateStatic

[English](README.md)

免费汇率静态 JSON，每小时更新。无需 API Key，支持浏览器跨域请求。

## 获取最新汇率

**[访问 latest.json](https://haxqer.github.io/FreeExchangeRateStatic/latest.json)** · [备用地址](https://raw.githubusercontent.com/haxqer/FreeExchangeRateStatic/main/latest.json)

```bash
curl -fsSL https://haxqer.github.io/FreeExchangeRateStatic/latest.json
```

响应示例（仅展示部分货币，数值用于演示）：

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

| 字段 | 含义 |
| --- | --- |
| `timestamp` | 上游汇率更新时间，Unix 秒时间戳。请检查此字段判断数据新鲜度。 |
| `base` | 固定为 `USD`。 |
| `rates` | 货币代码与汇率的映射，表示 1 USD 可兑换的各币种数量。 |

## 查询历史汇率

历史快照按 **UTC 采集时间**归档，每小时保留第一条成功记录：

```text
history/index.json                # 总索引：已归档日期、日索引路径及 SHA-256
history/2026/10/03/index.json     # 当天索引：date、timezone、hours
history/2026/10/03/02.json        # UTC 02 时的第一条成功快照（路径示例）
```

[查询已归档日期](https://haxqer.github.io/FreeExchangeRateStatic/history/index.json)，然后读取日索引中存在的小时文件。例如日索引中的 `hours: ["02", "03"]` 表示当天有 `02.json` 和 `03.json`。

历史文件包含与 `latest.json` 相同的 `timestamp`、`base`、`rates`，以及 `collected_at`（UTC ISO 8601 采集时间，例如 `2026-10-03T02:17:08Z`）。`timestamp` 仍表示上游更新时间，因此不同小时可能记录相同的汇率和上游时间戳。

历史从启用归档后开始积累，不回填此前数据。抓取失败的小时留空缺；定时任务可能延迟或漏跑，因此每天不保证有 24 条。重复执行同一小时不会覆盖已有快照。

最新汇率与历史归档由两个独立工作流维护，分别在每小时第 17、27 分钟尝试抓取（UTC）。自动提交分别使用 `Update exchange rate snapshot` 和 `Archive hourly exchange rate snapshot`。两个工作流共用并发锁并发布完整站点，历史索引发生变化时也会触发部署。

## 换算货币

```javascript
const response = await fetch('https://haxqer.github.io/FreeExchangeRateStatic/latest.json');
if (!response.ok) throw new Error(`HTTP ${response.status}`);
const { rates } = await response.json();

console.log(`1 USD = ${rates.CNY} CNY`);
console.log(`100 CNY = ${100 * rates.JPY / rates.CNY} JPY`);
```

对 `rates` 中收录的任意货币，可使用以下公式：

```text
目标金额 = 原金额 × rates[目标货币] ÷ rates[原货币]
```

基准货币固定，`?base=CNY` 等查询参数不会改变返回结果。

数据来源：[FreeExchangeRateApi](https://github.com/haxqer/FreeExchangeRateApi) · 许可证：[MIT](LICENSE)
