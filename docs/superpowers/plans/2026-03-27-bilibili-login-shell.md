# Bilibili Login Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the public web auth and account entry experience into a Bilibili-style desktop shell while keeping our existing auth APIs and real business data.

**Architecture:** Introduce a shared bright homepage shell that owns the banner, translucent top nav, search bar, and icon cluster; layer a reusable centered auth modal on top of that shell for `/login`, `/register`, and header-triggered auth entry; then refit the logged-in avatar card and `/account` first screen to match the same visual language. This stays frontend-only and preserves existing Zustand auth state plus existing profile, notification, subscription, and radar queries.

**Tech Stack:** Next.js 15 App Router, React 19, TypeScript, Tailwind CSS, Framer Motion, Zustand, existing REST auth APIs

---

## File Map

### Shared shell and theme

- Modify: `web-ui/src/app/globals.css`
  Purpose: Replace the dark dashboard baseline with bright Bilibili-style theme tokens, shared utility classes, and modal/surface helpers.
- Modify: `web-ui/src/app/layout.tsx`
  Purpose: Keep the global providers but ensure the new shell/header/background stack renders correctly across `/`, `/login`, `/register`, and `/account`.
- Modify: `web-ui/src/components/layout/Background.tsx`
  Purpose: Swap the sci-fi grid background for route-aware banner/backdrop treatment.

### Header and logged-in account entry

- Modify: `web-ui/src/components/layout/Header.tsx`
  Purpose: Replace the existing dark header with a Bilibili-style nav/search/icon/CTA layout and attach the avatar trigger.
- Create: `web-ui/src/components/layout/BiliHeaderUserCard.tsx`
  Purpose: Render the floating logged-in account card that opens from the top-right avatar.
- Create: `web-ui/src/components/layout/bili-header-data.ts`
  Purpose: Map real auth/profile/watchlist/radar counts into header card-friendly values and quick links.

### Homepage shell

- Modify: `web-ui/src/app/page.tsx`
  Purpose: Replace the timeline hero with a Bilibili-style homepage composition that still uses our content.
- Create: `web-ui/src/components/home/BiliHeroBanner.tsx`
  Purpose: Render the top illustrated banner, search overlay support, and top spacing contract.
- Create: `web-ui/src/components/home/BiliCategoryStrip.tsx`
  Purpose: Render the homepage category chips / entry strip below the hero.
- Create: `web-ui/src/components/home/BiliRecommendationGrid.tsx`
  Purpose: Render recommendation-like content cards using existing announcement data.

### Authentication modal and routes

- Modify: `web-ui/src/components/shared/AuthEntryPage.tsx`
  Purpose: Convert the full-page auth surface into a centered modal implementation and keep password login/register working.
- Create: `web-ui/src/components/shared/BiliAuthModal.tsx`
  Purpose: Own the modal shell, tab UI, QR column, social-login placeholders, and mode switching.
- Create: `web-ui/src/components/shared/bili-auth-copy.ts`
  Purpose: Keep Bilibili-like wording rhythm while using our own product copy.
- Modify: `web-ui/src/app/login/page.tsx`
  Purpose: Open the auth shell in login mode over the shared homepage backdrop.
- Modify: `web-ui/src/app/register/page.tsx`
  Purpose: Open the auth shell in register mode over the shared homepage backdrop.
- Modify: `web-ui/src/lib/store.ts`
  Purpose: Ensure header-triggered auth modal open/close, route mode switching, and logged-out fallback continue to work cleanly.

### Account space

- Modify: `web-ui/src/components/account/AccountSpacePage.tsx`
  Purpose: Re-compose the page into a Bilibili-space-style shell rather than the current dashboard layout.
- Modify: `web-ui/src/components/account/AccountSpaceHero.tsx`
  Purpose: Replace the current hero block with a banner + overlapping avatar + stat rail composition.
- Modify: `web-ui/src/components/account/AccountSpaceTabs.tsx`
  Purpose: Restyle the tabs to match the Bilibili-space rhythm while keeping our tab semantics.
- Modify: `web-ui/src/components/account/AccountSpaceSidebar.tsx`
  Purpose: Reframe the right-side cards as profile/service panels that visually match the space page.

### Documentation

- Modify: `docs/current_status_2026-03-18.md`
  Purpose: Update the frontend/account/auth shell rollout description once the implementation lands.

## Validation Baseline

`web-ui/package.json` does not currently provide a dedicated frontend unit/integration test runner. Validation for this plan therefore relies on:

