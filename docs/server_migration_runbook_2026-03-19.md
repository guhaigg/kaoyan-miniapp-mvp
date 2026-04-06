# 服务器迁移运行手册（2026-03-19）

本文档用于把当前项目从现有生产机迁移到新服务器，并把截至 `2026-03-19` 的代码快照、配置位置、未完成任务和数据修复状态一起备份到 Git。

## 1. 当前代码快照

- 本地仓库当前提交：`6ec29ab`
- 当前应作为迁移基线的关键提交：
  - `bacc475` `fix: preserve department-aware adjustment matches`
  - `7451971` `fix: avoid loading archive blobs during imports`
  - `be89e74` `fix: ignore virtual attrs in historical upserts`
  - `6ec29ab` `fix: drop transient profile fields before upsert`

迁移时建议直接从 `origin/main` 检出，且至少包含 `6ec29ab`。

## 2. 当前线上结构

现有生产机：`<production-server-ip>`

- 仓库目录：`/srv/kaoyan-miniapp-mvp`
- 后端运行目录：`/srv/kaoyan-miniapp-mvp/backend`
- 前端源码目录：`/srv/kaoyan-miniapp-mvp/web-ui`
- 前端静态站点目录：`/var/www/html`
- 后端 systemd 服务：`kaoyan-backend`
- API Nginx 配置：`/etc/nginx/sites-enabled/kaoyan-api`
- Web Nginx 配置：`/etc/nginx/sites-enabled/kaoyan-www`
- systemd 主配置：`/etc/systemd/system/kaoyan-backend.service`
- systemd override：`/etc/systemd/system/kaoyan-backend.service.d/override.conf`

当前 Nginx 真实职责：

- `https://api.example.com` 反代 `127.0.0.1:8000`
- `https://example.com` / `https://www.example.com` 静态根目录是 `/var/www/html`
- `https://example.com/api/v1/` 同样反代 `127.0.0.1:8000`

## 3. 当前环境与配置文件

版本库中可直接参考的模板：

- [backend/.env.example](/Users/guhai/Documents/New%20project/gewujl/kaoyan-miniapp-mvp/backend/.env.example)
- [web-ui/.env.example](/Users/guhai/Documents/New%20project/gewujl/kaoyan-miniapp-mvp/web-ui/.env.example)

迁移时必须从旧服务器额外带走，但不要提交到 Git 的内容：

- `backend/.env`
- SSL 证书目录：
  - `/etc/letsencrypt/live/api.example.com/`
  - `/etc/letsencrypt/live/example.com/`
  - `/etc/letsencrypt/options-ssl-nginx.conf`
  - `/etc/letsencrypt/ssl-dhparams.pem`

后端 `.env` 至少要覆盖：

- `DATABASE_URL`
- `REDIS_URL`
- `SECRET_KEY`
- `WECHAT_APPID`
- `WECHAT_SECRET`
- `ADMIN_TOKEN`
- `CORS_ALLOW_ORIGINS`

说明：

- 当前数据库是外部腾讯云 MySQL，不是本机 MySQL。
- 当前 Redis 健康状态长期是 `down`，不是本次迁移新增问题。

## 4. 当前数据与未完成任务

截至本文档编写时，线上数据库状态如下：

- `adjustment_opportunities = 161425`
- `historical_adjustment_profiles = 95000`
- `historical_release_timing_profiles = 777`
- `mentor_evaluations = 16631`

其中：

- `adjustment_opportunities` 已成功切到新规则结果。
- `historical_adjustment_profiles` 正在补跑恢复，尚未完全结束。
- 当前补跑进程：
  - PID：`203522`
  - 脚本：`/tmp/repair_profiles_import.py`
  - 日志：`/tmp/repair_profiles_import.log`
- 当前日志状态：
  - `START profiles`
  - `BUILT profiles 126807 228.09s`

这意味着：

1. 机会表已经可用。
2. 历史画像正在从异常中恢复，旧服务器此刻不适合作为“最终一致状态”来源。
3. 迁移到新服务器后，建议重新执行一次完整历史智能导入，而不是依赖旧服务器此刻的中间状态。

## 5. 已修复但需要带到新服务器的逻辑

这次迁移必须带上以下代码能力：

1. 主调剂按院系感知合并：
   - 同校同年同专业同人数但学院不同，不合并。
   - 一条有学院、一条无学院，仅在唯一候选时吸附。
2. 历史画像按院系感知匹配。
3. 导师评价按院系精确匹配，校级无院系评价只作为 fallback。
4. 跨年分数按 A/B 区国家线折算后比较。
5. 导入时优先使用归档文件路径，不再把大 blob 全量拉进内存。
6. MySQL upsert 只消费物理列，不再把中间字段 `initial_score`、`adjustment_score` 送进 SQL。

关键代码位置：

- [backend/app/services/historical_intelligence.py](/Users/guhai/Documents/New%20project/gewujl/kaoyan-miniapp-mvp/backend/app/services/historical_intelligence.py)
- [backend/app/routers/search.py](/Users/guhai/Documents/New%20project/gewujl/kaoyan-miniapp-mvp/backend/app/routers/search.py)
- [backend/tests/test_historical_intelligence.py](/Users/guhai/Documents/New%20project/gewujl/kaoyan-miniapp-mvp/backend/tests/test_historical_intelligence.py)
- [backend/tests/test_search.py](/Users/guhai/Documents/New%20project/gewujl/kaoyan-miniapp-mvp/backend/tests/test_search.py)

