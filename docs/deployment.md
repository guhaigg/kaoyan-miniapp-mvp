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
