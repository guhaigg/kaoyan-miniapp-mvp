# Account Space Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the web `/account` experience into a Bilibili-inspired personal space homepage that prioritizes activity, following, and radar while keeping membership, security, and WeChat binding accessible as secondary surfaces.

**Architecture:** Replace the current all-in-one `AccountDashboard` with a new `AccountSpacePage` container that owns URL-driven tab state and composes smaller presentational sections. Reuse the existing account overview, notification history, subscription, monitoring-target, and notice-query hooks to build four tabs: `activity`, `following`, `radar`, and `account`. Keep `/account` as the canonical route and convert `/account/security`, `/account/billing`, and `/account/notifications` into redirects with query-state handoff.

**Tech Stack:** Next.js App Router, React 19, TypeScript, Tailwind CSS, Zustand, TanStack Query, Framer Motion, Lucide React.

---

## File Map

- Delete `web-ui/src/components/account/AccountDashboard.tsx`
  - Remove the old monolithic account dashboard once the new space page is wired.
- Create `web-ui/src/components/account/account-space-query.ts`
  - Parse and normalize `tab` and `panel` query parameters.
- Create `web-ui/src/components/account/account-space-data.ts`
  - Convert raw account, subscription, monitor, and notification payloads into UI-ready space-page summaries.
- Create `web-ui/src/components/account/AccountSpacePage.tsx`
  - Main client container for the new `/account` experience.
- Create `web-ui/src/components/account/AccountSpaceHero.tsx`
  - Cover, avatar, nickname, badges, and top summary strip.
- Create `web-ui/src/components/account/AccountSpaceTabs.tsx`
  - Tab rail with Bilibili-like motion and URL-state switching.
- Create `web-ui/src/components/account/AccountSpaceSidebar.tsx`
  - Membership, WeChat, security, and quick-action sidebar.
- Create `web-ui/src/components/account/AccountActivityTab.tsx`
  - Unified personal activity feed.
- Create `web-ui/src/components/account/AccountFollowingTab.tsx`
  - Subscription and monitor-target card wall.
- Create `web-ui/src/components/account/AccountRadarTab.tsx`
  - Radar overview and recent-signal summaries.
- Create `web-ui/src/components/account/AccountAccountTab.tsx`
  - Membership orders, password change, WeChat bind code, logout, and panel-specific focus blocks.
- Modify `web-ui/src/app/account/page.tsx`
  - Render `AccountSpacePage` with parsed query-state defaults.
- Modify `web-ui/src/app/account/security/page.tsx`
  - Redirect to `/account?tab=account&panel=security`.
- Modify `web-ui/src/app/account/billing/page.tsx`
  - Redirect to `/account?tab=account&panel=billing`.
- Modify `web-ui/src/app/account/notifications/page.tsx`
  - Redirect to `/account?tab=activity&panel=notifications`.
- Modify `docs/current_status_2026-03-18.md`
  - Add a short follow-up note describing the new account-page IA and route compatibility.

## Validation Notes

- There is no committed frontend unit-test harness in `web-ui` today.
- Frontend validation for this task should therefore be:
  - `cd web-ui && npm run lint`
  - `cd web-ui && npm run build`
  - manual smoke in the browser for account routes and responsive states
- `npm run test:backend` is not required unless backend files change during implementation.

### Task 1: Add URL-State Parsing and the New Page Shell

**Files:**
- Create: `web-ui/src/components/account/account-space-query.ts`
- Create: `web-ui/src/components/account/AccountSpacePage.tsx`
- Modify: `web-ui/src/app/account/page.tsx`

- [ ] **Step 1: Create typed query parsing helpers**

