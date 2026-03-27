# Homepage Dashboard Refresh

Date: `2026-03-28`

## Scope

This change replaces the previous Bilibili-style homepage composition with a new signal-dashboard homepage adapted from the repository root `ui.html`.

It only changes the `/` page in `web-ui`.

## What Changed

- The homepage no longer renders `BiliHeroBanner`, `BiliCategoryStrip`, and `BiliRecommendationGrid` as the primary landing experience.
- `/` now renders `SignalDashboardHome`, a dedicated homepage component that keeps the supplied `ui.html` visual direction but adapts it to the real application shell.
- The new homepage keeps the existing global layout primitives:
  - shared top header
  - auth modal
  - watchlist drawer
  - toast and SSE bootstrap
- Homepage CTA wiring now points to real application flows instead of static demo actions:
  - search CTA -> `/search`
  - account CTA -> `/account`
  - login CTA -> existing auth modal
  - radar CTA -> `/radar` or watchlist/auth flow depending on user state

## Data Wiring

- Announcement cards and top-level counters use the existing homepage announcement query.
- Adjustment preview cards use a new homepage adjustment query hook, gated behind login so anonymous users do not trigger protected adjustment fetches.
- When announcement data is temporarily unavailable, the homepage shows offline placeholder copy instead of leaving the page visually broken.

## Files

- `web-ui/src/app/page.tsx`
- `web-ui/src/components/home/SignalDashboardHome.tsx`
- `web-ui/src/hooks/useSearch.ts`

## Verification

- `cd web-ui && npm run lint`
- `cd web-ui && npm run build`
- Browser smoke on `http://127.0.0.1:3000/`:
  - verified the new homepage structure renders under the existing global header
  - verified no duplicate top navigation was introduced
  - verified homepage login CTA opens the existing auth modal
