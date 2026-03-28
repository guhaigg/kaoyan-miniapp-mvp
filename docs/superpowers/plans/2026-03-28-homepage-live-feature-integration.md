# Homepage Live Feature Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the homepage into a real data-backed portal entry: real feature routing, `最新 / 我的关注` section tabs, live reminder summary, and upgraded real-data micro charts without changing the approved homepage shell.

**Architecture:** Keep the approved homepage shell intact and concentrate the work in the homepage component plus one small helper module for data derivation. Public latest data continues to come from the search APIs; personalized homepage views are derived from the existing subscriptions, monitoring targets, and pending notification APIs instead of introducing a new backend contract.

**Tech Stack:** Next.js App Router, React 19, TypeScript, TanStack Query, Framer Motion, existing portal API wrappers

---

## File Structure

**Create:**

- `web-ui/src/components/home/homepage-live-data.ts`
  - Pure homepage-specific data shaping:
    - latest announcement/adjustment item mapping
    - watched announcement/reminder item mapping
    - focused adjustment query derivation from subscriptions
    - live reminder summary derivation
    - trend series / tier distribution derivation for the top micro charts

**Modify:**

- `web-ui/src/components/home/SignalDashboardHome.tsx`
  - Header routing
  - homepage tab state and query wiring
  - chart props and motion upgrades
  - live `See Live` summary
  - real card actions and empty states
- `docs/homepage_frozen_ui_logic_integration_2026-03-28.md`
  - record homepage live routing, personalized tabs, and real-data chart behavior
- `docs/current_status_2026-03-18.md`
  - note that homepage is now a real live portal entry rather than a mock showcase

**Verification:**

- `cd web-ui && npm run lint`
- `cd web-ui && npm run build`
- manual browser review on `/`

**Important note:**

- `web-ui` does not currently expose a frontend unit-test runner in `package.json`
- this plan therefore uses:
  - pure helper extraction for safer reasoning
  - lint/build as hard gates
  - manual browser verification for behavior and motion

### Task 1: Extract Homepage Live Data Helpers

**Files:**
- Create: `web-ui/src/components/home/homepage-live-data.ts`
- Modify: `web-ui/src/components/home/SignalDashboardHome.tsx`

- [ ] **Step 1: Create homepage-specific types and pure mapping helpers**

Add a focused helper module so the homepage component stops mixing rendering with live-data derivation.

```ts
import type {
  NotificationEventItem,
  MonitorTargetItem,
  SearchItem,
  SubscriptionItem,
} from "@/lib/api";

export type HomeSectionView = "latest" | "watching";

export type AnnouncementFeedItem = {
  id: string;
  type: string;
  title: string;
  content: string;
  school: string;
  time: string;
  isNew: boolean;
  href: string | null;
  sourceUrl: string | null;
};

export type AdjustmentFeedItem = {
  id: string;
  school: string;
  title: string;
  tags: string[];
  major: string;
  count: number;
  urgent: boolean;
  href: string | null;
  sourceUrl: string | null;
};

export type HomeLiveSummary = {
  pendingCount: number;
  activeTargetCount: number;
  latestTitle: string | null;
  latestSchool: string | null;
};

export type TrendPoint = {
  label: string;
  value: number;
};

export type TierBreakdownItem = {
  label: "985" | "211" | "双一流" | "其他";
  count: number;
};
```

- [ ] **Step 2: Add reusable pure functions for homepage data derivation**

Implement the homepage-only derivation utilities in the helper file.

