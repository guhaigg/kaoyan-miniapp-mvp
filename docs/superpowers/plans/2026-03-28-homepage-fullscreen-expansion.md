# Homepage Fullscreen Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the homepage to a desktop/fullscreen fluid layout while preserving the existing homepage design, content hierarchy, animations, and business logic.

**Architecture:** Keep all changes inside the homepage component so the rest of the site shell and business flows remain untouched. Adjust only container-width and section-width constraints, plus the fixed-width inline chart wrappers that currently prevent the top modules from visually expanding on large screens.

**Tech Stack:** Next.js App Router, React 19, Tailwind CSS, Framer Motion, TypeScript

---

### Task 1: Widen the homepage root container

**Files:**
- Modify: `web-ui/src/components/home/SignalDashboardHome.tsx`
- Test: `web-ui/src/components/home/SignalDashboardHome.tsx`

- [ ] **Step 1: Replace the centered narrow root container with a full-width container**

Update the homepage root wrapper from a fixed-width centered shell to a fluid container with safe gutters.

Current target block:

```tsx
return (
  <div className="pt-28 max-w-[1200px] mx-auto px-6 pb-32 relative z-10">
```

Planned replacement:

```tsx
return (
  <div className="relative z-10 w-full px-6 pb-32 pt-28 md:px-8 xl:px-10 2xl:px-12">
```

- [ ] **Step 2: Verify no other homepage wrapper still reintroduces a narrow max width**

Run:

```powershell
rg -n "max-w-\\[1200px\\]|mx-auto px-6 pb-32 pt-28" web-ui/src/components/home/SignalDashboardHome.tsx
```

Expected:

- The old fixed-width root wrapper no longer exists.

- [ ] **Step 3: Commit**

```bash
git add web-ui/src/components/home/SignalDashboardHome.tsx
git commit -m "style: widen homepage root layout"
```

### Task 2: Expand the top data strip across large screens

**Files:**
- Modify: `web-ui/src/components/home/SignalDashboardHome.tsx`
- Test: `web-ui/src/components/home/SignalDashboardHome.tsx`

- [ ] **Step 1: Remove local width caps from the top metrics row**

Update the metrics-row wrapper and the three metric blocks so they can distribute across the available desktop width.

Current target patterns:

```tsx
<div className="flex flex-col lg:flex-row items-center justify-center gap-12 lg:gap-20 mb-20 px-8">
```

```tsx
<div className="flex items-end gap-6 w-full lg:w-auto flex-1 max-w-[350px]">
```

Planned direction:

```tsx
<div className="mb-20 flex w-full flex-col gap-12 px-0 lg:flex-row lg:items-stretch lg:gap-10 xl:gap-12">
```

```tsx
<div className="flex w-full flex-1 items-end gap-6">
```

Notes:

- Keep the third radar-match block visually consistent with the first two blocks.
- Do not change text content, icons, or animation config.

- [ ] **Step 2: Relax local chart wrapper width caps**

Update the chart wrapper classes so they can expand with their parent blocks.

Current target patterns:

```tsx
<div className="relative w-full max-w-[180px] h-[48px]">
```

```tsx
<div className="flex items-end gap-1.5 w-full max-w-[160px] h-[36px]">
```

Planned direction:

```tsx
<div className="relative h-[48px] w-full min-w-[180px] max-w-[320px] xl:max-w-[420px]">
```

```tsx
<div className="flex h-[36px] w-full min-w-[160px] max-w-[260px] items-end gap-1.5 xl:max-w-[320px]">
```

Notes:

- Keep the SVG drawing logic and Framer Motion transitions unchanged.
- Only expand the wrapper footprint so the modules look proportionate on 1440px+ screens.

- [ ] **Step 3: Confirm the metrics row no longer stays clustered in the center**

Run:

```powershell
rg -n "max-w-\\[350px\\]|max-w-\\[180px\\]|max-w-\\[160px\\]" web-ui/src/components/home/SignalDashboardHome.tsx
```

