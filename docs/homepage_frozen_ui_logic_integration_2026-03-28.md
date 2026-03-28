# Homepage Frozen UI Logic Integration (2026-03-28)

## What changed

- The `/` route now renders the frozen `ui.html` homepage structure through `web-ui/src/components/home/SignalDashboardHome.tsx`.
- Home-only chrome is isolated from the shared site shell:
  - `web-ui/src/components/layout/AppChrome.tsx` skips the shared `Background/Header/Modals/Toast` on `/`
  - `web-ui/src/components/shared/SSEClient.tsx` skips the shared SSE listener on `/`
- The homepage visual structure, Tailwind classes, and Framer Motion hierarchy were preserved from `ui.html`; only logic was replaced.
- The desktop homepage shell is now fluid: the top metric strip and the dual-column content area expand close to the viewport edges on large screens instead of staying inside the previous narrow centered container.

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
