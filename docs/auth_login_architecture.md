# 注册登录架构（Portal 用户）

## 目标

- 普通用户注册与登录可独立运行，不依赖管理员体系。
- Access Token 短期有效，Refresh Token 可轮换并可撤销。
- 支持后续接入风控（设备、IP、异常会话下线）而不推翻现有代码。

## 表结构

### `portal_users`

- 当前仍是主账号表。
- 承载业务身份、监控配置、订阅和通知配置。
- 当前保留 `username/password_hash` 作为网站账号基础字段。
- `premium_*` 旧字段已经退出运行时并已进入物理清理阶段。

### `account_identities`

- 登录身份表。
- 当前已接入：
  - `password`
  - `wechat_miniapp`
- 作用：
  - 将“主账号”和“登录方式”拆开
  - 为后续网站账号与微信账号绑定打底

### `account_roles`

- 账号角色表。
- 当前主要角色：`admin`
- 已替代历史 `admin_accounts`。

### `account_entitlements`

- 账号权益表。
- 当前主要权益：`premium_monitoring`
- 已替代 `portal_users.premium_monitoring_enabled / premium_expires_at` 旧字段。

### `portal_user_sessions`

- 刷新会话表：保存 refresh token hash。
- 仍然直接绑定 `portal_users.id`，不需要额外迁移。

### `account_payment_orders`

- 会员订单/支付单账本。
- 当前网站侧会员订单已经走这张表，再发放 `account_entitlements`。

## 接口分层

### 1) 注册

- `POST /api/v1/auth/register`
- 创建 `portal_users` 记录。
- 同时创建 `account_identities(password)`。
- 返回基础用户信息。

### 1.5) 微信静默登录

- `POST /api/v1/auth/silent-login`
- 当前行为：
  - 若微信身份尚未绑定主账号：返回 `shadow` 模式
  - 若微信身份已绑定主账号：直接返回主账号 `access_token / refresh_token`
- 兼容点：
  - 仍保留 `visitor_token`
  - 仍保留 `users` 影子用户作为过渡层

### 2) 登录

- `POST /api/v1/auth/login`
- 按 `account_identities(password)` 查登录身份。
- 校验成功后：
  - 返回短期 `access_token`（Bearer）。
  - 返回 `refresh_token`（用于小程序或非 cookie 客户端）。
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
- `is_admin / is_premium / role` 只读取 `account_roles / account_entitlements`。

### 6) 微信绑定

- `POST /api/v1/auth/wechat/bind`
- 当前要求：
  - `X-Visitor-Token`：来自微信静默登录
  - `X-User-Token` / `Authorization: Bearer ...`：来自网站主账号登录
- 成功后：
  - 写入 `account_identities(wechat_miniapp)`
  - 后续同一微信再次静默登录会直接命中主账号

## 当前安全策略

- 密码：`PBKDF2-SHA256`（含随机盐）。
- Refresh Token：随机字符串 + SHA256 存库（明文不落库）。
- 会话撤销：支持主动登出和刷新轮换失效。
- 限流：登录/刷新接口继承现有限流策略。

## 可继续升级（下一步）

- 小程序提供正式的账号绑定/解绑 UI。
- 支持 `unionid` 做跨 app 账号归并。
- 首次微信登录直接创建主账号，而不是只保留 shadow。
- 接第三方支付网关到 `account_payment_orders -> account_entitlements` 链路。
- 管理员二次登录最终只保留角色账号 + root 救援入口。
