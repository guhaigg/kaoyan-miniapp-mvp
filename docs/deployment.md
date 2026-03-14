# Deployment and Operations Handbook

## 1) Environment Variables

Copy `backend/.env.example` to `backend/.env` and fill values:

- `DATABASE_URL`
- `REDIS_URL`
- `SECRET_KEY`
- `VISITOR_TOKEN_TTL_SECONDS`
- `WECHAT_APPID`
- `WECHAT_SECRET`
- `USE_MOCK_WECHAT`
- `AUTO_CREATE_TABLES`
- `ADMIN_TOKEN`
- `RATE_LIMIT_PER_MINUTE`
- `WORKER_POLL_INTERVAL_SECONDS`
- `WORKER_MAX_SOURCES_PER_JOB`
- `WORKER_MAX_ITEMS_PER_SOURCE`

Security rule:

- Never commit real `.env`.
- Keep secrets in CI/CD secret store.
- Production recommendation:
  - `USE_MOCK_WECHAT=false`
  - `AUTO_CREATE_TABLES=false` (use Alembic only)

## 2) Docker Compose Strategy

File: `infra/docker-compose.yml`

- Network:
  - Internal service names: `db`, `redis`, `backend`.
- Volumes:
  - `postgres_data` persists database state.
- Runtime:
  - Backend waits on `db` and `redis` dependencies.
  - Worker consumes `crawl_jobs` asynchronously from the same DB.

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

Project helper scripts:

```bash
npm run db:migrate
npm run db:downgrade
npm run db:revision
```

## 5) Rollback Checklist

- Keep previous backend image tag available.
- Keep last known good DB backup snapshot.
- In cutover window, rollback in this order:
  - switch gateway to previous backend image
  - verify `/api/v1/health`
  - replay failed requests if necessary
