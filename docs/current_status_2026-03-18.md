# 格物简录当前进度（2026-03-18）

最近更新：`2026-03-26`

本文档是当前现状主文档，用于记录真实开发状态，帮助后续继续开发、排障、部署与任务拆解。

未来目标、阶段路线和执行顺序请看：

- `docs/plan.md`

## 1. 当前总体判断

项目当前处于：

- `Web MVP 基本成型`
- `后端核心接口可用`
- `账号体系已打通`
- `实时通知底座已接通`
- `香港服务器线上可运行`
- `网站侧用户中心与管理后台框架已成型`
- `Crawler V2 Phase 1 已开始落地（搜索只读 + 显式 bootstrap + 独立 worker）`

但还没有到“可稳定运营的完整产品”阶段。当前最大未完成项不在视觉层，而在：

- 数据采集与内容生产链路
- 微信小程序端到端验收
- 第三方支付闭环
- 发布质量门槛与回滚流程

新增的数据资产补充：

- `23-25 调剂统计表` 已转成重点学校/学院 seed
- `2024 调剂余额表` 和 `2025 调剂信息快照表` 已转成补充 seed 与摘要 JSON
- `2025 调剂上岸名单` 已转成学校/学院结果画像摘要
- `导师公开评价汇总表` 已转成只读摘要 JSON，当前作为独立情报源保留，未混入主搜索
- `历史调剂分数/上岸画像` 已开始结构化入库，支撑调剂搜索里的历史最低分、均分和样本提示

最近新增的系统收口：

- 研招公告可见性规则已补一轮收紧，普通新闻、工会通知、行政公开等历史内容不再因为正文里提到“研招”“研究生招生”就自动混入公告结果。
- 学校级公告冷启动已补 preferred host 约束与同校前缀冲突拦截，`学校名 + 学院/分校/校区` 这类 sibling host 或 branch host 更难再次污染学校级公告候选。
- `content_snapshots.raw_html` 已补安全字节截断，超长详情页不会再因为原始 HTML 过大直接打失败抓取任务。
- 已新增 `docs/crawler_v2_full_migration_architecture_2026-03-26.md`，明确后续爬虫体系不再继续把规则无限堆进单一 worker 文件。
- 本地分支已落一版 `Crawler V2 Phase 1`：搜索请求不再触发在线冷启动，V2 workflow 表与分类表已入模型，学校/院系 bootstrap 改成显式管理入口，API 进程内 crawl worker 已拆出。

## 2. 当前已完成

### 2.1 Web UI

当前 Web UI 已具备以下页面与主链路：

- 官网首页：`web-ui/src/app/page.tsx`
- 登录页：`web-ui/src/app/login/page.tsx`
- 注册页：`web-ui/src/app/register/page.tsx`
- 查询导航页：`web-ui/src/app/query/page.tsx`
- 查询页：`web-ui/src/app/search/page.tsx`
- 账号中心：`web-ui/src/app/account/page.tsx`
- 账号安全：`web-ui/src/app/account/security/page.tsx`
- 会员与支付：`web-ui/src/app/account/billing/page.tsx`
- 通知中心：`web-ui/src/app/account/notifications/page.tsx`
- 管理页：`web-ui/src/app/admin/page.tsx`

已完成的关键能力：

- 站点基础 UI 已成型
- 查询页已接真实后端接口
- 管理页已接真实数据层
- 登录/注册/退出/会话恢复已接通
- 用户中心已从弹窗中拆出，改为独立应用式页面
- 管理后台已改成稳定 dashboard/settings 框架，而不是临时表单堆叠
- 关注抽屉、Toast、实时通知动画已落地
- 数据层已统一到 Axios 网关 + thin wrappers + hooks 的方向
- 未登录用户只能查看公告检索前 2 条预览；调剂、收藏、深度功能需要登录或会员

### 2.2 Portal 用户体系

普通用户账号体系已经具备完整基础闭环：

- 注册
- 登录
- Refresh
- Logout
- `GET /auth/me`