```ts
export function mapAnnouncementSearchItem(item: SearchItem): AnnouncementFeedItem {
  return {
    id: item.id,
    type: (item.notice_kind || item.channel_label || item.source_type || "公告").slice(0, 8),
    title: item.title,
    content: item.summary || item.school_intelligence?.signal_detail || "点击查看完整公告内容...",
    school: item.school_name || item.department_name || "目标院校",
    time: formatRelativeTime(item.published_at || item.updated_at),
    isNew: isFresh(item.published_at || item.updated_at),
    href: buildAnnouncementSearchHref(item),
    sourceUrl: item.source_url,
  };
}

export function mapAdjustmentSearchItem(item: SearchItem): AdjustmentFeedItem {
  return {
    id: item.id,
    school: item.school_name || "目标院校",
    title: item.title,
    tags: buildAdjustmentTags(item),
    major: item.major || item.department_name || item.channel_label || "调剂信息",
    count: item.adjustment_vacancy_count ?? item.historical_adjustment?.sample_count ?? 0,
    urgent: (item.adjustment_vacancy_count ?? item.historical_adjustment?.sample_count ?? 0) > 0 &&
      (item.adjustment_vacancy_count ?? item.historical_adjustment?.sample_count ?? 0) <= 5,
    href: buildAdjustmentSearchHref(item),
    sourceUrl: item.source_url,
  };
}

export function mapPendingAnnouncementNotice(item: NotificationEventItem): AnnouncementFeedItem {
  return {
    id: item.id,
    type: item.payload.category === "adjustment" ? "调剂提醒" : "关注公告",
    title: item.payload.title || item.payload.summary || "新的关注公告",
    content: item.payload.summary || item.payload.body || "点击查看关注范围内的最新公告提醒...",
    school: item.payload.school_name || item.payload.department_name || "我的关注",
    time: formatRelativeTime(item.created_at),
    isNew: true,
    href: item.payload.school_name ? `/search?tab=announcements&q=${encodeURIComponent(item.payload.school_name)}` : "/watchlist",
    sourceUrl: item.payload.source_url || null,
  };
}

export function buildFocusedAdjustmentPayload(subscriptions: SubscriptionItem[]) {
  const focus = subscriptions.find((item) => item.subscription_type === "radar" && item.status === "active")
    || subscriptions.find((item) => item.subscription_type === "school" && item.status === "active")
    || subscriptions.find((item) => item.subscription_type === "major" && item.status === "active");

  if (!focus) return null;

  return {
    focusLabel: focus.display_label || focus.value,
    payload: {
      school_name: focus.target_university || undefined,
      major: focus.target_major_name || focus.target_major_code || undefined,
      keywords: focus.subscription_type === "major" ? focus.value : undefined,
      page: 1,
      page_size: 3,
    },
  };
}

export function buildTrendSeries(items: SearchItem[]): TrendPoint[] {
  // derive 8-12 compact buckets from published_at / updated_at and smooth them
}

export function buildTierBreakdown(items: SearchItem[]): TierBreakdownItem[] {
  // classify into 985 / 211 / 双一流 / 其他
}

export function buildHomeLiveSummary(
  pending: NotificationEventItem[],
  targets: MonitorTargetItem[],
): HomeLiveSummary {
  return {
    pendingCount: pending.length,
    activeTargetCount: targets.filter((item) => item.status === "active").length,
    latestTitle: pending[0]?.payload.title || pending[0]?.payload.summary || null,
    latestSchool: pending[0]?.payload.school_name || pending[0]?.payload.department_name || null,
  };
}
```

- [ ] **Step 3: Move duplicated homepage mapping logic out of the component**

Replace the inline item mappers in `SignalDashboardHome.tsx` with imports from the new helper file.

```ts
import {
  buildFocusedAdjustmentPayload,
  buildHomeLiveSummary,
  buildTierBreakdown,
  buildTrendSeries,
  mapAnnouncementSearchItem,
  mapAdjustmentSearchItem,
  mapPendingAnnouncementNotice,
  type AnnouncementFeedItem,
  type AdjustmentFeedItem,
  type HomeSectionView,
} from "@/components/home/homepage-live-data";
```

- [ ] **Step 4: Commit the helper extraction**

```bash
git add web-ui/src/components/home/homepage-live-data.ts web-ui/src/components/home/SignalDashboardHome.tsx
git commit -m "refactor: extract homepage live data helpers"
```

### Task 2: Rewire Homepage Header Into Real Navigation

**Files:**
- Modify: `web-ui/src/components/home/SignalDashboardHome.tsx`

- [ ] **Step 1: Add App Router navigation to the homepage header**

Import the App Router hooks and add route helpers in the homepage header.

```ts
import Link from "next/link";
import { useRouter } from "next/navigation";

const Header = () => {
  const router = useRouter();

  function navigateToSearch(mode: "公告" | "调剂", keyword: string) {
    const params = new URLSearchParams();
    params.set("tab", mode === "公告" ? "announcements" : "adjustments");
    if (keyword.trim()) {
      params.set("q", keyword.trim());
    }
    router.push(`/search?${params.toString()}`);
  }
}
```

- [ ] **Step 2: Replace dead nav anchors with real feature routes**

Update the homepage local nav so each item points to the existing real page.

```tsx
<nav className="hidden lg:flex items-center gap-6 text-sm font-medium text-slate-500">
  <Link href="/search?tab=announcements" className="text-slate-900 transition-colors">公告汇总</Link>
  <Link href="/search?tab=adjustments" className="hover:text-slate-900 transition-colors">调剂汇总</Link>
  <Link href="/radar" className="hover:text-slate-900 transition-colors flex items-center gap-1">
    雷达测算 <span className="bg-orange-100 text-orange-600 text-[9px] px-1.5 py-0.5 rounded uppercase font-bold tracking-wider">Beta</span>
  </Link>
</nav>
```