## 6. 旧服务器上已有备份

历史智能重建前已做数据库备份：

- 目录：`/root/backups/manual-rebuild/20260319T075809Z`
- 文件：`historical_rebuild_backup.sql.gz`
- 大小：约 `105MB`

迁移前建议把这个目录也复制到新服务器，作为兜底回滚资产。

## 7. 建议迁移清单

### 7.1 必带资产

- Git 仓库代码：检出到 `6ec29ab` 或更新版本
- 旧服务器 `backend/.env`
- `/var/www/html`
- `/etc/nginx/sites-enabled/kaoyan-api`
- `/etc/nginx/sites-enabled/kaoyan-www`
- `/etc/systemd/system/kaoyan-backend.service`
- `/etc/systemd/system/kaoyan-backend.service.d/override.conf`
- `/root/backups/manual-rebuild/20260319T075809Z/historical_rebuild_backup.sql.gz`

### 7.2 不建议直接拷贝的内容

- 旧服务器 `backend/.venv`
- 旧服务器运行中的 `/tmp/*.log`、`/tmp/*.py`
- 旧服务器 systemd 运行态缓存

这些内容在新机应重新安装或重新生成。

## 8. 新服务器部署步骤

### 8.1 基础依赖

安装：

- `git`
- `python3.12` 和 `python3.12-venv`
- `nodejs >= 20`
- `nginx`
- `certbot`
- `mysql-client` 或等价工具

### 8.2 代码与依赖

```bash
mkdir -p /root/code
cd /root/code
git clone https://github.com/<your-org>/<your-repo>.git
cd kaoyan-miniapp-mvp
git checkout main
git reset --hard origin/main

cd /srv/kaoyan-miniapp-mvp/backend
python3.12 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -r requirements.txt

cd /srv/kaoyan-miniapp-mvp/web-ui
npm ci
npm run build
```

### 8.3 环境变量

```bash
cp /srv/kaoyan-miniapp-mvp/backend/.env.example /srv/kaoyan-miniapp-mvp/backend/.env
```

然后用旧服务器上的真实 `.env` 内容覆盖。不要把真实值提交到仓库。

### 8.4 前端发布

```bash
rm -rf /var/www/html/*
cp -R /srv/kaoyan-miniapp-mvp/web-ui/out/* /var/www/html/
```

### 8.5 systemd

把以下文件从旧服务器复制到新服务器同路径：

- `/etc/systemd/system/kaoyan-backend.service`
- `/etc/systemd/system/kaoyan-backend.service.d/override.conf`

然后：

```bash
systemctl daemon-reload
systemctl enable kaoyan-backend
systemctl restart kaoyan-backend
```

### 8.6 Nginx

把以下文件从旧服务器复制到新服务器同路径：

- `/etc/nginx/sites-enabled/kaoyan-api`
- `/etc/nginx/sites-enabled/kaoyan-www`

如果域名解析切到新服务器后再申请证书，则需要重新执行 Certbot。

然后：

```bash
nginx -t
systemctl reload nginx
```

## 9. 数据迁移建议

当前数据库是外部腾讯云 MySQL，所以迁移到新服务器时有两种方案。

### 方案 A：继续使用现有腾讯云 MySQL

优先推荐。步骤：

1. 新服务器 `.env` 继续指向现有腾讯云 MySQL。
2. 应用先启动并通过健康检查。
3. 在新服务器重新执行历史智能导入。

推荐命令：

```bash
cd /srv/kaoyan-miniapp-mvp/backend
PYTHONPATH=/srv/kaoyan-miniapp-mvp/backend .venv/bin/python scripts/import_historical_intelligence.py
```

如果需要先验证，可先执行：

```bash
cd /srv/kaoyan-miniapp-mvp/backend
PYTHONPATH=/srv/kaoyan-miniapp-mvp/backend .venv/bin/python -m pytest -q backend/tests/test_historical_intelligence.py backend/tests/test_search.py
```

### 方案 B：数据库也迁移

如果连数据库也要迁到新环境：

1. 先恢复 `historical_rebuild_backup.sql.gz`
2. 校验表结构字段完整
3. 再跑一次 `import_historical_intelligence.py`

## 10. 迁移完成后的验收

### 10.1 服务检查

```bash
curl -sS http://127.0.0.1:8000/api/v1/health
curl -sS https://api.example.com/api/v1/health
curl -I https://example.com/search/
```

### 10.2 数据检查

至少核对：

- `adjustment_opportunities`
- `historical_adjustment_profiles`
- `historical_release_timing_profiles`
- `mentor_evaluations`

并抽查一个“同校同专业不同学院”的样本，确认没有被错误合并。

## 11. 当前建议

如果准备尽快换到更好的服务器，最稳的顺序是：

1. 以 `6ec29ab` 为代码基线迁移。
2. 不等待旧服务器上的补跑完全结束。
3. 新服务器上线后，直接在新服务器重新跑完整历史智能导入。
4. 验证通过后再切流量或切 DNS。

这样可以避免把旧服务器当前的“中间修复状态”一并带过去。