相关文档：

- `docs/auth_login_architecture.md`
- `docs/account_system_transition_plan_2026-03-18.md`

当前实现特点：

- Access Token + Refresh Token 双层机制
- Refresh Token 走 HttpOnly Cookie
- 登录/静默登录接口同时在响应体返回 `refresh_token`，便于小程序接入
- 支持会话撤销与后续风控升级
- 账号模型主路径已切到：
  - `portal_users` 作为主账号表
  - `account_identities` 作为登录身份
  - `account_roles` 作为管理员角色
  - `account_entitlements` 作为会员权益
  - `account_payment_orders` 作为订单/支付单账本
- 当前运行时权限判定：
  - 管理员只认 `account_roles`
  - 高级会员只认 `account_entitlements`
  - 旧 `admin_accounts / premium_*` 已不再参与放权
- 遗留物理清理：
  - `admin_accounts` 与 `portal_users.premium_*` 已从生产库物理删除
  - `users` 微信影子表保留，等待小程序正式切换后再处理
- 网站侧账号闭环已上线：
  - 用户可查看账号总览、通知历史、会员订单并自助改密
  - 用户可创建网站会员订单
  - 管理员可查看订单账本并确认支付发放权益
- 管理员后台已直接复用门户管理员登录态，不再要求后台二次登录
- 微信身份接口已保留在 `account_identities(wechat_miniapp)` 路径上

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

### 2.3.1 调剂补充数据资产

本地 Excel 补充数据已经转成仓库内可追踪的数据资产：

- `docs/data/adjustment_priority_school_targets_2023_2025.json`
- `docs/data/adjustment_opportunity_2024_summary.json`
- `docs/data/adjustment_opportunity_2025_snapshot_summary.json`
- `docs/data/adjustment_landing_2025_summary.json`
- `docs/data/adjustment_supplemental_priority_targets_2024_2025.json`
- `docs/data/mentor_review_summary.json`

当前用途分层：

- `23-25 调剂统计`：主力学校/学院 seed
- `2024 调剂余额表`：补充学校/学院优先级
- `2025 调剂快照`：补充近期高频调剂学校
- `2025 调剂上岸名单`：学校/学院结果画像，用于优先级和调剂情报判断
- `导师评价汇总`：已进入结构化导入链路，服务导师避坑雷达与后台图表
- `historical_adjustment_profiles`：学校/专业/学习形式/年份维度的历史分数与样本聚合，直接服务调剂搜索与分数预估
- `mentor_evaluations`：导师评价结构化留存，已进入调剂搜索和后台情报面板
- `historical_release_timing_profiles`：按学校聚合的历史发布时间规律，服务调剂搜索里的发榜生物钟和后台时间图表

### 2.4 管理端

当前管理端已有：

- 门户管理员直接进入后台
- 用户列表
- 提升管理员
- 降级普通/高级用户
- 内容指纹覆盖率面板
- 会员订单账本
- 栏目选择器编辑与 selector 预览
- 调剂 seed 摘要、24/25 补充 seed 摘要、上岸结果画像、导师评价补充摘要
- 调剂情报面板与导师风险榜
- 发榜时间规律榜和发榜时段分布
- PDF 解析队列与重试入口
- 审计日志基础能力
- 健康状态展示

管理页已完成从页面内散乱请求向 hooks / API wrapper 的迁移，并已重构为应用式固定侧栏框架。

### 2.5 服务器与部署

香港服务器线上状态已确认：

- 当前生产机 IP：`38.76.215.159`
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

补充：

- 生产机源码仓库位于 `/root/code/kaoyan-miniapp-mvp`
- 后端真实运行目录位于 `/root/code/kaoyan-miniapp-mvp/backend`
- 前端真实站点目录位于 `/var/www/html`
- 服务器仓库已收敛到与 `origin/main` 一致
- 详细说明见：
  - `docs/server_layout_and_deploy_paths_2026-03-19.md`

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
  - `content_files`（PDF 文本抽取与 OCR 留痕）
