# 格物简录当前进度（2026-03-18）

本文档用于记录 2026-03-18 时点的实际开发状态，帮助后续继续开发、排障、部署与任务拆解。

## 1. 当前总体判断

项目当前处于：

- `Web MVP 基本成型`
- `后端核心接口可用`
- `账号体系已打通`
- `实时通知底座已接通`
- `香港服务器线上可运行`

但还没有到“可稳定运营的完整产品”阶段。当前最大未完成项不在视觉层，而在：

- 数据采集与内容生产链路
- 微信小程序端到端验收
- 外部通知渠道
- 发布质量门槛与回滚流程

## 2. 当前已完成

### 2.1 Web UI

当前 Web UI 已具备以下页面与主链路：

- 官网首页：`web-ui/src/app/page.tsx`
- 查询页：`web-ui/src/app/search/page.tsx`
- 管理页：`web-ui/src/app/admin/page.tsx`

已完成的关键能力：

- 站点基础 UI 已成型
- 查询页已接真实后端接口
- 管理页已接真实数据层
- 登录/注册/退出/会话恢复已接通
- 关注抽屉、Toast、实时通知动画已落地
- 数据层已统一到 Axios 网关 + thin wrappers + hooks 的方向

### 2.2 Portal 用户体系

普通用户账号体系已经具备完整基础闭环：

- 注册
- 登录
- Refresh
- Logout
- `GET /auth/me`

相关文档：

- `docs/auth_login_architecture.md`

当前实现特点：

- Access Token + Refresh Token 双层机制
- Refresh Token 走 HttpOnly Cookie
- 支持会话撤销与后续风控升级

### 2.3 通知实时链路

站内实时通知第一阶段已经落地：

- 内容写库时写入 `notification_outbox`
- worker 轮询消费 outbox
- 结果写入 `notification_deliveries`
- 前端通过 SSE 接收实时通知

相关文档：

- `docs/notification_realtime_architecture_2026-03-17.md`

当前已完成：

- Outbox + Delivery 模型
- `FOR UPDATE SKIP LOCKED` 消费模式
- SSE 流接口
- 前端缓存合并、Toast、关注抽屉联动

### 2.4 管理端

当前管理端已有：

- 管理员登录
- 用户列表
- 提升管理员
- 审计日志基础能力
- 健康状态展示

管理页已完成从页面内散乱请求向 hooks / API wrapper 的迁移。

### 2.5 服务器与部署

香港服务器线上状态已确认：

- `kaoyan-backend.service`：运行中
- `nginx.service`：运行中
- `gewujl-backup.service`：非长期驻留型服务，通常配合定时器触发

线上域名：

- `https://gewujl.cloud`
- `https://www.gewujl.cloud`
- `https://api.gewujl.cloud`

当前 Redis 状态：

- Redis 未启用，健康检查显示 `down`
- 但主链路不依赖 Redis，当前系统可降级运行
- Redis 主要用于限流增强和未来扩展，不阻塞当前 MVP

### 2.6 抓取任务流最小闭环（Task Pack A）

已新增最小可运行抓取任务链路：

- `POST /api/v1/crawl-jobs`（创建任务）
- `GET /api/v1/crawl-jobs`（列表）
- `GET /api/v1/crawl-jobs/{job_id}`（状态）
- 后台 worker 消费 `crawl_jobs`，状态流转：`pending -> running -> done|failed`

当前已具备：

- 支持 `source_url` 拉取并入库 `contents`
- 支持 `simulate`/`content` 占位型任务，验证端到端链路
- 成功路径可保留原始快照到 `content_snapshots`（有 `raw_html` 时）
- 失败路径写入 `crawl_errors`，并回写任务失败信息

### 2.7 小程序主流程稳定性补丁（Task Pack B）

已补齐一轮小程序主流程稳定性补丁：

- silent login 增加“等待但不阻塞”的降级策略
- 首页会明确显示当前访问模式与静默登录降级状态
- detail 页面增加缺字段兜底
- status 页面统一错误展示与返回逻辑
- 已新增 miniapp smoke checklist 文档

当前判断：

- 代码层面的主流程保护已补上
- 但仍建议在微信开发者工具中按 checklist 再做一次人工 smoke

### 2.8 外部通知最小通道（Task Pack C）

在现有站内 SSE 通知基础上，已补一个最小外部通道：

- 当前接入 `Bark`
- 用户可保存 Bark key 并启用外部通知
- `notification_deliveries` 支持按 `channel` 区分投递
- worker 会继续消费外部通道 delivery
- 失败会重试并留 `failed/last_error`

当前判断：

- 已具备最小可运行外部通知能力
- 生产发布前仍需确认数据库结构已同步

### 2.9 发布与回滚清单（Task Pack D）

已新增独立发布/回滚检查清单文档，包含：

- 预发布检查
- Health check 步骤
- Redis 降级判定
- 标准发布步骤
- 标准回滚步骤
- Bark 相关表结构变更提醒