```ts
export type AccountSpaceTab = "activity" | "following" | "radar" | "account";
export type AccountSpacePanel = "billing" | "security" | "notifications" | null;

const VALID_TABS = new Set<AccountSpaceTab>(["activity", "following", "radar", "account"]);
const VALID_PANELS = new Set<Exclude<AccountSpacePanel, null>>(["billing", "security", "notifications"]);

function readSingle(value: string | string[] | undefined): string | null {
  if (typeof value === "string" && value.trim()) return value.trim().toLowerCase();
  if (Array.isArray(value) && typeof value[0] === "string" && value[0].trim()) {
    return value[0].trim().toLowerCase();
  }
  return null;
}

export function parseAccountSpaceTab(value: string | string[] | undefined): AccountSpaceTab {
  const next = readSingle(value);
  return next && VALID_TABS.has(next as AccountSpaceTab) ? (next as AccountSpaceTab) : "activity";
}

export function parseAccountSpacePanel(value: string | string[] | undefined): AccountSpacePanel {
  const next = readSingle(value);
  return next && VALID_PANELS.has(next as Exclude<AccountSpacePanel, null>)
    ? (next as Exclude<AccountSpacePanel, null>)
    : null;
}
```

- [ ] **Step 2: Build the new page-level client shell**

```tsx
"use client";

import { useMemo } from "react";
import { useAppStore } from "@/lib/store";
import { useSubscriptionsQuery } from "@/hooks/useSubscriptions";
import { useMonitorTargetsQuery } from "@/hooks/useMonitoringTargets";
import { useWatchlistNoticesQuery } from "@/hooks/useNotifications";
import {
  getCurrentUserAccountOverview,
  getCurrentUserNotificationHistory,
  getCurrentUserPaymentOrders,
} from "@/lib/api";
import { AccountSpaceHero } from "./AccountSpaceHero";
import { AccountSpaceTabs } from "./AccountSpaceTabs";
import { AccountSpaceSidebar } from "./AccountSpaceSidebar";
import { AccountActivityTab } from "./AccountActivityTab";
import { AccountFollowingTab } from "./AccountFollowingTab";
import { AccountRadarTab } from "./AccountRadarTab";
import { AccountAccountTab } from "./AccountAccountTab";
import type { AccountSpacePanel, AccountSpaceTab } from "./account-space-query";

export default function AccountSpacePage({
  initialTab,
  initialPanel,
}: {
  initialTab: AccountSpaceTab;
  initialPanel: AccountSpacePanel;
}) {
  const { portalAuth } = useAppStore();
  const canManageScopeTargets = Boolean(portalAuth?.isPremium || portalAuth?.isAdmin);
  const subscriptionsQuery = useSubscriptionsQuery(Boolean(portalAuth));
  const monitorTargetsQuery = useMonitorTargetsQuery(Boolean(portalAuth && canManageScopeTargets));
  const noticesQuery = useWatchlistNoticesQuery(Boolean(portalAuth));

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,#f5f7fb_0%,#eef4ff_38%,#f8fbff_100%)] text-slate-900">
      <div className="mx-auto max-w-7xl px-4 pb-20 pt-8 md:px-6">
        <AccountSpaceHero />
        <AccountSpaceTabs initialTab={initialTab} />
        <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
          <main className="min-w-0">{/* active tab panel */}</main>
          <aside className="min-w-0">{/* sidebar */}</aside>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Replace the `/account` route with parsed query-state input**

```tsx
import AccountSpacePage from "@/components/account/AccountSpacePage";
import { parseAccountSpacePanel, parseAccountSpaceTab } from "@/components/account/account-space-query";

