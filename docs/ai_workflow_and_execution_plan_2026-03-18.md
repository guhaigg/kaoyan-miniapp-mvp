# AI 协作工作流与近期执行计划（2026-03-18）

本文档用于统一当前项目的 AI 分工方式，并给出一组可以直接交给 `gpt-5.3-codex` 实现的任务包。

## 1. 推荐 AI 分工

### `gpt-5.4`

适合负责：

- 判断优先级
- 定方案
- 做取舍
- 审查阶段性结果
- 判断是否可以发布

不建议让它只做零碎小补丁，它更适合做“主线判断”和“最后把关”。

### `gpt-5.3-codex`

适合负责：

- 按明确任务单直接实现代码
- 多文件联动修改
- API / hooks / services / 页面联调
- 跑验证、补最小文档
- 在已有方案约束下推进

当前仓库最适合由它承担“主执行者”角色。

### `gpt-5.4-mini`

适合负责：

- 小函数
- 小样式
- 小范围 refactor
- 快速问答和草稿

不建议单独负责多文件主线任务。

### Claude / LongCat

适合负责：

- 文档整理
- 远程排查辅助
- 开发说明补充
- 基于规则的收尾工作

不建议让它单独做需要强上下文约束的大型代码改造。

## 2. 当前实际优先级

结合当前仓库状态，后续优先级建议如下：

### Priority 1：数据采集与内容生产链路

原因：

- 这是平台最核心的价值来源
- 当前 Web / 后端 / 账号体系已可用，但缺稳定内容生产
- 没有稳定抓取与入库，前台能力再完善也只是空转

### Priority 2：微信小程序端到端验收与补强

原因：

- 小程序页面已存在，但主流程没有完成正式验收
- 这里关系到产品是否真正可交付给用户使用

### Priority 3：通知系统第二阶段

原因：

- 站内 SSE 已可用
- 但“真正触达用户”的外部通道还没有
- 这属于 MVP 可运营化的重要一步

### Priority 4：发布门槛与回滚清单

原因：

- 当前系统已经开始有线上运行状态
- 如果继续开发而不补发布规范，后续上线风险会越来越大

## 3. 总体方案

近期不建议再优先投入大规模 UI 重做，而是按下面的顺序推进：

1. 先把“数据生产”从概念变成可运行链路
2. 再把“小程序主流程”验收到可用
3. 再给通知系统补一个外部渠道
4. 最后把发布清单、回滚清单、验证流程锁死

## 4. 可直接派给 `gpt-5.3-codex` 的任务包

以下任务包按照优先级排序，建议逐包推进，不建议并行开太多。

---

## Task Pack A：补齐最小可运行的抓取任务流

### 目标

让 `crawl_jobs`、`content_snapshots`、`crawl_errors` 这条线真正开始工作，先形成“可追踪、可落库、可失败留痕”的最小实现。

### 当前依据

- 已有模型：
  - `backend/app/models.py`
  - `CrawlJob`
  - `CrawlError`
  - `ContentSnapshot`
- 已有内容写库能力：
  - `backend/app/services/content.py`
- 已有管理端手动录入：
  - `backend/app/routers/admin.py`
- 规格文档：
  - `docs/backend_and_crawler.md`

### 需要 `5.3-codex` 做的事

1. 新增最小抓取任务 API
   - 创建 refresh job
   - 查询 job 状态/列表
2. 实现一个最小 worker
   - 能消费 `pending` 的 `crawl_jobs`
   - 能把执行结果更新为 `running / done / failed`
3. 先不做复杂爬虫框架
   - 先支持“模拟/占位型抓取结果”或“手工 URL 拉取 -> 内容入库”的最小闭环
4. 失败时写入 `crawl_errors`
5. 成功时保留原始快照到 `content_snapshots`

### 建议交付边界

- 不追求一步到位做成完整多站点爬虫系统
- 先把任务生命周期和失败可观测性做出来

### 验收标准

- 能创建 `crawl_jobs`
- worker 能消费任务
- 任务状态可查
- 成功时内容能进 `contents`
- 失败时能留 `crawl_errors`
- 原始快照可查

### 建议重点文件

- `backend/app/models.py`
- `backend/app/services/content.py`
- `backend/app/routers/admin.py`
- 新增 `backend/app/services/crawler*.py` 或等价模块
- 新增对应 tests