- `cd web-ui && npm run lint`
- `cd web-ui && npm run build`
- manual browser smoke for `/`, `/login`, `/register`, logged-in header state, and `/account`

## Task 1: Establish the Shared Bright Theme and Route-Aware Background

**Files:**
- Modify: `web-ui/src/app/globals.css`
- Modify: `web-ui/src/app/layout.tsx`
- Modify: `web-ui/src/components/layout/Background.tsx`

- [ ] **Step 1: Write the visual mismatch checklist**

Document the current mismatches directly in the implementation notes before touching code:

```text
- body uses dark navy background instead of bright Bilibili-style canvas
- header depends on glass-panel dark shell utilities
- background renders animated sci-fi grid behind every route
- main layout assumes dark foreground contrast
```

- [ ] **Step 2: Replace global theme tokens with bright-shell variables**

Add bright-shell CSS variables and helper classes in `web-ui/src/app/globals.css`:

```css
:root {
  --bili-bg: #f6f7fb;
  --bili-surface: rgba(255, 255, 255, 0.92);
  --bili-text: #18191c;
  --bili-muted: #61666d;
  --bili-pink: #fb7299;
  --bili-blue: #00aeec;
}

body {
  background: var(--bili-bg);
  color: var(--bili-text);
}

@layer utilities {
  .bili-surface {
    @apply rounded-2xl border border-black/5 bg-white/90 shadow-[0_18px_50px_rgba(15,23,42,0.08)] backdrop-blur-xl;
  }
}
```

- [ ] **Step 3: Update layout spacing to fit the new shell**

Adjust `web-ui/src/app/layout.tsx` so the main area works with banner-first pages instead of the old dark dashboard padding:

```tsx
<Background />
<Header />
<main className="relative z-10 min-h-screen pb-20 pt-16 md:pt-18">{children}</main>
```

- [ ] **Step 4: Make the background component route-aware**

Replace the current grid background logic in `web-ui/src/components/layout/Background.tsx` with a softer route-aware backdrop:

```tsx
const bannerRoutes = new Set(["/", "/login", "/register", "/account"]);
const showBannerGlow = bannerRoutes.has(pathname);

return (
  <>
    <div className="pointer-events-none fixed inset-0 z-0 bg-[linear-gradient(180deg,#fbfcff_0%,#f6f7fb_55%,#eef2f8_100%)]" />
    {showBannerGlow ? (
      <div className="pointer-events-none fixed inset-x-0 top-0 z-0 h-[420px] bg-[radial-gradient(circle_at_top,rgba(251,114,153,0.18),transparent_48%),radial-gradient(circle_at_35%_18%,rgba(0,174,236,0.16),transparent_34%)]" />
    ) : null}
  </>
);
```

- [ ] **Step 5: Verify the theme foundation**

Run: `cd web-ui && npm run lint`

Expected: `next lint` completes with no errors from `globals.css`, `layout.tsx`, or `Background.tsx`.

- [ ] **Step 6: Commit the theme foundation**

```bash
git add web-ui/src/app/globals.css web-ui/src/app/layout.tsx web-ui/src/components/layout/Background.tsx
git commit -m "feat: add bilibili-style web shell foundation"
```

## Task 2: Rebuild the Global Header and Logged-In Avatar Entry

**Files:**
- Modify: `web-ui/src/components/layout/Header.tsx`
- Create: `web-ui/src/components/layout/BiliHeaderUserCard.tsx`
- Create: `web-ui/src/components/layout/bili-header-data.ts`
- Modify: `web-ui/src/lib/store.ts`

- [ ] **Step 1: Add a focused data-mapper for header card content**

Create `web-ui/src/components/layout/bili-header-data.ts`:

```ts
export interface BiliHeaderSummary {
  displayName: string;
  levelLabel: string;
  isPremium: boolean;
  counters: Array<{ label: string; value: number }>;
}

export function buildHeaderSummary(input: {
  username: string;
  nickname: string | null;
  isPremium: boolean;
  followingCount: number;
  radarCount: number;
  activityCount: number;
}): BiliHeaderSummary {
  return {
    displayName: input.nickname || input.username,
    levelLabel: input.isPremium ? "PRO" : "LV1",
    isPremium: input.isPremium,
    counters: [
      { label: "关注", value: input.followingCount },
      { label: "雷达", value: input.radarCount },
      { label: "动态", value: input.activityCount },
    ],
  };
}
```

