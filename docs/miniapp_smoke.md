# Miniapp Smoke Checklist

This document defines the Ubuntu-friendly smoke path for the mini program when WeChat DevTools is unavailable.

## Prerequisites

- Install project dependencies: `npm install`
- Keep the mini program code upload private key outside git, recommended path: `.secrets/miniprogram-ci.key`
- Make sure the key IP whitelist on the WeChat public platform includes the current machine IP
- Confirm the mini program `appid` in `miniapp/project.config.json` is correct

## Generate Preview QR On Ubuntu

```bash
npm run smoke:miniapp:preview -- --privateKeyPath .secrets/miniprogram-ci.key
```

The command will:

- compile the mini program with `miniprogram-ci`
- delete existing `artifacts/miniprogram-preview*.jpg|png` old QR files before generation
- create a preview QR image at `artifacts/miniprogram-preview.jpg`
- print progress logs in the terminal

Optional launch parameters:

```bash
npm run smoke:miniapp:preview -- \
  --privateKeyPath .secrets/miniprogram-ci.key \
  --pagePath pages/announcements/index \
  --searchQuery "schoolName=北京大学&keywords=调剂"
```

Optional environment variable form:

```bash
export MINIPROGRAM_PRIVATE_KEY_PATH=.secrets/miniprogram-ci.key
export MINIPROGRAM_PREVIEW_PAGE_PATH=pages/adjustments/index
export MINIPROGRAM_PREVIEW_SEARCH_QUERY='schoolName=清华大学&keywords=材料'
npm run smoke:miniapp:preview
```

## Runtime Notes

- The current mini program runtime config uses multi-domain candidates in order:
  `https://api.gewujl.cloud/api/v1` -> `https://gewujl.cloud/api/v1` -> `https://www.gewujl.cloud/api/v1`
- Requests retry the same domain first (up to 3 attempts), then switch to next candidate domain
- `wx.request` network options force `enableHttp2: false` and `enableQuic: false` to reduce network-stack compatibility resets
- If you want to test against another backend, update `miniapp/utils/config.js` before generating the preview

## Manual Smoke Checklist

- Open home page and confirm the visible build marker (current expected: `Build 20260315-1830`)
- Open the preview from WeChat and confirm the home page loads without a white screen
- Confirm silent login failure does not block browsing
- Search announcements and verify the list loads
- Search adjustments and verify the list loads
- Open a detail page from each list and verify missing fields do not break rendering
- Trigger one error path if possible and verify it routes to `/pages/status/index` with readable text

## Real Device A/B Matrix (20 requests each)

Use the same phone and near-identical time window. For each network mode, enter list page and tap search 20 times.

| Network mode | Proxy state | Total | Failures | Failure rate | Failed requestId / time |
| --- | --- | --- | --- | --- | --- |
| Wi-Fi | N/A | 20 |  |  |  |
| 5G | Clash OFF | 20 |  |  |  |
| 5G | Clash ON | 20 |  |  |  |

## Request Domain Whitelist Checklist

In WeChat public platform (`当前 appid`), make sure all request legal domains are configured without path:

- `https://api.gewujl.cloud`
- `https://gewujl.cloud`
- `https://www.gewujl.cloud`

## Server Correlation Logging

- Miniapp now sends `X-Request-Id` on every API request.
- Nginx access log now records `request_id=...`.
- Backend service log now records `request_id=...`.

Quick check commands:

```bash
sudo tail -f /var/log/nginx/access.log
sudo journalctl -u gewujl-backend.service -f
```

If miniapp failure shows `requestId=...` but server logs have no same id, treat as "request never reached server".

## Troubleshooting

- `private key not found`: verify `--privateKeyPath` or `MINIPROGRAM_PRIVATE_KEY_PATH`
- preview upload permission error: re-check the WeChat code upload key and IP whitelist
- API request failures after scan: verify the backend health endpoint and the current API base URL
- `request:fail url not in domain list`: in WeChat public platform for current `appid`, add all used request legal domains:
  `https://api.gewujl.cloud`, `https://gewujl.cloud`, `https://www.gewujl.cloud` (no path), then retry after propagation
- `request:fail net::ERR_CONNECTION_RESET` / `errno:600001`: compare request id and timestamp with server logs first; if server has no same request id, prioritize client-side network/clash/tun path investigation
