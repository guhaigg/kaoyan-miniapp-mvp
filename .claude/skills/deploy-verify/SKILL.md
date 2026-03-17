---
name: deploy-verify
description: Verify deployment status and run health checks
user-invocable: true
disable-model-invocation: false
---

# Deployment Verification Skill

Verifies deployment status and runs comprehensive health checks for the Ge Wu Jian Lu platform.

## Usage

`/deploy-verify`

## Verification Steps

### 1. Service Health
- Checks Nginx status
- Verifies FastAPI backend health endpoint
- Tests database connectivity
- Checks Redis connection

### 2. API Endpoints
- Tests `/api/v1/health`
- Verifies authentication endpoints
- Checks search and notification APIs
- Tests admin endpoints (if applicable)

### 3. Web UI
- Verifies static file serving
- Checks Next.js build integrity
- Tests client-side hydration
- Verifies SSE connection

### 4. Miniapp API
- Tests WeChat authentication flow
- Verifies content APIs
- Checks subscription endpoints

## Remote Commands Used

- `systemctl status nginx`
- `curl -s http://localhost:8000/health`
- `curl -s http://localhost/api/v1/health`
- `journalctl -u nginx --tail=50`
- `ps aux | grep python`

## Expected Results

Returns detailed health status report with:
- ✅ Passing checks
- ❌ Failing components
- ⚠️ Warnings
- 📊 Performance metrics

## Common Issues Detected

- Backend service not running
- Nginx configuration errors
- Database connection failures
- API endpoint misconfigurations
- Static file serving issues