---

## Task Pack B：完成小程序主流程验收补丁

### 目标

把 miniapp 从“有页面”推进到“主流程稳定可用”。

### 当前依据

- `miniapp/app.js` 已有 silent login
- `miniapp/pages/announcements/*`
- `miniapp/pages/adjustments/*`
- `miniapp/pages/detail/*`
- `miniapp/pages/status/*`

### 需要 `5.3-codex` 做的事

1. 系统性验证 silent login 成功/失败两条路径
2. 补 detail 页面缺字段兜底
3. 统一 status 页面报错文案和跳转逻辑
4. 验证 announcements / adjustments 的筛选参数与跳转链路
5. 给 miniapp 增加一份 smoke checklist 文档

### 验收标准

- `wx.login` 成功和失败都不阻塞浏览
- 搜索 -> 列表 -> 详情 全链路可用
- detail 页面遇到缺字段不崩
- status 页面报错信息稳定、可读
- 有一份可重复执行的小程序 smoke checklist

### 建议重点文件

- `miniapp/app.js`
- `miniapp/pages/home/index.js`
- `miniapp/pages/announcements/index.js`
- `miniapp/pages/adjustments/index.js`
- `miniapp/pages/detail/index.js`
- `miniapp/pages/status/index.js`
- `miniapp/utils/status.js`

---

## Task Pack C：通知系统补一个外部通道

### 目标

在现有 SSE 站内通知之外，接一个最小外部通知通道。

### 推荐先做

- `WxPusher` 或 `Bark` 二选一

### 当前依据

- 现有站内实时链路文档：
  - `docs/notification_realtime_architecture_2026-03-17.md`
- 已有表：
  - `notification_outbox`
  - `notification_deliveries`

### 需要 `5.3-codex` 做的事

1. 选定一个通道
2. 在 `notification_deliveries` 基础上增加一个最小出站 sender
3. 做最基础的失败重试和错误留痕
4. 保持 `inapp` 逻辑不回归

### 验收标准

- 指定订阅用户能收到外部通知
- 失败可见
- 不影响现有 SSE

### 注意

- 不建议一上来同时做 WxPusher + Bark
- 不建议在这一阶段引入新的 MQ

---

## Task Pack D：发布清单与回滚清单

### 目标

把当前“能上线”推进到“敢发布”。

### 需要 `5.3-codex` 做的事

1. 补 release checklist
2. 补 rollback checklist
3. 补 health check 验证步骤
4. 把 Redis 降级状态写清楚，避免误判为硬故障

### 建议交付

- `docs/deployment.md` 补充
- 或新增单独发布清单文档

### 验收标准

- 团队能按文档在 20 分钟内完成一次预发布检查
- 回滚步骤明确
- 健康检查标准明确

## 5. 推荐执行顺序

建议你按下面的顺序把任务交给 `gpt-5.3-codex`：

1. `Task Pack A`
2. `Task Pack B`
3. `Task Pack D`
4. `Task Pack C`

这样排序的原因：

- A 决定有没有持续内容供给
- B 决定小程序是否可用
- D 决定后续每次上线是否稳
- C 是增强价值，但不应先于 A/B

## 6. 你给 `gpt-5.3-codex` 的推荐指令模板

### 模板 1：单任务包执行

```text
请先阅读 AGENTS.md、CLAUDE.md、docs/current_status_2026-03-18.md、docs/ai_workflow_and_execution_plan_2026-03-18.md。
然后只执行 Task Pack A。

要求：
1. 先阅读相关代码并确认改动范围
2. 只做这个任务包，不顺手扩展其他包
3. 每完成一个有意义步骤，先告诉我做了什么，再继续
4. 改完后运行相关验证
5. 最后更新对应 docs，并告诉我剩余风险
```

### 模板 2：先出实现方案再动手

```text
请先阅读 AGENTS.md、CLAUDE.md、docs/current_status_2026-03-18.md、docs/ai_workflow_and_execution_plan_2026-03-18.md。
针对 Task Pack B，先给我：
1. 改动范围
2. 影响文件
3. 最小实现方案
确认后再改代码。
```

## 7. 一句话建议

当前阶段最值钱的不是继续重做前台，而是把：

- 数据生产
- 小程序验收
- 发布门槛

这三件事做实。后续所有新功能都应该建立在这三件事完成之后。
