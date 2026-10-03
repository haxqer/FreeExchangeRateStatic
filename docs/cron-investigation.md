# 2026-10-03 定时调度排查

取证时间：2026-10-03 20:34:46（Asia/Singapore，即 UTC 12:34:46）。
原始证据见 [cron-investigation.json](cron-investigation.json)。该文件是本次查询的快照，不代表后续运行状态。

## 结论及边界

旧 cron 语法正确，工作流在默认分支上且处于启用状态，并已被 GitHub 定时触发过。缺失小时没有可见的 workflow run；已创建的两次定时运行很快开始并成功完成。故障范围位于创建运行之前的定时事件处理阶段，未发现脚本或部署步骤导致该空档的证据。

这不足以确认 GitHub 内部为何没有创建运行。公开 API 不提供每个计划时刻的调度记录、事件投递失败原因或丢弃日志。本次没有查询 GitHub 内部日志，也没有向 GitHub 提交支持请求。不能把“高负载”“新仓库注册延迟”或“平台故障”写成已经确认的根因。

查询到的公开运行记录可能不包含已经删除的运行；本次没有删除运行的证据，也不能从该 API 独立排除历史删除。结论以当前可见记录为依据。

## 旧配置与运行时间线

仓库于当日 10:48:15 创建；更新工作流于 10:55:52 注册，归档工作流于 11:21:43 注册。更新工作流自首次提交开始即使用 `17 * * * *`；归档为 `27 * * * *`。二者均使用 UTC，分钟不会因新加坡时区发生变化。

稳定旧配置为提交 `9a9754190b8abc8709023705e72a77c01a4c01ea`，由 `haxqer` 提交，11:21:44 已产生 push 运行。直到 20:17:19 新配置的 push 运行创建之前，旧表达式没有改动。

以下时间均为 2026-10-03 新加坡时间：

| 时间 | 事件 | 结果 |
| --- | --- | --- |
| 11:21:44 | 两个旧工作流由 push 触发 | 成功，分别在 11:22:03、11:22:24 完成 |
| 12:00–16:59 | 五个完整小时 | 没有可见的运行记录 |
| 17:07:37 | [更新定时运行 37111991272](https://github.com/haxqer/FreeExchangeRateStatic/actions/runs/37111991272) | update job 于 17:07:42 开始，17:07:56 完成 |
| 17:17:06 | [归档定时运行 37112524127](https://github.com/haxqer/FreeExchangeRateStatic/actions/runs/37112524127) | archive job 于 17:17:11 开始，17:17:28 完成 |
| 18:00–19:59 | 两个完整小时 | 没有可见的运行记录 |
| 20:17:19 | 增加触发次数的提交由 push 触发 | 两个工作流成功；这不等于定时调度已恢复 |

旧配置运行按第 17、27 分钟计划，却在第 07、17 分钟创建，两者相差 10 分钟与计划一致，存在一起延迟的迹象。但 REST 运行记录没有对应的计划时刻，不能断言它们就是上一小时延迟约 50 分钟的事件。

在稳定旧配置启用后、UTC 12:17 之前，更新计划覆盖 UTC 04:17–11:17 的 8 个时刻，归档覆盖 UTC 03:27–11:27 的 9 个时刻。API 只显示 2 个 schedule 运行；不能精确把这两次运行分配给某个计划时刻，因此这只是计划覆盖与运行记录的对照，不是精确的丢弃计数。

## 已核对的条件

| 检查 | 证据与判断 |
| --- | --- |
| 默认分支和文件位置 | 默认分支 `main`，旧配置文件均在该分支 |
| Actions 开关 | `enabled: true`、`allowed_actions: all` |
| 工作流状态 | 两个工作流均为 `active` |
| Fork / 归档 / 禁用 | 仓库不是 fork、未归档、未禁用 |
| 60 天无活动自动禁用 | 仓库当天创建且持续有提交，不符合该条件 |
| 身份及执行条件 | 两次 schedule 的 actor 均为 `haxqer`，head branch 为 `main`，采集 job 均执行成功 |
| 并发锁 | 全部 10 个可见运行均成功，没有取消记录。并发锁作用于已创建的运行，无法解释没有任何运行记录的多小时空档 |
| Runner 等待 | 两次定时采集 job 都在创建运行后约 5 秒开始；不是数小时等待 runner |
| Pages 人工审批 | 环境只有分支策略，没有 required reviewers 或 wait timer |
| 上游/API/部署 | 两次定时运行采集及部署均成功；这些步骤发生在创建运行之后，不能解释缺少运行记录 |
| GitHub 状态公告 | 查询快照没有未解决事故；最近的 Actions 延迟公告发生于 10 月 1 日，未覆盖本次空档。状态正常也不能排除局部调度异常 |

## 官方说明与尚未确认的原因

[GitHub schedule 文档](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)说明，高负载时定时事件可能延迟，负载足够高时部分排队任务可能被丢弃，建议避开整点。旧配置已经避开整点；本次没有后台证据证明具体属于延迟还是丢弃。

[并发文档](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency)说明，默认并发组只能有一个 running 和一个 pending；`cancel-in-progress: false` 不保证保留多个 pending。原方案存在潜在的 pending 替换风险，但本次没有取消记录，不能把它认定为旧空档的原因。

精确根因仍需要 GitHub 对仓库 `haxqer/FreeExchangeRateStatic`、两个旧 workflow ID `373642597` / `373653612`、UTC 03:21–12:17 的内部计划事件进行查询。

## 仅使用 GitHub Actions 的修改

- 合并采集和发布为一个定时工作流，减少重复 API 请求、提交及独立触发链路。旧归档入口保留手动兼容调用，不再独立定时写入。
- 保留 UTC 每小时第 7、27、47 分钟的三次触发机会。它们降低单次漏触发的影响，不提供严格按时保证。
- 首次成功保存当前小时数据后，后续重试读取该快照，修复索引或最新文件，并重试发布。原小时快照和较新的 latest 不被覆盖。
- 历史先写入；后续采集步骤失败时，工作流仍尝试提交已写入的数据。推送成功后，临时 runner 被回收也不影响后续恢复。若推送本身失败，Actions 仍无法保证该数据留存。
- 每次运行摘要记录 `github.event_name`、`github.event.schedule`、实际 job 开始时间和运行链接。没有被创建的运行依然无法自行写日志。

这些修改解决仓库中可控的重复采集及部分失败恢复问题，不代表确认或修复了 GitHub 调度平台内部的问题。完全依赖 GitHub 的方案无法在 GitHub 不启动任务时完成采集；不伪造缺失小时。

## 复查入口

```bash
gh api --paginate 'repos/haxqer/FreeExchangeRateStatic/actions/runs?per_page=100' \
  --jq '.workflow_runs[] | {id,name,event,status,conclusion,created_at,run_started_at,head_sha}'
gh api repos/haxqer/FreeExchangeRateStatic/actions/workflows
gh api repos/haxqer/FreeExchangeRateStatic/actions/permissions
gh api repos/haxqer/FreeExchangeRateStatic/environments/github-pages
```

复查时区分 `push`、`workflow_dispatch` 和 `schedule`；手动或推送运行成功只能验证执行链路，不能用来证明 cron 正常。