export default async function AccountPage({
  searchParams,
}: {
  searchParams: Promise<{ tab?: string | string[]; panel?: string | string[] }>;
}) {
  const params = await searchParams;
  return (
    <AccountSpacePage
      initialTab={parseAccountSpaceTab(params.tab)}
      initialPanel={parseAccountSpacePanel(params.panel)}
    />
  );
}
```

- [ ] **Step 4: Run a compile-focused check before building more UI**

Run: `cd web-ui && npm run build`

Expected: build either passes with the shell in place or fails only on components that have not been created yet. Fix only import or signature mistakes before moving on.

- [ ] **Step 5: Commit the shell**

```bash
git add web-ui/src/app/account/page.tsx web-ui/src/components/account/account-space-query.ts web-ui/src/components/account/AccountSpacePage.tsx
git commit -m "refactor: add account space page shell"
```

### Task 2: Build the Space Hero, Tabs, and Sidebar

**Files:**
- Create: `web-ui/src/components/account/AccountSpaceHero.tsx`
- Create: `web-ui/src/components/account/AccountSpaceTabs.tsx`
- Create: `web-ui/src/components/account/AccountSpaceSidebar.tsx`
- Modify: `web-ui/src/components/account/AccountSpacePage.tsx`

- [ ] **Step 1: Implement the cover and hero block**

```tsx
import { Crown, Sparkles } from "lucide-react";
import { motion } from "framer-motion";

