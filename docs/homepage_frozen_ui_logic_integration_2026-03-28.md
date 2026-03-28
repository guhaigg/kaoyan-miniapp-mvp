# Homepage Frozen UI Logic Integration (2026-03-28)

## What changed

- The `/` route now renders the frozen `ui.html` homepage structure through `web-ui/src/components/home/SignalDashboardHome.tsx`.
- Home-only chrome is isolated from the shared site shell:
  - `web-ui/src/components/layout/AppChrome.tsx` skips the shared `Background/Header/Modals/Toast` on `/`
  - `web-ui/src/components/shared/SSEClient.tsx` skips the shared SSE listener on `/`
- The homepage visual structure, Tailwind classes, and Framer Motion hierarchy were preserved from `ui.html`; only logic was replaced.
- The desktop homepage shell is now fluid: the local homepage navigation, top metric strip, and dual-column content area expand close to the viewport edges on large screens instead of staying inside the previous narrow centered container.

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
- Homepage search is no longer an in-place filter. The mode buttons and Enter action now redirect into the matching `/search` results view.
- Both homepage columns now support `最新 / 我的关注`:
  - announcement watching view is derived from pending notices plus active monitor-target recent signals
  - adjustment watching view is derived from the newest active saved subscription focus
- The top micro charts now use live-derived homepage data:
  - release trend uses latest adjustment timestamps
  - tier bars use latest adjustment school tiers
  - the right-side `See Live` card uses pending notices plus active monitor-target counts
- Homepage cards and CTA buttons now perform real actions:
  - open source URLs when available
  - otherwise route into the correct search or watchlist page
- Anonymous users now see an explicit login prompt in the adjustment column because the current adjustment search API requires authentication.