Expected:

- Old narrow caps are either removed or replaced with broader responsive caps.

- [ ] **Step 4: Commit**

```bash
git add web-ui/src/components/home/SignalDashboardHome.tsx
git commit -m "style: expand homepage metrics strip"
```

### Task 3: Let the two-column content area stretch toward the viewport edges

**Files:**
- Modify: `web-ui/src/components/home/SignalDashboardHome.tsx`
- Test: `web-ui/src/components/home/SignalDashboardHome.tsx`

- [ ] **Step 1: Convert the main content grid into a full-width desktop section**

Keep the two-column layout, but let it inherit the full-width homepage shell.

Current target block:

```tsx
<div className="grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-16">
```

Planned replacement:

```tsx
<div className="grid w-full grid-cols-1 gap-12 lg:grid-cols-2 lg:gap-10 xl:gap-12">
```

Notes:

- Do not change card structure or per-card spacing.
- Preserve the current dual-column behavior.

- [ ] **Step 2: Keep card density stable while widening the columns**

Inspect the announcement and adjustment card wrappers and leave their internal padding alone unless a width change causes obvious imbalance.

Do not rewrite these internals:

```tsx
className="group relative bg-white rounded-2xl p-5 ..."
```

The cards should become wider because the columns widen, not because the cards themselves get bulkier.

- [ ] **Step 3: Verify the content section now inherits the new full-width layout**

Run:

```powershell
rg -n "grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-16" web-ui/src/components/home/SignalDashboardHome.tsx
```

Expected:

- The old narrower content-grid class string no longer remains.

- [ ] **Step 4: Commit**

```bash
git add web-ui/src/components/home/SignalDashboardHome.tsx
git commit -m "style: stretch homepage content columns"
```

### Task 4: Validate the homepage layout change

**Files:**
- Modify: `docs/current_status_2026-03-18.md`
- Modify: `docs/homepage_frozen_ui_logic_integration_2026-03-28.md`
- Test: `web-ui/src/components/home/SignalDashboardHome.tsx`

- [ ] **Step 1: Run lint**

Run:

```bash
cd web-ui && npm run lint
```

Expected:

```text
✔ No ESLint warnings or errors
```

- [ ] **Step 2: Run build**

Run:

```bash
cd web-ui && npm run build
```

Expected:

```text
✓ Compiled successfully
✓ Generating static pages
✓ Exporting
```

- [ ] **Step 3: Update docs to record the fullscreen expansion**

Append a short note stating that the frozen homepage now uses a fluid desktop layout and no longer stays inside the prior narrow centered container.

Suggested doc note:

```md
- Homepage frozen UI now uses a fluid desktop shell: the top metric strip and the dual-column content area expand close to the viewport edges on large screens without changing the approved visual language.
```

- [ ] **Step 4: Manual visual review**

Review `/` at desktop widths if a browser session is available:

- 1440px
- 1728px or similar
- 1920px

Confirm:

- design is unchanged
- top modules span the page naturally
- two-column content stretches outward
- mobile layout still stacks correctly

- [ ] **Step 5: Final commit**

```bash
git add web-ui/src/components/home/SignalDashboardHome.tsx docs/current_status_2026-03-18.md docs/homepage_frozen_ui_logic_integration_2026-03-28.md
git commit -m "style: expand homepage layout for large screens"
git push origin main
```

## Notes For The Implementer

- This plan intentionally avoids changing `AppChrome`, `SSEClient`, auth flow, search flow, and card internals.
- There is no dedicated frontend component test harness in the current `web-ui` package for this layout-only task. Use `lint + build + manual viewport review` as the release gate.
- If a width adjustment makes any section feel too sparse on 1920px, tighten by adding larger responsive `max-w` values to the local chart wrappers rather than reintroducing a page-level narrow shell.
