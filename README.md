# FreeExchangeRateStatic

[![Update exchange rates](https://github.com/haxqer/FreeExchangeRateStatic/actions/workflows/update-rates.yml/badge.svg)](https://github.com/haxqer/FreeExchangeRateStatic/actions/workflows/update-rates.yml)

每小时从 [FreeExchangeRateApi](https://github.com/haxqer/FreeExchangeRateApi) 获取完整的美元基准汇率，自动生成固定地址的 `latest.json`，供任何人免费访问，无需 API Key。

## 公开访问地址

推荐使用 GitHub Pages（返回 JSON，支持浏览器跨域请求）：

**<https://haxqer.github.io/FreeExchangeRateStatic/latest.json>**

备用地址（GitHub Raw）：

<https://raw.githubusercontent.com/haxqer/FreeExchangeRateStatic/main/latest.json>

```bash
curl -fsSL https://haxqer.github.io/FreeExchangeRateStatic/latest.json
```

地址固定，每次成功更新会覆盖同一个文件，历史版本保存在 Git 提交中。

## 数据结构

下面是结构示例，数值仅作演示；真实文件包含上游全部货币：

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
| `timestamp` | **上游汇率更新时间**，Unix 时间戳，单位为秒；不是文件生成时间。 |
| `base` | 固定为 `USD`。 |
| `rates` | 货币代码到汇率的映射，表示 **1 USD 可兑换的目标货币数量**，包括上游支持的法币、加密货币和贵金属。 |

静态文件不处理 `?base=CNY` 等查询参数。使用下面的公式即可用同一份 JSON 换算任意已收录的货币：

```text
目标金额 = 原金额 × rates[目标货币] ÷ rates[原货币]
```

### JavaScript

```javascript
const response = await fetch('https://haxqer.github.io/FreeExchangeRateStatic/latest.json');
if (!response.ok) throw new Error(`HTTP ${response.status}`);
const data = await response.json();

console.log(`汇率更新时间：${new Date(data.timestamp * 1000).toISOString()}`);
console.log(`1 USD = ${data.rates.CNY} CNY`);
console.log(`100 CNY = ${100 * data.rates.JPY / data.rates.CNY} JPY`);
```

### Python（无需第三方库）

```python
import json
from urllib.request import urlopen

with urlopen('https://haxqer.github.io/FreeExchangeRateStatic/latest.json', timeout=30) as response:
    data = json.load(response)
print(f"1 USD = {data['rates']['CNY']} CNY")
print(f"100 CNY = {100 * data['rates']['JPY'] / data['rates']['CNY']} JPY")
```

## 自动更新机制

- GitHub Actions 按 UTC 每小时第 17 分钟触发（新加坡 / 北京时间同样为每小时第 17 分钟），也支持手动运行；实现代码或首页推送到 `main` 时也会运行。
- 每次只请求一次 `https://api.exchangerate.fun/latest?base=USD`，网络错误、HTTP 429 或 5xx 最多尝试三次。
- 发布前检查 JSON 格式、重复字段、USD 基准、时间戳、至少 150 个货币以及正数且有限的汇率。拒绝超过 6 小时、超过当前时间 5 分钟或早于已发布版本的数据。
- 校验失败则任务失败，保留仓库及网站上的上一份有效文件。成功后原子替换文件，只在内容变化时提交。
- 对比线上 `latest.json` 和首页，仅在网站内容不同或无法确认时部署 GitHub Pages；即使文件已提交而上次部署失败，下次运行仍会重新发布。手动运行会强制部署。
- 文件保留上游时间戳和汇率精度，不伪造更新时间、不将小额汇率四舍五入为零。

GitHub Actions 的定时任务可能延迟，不承诺精确到分钟。GitHub Pages 和 Raw 均有缓存，访问者应检查 `timestamp` 判断数据新鲜度；更新失败时旧文件仍可访问。

GitHub 对公开仓库连续 60 天无活动的定时工作流可能自动停用。正常的汇率更新提交会持续产生仓库活动；如果上游长期停止更新，需在 Actions 中重新启用工作流。

## Actions 额度与运行优化

按 [GitHub 官方计费说明](https://docs.github.com/en/billing/concepts/product-billing/github-actions)，**公开仓库使用标准 GitHub-hosted runner 的运行时间免费且不限月度分钟数**，不消耗私有仓库的月度免费分钟额度。本仓库为公开仓库，使用标准 `ubuntu-24.04` runner。

私有仓库的分钟额度按账号共享，不能按每个仓库重复领取：

| 账号方案 | 每月免费分钟 |
| --- | --- |
| GitHub Free / Free for organizations | 2,000 |
| GitHub Pro / Team | 3,000 |
| GitHub Enterprise Cloud | 50,000 |

本项目已减少重复运行与部署开销：

- 每小时只启动 **1 个任务**，在同一个 runner 中完成抓取、提交和发布。
- 使用 Ubuntu 24.04 自带的 Python 3.12，无需安装 Python 或第三方依赖。
- 单元测试在代码推送和 Pull Request 时执行，定时及手动更新仅运行实际数据校验。
- 线上内容一致时跳过 Pages 产物上传和部署；Pages 产物仅保留 1 天，不创建依赖缓存。

若以后将仓库改为私有，应重新评估账号总用量。公开仓库的免费运行时间与产物存储额度是不同概念；产物存储应单独关注。

## 本地运行

需要 Python 3.10+，无第三方依赖：

```bash
python3 -m unittest discover -s tests -v
python3 scripts/update_rates.py
```

默认写入 `latest.json`；可用 `--output /path/to/latest.json` 指定输出路径。

## 仓库部署配置

本仓库使用 `.github/workflows/update-rates.yml` 同时更新数据并部署网站。仓库的 **Settings → Pages → Build and deployment → Source** 应设为 **GitHub Actions**。更新与部署合并在同一个任务中，申请 `contents: write`、`pages: write` 和 `id-token: write`；Pull Request 测试任务仅有读取权限。无需个人访问令牌或额外 Secret。

## 数据来源

- [FreeExchangeRateApi](https://github.com/haxqer/FreeExchangeRateApi)
- [官方网站](https://www.exchangerate.fun/)
- [上游接口](https://api.exchangerate.fun/latest?base=USD)

汇率仅供参考，实际交易以服务提供方报价为准。