- [ ] **Step 2: Implement the floating avatar card**

Create `web-ui/src/components/layout/BiliHeaderUserCard.tsx` with the white panel composition:

```tsx
export default function BiliHeaderUserCard({ summary, onLogout }: Props) {
  return (
    <div className="bili-surface absolute right-0 top-14 w-[360px] p-6">
      <div className="flex flex-col items-center text-center">
        <div className="h-24 w-24 rounded-full border-4 border-white bg-[linear-gradient(135deg,#ffd7e5,#d7f2ff)]" />
        <h3 className="mt-4 text-3xl font-black text-[#18191c]">{summary.displayName}</h3>
      </div>
      {/* counters + quick links + logout */}
    </div>
  );
}
```

- [ ] **Step 3: Replace the current dark header with the Bilibili-style shell**

Refactor `web-ui/src/components/layout/Header.tsx` around a bright translucent nav:

```tsx
<header className="fixed inset-x-0 top-0 z-50">
  <div className="mx-auto flex h-16 max-w-[1440px] items-center gap-4 px-6 text-white">
    <Link href="/" className="shrink-0 text-3xl font-black tracking-tight text-[#2aa7ff]">
      GEWU
    </Link>
    <nav className="hidden items-center gap-6 lg:flex">{/* nav links */}</nav>
    <div className="mx-auto hidden max-w-[520px] flex-1 lg:block">{/* search */}</div>
    <div className="flex items-center gap-4">{/* icon cluster + avatar/login */}</div>
  </div>
</header>
```

- [ ] **Step 4: Keep auth modal open/close state explicit in the store**

Adjust `web-ui/src/lib/store.ts` so the header can open login mode cleanly:

```ts
interface AppState {
  isAuthOpen: boolean;
  authMode: "login" | "register";
  setAuthOpen: (open: boolean, mode?: "login" | "register") => void;
}

setAuthOpen: (open, mode = "login") =>
  set((state) => ({
    isAuthOpen: open,
    authMode: open ? mode : state.authMode,
  })),
```

- [ ] **Step 5: Verify header compilation**

Run: `cd web-ui && npm run build`

Expected: Next build succeeds and the new header imports compile without type errors.

- [ ] **Step 6: Commit the header overhaul**

```bash
git add web-ui/src/components/layout/Header.tsx web-ui/src/components/layout/BiliHeaderUserCard.tsx web-ui/src/components/layout/bili-header-data.ts web-ui/src/lib/store.ts
git commit -m "feat: add bilibili-style header and avatar card"
```

## Task 3: Convert Authentication into a Centered Modal Over the Shared Shell

**Files:**
- Modify: `web-ui/src/components/shared/AuthEntryPage.tsx`
- Create: `web-ui/src/components/shared/BiliAuthModal.tsx`
- Create: `web-ui/src/components/shared/bili-auth-copy.ts`
- Modify: `web-ui/src/app/login/page.tsx`
- Modify: `web-ui/src/app/register/page.tsx`

- [ ] **Step 1: Extract auth copy and placeholder messages**

Create `web-ui/src/components/shared/bili-auth-copy.ts`:

```ts
export const authCopy = {
  unavailableTitle: "暂未开放",
  unavailableBody: "这个入口先保留视觉位，后续再接真实能力。",
  loginTabs: ["密码登录", "短信登录"] as const,
};
```

- [ ] **Step 2: Build the reusable modal shell**

Create `web-ui/src/components/shared/BiliAuthModal.tsx`:

```tsx
export default function BiliAuthModal({ mode, onClose, children }: Props) {
  return (
    <div className="fixed inset-0 z-[90] flex items-center justify-center bg-black/35 px-6 py-10">
      <div className="bili-surface relative grid w-full max-w-[1140px] overflow-hidden rounded-[24px] lg:grid-cols-[420px_minmax(0,1fr)]">
        <aside className="relative hidden bg-[linear-gradient(180deg,#ffffff,#f3f7ff)] p-10 lg:block">{/* QR + art */}</aside>
        <section className="relative p-8 lg:p-10">{children}</section>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Rework `AuthEntryPage` around modal content instead of full-page layout**

Keep existing API calls but swap the shell:

```tsx
return (
  <BiliAuthModal mode={mode} onClose={handleClose}>
    <AuthTabs mode={mode} onChangeMode={setMode} />
    <PasswordForm onSubmit={handleSubmit} />
    <SocialLoginPlaceholders onUnavailable={handleUnavailable} />
  </BiliAuthModal>
);
```

- [ ] **Step 4: Make `/login` and `/register` mount the same shared shell**

Leave route files thin:

```tsx
export default function LoginPage() {
  return <AuthEntryPage initialMode="login" />;
}

