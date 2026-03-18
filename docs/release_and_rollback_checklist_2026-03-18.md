# Release and Rollback Checklist（2026-03-18）

目标：把当前项目的发布前检查、上线步骤、回滚步骤收束为 20 分钟内可重复执行的固定流程。

## 1. 预发布检查

- 确认代码分支与目标提交正确
- 确认后端运行 Python `>=3.11`
- 确认 Node.js `>=20`
- 确认 `backend/.env` 已配置生产值
- 确认 `USE_MOCK_WECHAT=false`
- 确认 `CORS_ALLOW_ORIGINS` 不使用 `*`
- 确认数据库可连通
- 确认 `ADMIN_TOKEN` 或管理员会话可用

## 2. 数据库结构检查

当前仓库仍以 `create_all()` 为主，不能自动修改已存在表结构。

如果生产库已经存在以下表，发布包含 Bark 通知功能的版本前，需要先补齐结构：

```sql
ALTER TABLE portal_users
  ADD COLUMN notify_bark_key VARCHAR(255) NULL,
  ADD COLUMN notify_bark_enabled INTEGER NOT NULL DEFAULT 0;

ALTER TABLE notification_deliveries
  ADD COLUMN processing_started_at DATETIME NULL;

DROP INDEX uq_notification_deliveries_outbox_user ON notification_deliveries;

CREATE UNIQUE INDEX uq_notification_deliveries_outbox_user_channel
  ON notification_deliveries (outbox_id, user_id, channel);
```

如果是全新库，可直接由应用启动时建表。

## 3. Health Check 清单

上线前后至少执行一次：

- `GET /api/v1/health`
- 管理后台健康页是否可打开
- 管理员登录是否正常
- 普通用户登录是否正常
- `POST /api/v1/search/announcements` 是否返回 200
- `POST /api/v1/search/adjustments` 是否返回 200
- `GET /api/v1/notifications/pending` 是否返回 200（带用户 token）

## 4. Redis 降级判定

Redis 当前不是 MVP 主链路硬依赖。

判定规则：

- `health` 中 Redis 为 `down`，但搜索、登录、内容写入仍正常：记为“降级运行”，不是阻塞发布的硬故障
- 如果接口开始出现大面积 429、鉴权异常或通知异常，再升级为发布阻塞问题

## 5. 标准发布步骤

1. 备份当前生产快照
2. 拉取目标提交
3. 安装后端依赖
4. 如有表结构变化，先执行数据库 DDL
5. 重启后端服务
6. 执行 health check
7. 验证 Web 首页、查询页、管理页
8. 验证 miniapp smoke checklist
9. 验证通知链路：
   - 站内 SSE
   - 如已配置 Bark，再验证一次外部通知
10. 记录发布结果和异常

## 6. 回滚触发条件

满足任一条件可直接回滚：

- `/api/v1/health` 连续失败
- 登录主链路失败
- 搜索接口连续失败
- 内容写库或通知链路出现明显异常
- miniapp 主流程无法浏览

## 7. 标准回滚步骤

1. 停止继续流量切换
2. 切回上一版后端代码或镜像
3. 重启服务
4. 重新验证 `/api/v1/health`
5. 验证登录与搜索主链路
6. 如本次发布执行过数据库 DDL，评估是否需要手动回退
7. 记录故障时间、影响范围、回滚结果

## 8. 发布后观察项

- `crawl_jobs` 是否有堆积
- `notification_outbox` 是否有持续 `pending/failed`
- `notification_deliveries` 是否出现异常大量 `failed`
- 管理端健康页中的 Redis 状态是否只是降级而非业务中断