### 2.10 官网栏目发现链路（Task Pack A-2 + A-3 Lite）

已新增“站点资产层 + 列表发现层”的最小落地：

- 数据层新增：
  - `departments`
  - `site_sections`
  - `site_section_links`
  - `content_files`（轻量占位）
- 新增管理接口：
  - `POST /api/v1/site-sections`
  - `GET /api/v1/site-sections`
  - `POST /api/v1/site-sections/discover`
  - `GET /api/v1/site-sections/{id}/links`
- worker 新能力：
  - 处理 `job_kind=site_section_discovery`
  - 从栏目页列表发现新链接
  - HTML 链接生成后续详情抓取任务
  - PDF 链接写入 `content_files` 占位记录
- 失败可观测：
  - discovery 失败写 `crawl_errors`
  - `site_sections` 回写 `last_discovery_status / last_error`

## 3. 当前未完成 / 未收尾

### 3.1 微信小程序主流程尚未完成正式验收

`docs/plan.md` 中的 Phase 1 仍有未收尾项：

- 静默登录 fallback 还未做完整验收
- 查询筛选链路还未完成小程序端到端确认
- detail 页面缺字段兜底仍需专项验证
- status 页面用户提示仍需继续统一

当前判断：

- 小程序并非“完全没做”
- 代码补丁已到位
- 但还不能认定为“已完成上线级别验收”，仍需按 smoke checklist 人工确认

### 3.2 数据采集与内容生产链路未闭环

这是当前最大缺口。

还未完全做实的部分：

- 多站点真实抓取策略（UA 轮换、频控、重试）的生产级实现
- `sources` 驱动的调度策略与优先级机制
- 解析规则质量与字段标准化的系统化验证
- 列表页精细抽取规则（当前仍是通用 `<a>` 发现）
- 跨栏目去重与公告聚合策略
- PDF 正文抽取/OCR（当前仅 `content_files` 占位留痕）
- 去重策略的完整验证（跨源/跨轮次）
- 内容持续稳定灌入后台数据库

当前更像是：

- 平台结构已准备好
- 但“稳定生产新内容”的系统还没彻底打磨完

### 3.3 通知系统只完成站内通道

当前已完成：

- 站内 SSE 实时通知
- Bark 最小外部通道

当前未完成：

- WxPusher
- 第三方通道的批量聚合出站优化
- 多渠道通知策略

### 3.4 管理后台仍偏早期

虽然后台已能用，但还不是完整中控系统。

当前仍可继续补：

- 用户状态编辑
- 更细粒度的审计筛选
- 内容审核/人工录入工作流打磨
- 更完整的运维状态面板
- 抓取/内容生产的可观测面板

### 3.5 质量门槛与发布规范尚未完全成型

`docs/plan.md` 中的 Phase 3 仍未完成：

- 统一 release checklist
- miniapp smoke checklist
- rollback 验证流程
- 20 分钟内可重复执行的预发布检查

当前更新：

- checklist 文档已补
- 还缺一次团队按文档实跑验证

## 4. 当前技术状态判断

### 4.1 已比较稳定的部分

- FastAPI 主 API
- Portal 用户认证
- Web UI 基础查询能力
- 管理端基本能力
- SSE 站内通知底座
- 香港服务器部署链路

### 4.2 当前属于“能跑但还要继续打磨”的部分

- 小程序主流程
- 数据抓取与内容生产
- 后台管理的深度能力
- 外部通知渠道
- 运维发布与回滚标准化

## 5. 建议优先级

如果按价值和阻塞关系排序，建议后续这样推进：

### Priority 1：补完数据采集生产链路

原因：

- 没有稳定内容生产，前台再完整也只是展示壳
- 这是整个平台长期价值的核心

建议目标：

- 定时抓取
- 去重
- 入库
- 失败留痕
- 管理端可见抓取结果

### Priority 2：完成微信小程序端到端验收

建议验收清单：

- 登录
- 查询
- 列表
- 详情
- 状态页
- 异常路径

目标：

- 把小程序从“有页面”推进到“可稳定使用”

### Priority 3：通知系统进入第二阶段

建议先完成一个外部通道即可：

- WxPusher
或
- Bark

不建议一开始同时做多个渠道。

### Priority 4：补发布清单与回滚说明

建议明确：

- 环境变量
- 备份前检查
- 部署步骤
- 健康检查
- 回滚方法

## 6. 当前建议的下一步

最建议马上启动的不是重新设计页面，而是：

1. 明确并实现爬虫/内容生产链路的最小可运行方案
2. 完成一次小程序端到端联调验收
3. 选一个外部通知渠道做第二阶段接入
4. 锁定发布清单

## 7. 一句话总结

截至 2026-03-18：

- 网站、后端、账号体系、实时通知、服务器部署已经进入“可工作的 MVP 阶段”
- 最大短板在数据生产与小程序闭环
- 后续开发不应再优先花力气重做 UI，而应优先补齐内容供给、通知外发、验收和发布规范
