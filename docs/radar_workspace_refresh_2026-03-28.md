# Radar Workspace Refresh

Date: `2026-03-28`

## Scope

This change refreshes the `/radar` page in `web-ui` so it follows the same light dashboard language as the updated homepage shell.

The radar prediction API flow is unchanged. The work only reorganizes the page structure, visual hierarchy, and result presentation.

## What Changed

- Rebuilt the `/radar` hero into a light workspace header with an explicit explanation of what the page does and when to use it.
- Reworked `RadarCalculator` from a dark isolated control panel into a two-column workspace:
  - left: cleaner parameter entry with presets and guide chips
  - right: richer idle/loading/result canvas with clearer preview and outcome states
- Added more decision context to the result panel:
  - level badge
  - win-rate bar
  - percentile band
  - historical group count
  - direct next-step links into `/search`
- Reused the shared top navigation and extended the light grid background treatment to `/radar` so it no longer feels visually disconnected from the homepage.

## Files

- `web-ui/src/app/radar/page.tsx`
- `web-ui/src/components/search/RadarCalculator.tsx`
- `web-ui/src/components/layout/Background.tsx`

## Verification

- `cd web-ui && npm run lint`
- `cd web-ui && npm run build`
- Browser/live inspection of `https://gewujl.cloud/radar/` before implementation to confirm the existing UX issues being addressed