export function AccountSpaceHero({
  displayName,
  username,
  roleLabel,
  signature,
  stats,
}: {
  displayName: string;
  username: string;
  roleLabel: string;
  signature: string;
  stats: Array<{ label: string; value: string }>;
}) {
  return (
    <section className="overflow-hidden rounded-[36px] border border-sky-100 bg-white shadow-[0_30px_90px_rgba(112,148,205,0.18)]">
      <motion.div
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        className="h-44 bg-[linear-gradient(135deg,#74d7ff_0%,#8fdcff_18%,#ffd0e5_62%,#ff8dc1_100%)]"
      />
      <div className="relative px-5 pb-6 md:px-8">
        <div className="-mt-10 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div className="flex items-end gap-4">
            <div className="flex h-24 w-24 items-center justify-center rounded-full border-[6px] border-white bg-[linear-gradient(135deg,#ffb3d4,#85d9ff)] text-3xl font-black text-white shadow-[0_18px_40px_rgba(83,114,176,0.22)]">
              {displayName.slice(0, 1).toUpperCase()}
            </div>
            <div className="pb-2">
              <div className="flex items-center gap-2">
                <h1 className="text-3xl font-black tracking-tight text-slate-900">{displayName}</h1>
                <span className="inline-flex items-center gap-1 rounded-full bg-pink-50 px-3 py-1 text-xs font-semibold text-pink-600">
                  <Crown size={12} />
                  {roleLabel}
                </span>
              </div>
              <div className="mt-1 text-sm text-slate-500">@{username}</div>
              <div className="mt-2 text-sm text-slate-600">{signature}</div>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3 md:min-w-[360px]">
            {stats.map((item) => (
              <div key={item.label} className="rounded-2xl border border-slate-100 bg-slate-50/80 px-4 py-3">
                <div className="text-xs uppercase tracking-[0.18em] text-slate-400">{item.label}</div>
                <div className="mt-2 text-2xl font-black text-slate-900">{item.value}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 2: Implement the tab rail with sliding active state**

```tsx
"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import type { AccountSpaceTab } from "./account-space-query";

const ITEMS: Array<{ id: AccountSpaceTab; label: string }> = [
  { id: "activity", label: "Activity" },
  { id: "following", label: "Following" },
  { id: "radar", label: "Radar" },
  { id: "account", label: "Account" },
];

export function AccountSpaceTabs({ activeTab }: { activeTab: AccountSpaceTab }) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  return (
    <nav className="mt-5 rounded-[24px] border border-white/70 bg-white/80 p-2 shadow-[0_14px_40px_rgba(120,147,193,0.12)] backdrop-blur">
      <div className="flex gap-2 overflow-x-auto">
        {ITEMS.map((item) => {
          const params = new URLSearchParams(searchParams.toString());
          params.set("tab", item.id);
          if (item.id !== "account") params.delete("panel");
          const active = item.id === activeTab;
          return (
            <Link key={item.id} href={`${pathname}?${params.toString()}`} className="relative rounded-full px-5 py-3 text-sm font-semibold">
              {active ? <motion.span layoutId="account-space-tab" className="absolute inset-0 rounded-full bg-[linear-gradient(90deg,#ff7db6,#67d0ff)]" /> : null}
              <span className={`relative z-10 ${active ? "text-white" : "text-slate-600"}`}>{item.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
```

- [ ] **Step 3: Implement the personal sidebar instead of an admin-looking aside**

```tsx
import Link from "next/link";
import { LockKeyhole, QrCode, Sparkles, LogOut } from "lucide-react";

export function AccountSpaceSidebar({
  membershipLabel,
  wechatBound,
  securityHint,
  onLogout,
}: {
  membershipLabel: string;
  wechatBound: boolean;
  securityHint: string;
  onLogout: () => void;
}) {
  return (
    <div className="space-y-4 xl:sticky xl:top-24">
      <section className="rounded-[28px] border border-white/80 bg-white/90 p-5 shadow-[0_18px_46px_rgba(124,147,190,0.14)]">
        <div className="text-xs uppercase tracking-[0.24em] text-sky-500">Membership</div>
        <div className="mt-2 text-xl font-bold text-slate-900">{membershipLabel}</div>
        <div className="mt-2 text-sm leading-6 text-slate-600">Keep billing, security, and binding controls on the right so the main column stays feed-first.</div>
      </section>
      <section className="rounded-[28px] border border-white/80 bg-white/90 p-5 shadow-[0_18px_46px_rgba(124,147,190,0.14)]">
        <div className="grid gap-3">
          <Link href="/account?tab=account&panel=billing" className="rounded-2xl bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-700">Membership and orders</Link>
          <Link href="/account?tab=account&panel=security" className="rounded-2xl bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-700">Account security</Link>
          <Link href="/account?tab=account" className="rounded-2xl bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-700">
            {wechatBound ? "WeChat bound" : "Bind WeChat"}
          </Link>
          <button type="button" onClick={onLogout} className="rounded-2xl bg-rose-50 px-4 py-3 text-left text-sm font-semibold text-rose-600">
            Log out
          </button>
        </div>
      </section>
    </div>
  );
}
```

- [ ] **Step 4: Wire the shell to render real hero, tabs, and sidebar props**

```tsx
const activeTab = currentTab;
const sidebar = (
  <AccountSpaceSidebar
    membershipLabel={spaceSummary.membershipLabel}
    wechatBound={spaceSummary.wechatBound}
    securityHint={spaceSummary.securityHint}
    onLogout={handleLogout}
  />
);
```

- [ ] **Step 5: Run lint and commit the layout**

Run: `cd web-ui && npm run lint`

Expected: `next lint` completes without new warnings or errors in the account components.

```bash
git add web-ui/src/components/account/AccountSpaceHero.tsx web-ui/src/components/account/AccountSpaceTabs.tsx web-ui/src/components/account/AccountSpaceSidebar.tsx web-ui/src/components/account/AccountSpacePage.tsx
git commit -m "feat: add account space hero and sidebar"
```

### Task 3: Build the Activity, Following, and Radar Tabs from Existing Data

**Files:**
- Create: `web-ui/src/components/account/account-space-data.ts`
- Create: `web-ui/src/components/account/AccountActivityTab.tsx`
- Create: `web-ui/src/components/account/AccountFollowingTab.tsx`
- Create: `web-ui/src/components/account/AccountRadarTab.tsx`
- Modify: `web-ui/src/components/account/AccountSpacePage.tsx`

- [ ] **Step 1: Add UI-data adapters so the space page does not work directly on raw API shapes**

```ts
import type {
  MonitorTargetItem,
  NotificationEventItem,
  SubscriptionItem,
  UserNotificationHistoryItem,
  UserAccountOverviewResponse,
} from "@/lib/api";

export type AccountSpaceSummary = {
  displayName: string;
  username: string;
  membershipLabel: string;
  signature: string;
  wechatBound: boolean;
  followCount: number;
  radarCount: number;
  recentActivityCount: number;
  securityHint: string;
};

export type AccountActivityItem = {
  id: string;
  kind: "history" | "notice" | "signal";
  title: string;
  subtitle: string;
  timestamp: string | null;
  href: string | null;
  tags: string[];
};

export function buildAccountSpaceSummary(args: {
  portalName: string;
  username: string;
  overview: UserAccountOverviewResponse | null;
  subscriptions: SubscriptionItem[];
  monitorTargets: MonitorTargetItem[];
  activityCount: number;
}): AccountSpaceSummary {
  const wechatBound = Boolean(
    args.overview?.identities.some((item) => item.identity_type === "wechat_miniapp" && item.status === "active"),
  );
  return {
    displayName: args.portalName,
    username: args.username,
    membershipLabel: args.overview?.is_premium ? "Premium" : args.overview?.is_admin ? "Admin" : "Standard",
    signature: args.overview?.is_premium ? "Your followed scopes, radar signals, and account activity gather here." : "Start by following the schools and sections you care about.",
    wechatBound,
    followCount: args.subscriptions.length + args.monitorTargets.length,
    radarCount: args.monitorTargets.length,
    recentActivityCount: args.activityCount,
    securityHint: wechatBound ? "WeChat is already linked; keep password and session security tidy." : "Recommend finishing WeChat binding and password setup.",
  };
}

export function buildAccountActivityItems(args: {
  history: UserNotificationHistoryItem[];
  pending: NotificationEventItem[];
  monitorTargets: MonitorTargetItem[];
}): AccountActivityItem[] {
  return [...args.history.map(/* map history */), ...args.pending.map(/* map pending */)]
    .sort((a, b) => String(b.timestamp || "").localeCompare(String(a.timestamp || "")));
}
```

- [ ] **Step 2: Implement the default `activity` feed**

```tsx
import { BellRing, Radar } from "lucide-react";
import type { AccountActivityItem } from "./account-space-data";

export function AccountActivityTab({
  items,
  emptyLoggedIn,
}: {
  items: AccountActivityItem[];
  emptyLoggedIn: boolean;
}) {
  if (emptyLoggedIn && items.length === 0) {
    return (
      <section className="rounded-[32px] border border-white/80 bg-white/90 p-8 shadow-[0_20px_60px_rgba(118,141,187,0.15)]">
        <div className="text-2xl font-bold text-slate-900">Your space has no activity yet</div>
        <div className="mt-3 text-sm leading-7 text-slate-600">Follow a school, add a radar scope, or finish WeChat binding and then come back. This is where the personal activity feed should grow.</div>
      </section>
    );
  }

  return (
    <section className="space-y-4">
      {items.map((item) => (
        <article key={item.id} className="rounded-[28px] border border-white/80 bg-white/90 p-5 shadow-[0_16px_44px_rgba(118,141,187,0.14)] transition-transform hover:-translate-y-0.5">
          <div className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-sky-500">
            {item.kind === "signal" ? <Radar size={14} /> : <BellRing size={14} />}
            {item.kind}
          </div>
          <div className="mt-3 text-lg font-bold text-slate-900">{item.title}</div>
          <div className="mt-2 text-sm leading-7 text-slate-600">{item.subtitle}</div>
        </article>
      ))}
    </section>
  );
}
```

- [ ] **Step 3: Implement `following` and `radar` as card walls, not admin tables**

```tsx
export function AccountFollowingTab({
  subscriptions,
  monitorTargets,
}: {
  subscriptions: SubscriptionItem[];
  monitorTargets: MonitorTargetItem[];
}) {
  return (
    <section className="grid gap-4 md:grid-cols-2">
      {subscriptions.map((item) => (
        <div key={item.id} className="rounded-[28px] border border-white/80 bg-white/90 p-5 shadow-[0_16px_44px_rgba(118,141,187,0.14)]">
          <div className="text-xs uppercase tracking-[0.2em] text-pink-500">{item.subscription_type}</div>
          <div className="mt-3 text-lg font-bold text-slate-900">{item.display_label || item.value}</div>
        </div>
      ))}
      {monitorTargets.map((item) => (
        <div key={item.id} className="rounded-[28px] border border-white/80 bg-white/90 p-5 shadow-[0_16px_44px_rgba(118,141,187,0.14)]">
          <div className="text-xs uppercase tracking-[0.2em] text-sky-500">{item.scope_type}</div>
          <div className="mt-3 text-lg font-bold text-slate-900">{item.display_label}</div>
        </div>
      ))}
    </section>
  );
}

export function AccountRadarTab({
  targets,
  overview,
}: {
  targets: MonitorTargetItem[];
  overview: MonitorTargetListResponse["recent_signal_overview"] | null;
}) {
  return (
    <section className="space-y-5">
      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-[28px] border border-white/80 bg-white/90 p-5 shadow-[0_16px_44px_rgba(118,141,187,0.14)]">
          <div className="text-xs uppercase tracking-[0.2em] text-slate-400">Tracked</div>
          <div className="mt-3 text-3xl font-black text-slate-900">{overview?.tracked_target_count || targets.length}</div>
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Connect tab rendering inside the page container**

```tsx
const activityItems = buildAccountActivityItems({
  history: notificationHistory,
  pending: noticesQuery.data || [],
  monitorTargets: monitorTargetsQuery.data?.items || [],
});

let content: ReactNode;
switch (currentTab) {
  case "following":
    content = <AccountFollowingTab subscriptions={subscriptionsQuery.data?.items || []} monitorTargets={monitorTargetsQuery.data?.items || []} />;
    break;
  case "radar":
    content = <AccountRadarTab targets={monitorTargetsQuery.data?.items || []} overview={monitorTargetsQuery.data?.recent_signal_overview || null} />;
    break;
  default:
    content = <AccountActivityTab items={activityItems} emptyLoggedIn={Boolean(portalAuth)} />;
}
```

- [ ] **Step 5: Run build and commit the three content tabs**

Run: `cd web-ui && npm run build`

Expected: production build succeeds and the new account components compile without route errors.

```bash
git add web-ui/src/components/account/account-space-data.ts web-ui/src/components/account/AccountActivityTab.tsx web-ui/src/components/account/AccountFollowingTab.tsx web-ui/src/components/account/AccountRadarTab.tsx web-ui/src/components/account/AccountSpacePage.tsx
git commit -m "feat: add account space activity following and radar tabs"
```

### Task 4: Implement the Account Tab, Redirect Legacy Routes, and Remove the Old Dashboard

**Files:**
- Create: `web-ui/src/components/account/AccountAccountTab.tsx`
- Modify: `web-ui/src/components/account/AccountSpacePage.tsx`
- Modify: `web-ui/src/app/account/security/page.tsx`
- Modify: `web-ui/src/app/account/billing/page.tsx`
- Modify: `web-ui/src/app/account/notifications/page.tsx`
- Delete: `web-ui/src/components/account/AccountDashboard.tsx`

- [ ] **Step 1: Move account operations into a dedicated `account` tab**

```tsx
import { useState } from "react";
import { ApiError, changeCurrentUserPassword, createCurrentUserPaymentOrder, createWechatBindCode, logoutUser } from "@/lib/api";

export function AccountAccountTab({
  accessToken,
  initialPanel,
  paymentOrders,
  wechatBound,
  onLoggedOut,
}: {
  accessToken: string;
  initialPanel: AccountSpacePanel;
  paymentOrders: UserPaymentOrderItem[];
  wechatBound: boolean;
  onLoggedOut: () => void;
}) {
  const [message, setMessage] = useState("");
  const [passwordForm, setPasswordForm] = useState({ oldPassword: "", newPassword: "" });

  return (
    <section className="space-y-5">
      <div className="rounded-[32px] border border-white/80 bg-white/90 p-6 shadow-[0_20px_60px_rgba(118,141,187,0.15)]">
        <div className="text-xs uppercase tracking-[0.2em] text-sky-500">Account Center</div>
        <div className="mt-3 text-2xl font-bold text-slate-900">Membership, security, and account actions live here</div>
      </div>
      {/* membership cards, WeChat bind card, password form, logout button */}
    </section>
  );
}
```

- [ ] **Step 2: Redirect legacy routes into canonical query-state URLs**

```tsx
import { redirect } from "next/navigation";

export default function AccountSecurityPage() {
  redirect("/account?tab=account&panel=security");
}
```

```tsx
import { redirect } from "next/navigation";

export default function AccountBillingPage() {
  redirect("/account?tab=account&panel=billing");
}
```

```tsx
import { redirect } from "next/navigation";

export default function AccountNotificationsPage() {
  redirect("/account?tab=activity&panel=notifications");
}
```

- [ ] **Step 3: Delete the old dashboard file once nothing imports it**

Run: `rg -n "AccountDashboard" web-ui/src`

Expected: only dead references remain. Then remove the file.

```bash
git rm web-ui/src/components/account/AccountDashboard.tsx
```

- [ ] **Step 4: Run lint, then do route smoke checks locally**

Run: `cd web-ui && npm run lint`

Expected: pass.

Then run: `cd web-ui && npm run dev`

Smoke checklist:
- open `/account`
- open `/account?tab=following`
- open `/account?tab=radar`
- open `/account?tab=account&panel=security`
- open `/account/security`
- open `/account/billing`
- open `/account/notifications`
- verify mobile width in browser responsive mode

- [ ] **Step 5: Commit the route and account-tab migration**

```bash
git add web-ui/src/components/account/AccountAccountTab.tsx web-ui/src/components/account/AccountSpacePage.tsx web-ui/src/app/account/security/page.tsx web-ui/src/app/account/billing/page.tsx web-ui/src/app/account/notifications/page.tsx
git commit -m "feat: migrate account routes to space page"
```

### Task 5: Final Verification and Docs Update

**Files:**
- Modify: `docs/current_status_2026-03-18.md`

- [ ] **Step 1: Add a short current-status follow-up note for the account IA change**

```md
## 2026-03-27 Account Space Page Follow-up

- `/account` is now the canonical personal space homepage.
- The default tab is activity-first rather than settings-first.
- `/account/security`, `/account/billing`, and `/account/notifications` redirect into `/account` query-state panels.
- Membership, WeChat binding, and security controls remain available under the account tab and sidebar.
```

- [ ] **Step 2: Run the final frontend verification set**

Run:

```bash
cd web-ui
npm run lint
npm run build
```

Expected:

- `next lint` passes
- `next build` passes

- [ ] **Step 3: Run one final manual smoke pass**

Manual checks:

- logged-out `/account` still renders a stable shell with login/register CTA
- logged-in `/account` lands on the activity tab
- empty-data account still shows guidance cards rather than blank columns
- non-premium account still sees radar and membership messaging
- sidebar actions still reach billing, security, and logout paths

- [ ] **Step 4: Commit docs and final polish**

```bash
git add docs/current_status_2026-03-18.md
git commit -m "docs: record account space page rollout"
```

- [ ] **Step 5: Push the branch**

```bash
git push origin main
```

## Self-Review

### Spec coverage

- Bilibili-inspired space-page layout: covered by Tasks 1 and 2.
- Default `activity` tab and four-tab IA: covered by Tasks 1 and 3.
- Reuse of existing data sources only: covered by Task 3.
- Secondary account actions moved out of the first screen: covered by Task 4.
- Canonical `/account` route plus legacy redirects: covered by Task 4.
- Responsive and state-based validation: covered by Tasks 4 and 5.

### Placeholder scan

- No `TODO`, `TBD`, or deferred strategy placeholders remain.
- Legacy-route compatibility strategy is explicit.
- Validation commands are concrete and match current repo scripts.

### Type consistency

- Canonical tab values are `activity`, `following`, `radar`, and `account` throughout the plan.
- Canonical panel values are `billing`, `security`, and `notifications` throughout the plan.
- The page shell, tab rail, and redirects all use the same query-state names: `tab` and `panel`.
