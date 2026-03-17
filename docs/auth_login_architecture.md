# 注册登录架构（Portal 用户）

## 目标

- 普通用户注册与登录可独立运行，不依赖管理员体系。
- Access Token 短期有效，Refresh Token 可轮换并可撤销。
- 支持后续接入风控（设备、IP、异常会话下线）而不推翻现有代码。

## 表结构

### `portal_users`

- 账号主表：`username`、`password_hash`、`status`、`last_login_at`。
- 用于业务身份（普通用户/被提升管理员用户共用）。

### `portal_user_sessions`

- 会话表：保存刷新令牌哈希（`token_hash`），而不是明文 token。
- 字段：`user_id`、`status`、`expires_at`、`revoked_at`、`ip`、`user_agent`。
- 约束：`token_hash` 唯一，支持 refresh token 轮换与单会话失效。

## 接口分层

### 1) 注册

- `POST /api/v1/auth/register`
- 创建 `portal_users` 记录，返回基础用户信息。

### 2) 登录

- `POST /api/v1/auth/login`
- 校验用户名密码后：
  - 返回短期 `access_token`（Bearer）。
  - 创建 `portal_user_sessions`。
  - 下发 HttpOnly Cookie：`gw_user_refresh`。

### 3) 刷新

- `POST /api/v1/auth/refresh`
- 接受 cookie 或 body 的 refresh token。
- 通过 token hash 查询会话：
  - 会话有效：旧 token 立刻撤销，新 token 轮换。
  - 会话无效：401。

### 4) 登出

- `POST /api/v1/auth/logout`
- 撤销当前 refresh 会话并清理 cookie。

### 5) 当前用户

- `GET /api/v1/auth/me`
- 通过 Bearer access token 识别 `portal_users` 并返回基础资料。

## 当前安全策略

- 密码：`PBKDF2-SHA256`（含随机盐）。
- Refresh Token：随机字符串 + SHA256 存库（明文不落库）。
- 会话撤销：支持主动登出和刷新轮换失效。
- 限流：登录/刷新接口继承现有限流策略。

## 可继续升级（下一步）

- Refresh 会话上限（每用户最多 N 个活跃设备）。
- 异地登录提醒与会话管理列表。
- Access Token 改为更短 TTL + 前端静默刷新。
- 登录失败计数与用户级锁定策略。
