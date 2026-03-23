# 通知实时链路（Outbox + SKIP LOCKED + SSE）

更新时间：2026-03-17

## 目标

- 不引入 Celery / Redis 队列，直接基于 MySQL 实现可靠通知链路。
- 支持多进程并发消费，避免重复推送和锁冲突。
- 前端通过 SSE 接收通知，后端业务状态仍以 MySQL 为准。
- 在线用户优先走内存连接池实时推送，离线或断连用户仍可通过 delivery 表补拉。

## 数据表

### `notification_outbox`

- 作用：内容入库时的事务收件箱。
- 关键字段：
  - `status`：`pending | processing | done | failed`
  - `available_at`：重试/延迟投递时间
  - `attempts`：重试次数
- 关键索引：
  - `ix_outbox_status_created(status, created_at)`

### `notification_deliveries`

- 作用：按用户分发后的投递箱（站内 SSE 与外部通道的共同兜底层）。
- 关键字段：
  - `user_id`
  - `channel`：当前支持 `inapp | bark`
  - `status`：`pending | processing | sent | failed`
  - `deliver_after`：用于 3 分钟聚合窗口
  - `processing_started_at`：外部通道发送中的抢占标记
- 关键约束：
  - `uq_notification_deliveries_outbox_user_channel`，防止同一 outbox 对同一用户同一通道重复插入

## 链路流程

1. `/content` 或 `/admin/manual-entry` 调用 `upsert_content`。
2. 内容写库同事务新增 `notification_outbox` 记录。
3. 后台 worker 轮询 `notification_outbox`：
   - 使用 `FOR UPDATE SKIP LOCKED` 抢占任务（SQLite 自动降级）。
   - 热更新订阅缓存。
   - 用 AC 自动机（`pyahocorasick`）+ 类型规则匹配用户。
   - 写入 `notification_deliveries`，并标记 outbox 为 `done`。
   - 对 `inapp` 且 `deliver_after<=now` 的 delivery，如果用户当前在线，则直接推入该用户的 SSE 队列。
4. 后台 worker 继续轮询外部通道 delivery：
   - 当前最小实现支持 `Bark`
   - 到达 `deliver_after` 后发送
   - 成功标记 `sent`
   - 失败按重试窗口回到 `pending`，超过最大次数标记 `failed`
5. 前端连接 `GET /api/v1/notifications/stream`：
   - 连接时先补拉当前用户 `pending + deliver_after<=now` 的投递记录，并标记为 `sent`。
   - 然后进入该用户的内存 SSE 队列等待实时消息。
   - 收到实时消息后，会再次尝试按 delivery id 原子 claim；claim 成功才真正下发给前端。
   - 这样可以避免“首次补拉”和“实时队列”命中同一条 delivery 时双发。

## SSE 连接管理

- 当前实现维护一个全局 `ConnectionManager`，按 `user_id -> [asyncio.Queue, ...]` 保存在线连接。
- 同一用户可同时保留多个活跃 SSE 连接，用于多个可见标签页或多窗口并发接收站内通知。
- 通知 worker 是同步线程环境，因此推送到 SSE 队列时必须通过线程安全方式切回对应事件循环。
- 前端收到同一条 SSE `notice` 后，会先更新各自标签页的通知缓存，再通过浏览器级 claim gate 决定哪个标签页真正展示 Toast。
- MySQL 中的 `notification_deliveries` 仍是最终状态来源：
  - 在线推送成功前，delivery 仍保留 `pending`
  - SSE 侧 claim 成功后再改成 `sent`
  - 如果用户不在线或连接中断，稍后仍能通过 `/notifications/pending` 或 SSE 首次补拉拿到这条通知

## 新接口

- `GET /api/v1/notifications/pending`
  - 调试/轮询接口，返回并消费当前用户待推送通知。
- `GET /api/v1/notifications/stream`
  - SSE 实时流接口，事件类型：
    - `notice`：实际通知数据
    - `ping`：心跳
- `GET /api/v1/auth/me/notifications/bark`
  - 查询当前用户 Bark 通道配置
- `PUT /api/v1/auth/me/notifications/bark`
  - 更新当前用户 Bark device key 与启用状态

## 环境变量

新增：

- `ENABLE_NOTIFICATION_WORKER`
- `NOTIFICATION_BATCH_SIZE`
- `NOTIFICATION_POLL_INTERVAL_SECONDS`
- `NOTIFICATION_CACHE_REFRESH_SECONDS`
- `NOTIFICATION_BATCH_WINDOW_SECONDS`
- `NOTIFICATION_INAPP_DELAY_SECONDS`
- `NOTIFICATION_RETRY_DELAY_SECONDS`
- `NOTIFICATION_MAX_ATTEMPTS`
- `NOTIFICATION_PROCESSING_TIMEOUT_SECONDS`
- `NOTIFICATION_SSE_POLL_SECONDS`
- `ENABLE_BARK_NOTIFICATIONS`
- `BARK_SERVER_URL`
- `BARK_PUSH_GROUP`
- `BARK_PUSH_SOUND`

## 说明

- 这是“战役一”可运行版，已满足：
  - 事务收件箱
  - 多进程抢占消费
  - 热更新订阅匹配
  - SSE 实时推送 + delivery 表兜底
- 当前已补 `Bark` 最小外部通道，`inapp(SSE)` 逻辑保持不变。
- `inapp(SSE)` 默认即时投递（`NOTIFICATION_INAPP_DELAY_SECONDS=0`），批量窗口主要用于外部通道。
