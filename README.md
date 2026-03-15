# 格物简录 (Ge Wu Jian Lu)

格物简录是一个微信小程序 + FastAPI 后端的项目，用于聚合与检索公告/调剂信息。当前开发环境已接入外部 MySQL，服务域名已配置 HTTPS。

## Online Endpoints

- Web: `https://gewujl.cloud`
- Web (www): `https://www.gewujl.cloud`
- API: `https://api.gewujl.cloud`
- Health: `https://api.gewujl.cloud/api/v1/health`

## Tech Stack

- Mini Program frontend (`miniapp/`)
- FastAPI backend (`backend/`)
- External MySQL
- Redis
- Nginx + Certbot + systemd

## Quick Start (Development)

```bash
git clone <your-repo-url>
cd gewujl

python3 -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements.txt

npm install
cp backend/.env.example backend/.env

# optional local redis
docker compose -f infra/docker-compose.yml up -d redis

npm run dev:backend
```

Open `miniapp/` in WeChat DevTools.

## Testing

```bash
npm run test:backend
```

Ubuntu miniapp preview smoke:

```bash
npm run smoke:miniapp:preview -- --privateKeyPath .secrets/miniprogram-ci.key
```

## Branch Policy

- Default delivery branch: `dev`
- Feature work branch: `feat/*` (branched from `dev`)
- Keep `main` unchanged during normal development
- Only push or merge to `main` after explicit confirmation

## Project Docs

- [Docs Index](./docs/README.md)
- [Development Protocol](./docs/development_protocol.md)
- [Git Workflow](./docs/git_workflow.md)
- [Deployment Handbook](./docs/deployment.md)
- [Miniapp Smoke Checklist](./docs/miniapp_smoke.md)
- [Update Log](./docs/update_log.md)

## Deployment Assets

- Nginx template: `infra/nginx/gewujl.conf`
- Backend systemd service: `infra/systemd/gewujl-backend.service`
