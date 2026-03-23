# 服务器目录与部署路径说明（2026-03-19）

本文档说明生产机 `38.76.215.159` 上，源码目录、后端运行目录、前端站点目录分别是什么，以及后续发布时应该改哪里、不要改哪里。

## 1. 当前真实部署拓扑

### 1.1 源码仓库

- 路径：`/root/code/kaoyan-miniapp-mvp`
- 作用：
  - Git 仓库主目录
  - 后端源码、前端源码、文档、脚本的统一来源
  - 维护与排障时应该优先查看这里

当前校验结果：

- 分支：`main`
- 状态：工作区干净
- HEAD：应与 `origin/main` 保持一致

### 1.2 后端运行目录

- 路径：`/root/code/kaoyan-miniapp-mvp/backend`
- 作用：
  - systemd 直接从这里启动 FastAPI
  - `.env` 也从这里读取

当前 `systemd` 配置指向：

- `WorkingDirectory=/root/code/kaoyan-miniapp-mvp/backend`
- `EnvironmentFile=/root/code/kaoyan-miniapp-mvp/backend/.env`
- `ExecStart=/root/code/kaoyan-miniapp-mvp/backend/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --timeout-keep-alive 5 --timeout-graceful-shutdown 5`

结论：

- 后端不是从 `/var/www/html` 跑
- 后端也不是从某个单独的发布目录跑
- 修改后端代码，最终应该落到 `/root/code/kaoyan-miniapp-mvp/backend`

### 1.3 前端源码目录

- 路径：`/root/code/kaoyan-miniapp-mvp/web-ui`
- 作用：
  - Next.js 源码目录
  - 本地或服务器构建时，`web-ui/out` 是静态导出产物

注意：

- `web-ui/out` 是构建结果，不是线上实际服务目录
- 它只是发布时的中间产物

### 1.4 前端线上站点目录

- 路径：`/var/www/html`
- 作用：
  - Nginx 直接对外提供的网站静态文件目录
  - 域名 `https://gewujl.cloud` / `https://www.gewujl.cloud` 的页面来自这里

当前核对结果：

- `/var/www/html` 的文件布局与仓库里的 `web-ui/out` 一致
- 已确认存在：
  - `/account/index.html`
  - `/admin/index.html`
  - `/login/index.html`
  - `/register/index.html`
  - `/query/index.html`
  - `/search/index.html`

结论：

- 改前端源码时，真正上线要同步的是：
  - `web-ui/out/* -> /var/www/html/`
- 不能只改 `/root/code/kaoyan-miniapp-mvp/web-ui/src`
  - 那样不会自动影响线上页面

## 2. Nginx 与后端的实际分工

当前 Nginx 配置分两块：

### 2.1 `api.gewujl.cloud`

- 反向代理到：`http://127.0.0.1:8000`
- 对应后端 FastAPI

### 2.2 `gewujl.cloud` / `www.gewujl.cloud`

- `root /var/www/html`
- `/api/v1/` 请求代理到：`http://127.0.0.1:8000`
- 其他页面静态文件从 `/var/www/html` 提供

结论：

- 前端页面：Nginx 读 `/var/www/html`
- API：Nginx 转发给 `127.0.0.1:8000`

## 3. 正确发布路径

### 3.1 后端改动

后端发布应修改：

- `/root/code/kaoyan-miniapp-mvp/backend/...`

后端发布后通常需要：

1. 安装或更新依赖
2. 重启 `kaoyan-backend.service`
3. 健康检查：
   - `http://127.0.0.1:8000/api/v1/health`
   - `https://api.gewujl.cloud/api/v1/health`

### 3.2 前端改动

前端发布应执行：

1. 在源码目录构建：
   - `/root/code/kaoyan-miniapp-mvp/web-ui`
2. 生成：
   - `/root/code/kaoyan-miniapp-mvp/web-ui/out`
3. 同步到：
   - `/var/www/html`

结论：

- 前端真正上线依赖 `/var/www/html`
- 服务器仓库里的 `web-ui/out` 只是发布来源，不是最终服务目录

## 4. 以后不要再混用的几类路径

### 4.1 不要把源码目录当站点目录

错误思路：

- 直接改 `/root/code/kaoyan-miniapp-mvp/web-ui/src/...` 就以为页面已经上线

正确思路：

- 改源码
- 构建 `web-ui/out`
- 同步到 `/var/www/html`

### 4.2 不要把 `/var/www/html` 当源码仓库

错误思路：

- 直接在 `/var/www/html` 手改页面，再希望这些内容回流到 Git

正确思路：

- 只把 `/var/www/html` 当部署产物目录
- 任何长期变更都先改 Git 仓库

### 4.3 不要再用会打平目录结构的 `rsync` 写法

错误写法：

```bash
rsync file1 file2 file3 root@host:/root/code/kaoyan-miniapp-mvp/web-ui/src/
```

这会把不同子目录文件直接平铺到 `src/` 根目录。

正确写法：

```bash
rsync -avz local/path/file.tsx root@host:/root/code/kaoyan-miniapp-mvp/web-ui/src/components/.../file.tsx
```

或者：

```bash
cd /local/repo
rsync -avz web-ui/src/ root@host:/root/code/kaoyan-miniapp-mvp/web-ui/src/
```

## 5. 当前建议的维护规则

后端：

- 只在 `/root/code/kaoyan-miniapp-mvp/backend` 改
- 服务由 `kaoyan-backend.service` 托管

前端：

- 只在 Git 仓库源码里改
- 发布目标始终是 `/var/www/html`

仓库：

- `/root/code/kaoyan-miniapp-mvp` 只保持和 `origin/main` 一致
- 不在服务器仓库里长期保留未提交手工改动

## 6. 本次核对结论

本次核对确认：

- 服务器仓库已对齐到 `origin/main`
- `/root/code/kaoyan-miniapp-mvp/backend` 是后端真实运行目录
- `/var/www/html` 是前端真实站点目录
- `/root/code/kaoyan-miniapp-mvp/web-ui/out` 与 `/var/www/html` 当前文件布局一致

后续如果出现“改了源码但线上没变”，优先检查这两个点：

1. 是否重新构建了 `web-ui/out`
2. 是否把 `web-ui/out` 同步到了 `/var/www/html`