export default function RegisterPage() {
  return <AuthEntryPage initialMode="register" />;
}
```

- [ ] **Step 5: Verify auth pages**

Run: `cd web-ui && npm run lint`

Expected: the modal, route wrappers, and store-driven mode changes pass linting.

- [ ] **Step 6: Commit the auth modal conversion**

```bash
git add web-ui/src/components/shared/AuthEntryPage.tsx web-ui/src/components/shared/BiliAuthModal.tsx web-ui/src/components/shared/bili-auth-copy.ts web-ui/src/app/login/page.tsx web-ui/src/app/register/page.tsx
git commit -m "feat: convert auth pages to bilibili-style modal shell"
```

## Task 4: Recompose the Homepage Into a Bilibili-Style Public Shell

**Files:**
- Modify: `web-ui/src/app/page.tsx`
- Create: `web-ui/src/components/home/BiliHeroBanner.tsx`
- Create: `web-ui/src/components/home/BiliCategoryStrip.tsx`
- Create: `web-ui/src/components/home/BiliRecommendationGrid.tsx`

- [ ] **Step 1: Add a reusable hero banner component**

Create `web-ui/src/components/home/BiliHeroBanner.tsx`:

```tsx
export default function BiliHeroBanner() {
  return (
    <section className="relative h-[180px] overflow-hidden md:h-[240px] lg:h-[300px]">
      <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(13,18,32,0.08),rgba(13,18,32,0.24))]" />
      <div className="absolute inset-0 bg-[url('/images/bili-login-cover.jpg')] bg-cover bg-center" />
    </section>
  );
}
```

- [ ] **Step 2: Add the category strip and recommendation grid shells**

Create the supporting homepage sections:

```tsx
export function BiliCategoryStrip() {
  return <div className="mx-auto flex max-w-[1440px] gap-3 overflow-x-auto px-6 py-5">{/* chips */}</div>;
}

export function BiliRecommendationGrid({ items }: { items: HomeAnnouncement[] }) {
  return <section className="mx-auto grid max-w-[1440px] gap-6 px-6 pb-16 md:grid-cols-2 xl:grid-cols-3">{/* cards */}</section>;
}
```

- [ ] **Step 3: Replace the existing homepage timeline composition**

Refactor `web-ui/src/app/page.tsx`:

```tsx
return (
  <div className="pb-20">
    <BiliHeroBanner />
    <BiliCategoryStrip />
    <BiliRecommendationGrid items={data?.items ?? []} />
  </div>
);
```

- [ ] **Step 4: Preserve real data instead of fake video data**

When shaping homepage cards, use actual announcement fields:

```tsx
<article className="bili-surface overflow-hidden">
  <div className="aspect-[16/10] bg-[linear-gradient(135deg,#dfefff,#ffe2ee)]" />
  <div className="p-4">
    <h3 className="line-clamp-2 text-lg font-semibold text-[#18191c]">{item.title}</h3>
    <p className="mt-2 text-sm text-[#61666d]">{item.school_name ?? "院校待补充"}</p>
  </div>
