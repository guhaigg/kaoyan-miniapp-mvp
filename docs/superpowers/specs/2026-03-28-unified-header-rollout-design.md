# Unified Header Rollout Design

**Date:** 2026-03-28

## Goal

Replace the current split homepage/header implementations with one shared header based on the current homepage navigation design, while keeping route-specific behavior:

- all pages use the same visual header
- announcement summary and adjustment summary views hide the center search box
- every other page that shows the search box uses the same shorter width

## Current Problem

The project currently has two header implementations:

- homepage-local header inside `web-ui/src/components/home/SignalDashboardHome.tsx`
- shared site header inside `web-ui/src/components/layout/Header.tsx`

That split already creates drift in:

- visual styling
- nav labels and routing
- search behavior
- future extensibility

Because the user plans to keep adding new navigation-level features, keeping two implementations would turn every future header change into duplicate work with increasing risk of inconsistency.

## Chosen Approach

Create one shared header implementation and make it the only header used by both homepage and the rest of the app.

The homepage header is the source design. The shared app shell will adopt that implementation instead of continuing to evolve the older `layout/Header.tsx`.

Route-aware configuration will control the center search area rather than duplicating the header for special pages.

## Design

### 1. Single Shared Header

A new shared header component will become the only production header implementation.

Responsibilities:

- render the homepage-approved visual shell
- render the common nav links
- render the user area / login state / quick actions
- handle route-aware search visibility
- handle route-aware search submit behavior

Homepage and non-home pages must both use this same component.

The old shared header should no longer remain as an independent competing implementation.

### 2. Route-Aware Search Visibility

The header must decide whether to show the center search box from route state.

Rules:

- `/` shows the search box
- ordinary pages keep the search box
- `/search?tab=announcements` hides the search box
- `/search?tab=adjustments` hides the search box

This is specifically scoped to the summary views for announcement search and adjustment search, matching the user request.

The rest of the header remains visible on those pages.

### 3. Unified Search Width

All pages that do show the center search box must use the same shorter width.

Decision:

- use one shared desktop max width for the search box
- do not let homepage stay wider than the rest of the site
- keep mobile behavior compact; the main change is desktop/tablet visual balance

Target direction:

- desktop search width should feel clearly shorter than the current homepage version
- the center area should remain visually centered, but not dominate the nav row

Implementation expectation:

- use a single shared width constraint in the unified header component
- avoid route-specific width tweaks unless a future requirement explicitly asks for them

### 4. Navigation Extensibility

The unified header should not hardcode future growth into one monolithic block.

The design should split:

- nav item definitions
- route behavior flags
- header rendering

This keeps future changes simple when adding:

- new feature entry points
- badges
- role-specific links
- reminder counters
- user-menu actions

### 5. Shell Integration

The shared app shell should stop rendering the old layout header and render the unified header instead.

The homepage should also stop maintaining its own private header implementation and consume the same shared component.

That means:

- `AppChrome` uses the shared unified header
- homepage page/component also uses the same shared unified header
- the old duplication is removed

### 6. Search Behavior

The shared header search continues to act as a launcher, not an inline result surface.

Behavior:

- announcement mode routes to announcement summary
- adjustment mode routes to adjustment summary
- existing auth gating for adjustment search remains intact

Hidden-search pages simply do not render the center search box.

## File-Level Direction

Expected implementation shape:

- create a shared unified header component under `web-ui/src/components/layout/`
- create a small route/header config helper if needed
- update `AppChrome.tsx` to use the unified header
- update homepage code so it no longer owns a private header implementation

Likely touched files:

- `web-ui/src/components/layout/AppChrome.tsx`
- `web-ui/src/components/layout/Header.tsx` or a replacement shared header file
- `web-ui/src/components/home/SignalDashboardHome.tsx`

Optional supporting file:

- `web-ui/src/components/layout/header-config.ts`

## Non-Goals

- no redesign of the approved homepage navigation style
- no new navigation features in this task
- no new backend work
- no change to announcement/adjustment search page business logic beyond header visibility

## Verification

Minimum verification for implementation:

- `cd web-ui && npm run lint`
- `cd web-ui && npm run build`

Manual review targets:

- homepage uses the shared header
- account/watchlist/radar/admin pages use the same header style
- `/search?tab=announcements` has no center search box
- `/search?tab=adjustments` has no center search box
- another non-search page still shows the shorter search box
- nav links and user actions still work

## Risks

- moving homepage to a shared header can accidentally reintroduce double-header rendering if shell conditions are not updated carefully
- route detection for `/search` must read query state correctly, not just pathname
- replacing the old shared header can affect login/user-card/watchlist interactions if state wiring is missed

## Decision Summary

The project should use one shared header derived from the current homepage navigation design. Search visibility must be controlled by route rules, and every page that shows the center search box must use the same shorter width. This is the safest path for future navigation feature growth.