- 新增管理接口：
  - `POST /api/v1/site-sections`
  - `GET /api/v1/site-sections`
  - `POST /api/v1/site-sections/discover`
  - `GET /api/v1/site-sections/{id}/links`
- worker 新能力：
  - 处理 `job_kind=site_section_discovery`
  - 从栏目页列表发现新链接
  - HTML 链接生成后续详情抓取任务
  - PDF 链接写入 `content_files` 并排入 `file_parse` 子任务
  - 文字型 PDF 自动提取正文并入库
  - 扫描型/低文本 PDF 标记为 `needs_ocr`，生成原文件占位内容
  - 链接型公告会生成补充说明与目标链接，不再把“点击查看/详见附件”原样丢给用户
- 失败可观测：
  - discovery 失败写 `crawl_errors`
  - `site_sections` 回写 `last_discovery_status / last_error`

### 2.10.2 Selector 治理工具

管理员后台现已支持：

- 编辑 `list_selector_config`
- 编辑 `detail_selector_config`
- 查看推荐规则
- 恢复推荐规则
- 实时预览列表提取结果
- 实时预览详情正文抽取结果与 warning

这部分的实际价值是：

- 控制 discovery 抓取范围
- 控制正文抽取范围
- 把“全页扫描”的噪音栏目收敛成可运营栏目

### 2.10.3 数据去重与搜索缓存

当前内容链路已经补齐：

- `content_fingerprint` 幂等去重
- MySQL / SQLite 迁移脚本
- 历史内容指纹回填
- 搜索前两页 TTL 缓存
- 内容更新后搜索缓存失效

当前判断：

- 公告检索已经进入“可用但仍需治理数据质量”的阶段
- 调剂检索主链路可用，但业务成熟度仍低于公告检索

### 2.10.4 调剂统计 Excel 已接入资产补齐流程

基于外部 `23-25调剂统计数据.xlsx`，当前已经补齐：

- 流式解析脚本：
  - `backend/scripts/build_adjustment_priority_targets.py`
- 机器可读摘要：
  - `docs/data/adjustment_stats_2023_2025_summary.json`
- 可导入的重点学校/学院 seed：
  - `docs/data/adjustment_priority_school_targets_2023_2025.json`
- 后台导入接口：
  - `POST /api/v1/schools/import/adjustment-priority-targets`

这一步的意义是：

- 不再只靠手工整理重点学校
- 可以用调剂历史样本反推优先补站点资产的学校和学院

### 2.10.1 正文抽取与标签化增强

详情抓取链路已补一轮“正文清洗 + 标签提取”增强：

- 正文抽取：
  - 优先使用 `detail_selector_config`
  - 若选择器命中不足，则降级到 `readability-lxml`
  - 若仍失败，则退回通用全文去标签文本
- 标签提取：
  - 接入 `jieba` 领域词增强
  - 自动提取如 `调剂 / 复试 / 拟录取 / 0854 / 电子信息` 等标签
  - 标签写入 `contents.extra.tags`
  - 搜索结果和通知 payload 可透传这些标签

### 2.11 高级监控 Phase 1（当前分支收口状态）

截至 2026-03-18，本分支高级监控 Phase 1 已具备最小可运行主链路：

- 数据层：`portal_user_monitor_targets / portal_user_monitor_keywords / portal_user_monitor_hits` 已在模型中落地。
- 接口层：`/api/v1/monitoring/*` 目标配置、关键词配置、命中查询、管理员命中查询接口已挂载。
- 权限层：普通用户无权限；高级会员权益从 `account_entitlements(premium_monitoring)` 读取，管理员从 `account_roles(admin)` 读取。
- 联动层：内容写入时会触发监控命中计算，并写入命中记录与 `notification_outbox(event_type=monitor.hit)`。
- 测试与文档：已补充 `backend/tests/test_premium_monitoring_authz.py` 与 `backend/tests/test_premium_monitoring_targets.py`，并同步 backend/crawler 与需求文档。