- [ ] **Step 3: Turn homepage search into a redirect launcher instead of an in-place filter**

Update the local search actions so the homepage no longer tries to become its own search results page.

```ts
const executeSearch = () => {
  navigateToSearch(searchMode, localKw);
};
```

```tsx
onKeyDown={(event) => {
  if (event.key === "Enter") {
    executeSearch();
  }
}}
```

```tsx
onClick={() => {
  setSearchMode(mode);
  navigateToSearch(mode, localKw);
}}
```

- [ ] **Step 4: Route the right-side quick actions to real pages**

Replace the fake profile menu links with real pages while keeping the homepage shell.

```tsx
<Link href="/watchlist" className="flex items-center gap-2 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50 hover:text-cyan-600 rounded-lg transition-colors">
  <Star size={16} /> 雷达工作台
</Link>
<Link href="/account" className="flex items-center gap-2 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50 hover:text-cyan-600 rounded-lg transition-colors">
  <User size={16} /> 账号中心
</Link>
```

- [ ] **Step 5: Commit the header routing work**

```bash
git add web-ui/src/components/home/SignalDashboardHome.tsx
git commit -m "feat: wire homepage header to live routes"
```

### Task 3: Add `最新 / 我的关注` Views With Real Data Sources

**Files:**
- Modify: `web-ui/src/components/home/SignalDashboardHome.tsx`
- Create: `web-ui/src/components/home/homepage-live-data.ts`

- [ ] **Step 1: Add homepage section-view state and import the existing user-context hooks**

Use the existing watchlist-related query hooks rather than inventing new API wrappers.

```ts
import { useMonitorTargetsQuery } from "@/hooks/useMonitoringTargets";
import { useWatchlistNoticesQuery } from "@/hooks/useNotifications";
import { useSubscriptionsQuery } from "@/hooks/useSubscriptions";

const [announcementView, setAnnouncementView] = useState<HomeSectionView>("latest");
const [adjustmentView, setAdjustmentView] = useState<HomeSectionView>("latest");

const pendingNoticesQuery = useWatchlistNoticesQuery(Boolean(portalAuth));
const monitorTargetsQuery = useMonitorTargetsQuery(Boolean(portalAuth && (portalAuth.isPremium || portalAuth.isAdmin)));
const subscriptionsQuery = useSubscriptionsQuery(Boolean(portalAuth));
```

- [ ] **Step 2: Rename the public homepage hooks to reflect their actual role**

Keep the public latest requests, but stop using them as a fake local search mode.

```ts
const useLatestAnnouncements = () =>
  useQuery({
    queryKey: ["home", "latest-announcements"],
    queryFn: async () => {
      const response = await fetchAnnouncementResults({ page: 1, page_size: 3 });
      return response.items.map((item) => mapAnnouncementSearchItem(item));
    },
  });

const useLatestAdjustments = () =>
  useQuery({
    queryKey: ["home", "latest-adjustments"],
    queryFn: async () => {
      const response = await fetchAdjustmentResults({ page: 1, page_size: 3 });
      return response.items.map((item) => item);
    },
  });
```

- [ ] **Step 3: Derive watched announcement cards from pending reminders**

Use pending notices for `我的关注` on the announcement side.

```ts
const watchedAnnouncements = (pendingNoticesQuery.data || [])
  .filter((item) => item.payload.category !== "adjustment")
  .slice(0, 3)
  .map((item) => mapPendingAnnouncementNotice(item));

const announcementCards =
  announcementView === "latest"
    ? latestAnnouncementsQuery.data || []
    : watchedAnnouncements;
```

- [ ] **Step 4: Derive watched adjustment cards from saved focus and one focused search**

Build one homepage-focused adjustment request from subscriptions and execute it only when there is a usable focus item.

```ts
const focusedAdjustment = buildFocusedAdjustmentPayload(subscriptionsQuery.data?.items || []);

const watchedAdjustmentsQuery = useQuery({
  queryKey: ["home", "watching-adjustments", focusedAdjustment?.focusLabel],
  queryFn: async () => {
    if (!focusedAdjustment) return [];
    const response = await fetchAdjustmentResults(focusedAdjustment.payload);
    return response.items.map((item) => mapAdjustmentSearchItem(item));
  },
  enabled: Boolean(portalAuth && focusedAdjustment),
});

const adjustmentCards =
  adjustmentView === "latest"
    ? (latestAdjustmentsQuery.data || []).map((item) => mapAdjustmentSearchItem(item))
    : watchedAdjustmentsQuery.data || [];
```

