# Homepage Fullscreen Expansion Design

**Date:** 2026-03-28

## Goal

Keep the current homepage visual design unchanged while expanding the desktop and large-screen layout so the top data modules and the two-column content area both stretch close to the viewport edges instead of staying inside the current narrow centered container.

## Scope

In scope:

- Homepage only: `web-ui/src/components/home/SignalDashboardHome.tsx`
- Desktop and large-screen layout expansion
- Existing cards, typography, colors, icons, and animation behavior remain intact

Out of scope:

- Any redesign of the homepage
- Changes to card hierarchy or information architecture
- Changes to search, auth, SSE, or data-mapping logic
- Changes to non-home routes

## Constraints

- Preserve the current homepage design language.
- Do not introduce a second visual system.
- Keep the current card internals and section order unchanged.
- Treat this as a layout-width adjustment, not a content rewrite.

## Chosen Approach

Use a fluid full-width homepage container with controlled horizontal padding, then remove the local width caps that keep the top modules and the two main columns artificially narrow. The homepage keeps its current sections and component structure, but each section can consume substantially more horizontal space on desktop and large monitors.

This is intentionally not a “scale everything up” pass. The cards keep their current internal density so the page still feels crisp rather than empty. The expansion happens at the container and section-distribution level.

## Layout Design

### 1. Page-Level Container

Current behavior:

- The homepage root container is centered with `max-w-[1200px]`.

Planned behavior:

- Replace the fixed-width root container with a full-width container.
- Keep responsive horizontal gutters so content does not touch the viewport edge.
- Maintain the current vertical spacing (`pt-28`, `pb-32`) unless a width change makes a spacing bug obvious.

Expected outcome:

- On 1440px, 1728px, and 1920px displays, the homepage should visibly open up and no longer look boxed into a narrow middle strip.

### 2. Top Data Modules

Current behavior:

- The three top modules are visually centered and partially capped by local `max-w` constraints.

Planned behavior:

- Let the top metrics row span the full available width inside the page gutters.
- Remove the local narrow caps that keep each metric block compressed.
- Keep the existing three-module composition:
  - release velocity
  - quality tier
  - radar match
- Preserve current typography, motion, and chart styling.

Expected outcome:

- The top row should read as a real full-width dashboard strip rather than three small modules parked in the center.

### 3. Two-Column Main Content

Current behavior:

- The announcement stream and adjustment radar already form a two-column layout, but the full section is still visually constrained by the outer page width.

Planned behavior:

- Let the two-column section inherit the new full-width homepage container.
- Keep the same two-column relationship and gap behavior.
- Preserve each card’s internal structure and hover behavior.

Expected outcome:

- Both columns become wider and more useful on desktop, but the page still reads as the same design.

## File Boundaries

### Modify

- `web-ui/src/components/home/SignalDashboardHome.tsx`
  - adjust the outer homepage width classes
  - relax the top-row local width caps
  - relax the main two-column section width constraints

### Do Not Modify For This Task

- `web-ui/src/components/layout/AppChrome.tsx`
- `web-ui/src/components/shared/SSEClient.tsx`
- auth/search/api wrappers

## Error Handling

This task is layout-only. There is no new runtime branch, network behavior, or business-state change. The main failure mode is visual regression, not logic regression.

Primary risks:

- overly wide empty space on ultra-wide monitors
- top modules becoming visually detached from each other
- card rows looking sparse if local width caps are removed too aggressively

Mitigation:

- keep horizontal gutters
- expand section containers first before changing card internals
- avoid inflating text sizes or card paddings

## Testing Plan

### Required

- `cd web-ui && npm run lint`
- `cd web-ui && npm run build`

### Visual Review

Manual homepage checks at:

- 1440px width
- 1728px or similar large desktop width
- 1920px width if available

Verify:

- homepage still matches the current visual design
- top modules now span the screen more naturally
- announcement and adjustment columns both expand outward
- mobile and tablet layouts are not broken by desktop width changes

## Acceptance Criteria

- The homepage remains visually the same design.
- The homepage no longer appears boxed into the previous centered narrow container on desktop.
- The top data modules stretch across the page width within safe gutters.
- The dual-column content section also expands close to the viewport edges.
- Lint and build both pass.
