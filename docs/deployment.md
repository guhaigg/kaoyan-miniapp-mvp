# Deployment and Operations Handbook

## 0) Python/Node Baseline

- Python: `>=3.11` (recommended `3.12`)
- Node.js: `>=20`

If you run tests with Python 3.9, you may hit compatibility errors such as `datetime.UTC` import failure.

## 0.1) Current Production Paths (Hong Kong Server)

- Static web root: `/var/www/html`
- Backend repo root: `/root/code/kaoyan-miniapp-mvp`
- Admin static files: `/root/code/kaoyan-miniapp-mvp/backend/app/static/console`
- Web build source: `/root/code/kaoyan-miniapp-mvp/web-ui/out`

Version-controlled source mapping:

- `/var/www/html/*`  <- `web-ui/out/*`
- `/root/code/kaoyan-miniapp-mvp/backend/app/static/console/*` <- `backend/app/static/console/*`

Important:

- `infra/nginx/` still contains historical static files from an older site iteration.
- Those files are no longer the source of truth for the production web UI.
- Do not sync `infra/nginx/` into `/var/www/html` during normal deployment.

## 0.2) Current Production SSH Management Baseline

Production SSH on `38.76.215.159` is now managed as key-only access.

Current hardening file:

- `/etc/ssh/sshd_config.d/99-gewu-ssh-hardening.conf`

Repo copy:

- `infra/ssh/99-gewu-ssh-hardening.conf`

Current effective expectations:

- `PasswordAuthentication no`
- `KbdInteractiveAuthentication no`
- `PermitRootLogin prohibit-password`
- `PubkeyAuthentication yes`
- `LoginGraceTime 20`
- `MaxStartups 100:30:200`
- `MaxSessions 50`
- `UseDNS no`

Why this was added:

- Production SSH was intermittently dropping new sessions during preauth / banner exchange.
- Root cause was not local key failure, but the combination of:
  - internet password-scan noise against `root`
  - our bursty deploy / diagnostic connections
  - the default-ish `MaxStartups 10:30:100` preauth window being too small

Operational rule:

- Prefer a small number of longer-lived SSH sessions for deploy/debug work.
- Avoid spawning many parallel SSH commands unless required.
- After changing SSH config on the host, always run:

```bash
sshd -t
systemctl reload ssh
```

- Then verify with:

```bash
ssh -o BatchMode=yes root@38.76.215.159 'echo ok'
```

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
- `ENABLE_SITE_SECTION_BROWSER_PROBE` (optional, default `false`)
- `SITE_SECTION_BROWSER_PROBE_TIMEOUT_SECONDS` (optional, default `8`)

Security rule:

- Never commit real `.env`.
- Keep secrets in CI/CD secret store.
- In production, replace `CORS_ALLOW_ORIGINS=*` with explicit trusted origins.

Recommended environment policy:

- Local dev: `USE_MOCK_WECHAT=true`, `CORS_ALLOW_ORIGINS=*`
- Shared test or staging: prefer real `WECHAT_APPID` and `WECHAT_SECRET`, set `USE_MOCK_WECHAT=false`, and restrict `CORS_ALLOW_ORIGINS`
- Production: `USE_MOCK_WECHAT=false`, real WeChat credentials required, never use wildcard CORS

Site-section browser probe note:

- Browser probe is optional and defaults to disabled.
- Installing the Python `playwright` package alone is not enough to execute browser probe.
- If you enable `ENABLE_SITE_SECTION_BROWSER_PROBE=true` in production, install browser binaries on the host as well, for example:

```bash
cd /root/code/kaoyan-miniapp-mvp/backend
./.venv/bin/python -m playwright install chromium
```

- If browser binaries are missing, the backend should log a warning and fall back to static/iframe/script-based probe instead of failing the request.

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

- `HK_HOST` (current production example: `38.76.215.159`)
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
3. Build `web-ui` in GitHub Actions and upload `web-ui/out` as a tarball to the server
4. Replace the web root with the extracted `web-ui/out` bundle
   - remove stale old files before extraction
   - clean accidental macOS `._*` metadata files after extraction
5. Install/enable backup automation (`gewujl-backup.timer`)
6. Install backend dependencies if `.venv/bin/pip` exists
7. Restart backend service if `HK_BACKEND_SERVICE` is configured
8. `nginx -t` and `systemctl reload nginx`

Recommended static-site Nginx behavior:

- For the exported Next site, prefer `try_files $uri $uri/ =404;`
- Do not use `try_files ... /index.html;` unless the exported frontend intentionally relies on SPA fallback routing
- This prevents genuinely removed legacy paths such as historical `/about/` pages from appearing to still exist
- Current live routes such as `/login/`, `/register/`, `/query/`, `/search/`, `/account/`, `/admin/` should continue to resolve from exported static files

## 7) Fully Automated Backups

Backup assets:

- Repository snapshot (excluding `.git` and `backend/.venv`)
- Static web root (`/var/www/html`)
- Nginx config (`/etc/nginx`)
- Systemd units (`kaoyan-backend.service`, `gewujl-backup.*`)
- MySQL dump (auto-read from `DATABASE_URL` in backend `.env`, if MySQL URL)
  - If dump fails and `DB_DUMP_REQUIRED=false`, backup continues with warning.
  - If dump is mandatory, set `DB_DUMP_REQUIRED=true`.

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

Retention and auto-cleanup:

- Count-based cleanup:
  - `KEEP_DAILY_COUNT` (keep latest N daily backups)
  - `KEEP_PREDEPLOY_COUNT` (keep latest N predeploy backups)
- Day-based cleanup:
  - `KEEP_DAYS_DAILY`
  - `KEEP_DAYS_PREDEPLOY`
- Quota-based cleanup:
  - `MAX_BACKUP_TOTAL_MB` (if total backup size exceeds this, delete oldest snapshots automatically)

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