- [ ] **Step 5: Add lightweight section tabs and honest empty states**

Keep the current section shell, but introduce the `最新 / 我的关注` switch with correct login and setup prompts.

```tsx
<div className="flex items-center gap-2">
  {(["latest", "watching"] as const).map((view) => (
    <button
      key={view}
      type="button"
      onClick={() => setAnnouncementView(view)}
      className={`px-3 py-1 text-[11px] font-bold rounded-md transition-all ${
        announcementView === view ? "bg-slate-900 text-white shadow-sm" : "text-slate-400 hover:text-slate-700"
      }`}
    >
      {view === "latest" ? "最新" : "我的关注"}
    </button>
  ))}
</div>
```

```tsx
{!portalAuth && announcementView === "watching" ? (
  <HomepageEmptyState title="登录后查看我的关注" ctaHref="/login" ctaLabel="立即登录" />
) : portalAuth && announcementView === "watching" && !(monitorTargetsQuery.data?.items || []).length ? (
  <HomepageEmptyState title="还没有关注范围" ctaHref="/watchlist" ctaLabel="去设置关注" />
) : null}
```

- [ ] **Step 6: Commit the section-tab and live data wiring**

```bash
git add web-ui/src/components/home/homepage-live-data.ts web-ui/src/components/home/SignalDashboardHome.tsx
git commit -m "feat: add homepage latest and watching feeds"
```

### Task 4: Replace Mock Micro Charts With Real Data and Richer Motion

**Files:**
- Create: `web-ui/src/components/home/homepage-live-data.ts`
- Modify: `web-ui/src/components/home/SignalDashboardHome.tsx`

- [ ] **Step 1: Convert the charts from hardcoded arrays to prop-driven components**

Update the chart components so the homepage can inject live series and tier data.

```ts
type QuotaTrendChartProps = {
  data: TrendPoint[];
};

const QuotaTrendChart = ({ data }: QuotaTrendChartProps) => {
  const values = data.map((item) => item.value);
  const labels = data.map((item) => item.label);
  const safeValues = values.length ? values : [0, 0, 0, 0];
  // keep the existing SVG footprint, but derive points from props
};

type TierDistributionChartProps = {
  tiers: TierBreakdownItem[];
};
```

- [ ] **Step 2: Build real chart inputs from the latest adjustment payload**

Use the un-mapped latest adjustment search items for top-strip calculations.

```ts
const latestAdjustmentSearchItems = latestAdjustmentsQuery.data || [];
const trendSeries = buildTrendSeries(latestAdjustmentSearchItems);
const tierBreakdown = buildTierBreakdown(latestAdjustmentSearchItems);
const highTierCount = tierBreakdown
  .filter((item) => item.label === "985" || item.label === "211" || item.label === "双一流")
  .reduce((sum, item) => sum + item.count, 0);
const qualityTierRate = latestAdjustmentSearchItems.length
  ? Math.round((highTierCount / latestAdjustmentSearchItems.length) * 100)
  : 0;
```

- [ ] **Step 3: Upgrade the line-chart motion without changing the borderless shell**

Keep the compact chart look, but add the more expressive motion requested in the spec:

```tsx
<motion.path
  d={`M ${points}`}
  fill="none"
  stroke="#06b6d4"
  strokeWidth="2"
  strokeLinecap="round"
  strokeLinejoin="round"
  initial={{ pathLength: 0, opacity: 0.35 }}
  animate={{ pathLength: 1, opacity: 1 }}
  transition={{ duration: 1.6, ease: "easeInOut" }}
/>
<motion.circle
  cx={endX}
  cy={endY}
  r="3.5"
  fill="#ffffff"
  stroke="#06b6d4"
  strokeWidth="2"
  animate={{ scale: [1, 1.22, 1], opacity: [0.85, 1, 0.9] }}
  transition={{ duration: 1.8, repeat: Infinity, ease: "easeInOut" }}
/>
<motion.rect
  x="-40"
  y="0"
  width="40"
  height={height}
  fill="url(#sweepGradient)"
  animate={{ x: [0, width + 40] }}
  transition={{ duration: 2.4, repeat: Infinity, ease: "linear" }}
/>
```

- [ ] **Step 4: Upgrade the bar-chart motion and wire the `See Live` summary**

Use the real reminder/monitor state for the third module and enrich the tier bars with stagger, glow, and shimmer.

