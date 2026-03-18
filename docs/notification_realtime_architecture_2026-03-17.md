# 通知实时链路（Outbox + SKIP LOCKED + SSE）

更新时间：2026-03-17

## 目标

- 不引入 Celery / Redis 队列，直接基于 MySQL 实现可靠通知链路。
- 支持多进程并发消费，避免重复推送和锁冲突。
- 前端通过 SSE 接收通知，后端保持无状态。

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

- 作用：按用户分发后的投递箱（SSE 读取此表）。
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
4. 后台 worker 继续轮询外部通道 delivery：
   - 当前最小实现支持 `Bark`
   - 到达 `deliver_after` 后发送
   - 成功标记 `sent`
   - 失败按重试窗口回到 `pending`，超过最大次数标记 `failed`
5. 前端连接 `GET /api/v1/notifications/stream`：
   - 每轮查询当前用户 `pending + deliver_after<=now` 的投递记录。
   - 推送后标记为 `sent`。

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
  - SSE 无状态推送
- 当前已补 `Bark` 最小外部通道，`inapp(SSE)` 逻辑保持不变。
- `inapp(SSE)` 默认即时投递（`NOTIFICATION_INAPP_DELAY_SECONDS=0`），批量窗口主要用于外部通道。
