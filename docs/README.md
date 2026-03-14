# Kaoyan Miniapp MVP Docs

This repo is a fresh implementation for:
- WeChat Mini Program frontend
- Python FastAPI backend
- MySQL 8.0 + Redis
- Crawler-ready ingestion pipeline

## Architecture Overview

```mermaid
flowchart LR
  A["WeChat Mini Program"] --> B["FastAPI Gateway (/api/v1/*)"]
  B --> C["PostgreSQL"]
  B --> D["Redis"]
  E["Crawler Workers"] --> B
  F["Manual Admin Entry"] --> B
```

## Environment Requirements

- Python 3.10+
- Node.js 18+
- Docker Compose v2+
- WeChat DevTools (for miniapp debug)

## Quick Start (Local)

1. Clone and enter project:
```bash
git clone <your-repo-url>
cd kaoyan-miniapp-mvp
```

2. Start infra:
```bash
docker compose -f infra/docker-compose.yml up -d db redis
```

3. Run backend:
```bash
cd backend
cp .env.example .env
pip install -r requirements.txt
python -m alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

4. Seed Week 4 sources (20 schools):
```bash
cd backend
python scripts/seed_sources.py
```

5. Run miniapp:
- Open `miniapp/` with WeChat DevTools.
- Keep default no-popup silent login flow via `wx.login`.
- For local-only flow without WeChat secret, set `USE_MOCK_WECHAT=true` in `backend/.env`.

## Core Docs Index

- [Backend and Crawler Spec](./backend_and_crawler.md)
- [Frontend and Design Spec](./frontend_and_design.md)
- [Deployment Handbook](./deployment.md)
- [Git Workflow and Release Rules](./git_workflow.md)
- [PR Draft: dev -> main](./pr_dev_to_main.md)
