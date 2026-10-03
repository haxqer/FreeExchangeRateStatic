# FreeExchangeRateStatic

[English](README.md)

免费汇率静态 JSON，按小时采集，并在同一小时内重试。无需 API Key，支持浏览器跨域请求。

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

采集由一个工作流 **Collect and publish exchange rates** 负责，在每小时第 7、27、47 分钟尝试运行（UTC）。当前小时首次成功采集时只请求一次公开 API，同时保存小时快照和 `latest.json`。后续重试使用已保存的小时记录修复未完成的写入，不重复请求上游、不覆盖历史，也不回退较新的 `latest.json`。最新文件与历史一起提交，提交信息为 `Collect hourly exchange rate snapshot`，然后发布完整站点。若后续采集步骤失败，已保存的历史仍会尝试提交，以便后续运行恢复。上游在保存数据前失败时，原文件保持不变。

工作流串行执行采集与发布；文件未变化时不产生提交或部署，首次采集之后的上游变化在下一小时获取。原归档工作流保留为手动兼容入口，调用同一流程。每次运行摘要记录触发类型、cron 表达式（定时事件）和任务实际开始时间。[定时调度排查记录](docs/cron-investigation.md)包含旧任务的运行时间线和诊断边界。

GitHub 定时调度仍不保证准时：持续的调度故障可能使同一小时内的重试全部失效。本项目仅使用 GitHub Actions；若需在 GitHub 无法启动工作流时仍采集数据，必须引入独立采集器。未启动的运行没有任务日志，无法推送的快照也可能随临时 runner 丢失。已经缺失的小时无法根据当前上游快照还原。可以通过 `workflow_dispatch` 手动触发 `update-rates.yml`，采集当前小时并重试发布。

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
