# Homepage Frozen UI Logic Integration (2026-03-28)

## What changed

- The `/` route now renders the frozen `ui.html` homepage structure through `web-ui/src/components/home/SignalDashboardHome.tsx`.
- The homepage visual structure, Tailwind classes, and Framer Motion hierarchy were preserved from `ui.html`; only logic was replaced.
- The desktop homepage shell is now fluid: the top metric strip and dual-column content area expand close to the viewport edges on large screens instead of staying inside the previous narrow centered container.
- The homepage navigation is no longer a one-off local implementation. The whole site now shares the same homepage-based shell through `web-ui/src/components/layout/AppChrome.tsx`, `web-ui/src/components/layout/Header.tsx`, and `web-ui/src/components/layout/Background.tsx`.

## 2026-03-28 Site Architecture Rollout

- The visible product route model is now:
  - `/`
  - `/announcements`
  - `/announcements/detail?id=<content_id>`
  - `/adjustments`
  - `/adjustments/detail?id=<item_id>&kind=<content|opportunity>`
  - `/radar`
  - `/watchlist`
  - `/account`
  - `/admin`
- The old `/search` and `/query` pages were removed from the visible product architecture.
- The shared navigation now uses the homepage labels across the site:
  - `首页`
  - `公告汇总`
  - `调剂汇总`
  - `雷达测算`
  - `关注库`
  - `我的空间`
  - `管理后台` when admin access is available
- The global header search bar is hidden on `/announcements` and `/adjustments`, and remains visible in the shortened-width variant on the other pages.
- `watchlist` was refocused into a pure operations workspace, `account` was refocused into account / membership / notifications / personal summary, and `/admin` adopted the homepage-based light shell while retaining dense management panels.

## Real integrations on the frozen homepage

- Announcement feed:
  - `POST /api/v1/search/announcements`
  - mapped into the existing `useAnnouncements` hook shape
- Adjustment feed:
  - `POST /api/v1/search/adjustments`
  - mapped into the existing `useAdjustments` hook shape
- Auth modal:
  - `POST /api/v1/auth/login`
  - `POST /api/v1/auth/register` on register mode
  - `GET /api/v1/auth/me`
  - token and profile are synced back into the shared persisted portal store
- Realtime notice stream:
  - `GET /api/v1/notifications/stream`
  - homepage-local toast queue now consumes SSE events directly

## Verification

- `cd web-ui && npm run lint`
- `cd web-ui && npm run build`

## Notes

- This task was frontend-only. `npm run test:backend` was not run.
- The build still shows the pre-existing Next.js workspace-root warning caused by multiple lockfiles; it does not block lint or export.

## 2026-03-28 Live Homepage Upgrade

- Homepage local navigation now routes into the real announcement search, adjustment search, radar, watchlist, account, and admin pages instead of placeholder actions.
- Homepage search is no longer an in-place filter. The mode buttons and Enter action now redirect into the matching `/announcements` or `/adjustments` results view.
- Both homepage columns now support `最新 / 我的关注`:
  - announcement watching view is derived from pending notices plus active monitor-target recent signals
  - adjustment watching view is derived from the newest active saved subscription focus
- The top micro charts now use live-derived homepage data:
  - release trend uses latest adjustment timestamps
  - tier bars use latest adjustment school tiers
  - the right-side `See Live` card uses pending notices plus active monitor-target counts
- Homepage cards and CTA buttons now perform real actions:
  - open source URLs when available
  - otherwise route into the correct summary, detail, or watchlist page
- Anonymous users now see an explicit login prompt in the adjustment column because the current adjustment search API requires authentication.
