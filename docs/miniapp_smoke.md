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

- Open the preview from WeChat and confirm the home page loads without a white screen
- Confirm silent login failure does not block browsing
- Search announcements and verify the list loads
- Search adjustments and verify the list loads
- Open a detail page from each list and verify missing fields do not break rendering
- Trigger one error path if possible and verify it routes to `/pages/status/index` with readable text

## Troubleshooting

- `private key not found`: verify `--privateKeyPath` or `MINIPROGRAM_PRIVATE_KEY_PATH`
- preview upload permission error: re-check the WeChat code upload key and IP whitelist
- API request failures after scan: verify the backend health endpoint and the current API base URL
- `request:fail url not in domain list`: in WeChat public platform for current `appid`, add all used request legal domains:
  `https://api.gewujl.cloud`, `https://gewujl.cloud`, `https://www.gewujl.cloud` (no path), then retry after propagation
- `request:fail net::ERR_CONNECTION_RESET`: check clash/mihomo fake-ip policy, ensure `api.gewujl.cloud` is excluded from fake-ip mapping and avoid proxy-induced DNS pollution