</article>
```

- [ ] **Step 5: Verify homepage render**

Run: `cd web-ui && npm run build`

Expected: homepage sections compile and the old GSAP timeline logic is fully removed or isolated.

- [ ] **Step 6: Commit the homepage shell**

```bash
git add web-ui/src/app/page.tsx web-ui/src/components/home/BiliHeroBanner.tsx web-ui/src/components/home/BiliCategoryStrip.tsx web-ui/src/components/home/BiliRecommendationGrid.tsx
git commit -m "feat: rebuild homepage as bilibili-style public shell"
```

## Task 5: Refit `/account` Into a Bilibili-Space-Style Personal Homepage

**Files:**
- Modify: `web-ui/src/components/account/AccountSpacePage.tsx`
- Modify: `web-ui/src/components/account/AccountSpaceHero.tsx`
- Modify: `web-ui/src/components/account/AccountSpaceTabs.tsx`
- Modify: `web-ui/src/components/account/AccountSpaceSidebar.tsx`

- [ ] **Step 1: Replace the hero with a banner + overlap composition**

Update `web-ui/src/components/account/AccountSpaceHero.tsx`:

```tsx
export default function AccountSpaceHero(props: Props) {
  return (
    <section className="relative overflow-hidden rounded-b-[28px] bg-white">
      <div className="h-[220px] bg-[url('/images/bili-space-cover.jpg')] bg-cover bg-center" />
      <div className="mx-auto flex max-w-[1440px] items-end gap-6 px-6 pb-6">
        <div className="-mt-14 h-28 w-28 rounded-full border-4 border-white bg-[linear-gradient(135deg,#ffe0ea,#d8f4ff)]" />
        <div className="pb-1">{/* name + badge + signature */}</div>
        <div className="ml-auto grid grid-cols-4 gap-8 text-center">{/* stat rail */}</div>
      </div>
    </section>
  );
}
```

- [ ] **Step 2: Restyle tabs and sidebar into space-page modules**

Adjust tabs and sidebar:

```tsx
<div className="border-b border-black/6 bg-white">
  <div className="mx-auto flex max-w-[1440px] items-center gap-8 px-6">
    {tabs.map((tab) => (
      <button className={active ? "text-[#00aeec] after:h-[3px]" : "text-[#18191c]/80"}>{tab.label}</button>
    ))}
  </div>
</div>
```

```tsx
<aside className="space-y-4">
  <section className="bili-surface p-6">{/* profile service card */}</section>
  <section className="bili-surface p-6">{/* account utility card */}</section>
</aside>
```

- [ ] **Step 3: Recompose the page layout**

Update `web-ui/src/components/account/AccountSpacePage.tsx`:

```tsx
return (
  <div className="pb-20">
    <AccountSpaceHero {...heroProps} />
    <AccountSpaceTabs {...tabProps} />
    <div className="mx-auto grid max-w-[1440px] gap-6 px-6 py-8 lg:grid-cols-[minmax(0,1fr)_320px]">
      <section>{activeTabContent}</section>
      <AccountSpaceSidebar {...sidebarProps} />
    </div>
  </div>
);
```

- [ ] **Step 4: Keep metrics truthful**

Map the right-side stat rail to real fields only:

```ts
const stats = [
  { label: "关注数", value: followingCount },
  { label: "雷达数", value: radarCount },
  { label: "动态数", value: activityCount },
  { label: "会员状态", value: isPremium ? "已开通" : "普通" },
];
```

- [ ] **Step 5: Verify account page**

Run: `cd web-ui && npm run lint`

Expected: account components compile cleanly and tab/hero/sidebar props remain type-safe.

- [ ] **Step 6: Commit the account redesign**

```bash
git add web-ui/src/components/account/AccountSpacePage.tsx web-ui/src/components/account/AccountSpaceHero.tsx web-ui/src/components/account/AccountSpaceTabs.tsx web-ui/src/components/account/AccountSpaceSidebar.tsx
git commit -m "feat: redesign account page as bilibili-style space"
```

## Task 6: Final Validation and Documentation

**Files:**
- Modify: `docs/current_status_2026-03-18.md`

- [ ] **Step 1: Update rollout docs to match the new shell**

Add a concise status note to `docs/current_status_2026-03-18.md` covering:

```md
- Web auth now uses a Bilibili-style homepage shell and centered modal presentation.
- `/login` and `/register` share the same backdrop and modal system.
- The header now exposes an avatar-driven floating account card.
- `/account` first screen now follows a Bilibili-space-inspired layout while keeping real business data.
```

- [ ] **Step 2: Run final frontend validation**

Run:

```bash
cd web-ui
npm run lint
npm run build
```

Expected:

```text
✓ next lint completed successfully
✓ next build completed successfully
```

- [ ] **Step 3: Run manual browser smoke**

Check these routes and interactions:

```text
/
/login
/register
/account
header login button -> opens modal
password login -> succeeds
logged-in avatar -> opens user card
placeholder auth entries -> show unavailable feedback
```

- [ ] **Step 4: Commit documentation and validation close-out**

```bash
git add docs/current_status_2026-03-18.md
git commit -m "docs: record bilibili-style auth shell rollout"
```

## Self-Review Notes

- Spec coverage:
  - homepage shell: Task 1 + Task 4
  - login modal: Task 3
  - logged-in avatar card: Task 2
  - account space: Task 5
  - docs/validation: Task 6
- No placeholder markers such as `TBD` or `TODO` remain.
- Naming is consistent around `BiliAuthModal`, `BiliHeaderUserCard`, and `AccountSpace*` components.