```ts
const liveSummary = buildHomeLiveSummary(
  pendingNoticesQuery.data || [],
  monitorTargetsQuery.data?.items || [],
);
```

```tsx
<div
  className="hidden flex-col items-start gap-1.5 rounded-xl border border-orange-200/50 bg-orange-50/60 px-5 py-3 shadow-sm backdrop-blur-sm transition-colors group cursor-pointer hover:bg-orange-100/60 xl:flex xl:min-w-[220px] xl:flex-none"
  onClick={() => router.push("/watchlist")}
>
  <span className="text-[10px] font-bold text-orange-600 uppercase tracking-widest">SEE LIVE</span>
  <div className="flex items-end gap-2 mt-0.5">
    <span className="text-xl font-bold font-mono text-orange-500 leading-none">{liveSummary.pendingCount}</span>
    <span className="text-[10px] text-slate-500 mb-0.5 group-hover:text-orange-600 transition-colors">
      {liveSummary.latestSchool || "关注范围最新提醒"}
    </span>
  </div>
</div>
```

- [ ] **Step 5: Commit the real chart and live-summary work**

```bash
git add web-ui/src/components/home/homepage-live-data.ts web-ui/src/components/home/SignalDashboardHome.tsx
git commit -m "feat: replace homepage mock charts with live data"
```

### Task 5: Wire Real Card Actions, Update Docs, and Verify

**Files:**
- Modify: `web-ui/src/components/home/SignalDashboardHome.tsx`
- Modify: `docs/homepage_frozen_ui_logic_integration_2026-03-28.md`
- Modify: `docs/current_status_2026-03-18.md`

- [ ] **Step 1: Replace homepage CTA buttons and card clicks with real routes**

Turn the current toast placeholders into real page handoffs.

```tsx
<button
  onClick={() => router.push("/search?tab=announcements")}
  className="text-xs font-bold text-cyan-600 hover:text-cyan-700 transition-colors flex items-center gap-1"
>
  高级检索 <ChevronRight size={12} />
</button>
```

```tsx
<button
  onClick={() => router.push("/search?tab=adjustments")}
  className="text-xs font-bold text-orange-500 hover:text-orange-600 transition-colors flex items-center gap-1"
>
  查看调剂汇总 <ChevronRight size={12} />
</button>
```

```tsx
onClick={() => {
  if (item.sourceUrl) {
    window.open(item.sourceUrl, "_blank", "noopener,noreferrer");
    return;
  }
  if (item.href) {
    router.push(item.href);
  }
}}
```

- [ ] **Step 2: Update the homepage docs to record the new live behavior**

Append concise notes to both homepage docs.

```md
- Homepage local navigation now routes into the real announcement search, adjustment search, radar, watchlist, and account pages instead of using placeholder actions.
- Homepage columns now support `最新 / 我的关注`; personalized content is derived from pending notices, monitor targets, and saved subscriptions.
- Top micro charts now use live homepage data instead of mock values and keep the approved borderless visual shell with upgraded motion.
```

- [ ] **Step 3: Run lint**

Run:

```bash
cd web-ui && npm run lint
```

Expected:

```text
✔ No ESLint warnings or errors
```

- [ ] **Step 4: Run build**

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

- [ ] **Step 5: Manually review the homepage in a browser**

Check:

- top nav routes to real pages
- search redirects to the right results page based on `公告 / 调剂`
- `高级检索` goes to the announcement search page
- `See Live` routes to `/watchlist`
- both columns switch between `最新` and `我的关注`
- watched empty states are honest for logged-out and unconfigured users
- top line chart uses real-derived data and visibly richer motion
- top bar chart uses real-derived tier breakdown and enhanced motion
- homepage still keeps the approved borderless shell

- [ ] **Step 6: Final commit and push**

```bash
git add web-ui/src/components/home/homepage-live-data.ts web-ui/src/components/home/SignalDashboardHome.tsx docs/homepage_frozen_ui_logic_integration_2026-03-28.md docs/current_status_2026-03-18.md
git commit -m "feat: connect homepage to live portal features"
git push origin main
```

## Plan Self-Review

### Spec coverage

- real feature routing: Task 2
- search redirect behavior: Task 2
- `最新 / 我的关注`: Task 3
- `See Live` live reminder summary: Task 4
- real cards and CTAs: Task 5
- real charts and richer motion: Task 4
- docs and verification: Task 5

### Placeholder scan

- no `TODO`, `TBD`, or deferred pseudo-steps were left in the task list

### Type consistency

- homepage live types live in `homepage-live-data.ts`
- the main component consumes those types rather than redefining conflicting local variants