### 2.12 公告门户可见性与冷启动收口（2026-03-25 ~ 2026-03-26）

这一轮不是新增页面，而是收紧“什么算学校级研招公告”的后端判定边界，重点收口两类线上问题：

- 栏目 scope 元数据在 upsert/backfill 后被冲掉，导致监控命中失败
- 学校级公告冷启动把 sibling host、学院站或分校站重新当成学校级公告入口

当前已补齐：

- `announcement_portal` 可见性规则收紧，负向语义如“与研究生招生无关”“不属于研招”不再误提升普通历史新闻
- `site_section_id / site_section_name` 作为 scope 元数据保留，section 级监控 target 不再因为元数据重算丢 scope
- school-level announcement cold start 引入 preferred host 约束，已有 preferred host 时，缓存候选 URL 和 bootstrap 输出 section 都会尽量留在该 host 集合内
- 对 `学校名 + 学院/学部/研究院/分校/校区` 这类同校前缀冲突做了显式拦截，减少 `东北大学 -> 艺术学院 / 秦皇岛分校` 这类错误学校级匹配
- `content_snapshots.raw_html` 新增 UTF-8 字节预算截断和元数据记录，避免超长页面快照导致写库失败
- 针对以上规则新增了一轮后端回归测试，最近一轮 `npm run test:backend` 已达到 `237 passed`

这一轮的实际意义是：

- 学校级公告搜索结果比 3 月中旬更干净
- 学校级和院系级作用域边界比之前更稳定
- 抓取链路对“超长详情页”这一类工程性故障更稳
- 但它仍然是“把现有启发式系统收紧一轮”，还不是 V2 那种强类型 workflow + portal graph + explainable classification 架构

### 2.13 Crawler V2 Phase 1 落地状态（2026-03-26）

这一轮开始把“继续修冷启动”切到“重建执行主路径”，当前已经落下来的部分是：

- 搜索主路径改成只读：学校限定搜索只消费已批准 section 和 `content_classifications`，不会再因为用户请求在线触发 bootstrap、family discovery 或 repair job
- 新增 V2 表：`portal_nodes`、`portal_edges`、`portal_host_decisions`、`workflow_runs`、`workflow_steps`、`raw_artifacts`、`parse_artifacts`、`content_classifications`、`governance_actions`
- 新增管理入口：
  - `POST /api/v1/admin/bootstrap/schools`
  - `POST /api/v1/admin/bootstrap/departments`
  - `POST /api/v1/admin/rebuilds`
  - `POST /api/v1/admin/contents/{id}/reclassify`
  - `GET /api/v1/admin/contents/{id}/explain`
  - `POST /api/v1/site-sections/content-files/{id}/retry-ocr`
- API 进程内 crawl worker 已移除，V2 步骤由独立 worker `python -m app.workers.crawler_v2_worker` 消费
- 公告可见性已开始持久化到 `content_classifications`，搜索和高级监控都优先复用这份判定结果
- 学校级与院系级 bootstrap 已按 `scope_type + scope_key` 分轨，新的 workflow 路径不再把 `announcement_portal_caches.candidate_urls`、旧详情页 URL 或历史 `content.source_url` 当 discovery seed
- school / department bootstrap 已开始真实写入 `portal_nodes / portal_edges / portal_host_decisions / raw_artifacts / parse_artifacts`
- department bootstrap 若产出 school-scoped section，会直接终态失败并回滚本次部分写入，不再把 scope 错误当成可重试故障
- legacy `family_discovery` job 已新增受控 handoff 路径：带 `workflow_handoff=v2` 时，会直接转成 V2 `scope_rebuild` workflow，并优先使用显式 seed 或维护好的 canonical seed

当前边界：

- 这还不是“V2 完全迁移完成”，因为老的 `crawl_jobs`、`school_cold_start.py`、`site_section_bootstrap.py` 兼容路径仍在仓库里
- 但搜索不再承担冷启动职责，后续重构可以围绕离线 workflow、审核资产、统一分类引擎继续推进

