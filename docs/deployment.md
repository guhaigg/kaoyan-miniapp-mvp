# Deployment and Operations Handbook

## 0) Python/Node Baseline

- Python: `>=3.11` (recommended `3.12`)
- Node.js: `>=20`

If you run tests with Python 3.9, you may hit compatibility errors such as `datetime.UTC` import failure.

## 0.1) Current Production Paths (Hong Kong Server)

- Static web root: `/var/www/html`
- Backend repo root: `/root/code/kaoyan-miniapp-mvp`
- Admin static files: `/root/code/kaoyan-miniapp-mvp/backend/app/static/console`

Version-controlled source mapping:

- `/var/www/html/index.html`  <- `infra/nginx/index.html`
- `/var/www/html/register.html` + `/var/www/html/register/index.html` <- `infra/nginx/register.html`
- `/var/www/html/query/index.html` <- `infra/nginx/query/index.html`
- `/var/www/html/assets/brand/gw-mark.svg` <- `infra/nginx/assets/brand/gw-mark.svg`
- `/root/code/kaoyan-miniapp-mvp/backend/app/static/console/*` <- `backend/app/static/console/*`

## 1) Environment Variables

Copy `backend/.env.example` to `backend/.env` and fill values:

- `DATABASE_URL`
- `REDIS_URL`
- `SECRET_KEY`
- `VISITOR_TOKEN_TTL_SECONDS`
- `WECHAT_APPID`
- `WECHAT_SECRET`
- `USE_MOCK_WECHAT`
- `ADMIN_TOKEN`
- `RATE_LIMIT_PER_MINUTE`
- `CORS_ALLOW_ORIGINS`

Security rule:

- Never commit real `.env`.
- Keep secrets in CI/CD secret store.
- In production, replace `CORS_ALLOW_ORIGINS=*` with explicit trusted origins.

Recommended environment policy:

- Local dev: `USE_MOCK_WECHAT=true`, `CORS_ALLOW_ORIGINS=*`
- Shared test or staging: prefer real `WECHAT_APPID` and `WECHAT_SECRET`, set `USE_MOCK_WECHAT=false`, and restrict `CORS_ALLOW_ORIGINS`
- Production: `USE_MOCK_WECHAT=false`, real WeChat credentials required, never use wildcard CORS

Database note:

- The formal development environment uses external MySQL.
- Recommended format:
  `DATABASE_URL=mysql+pymysql://user:password@host:3306/gewu_jianlu?charset=utf8mb4`
- Ensure the MySQL user can create and alter tables during initial bootstrap.

Miniapp note:

- `miniapp/project.config.json` can keep `touristappid` for local DevTools work.
- Before real release, replace it with the actual miniapp `appid`.

## 2) Docker Compose Strategy

File: `infra/docker-compose.yml`

- Network:
  - Internal service names: `redis`, `backend`.
- Runtime:
  - Backend waits on `redis`; MySQL is provided externally.

Start services:

```bash
docker compose -f infra/docker-compose.yml up -d
```

Stop services:

```bash
docker compose -f infra/docker-compose.yml down
```

## 3) Nginx Reverse Proxy (Template)

```nginx
server {
  listen 443 ssl;
  server_name api.example.com;

  ssl_certificate /etc/letsencrypt/live/api.example.com/fullchain.pem;
  ssl_certificate_key /etc/letsencrypt/live/api.example.com/privkey.pem;

  location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Real-IP $remote_addr;
  }
}
```

## 4) Database Migration Baseline

Recommended migration tool: Alembic.

Common commands:

```bash
alembic revision --autogenerate -m "init schema"
alembic upgrade head
alembic downgrade -1
```

## 5) Rollback Checklist

- Keep previous backend image tag available.
- Keep last known good DB backup snapshot.
- In cutover window, rollback in this order:
  - switch gateway to previous backend image
  - verify `/api/v1/health`
  - replay failed requests if necessary

## 6) GitHub Actions Auto-Deploy (Hong Kong Server)

Workflow file:

- `.github/workflows/deploy-hk.yml`

Trigger:

- push to `main`
- manual trigger (`workflow_dispatch`)

Required GitHub Secrets:

- `HK_HOST` (example: `45.192.110.219`)
- `HK_USER` (example: `root`)
- `HK_SSH_PRIVATE_KEY` (private key content)
- `HK_SSH_PORT` (optional, default `22`)

Optional GitHub Variables:

- `HK_DEPLOY_PATH` (default `/root/code/kaoyan-miniapp-mvp`)
- `HK_WEB_ROOT` (default `/var/www/html`)
- `HK_BACKEND_SERVICE` (example: `kaoyan-backend`)

Deploy actions on server:

1. Create pre-deploy snapshot under `/root/backups/predeploy/<timestamp>/`
2. `git pull --ff-only origin main` in repo path
3. Sync static pages to web root:
   - `index.html`
   - `register.html`
   - `register/index.html`
   - `query/index.html`
   - `assets/brand/gw-mark.svg`
4. Install/enable backup automation (`gewujl-backup.timer`)
5. Install backend dependencies if `.venv/bin/pip` exists
6. Restart backend service if `HK_BACKEND_SERVICE` is configured
7. `nginx -t` and `systemctl reload nginx`

## 7) Fully Automated Backups

Backup assets:

- Repository snapshot (excluding `.git` and `backend/.venv`)
- Static web root (`/var/www/html`)
- Nginx config (`/etc/nginx`)
- Systemd units (`kaoyan-backend.service`, `gewujl-backup.*`)
- MySQL dump (auto-read from `DATABASE_URL` in backend `.env`, if MySQL URL)

Files:

- Script: `infra/backup/gewujl-backup.sh`
- Env template: `infra/backup/gewujl-backup.env.example`
- Service: `infra/systemd/gewujl-backup.service`
- Timer: `infra/systemd/gewujl-backup.timer`

Server runtime files:

- `/usr/local/bin/gewujl-backup`
- `/etc/default/gewujl-backup`
- `/etc/systemd/system/gewujl-backup.service`
- `/etc/systemd/system/gewujl-backup.timer`

Daily schedule:

- `03:30` server local time (`OnCalendar=*-*-* 03:30:00`)
- with `Persistent=true` (missed runs execute after reboot)

### Upload backups to another Tencent Cloud server (SSH)

Edit `/etc/default/gewujl-backup`:

```bash
REMOTE_BACKUP_TARGET=root@<backup_server_ip>:/data/gewujl-backups
REMOTE_SSH_PORT=22
REMOTE_SSH_KEY=/root/.ssh/id_ed25519
```

Then reload and test:

```bash
sudo systemctl daemon-reload
sudo systemctl restart gewujl-backup.timer
sudo /usr/local/bin/gewujl-backup daily
sudo systemctl list-timers --all | grep gewujl-backup
```
