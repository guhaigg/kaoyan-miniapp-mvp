# Homepage Dashboard Refresh

Date: `2026-03-28`

## Scope

This change replaces the previous Bilibili-style homepage composition with a standalone homepage shell adapted from the repository root `ui.html`.

The refresh also consolidates the shared top navigation so the homepage and the rest of the site render through the same header component.

## What Changed

- The homepage no longer renders `BiliHeroBanner`, `BiliCategoryStrip`, and `BiliRecommendationGrid` as the landing experience.
- `/` now renders `SignalDashboardHome`, a dedicated homepage component that mirrors the updated `ui.html` composition directly:
  - fixed white grid background
  - centered shared search hub in the header
  - top `Live Data / Sources` strip
  - `Latest Notices` and `Adjustment Radar` dual-column feed
- The navigation bar is now unified through the shared `Header` component so `/`, `/search`, `/radar`, and the rest of the site use the same logo, centered search layout, and typography treatment.
- Homepage actions now point to real application flows instead of static demo actions:
  - search bar -> `/search`
  - profile button -> `/account` when logged in
  - login modal -> real `/auth/login` + `/auth/me` flow through existing frontend API helpers
  - radar button -> `/radar`

## Data Wiring

- Announcement cards and top-level counters use the existing homepage announcement query.
- Adjustment preview cards use the homepage adjustment query, gated behind login so anonymous users do not trigger protected adjustment fetches.
- The homepage login modal updates the shared portal session store after a successful login, so the rest of the app still sees the same authenticated session.

## Files

- `web-ui/src/app/page.tsx`
- `web-ui/src/app/layout.tsx`
- `web-ui/src/components/layout/AppChrome.tsx`
- `web-ui/src/components/layout/Header.tsx`
- `web-ui/src/components/layout/Background.tsx`
- `web-ui/src/components/home/SignalDashboardHome.tsx`
- `web-ui/src/hooks/useSearch.ts`

## Verification

- `cd web-ui && npm run lint`
- `cd web-ui && npm run build`
- Browser smoke on the local homepage implementation:
  - verified the shared top navigation renders once across the app shell
  - verified the homepage now uses the `ui.html`-style stat strip and dual-column feed layout
