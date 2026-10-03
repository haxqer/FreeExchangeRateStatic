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