## 3. 当前未完成 / 未收尾

### 3.1 微信小程序主流程尚未完成正式验收

当前主路线图里，小程序仍被放在 Web 正式可运营之后的后续阶段。当前未收尾项主要是：

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
- 跨栏目去重与公告聚合策略
- OCR（当前仅支持文字型 PDF 自动提取，扫描型 PDF 会标记 `needs_ocr`）
- 去重策略的完整验证（跨源/跨轮次）
- 内容持续稳定灌入后台数据库

当前更像是：

- 平台结构已准备好
- 但“稳定生产新内容”的系统还没彻底打磨完

补充判断（2026-03-26）：

- 公告门户可见性、历史脏数据过滤、学校级冷启动 preferred host 约束已经比 3 月中旬明显更稳
- 新落地的 V2 Phase 1 已经把搜索从冷启动主路径上摘下来，但核心问题仍没完全解决：当前抓取体系仍处于“V1/V2 并行过渡态”，还不是“强类型任务 + 证据图谱 + 统一分类引擎”的唯一内容生产平台
- 所以后续主线不应再只是补一批 if/else，而应逐步朝 `Crawler V2` 文档定义的执行内核和治理架构迁移

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

当前仍未完全做实的部分：

- 统一 release checklist
- miniapp smoke checklist
- rollback 验证流程
- 20 分钟内可重复执行的预发布检查

当前更新：

- checklist 文档已补
- 还缺一次团队按文档实跑验证

### 3.6 高级监控 Phase 1 仍待收尾项

当前仍未闭环的关键点：

- 管理员侧虽然已有提权/降级路径，但高级监控与会员权益的产品化控制仍可继续收口。
- 命中策略目前仅 `contains`，尚未进入更复杂规则（regex/评分分层/高级排序）。

## 4. 当前技术状态判断

### 4.1 已比较稳定的部分

- FastAPI 主 API
- Portal 用户认证
- Web UI 基础查询能力
- 管理端基本能力
- SSE 站内通知底座
- 香港服务器部署链路
- 公告门户可见性基础规则
- 学校级公告冷启动的 preferred host 收敛逻辑

### 4.2 当前属于“能跑但还要继续打磨”的部分

- 小程序主流程
- 数据抓取与内容生产
- 后台管理的深度能力
- 外部通知渠道
- 运维发布与回滚标准化
- 生产 SSH / bundle 发布链路的稳定性

## 5. 建议优先级

如果按价值和阻塞关系排序，建议后续这样推进：

### Priority 1：补完数据采集生产链路，并开始 V2 迁移准备

原因：

- 没有稳定内容生产，前台再完整也只是展示壳
- 这是整个平台长期价值的核心

建议目标：

- 定时抓取
- 去重
- 入库
- 失败留痕
- 管理端可见抓取结果
- typed jobs / source intelligence / classification engine 的迁移边界

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

### Priority 4：补发布清单与运维链路稳定性

建议明确：

- 环境变量
- 备份前检查
- 部署步骤
- 健康检查
- 回滚方法
- 为什么生产 SSH 会在 `banner exchange / kex` 阶段间歇性被远端关闭

## 6. 当前建议的下一步

最建议马上启动的不是重新设计页面，而是：

1. 继续把学校级公告与院系级公告的边界守住，不让最近这一轮可见性和冷启动规则回退
2. 把爬虫/内容生产主线从“继续补启发式”推进到 `Crawler V2` 的执行内核和规则收口设计
3. 完成一次小程序端到端联调验收
4. 锁定发布清单，并排查生产 SSH 管理链路不稳定问题

## 7. 一句话总结

截至 2026-03-18：

- 网站、后端、账号体系、实时通知、服务器部署已经进入“可工作的 MVP 阶段”
- 最大短板在数据生产与小程序闭环
- 后续开发不应再优先花力气重做 UI，而应优先补齐内容供给、通知外发、验收和发布规范
