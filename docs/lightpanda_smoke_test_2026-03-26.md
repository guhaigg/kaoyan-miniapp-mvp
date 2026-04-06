# Lightpanda Smoke Test

This repo now includes a minimal Lightpanda smoke runner:

- `backend/scripts/lightpanda_smoke.py`

It is intentionally separate from the existing crawler / frontend test chain.
Use it to validate whether a page can be driven through Lightpanda's CDP server
before deciding to invest in wider compatibility work.

## 1) Start Lightpanda

Option A: Docker

```bash
docker run -d --rm --name lightpanda -p 9222:9222 lightpanda/browser:nightly
```

Option B: Local binary

```bash
./lightpanda serve --host 127.0.0.1 --port 9222
```

## 2) Run the smoke script

From the repo root:

```bash
python backend/scripts/lightpanda_smoke.py ^
  --cdp-url http://127.0.0.1:9222 ^
  --url https://example.com/search/ ^
  --selector "a" ^
  --selector "input"
```

Linux/macOS form:

```bash
python backend/scripts/lightpanda_smoke.py \
  --cdp-url http://127.0.0.1:9222 \
  --url https://example.com/search/ \
  --selector "a" \
  --selector "input"
```

## 3) Optional HTML dump

```bash
python backend/scripts/lightpanda_smoke.py \
  --url https://example.com/admin/ \
  --dump-html tmp/lightpanda-admin.html
```

## 4) Output

The script prints JSON like:

```json
{
  "engine": "lightpanda",
  "ok": true,
  "status": 200,
  "final_url": "https://example.com/search/",
  "title": "..."
}
```

## 5) Scope and limits

- This is a smoke tool, not a full E2E framework.
- It assumes Lightpanda is already running and reachable over CDP.
- It uses Python Playwright's `chromium.connect_over_cdp(...)`.
- A passing smoke result only means the specific page/script path works under the current Lightpanda build.
- Lightpanda is still beta, so do not treat this as a production-equivalent replacement for Chromium without additional coverage.
