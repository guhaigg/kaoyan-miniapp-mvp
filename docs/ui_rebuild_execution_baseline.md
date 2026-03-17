# UI Rebuild Execution Baseline

## Source
- Reference file: `/Users/guhai/Downloads/Copy of Website Development and Refinement`
- Parsed format: JSON (`systemInstruction` + `chunkedPrompt`)

## Product Direction
- Target style: immersive, motion-first, app-like transitions.
- Key interaction center: scroll-linked hero / timeline experience (GSAP + motion concept).
- Brand context: 格物简录 / GeWuJian.

## Agreed Stack (from reference)
- Framework: Next.js 15 (App Router) + TypeScript
- Styling: Tailwind CSS v4
- UI: shadcn/ui
- Motion: Framer Motion (global micro interactions), GSAP (heavy scroll choreography)
- State: Zustand
- Data: TanStack Query
- Realtime strategy: SSE (for incremental live updates)

## Core Page Scope
- Home (`app/page.tsx`)
- Search (`app/search/page.tsx`)
- Admin (`app/admin/page.tsx`)

## Core Shared Modules
- `components/layout/Background.tsx`
- `components/layout/Header.tsx`
- `components/shared/BootLoader.tsx`
- `components/shared/Modals.tsx`
- `components/ui/loading-spinner.tsx`
- `components/ui/toaster.tsx`
- `lib/store.ts`
- `lib/query-provider.tsx`
- `lib/utils.ts`

## Delivery Constraints
- Keep the UI in Chinese-first experience.
- Keep design language consistent and avoid mixed visual styles.
- Prioritize reusable component architecture over page-level duplication.
- Maintain deployability to Vercel and compatibility with existing FastAPI backend.

## Execution Order
1. Build app shell (layout, providers, global theme tokens, navigation).
2. Implement home interaction baseline (hero + motion section + fallback states).
3. Implement search page (filters, loading/empty/error, list cards, query integration stubs).
4. Implement admin page shell (permission gate UI + management panels).
5. Integrate modals/toasts/bootloader and unify interaction polish.
6. Connect to API base URL config and finalize deployment docs.
