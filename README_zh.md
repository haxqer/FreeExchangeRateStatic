# FreeExchangeRateStatic

[English](README.md)

免费汇率静态 JSON，每小时采集一次。无需 API Key，支持浏览器跨域请求。

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

历史从启用归档后开始积累，不回填此前数据。抓取失败的小时留空缺，因此每天不保证有 24 条。重复执行同一小时不会覆盖已有快照。

采集在自有服务器上运行，不使用 GitHub Actions：systemd 定时器在每小时第 7 分钟（UTC）运行一次 [`scripts/collect_and_push.sh`](scripts/collect_and_push.sh)，每天 24 次。当前小时首次成功采集时只请求一次公开 API，同时保存小时快照和 `latest.json`。同一小时内再次运行时，使用已保存的小时记录修复未完成的写入，不重复请求上游、不覆盖历史，也不回退较新的 `latest.json`。最新文件与历史一起提交，提交信息为 `Collect hourly exchange rate snapshot`，推送到 `main` 后由 GitHub Pages 发布。若后续采集步骤失败，已保存的历史仍会提交。推送失败的提交留在服务器上，由下一次运行推送。上游在保存数据前失败时，原文件保持不变。

文件未变化时不产生提交；首次采集之后的上游变化在下一小时获取。service 和 timer 配置见 [`deploy/`](deploy/)，运行日志在服务器的 systemd journal 中。[定时调度排查记录](docs/cron-investigation.md)记录了弃用 GitHub Actions 定时任务的原因。

服务器停机或上游请求失败的小时会留空缺；停机恢复后，定时器会补跑一次，采集当前小时。已经缺失的小时无法根据当前上游快照还原。

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
