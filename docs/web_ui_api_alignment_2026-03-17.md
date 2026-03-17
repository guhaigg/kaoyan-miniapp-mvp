# Web UI 接口对齐说明（2026-03-17）

本文档记录 `web-ui/` 首版上线前，前端与后端接口的对齐结果与主要改动。

## 1) 前端基础配置

- 新增目录：`web-ui/`（Next.js 15 + Tailwind + Framer Motion + GSAP + React Query + Zustand）
- 新增环境变量模板：`web-ui/.env.example`
  - `NEXT_PUBLIC_API_BASE_URL=/api/v1`
- 静态发布配置：
  - `web-ui/next.config.ts` 设置 `output: "export"`、`trailingSlash: true`

## 2) 接口映射（前端 -> 后端）

### 用户体系（Portal）

- `POST /auth/register`：注册
- `POST /auth/login`：登录
- `POST /auth/refresh`：刷新会话（依赖 HttpOnly refresh cookie）
- `POST /auth/logout`：退出
- `GET /auth/me`：当前用户信息（请求头 `X-User-Token`）

### 内容检索

- `POST /search/announcements`：公告检索
- `POST /search/adjustments`：调剂检索

### 管理员体系

- `POST /admin/auth/login`：管理员登录（cookie 会话）
- `POST /admin/auth/logout`：管理员退出
- `GET /admin/auth/me`：管理员会话检测
- `GET /admin/users`：用户列表
- `POST /admin/users/{user_id}/promote`：提升管理员
- `GET /admin/audits`：管理员审计日志
- `GET /health`：健康检查（DB/Redis）

## 3) 关键代码改动

### 新增

- `web-ui/src/lib/api.ts`
  - 统一请求封装、错误处理、接口类型定义
- `web-ui/src/components/shared/AuthBootstrap.tsx`
  - 首屏会话恢复（`/auth/refresh` + `/auth/me`）

### 改造

- `web-ui/src/lib/store.ts`
  - 增加 `portalAuth` 持久化状态（localStorage）
- `web-ui/src/components/shared/Modals.tsx`
  - 接入注册/登录/退出真实接口
- `web-ui/src/components/layout/Header.tsx`
  - 登录后显示当前账号
- `web-ui/src/app/page.tsx`
  - 首页时间线改为真实公告数据
- `web-ui/src/app/search/page.tsx`
  - 检索条件、查询结果、分页、空态/错误态
- `web-ui/src/app/admin/page.tsx`
  - 管理员登录、用户管理、提升管理员、审计日志、健康状态
- `web-ui/src/app/layout.tsx`
  - 挂载 `AuthBootstrap`

## 4) 当前交付状态

- `web-ui` 本地验证：
  - `npm run lint` 通过
  - `npm run build` 通过
- 发布模式：
  - 采用静态导出产物部署至 Nginx 站点目录
  - 浏览器端调用 `https://api.gewujl.cloud/api/v1/*`（或同源 `/api/v1/*`）

## 5) 后续建议

- 增加统一 401 拦截与静默刷新重试策略（当前为页面级处理）
- 管理页增加用户状态编辑（`PATCH /admin/users/{id}`）
- 查询页增加筛选项持久化与分页 URL 同步
