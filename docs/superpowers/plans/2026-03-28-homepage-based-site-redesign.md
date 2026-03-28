# Homepage-Based Site Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the site around the current homepage shell, split announcements and adjustments into separate first-class pages, remove `/search` and `/query` from the visible product, and realign watchlist, account, radar, and admin to one coherent route model.

**Architecture:** Keep the existing Next.js static-export deployment and introduce one shared homepage-based shell across all pages. Replace the monolithic dual-tab search page with separate announcement and adjustment page components, add dedicated static detail pages, and only add backend work where the frontend currently lacks a usable detail contract.

**Tech Stack:** Next.js App Router with `output: "export"`, React 19, TypeScript, TanStack Query, Framer Motion, Zustand, FastAPI, pytest

---

## File Structure

**Create:**

- `web-ui/src/components/layout/site-navigation.ts`
  - single source of truth for top-level routes, labels, search visibility rules, and route builders
- `web-ui/src/app/announcements/page.tsx`
  - route entry for the announcement hub
- `web-ui/src/app/announcements/detail/page.tsx`
  - static detail route for announcement detail with `id` in query params
- `web-ui/src/app/adjustments/page.tsx`
  - route entry for the adjustment hub
- `web-ui/src/app/adjustments/detail/page.tsx`
  - static detail route for adjustment detail with `id` in query params
- `web-ui/src/components/announcements/AnnouncementHubPage.tsx`
  - announcement-specific search, filter, result-list, and empty-state page core
- `web-ui/src/components/announcements/AnnouncementDetailPage.tsx`
  - dedicated announcement detail view
- `web-ui/src/components/announcements/announcement-page-data.ts`
  - page-local helpers for announcement query parsing and item-to-view mapping
- `web-ui/src/components/adjustments/AdjustmentHubPage.tsx`
  - adjustment-specific opportunity page with light diagnostic summary
- `web-ui/src/components/adjustments/AdjustmentDetailPage.tsx`
  - dedicated adjustment detail view wrapper around the existing detail API
- `web-ui/src/components/adjustments/adjustment-page-data.ts`
  - page-local helpers for adjustment filters, preview gating, and summary cards

**Modify:**

- `web-ui/src/components/layout/Header.tsx`
  - replace old IA labels, route targets, and search behavior with shared route config
- `web-ui/src/components/layout/AppChrome.tsx`
  - remove the homepage shell exception and route all pages through one shell
- `web-ui/src/app/layout.tsx`
  - keep the same providers, but rely on route-aware shell behavior instead of a homepage bypass
- `web-ui/src/components/home/SignalDashboardHome.tsx`
  - remove local duplicate header assumptions and rewire homepage actions to new routes
- `web-ui/src/components/home/homepage-live-data.ts`
  - replace `/search` targets with the new route helpers
- `web-ui/src/components/home/BiliCategoryStrip.tsx`
  - rewire category shortcuts to `/announcements` and `/adjustments`
- `web-ui/src/components/shared/AuthEntryPage.tsx`
  - replace legacy `/search` post-auth routing and quick links
- `web-ui/src/components/search/RadarCalculator.tsx`
  - route all outward search actions to `/adjustments` and `/announcements`
- `web-ui/src/components/watchlist/WatchlistWorkspace.tsx`
  - convert to the homepage-based light shell and sharpen the pure-operations role
- `web-ui/src/components/account/AccountSpacePage.tsx`
  - reduce overlap with watchlist and emphasize account/membership/notification summary
- `web-ui/src/components/account/AccountSpaceTabs.tsx`
  - adjust tab emphasis to the narrowed account responsibility
- `web-ui/src/app/admin/page.tsx`
  - keep dense admin internals but move the outer frame into the homepage language
- `web-ui/src/api/search.ts`
  - add announcement-detail fetcher alongside the existing adjustment detail fetcher
- `web-ui/src/lib/api.ts`
  - add the frontend announcement-detail response type
- `backend/app/routers/search.py`
  - add a public announcement-detail endpoint
- `backend/app/schemas.py`
  - add the announcement-detail response schema
- `backend/tests/test_search.py`
  - cover the new announcement-detail contract
- `docs/current_status_2026-03-18.md`
  - reflect the new top-level route model and unified shell
- `docs/homepage_frozen_ui_logic_integration_2026-03-28.md`
  - record homepage action rewiring into the new route structure

**Delete:**

- `web-ui/src/app/search/page.tsx`
- `web-ui/src/app/query/page.tsx`

**Verification:**

- `cd web-ui && npm run lint`
- `cd web-ui && npm run build`
- `npm run test:backend`
- manual browser smoke for `/`, `/announcements`, `/announcements/detail?id=<content_id>`, `/adjustments`, `/adjustments/detail?id=<item_id>&kind=<content|opportunity>`, `/radar`, `/watchlist`, `/account`, `/admin`

**Important notes:**

- `web-ui` is still built with `output: "export"`, so runtime dynamic segments like `/announcements/[id]` are not practical under the current deployment.
- This plan therefore implements dedicated static detail pages:
  - `/announcements/detail?id=<content_id>`
  - `/adjustments/detail?id=<item_id>&kind=<content|opportunity>`
- If strict `/[id]` detail URLs become mandatory later, treat that as a separate hosting-model migration.
- `web-ui` still does not expose a frontend unit-test runner, so frontend verification relies on lint, build, and explicit manual smoke.

### Task 1: Unify the Shell and Navigation Contract

**Files:**
- Create: `web-ui/src/components/layout/site-navigation.ts`
- Modify: `web-ui/src/components/layout/Header.tsx`
- Modify: `web-ui/src/components/layout/AppChrome.tsx`
- Modify: `web-ui/src/app/layout.tsx`
- Modify: `web-ui/src/components/home/SignalDashboardHome.tsx`

- [ ] **Step 1: Create the shared route manifest and helper API**

Create `site-navigation.ts` so every page consumes one route model.

```ts
export type PrimaryRouteKey =
  | "home"
  | "announcements"
  | "adjustments"
  | "radar"
  | "watchlist"
  | "account"
  | "admin";

export type SearchMode = "announcements" | "adjustments";

export const PRIMARY_NAV_ITEMS = [
  { key: "home", href: "/", label: "首页" },
  { key: "announcements", href: "/announcements", label: "公告汇总" },
  { key: "adjustments", href: "/adjustments", label: "调剂汇总" },
  { key: "radar", href: "/radar", label: "雷达测算" },
  { key: "watchlist", href: "/watchlist", label: "关注库" },
  { key: "account", href: "/account", label: "我的空间" },
] as const;

const HIDE_GLOBAL_SEARCH_PATHS = new Set(["/announcements", "/adjustments"]);

export function shouldShowGlobalSearch(pathname: string) {
  return !HIDE_GLOBAL_SEARCH_PATHS.has(pathname);
}

export function buildSearchDestination(mode: SearchMode, keyword: string) {
  const params = new URLSearchParams();
  if (keyword.trim()) {
    params.set("keywords", keyword.trim());
  }
  return mode === "announcements"
    ? `/announcements?${params.toString()}`
    : `/adjustments?${params.toString()}`;
}

export function buildAnnouncementDetailHref(contentId: string) {
  const params = new URLSearchParams({ id: contentId });
  return `/announcements/detail?${params.toString()}`;
}

export function buildAdjustmentDetailHref(itemId: string, itemKind: "content" | "opportunity") {
  const params = new URLSearchParams({ id: itemId, kind: itemKind });
  return `/adjustments/detail?${params.toString()}`;
}
```

- [ ] **Step 2: Refactor the shared header to consume the route manifest**

Update `Header.tsx` to use the new labels and route helpers instead of local constants.

```ts
import {
  PRIMARY_NAV_ITEMS,
  buildSearchDestination,
  shouldShowGlobalSearch,
  type SearchMode,
} from "@/components/layout/site-navigation";
```

```tsx
const showGlobalSearch = shouldShowGlobalSearch(pathname);
```

```tsx
<nav className="hidden items-center gap-7 text-[14px] font-semibold tracking-[0.02em] text-slate-500 lg:flex">
  {PRIMARY_NAV_ITEMS.map((item) => {
    const active =
      pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
    return (
      <Link
        key={item.key}
        href={item.href}
        className={`transition-colors ${active ? "text-slate-900" : "hover:text-slate-900"}`}
      >
        {item.label}
      </Link>
    );
  })}
</nav>
```

```ts
function handleSearchSubmit(event: FormEvent<HTMLFormElement>) {
  event.preventDefault();
  const keyword = searchInput.trim();
  if (searchMode === "adjustments" && !portalAuth) {
    showToast("请先登录", "调剂搜索需要登录后使用", "info");
    openAuth("login");
    return;
  }
  router.push(buildSearchDestination(searchMode, keyword));
}
```

- [ ] **Step 3: Remove the homepage shell bypass**

Make `AppChrome.tsx` always render the shared shell, and move any homepage-specific spacing into the homepage page core instead of the shell gate.

```tsx
export default function AppChrome({ children }: { children: ReactNode }) {
  return (
    <>
      <Background />
      <Header />
      <main className="relative z-10 min-h-screen pb-20 pt-16 md:pt-[4.5rem]">{children}</main>
      <Modals />
      <Toast />
    </>
  );
}
```

- [ ] **Step 4: Remove the homepage-local header dependency**

Strip the local duplicated header block out of `SignalDashboardHome.tsx` and let the shared header own navigation and top search.

```tsx
return (
  <div className="relative z-10 pb-16 pt-6 md:pb-20">
    <section className="mx-auto flex w-full flex-col gap-8 px-6">
      <div className="min-h-[280px] rounded-[2rem] border border-slate-200/70 bg-white/80" />
      <div className="grid gap-8 xl:grid-cols-2">
        <div className="min-h-[420px] rounded-[2rem] border border-slate-200/70 bg-white/80" />
        <div className="min-h-[420px] rounded-[2rem] border border-slate-200/70 bg-white/80" />
      </div>
    </section>
  </div>
);
```

- [ ] **Step 5: Verify the shell task**

Run:

```bash
cd web-ui && npm run lint
cd web-ui && npm run build
```

Expected:

```text
No ESLint warnings or errors
Compiled successfully
Generating static pages
Exporting
```

- [ ] **Step 6: Commit the shell-unification task**

```bash
git add web-ui/src/components/layout/site-navigation.ts web-ui/src/components/layout/Header.tsx web-ui/src/components/layout/AppChrome.tsx web-ui/src/app/layout.tsx web-ui/src/components/home/SignalDashboardHome.tsx
git commit -m "refactor: unify site shell around homepage navigation"
```

### Task 2: Rewire All Entry Points and Retire `/search` and `/query`

**Files:**
- Modify: `web-ui/src/components/home/homepage-live-data.ts`
- Modify: `web-ui/src/components/home/BiliCategoryStrip.tsx`
- Modify: `web-ui/src/components/home/SignalDashboardHome.tsx`
- Modify: `web-ui/src/components/shared/AuthEntryPage.tsx`
- Modify: `web-ui/src/components/search/RadarCalculator.tsx`
- Delete: `web-ui/src/app/search/page.tsx`
- Delete: `web-ui/src/app/query/page.tsx`
- Create: `web-ui/src/app/announcements/page.tsx`
- Create: `web-ui/src/app/adjustments/page.tsx`

- [ ] **Step 1: Add the new route wrappers**

Create the new route entry points first so rewired links always have valid destinations.

```tsx
// web-ui/src/app/announcements/page.tsx
import AnnouncementHubPage from "@/components/announcements/AnnouncementHubPage";

export default function AnnouncementsPage() {
  return <AnnouncementHubPage />;
}
```

```tsx
// web-ui/src/app/adjustments/page.tsx
import AdjustmentHubPage from "@/components/adjustments/AdjustmentHubPage";

export default function AdjustmentsPage() {
  return <AdjustmentHubPage />;
}
```

- [ ] **Step 2: Replace all old `/search` route builders with the shared route helpers**

Update homepage and global route emitters.

```ts
import {
  buildAnnouncementDetailHref,
  buildAdjustmentDetailHref,
  buildSearchDestination,
} from "@/components/layout/site-navigation";
```

```ts
return buildSearchDestination("announcements", keyword);
```

```ts
return buildSearchDestination("adjustments", keyword);
```

- [ ] **Step 3: Replace auth and radar route targets**

Update `AuthEntryPage.tsx` and `RadarCalculator.tsx` so they stop sending users into `/search`.

```ts
router.push("/announcements");
```

```ts
const primaryHref = `/adjustments?${primaryParams.toString()}`;
const secondaryHref = `/announcements?${secondaryParams.toString()}`;
```

- [ ] **Step 4: Remove the old public route files**

Delete the legacy visible route entries after all call sites are rewired.

```text
Delete:
- web-ui/src/app/search/page.tsx
- web-ui/src/app/query/page.tsx
```

- [ ] **Step 5: Commit the route-rewiring task**

```bash
git add web-ui/src/app/announcements/page.tsx web-ui/src/app/adjustments/page.tsx web-ui/src/components/home/homepage-live-data.ts web-ui/src/components/home/BiliCategoryStrip.tsx web-ui/src/components/home/SignalDashboardHome.tsx web-ui/src/components/shared/AuthEntryPage.tsx web-ui/src/components/search/RadarCalculator.tsx
git rm web-ui/src/app/search/page.tsx web-ui/src/app/query/page.tsx
git commit -m "feat: replace legacy search routes with announcement and adjustment hubs"
```

### Task 3: Add the Announcement Detail Contract and Static Detail Page

**Files:**
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/routers/search.py`
- Modify: `backend/tests/test_search.py`
- Modify: `web-ui/src/api/search.ts`
- Modify: `web-ui/src/lib/api.ts`
- Create: `web-ui/src/app/announcements/detail/page.tsx`
- Create: `web-ui/src/components/announcements/AnnouncementDetailPage.tsx`

- [ ] **Step 1: Add the backend announcement-detail response schema**

Add a public detail response that exposes the body, metadata, and links for one announcement content row.

```py
class AnnouncementSearchDetailResponse(BaseModel):
    id: str
    title: str
    school_name: str | None = None
    department_name: str | None = None
    notice_kind: str | None = None
    channel_label: str | None = None
    channel_tier: Literal["core", "supplemental"] | None = None
    source_type: str
    source_url: str | None = None
    published_at: datetime | None = None
    updated_at: datetime
    summary: str | None = None
    body: str | None = None
    tags: list[str] = Field(default_factory=list)
    system_tags: list[str] = Field(default_factory=list)
    links: list[AdjustmentSearchLinkItem] = Field(default_factory=list)
    meta_json: dict[str, Any] = Field(default_factory=dict)
```

- [ ] **Step 2: Add the public announcement-detail router endpoint**

Expose a content-backed announcement detail endpoint in `search.py`.

```py
@router.get("/announcements/items/{content_id}", response_model=AnnouncementSearchDetailResponse)
def get_announcement_search_detail(
    content_id: str,
    db: Session = Depends(get_db),
    request: Request | None = None,
):
    row = db.query(Content).filter(Content.id == content_id, Content.category == "announcement").first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Announcement not found")

    extra = dict(row.extra or {})
    links = [
        AdjustmentSearchLinkItem(
            label="原始链接",
            url=row.source_url,
            link_type="source_url",
            source=row.source_type,
        )
    ] if row.source_url else []

    return AnnouncementSearchDetailResponse(
        id=row.id,
        title=row.title,
        school_name=extra.get("school_name"),
        department_name=extra.get("department_name"),
        notice_kind=extra.get("notice_kind"),
        channel_label=extra.get("channel_label"),
        channel_tier=extra.get("channel_tier"),
        source_type=row.source_type,
        source_url=row.source_url,
        published_at=row.published_at,
        updated_at=row.updated_at,
        summary=row.summary,
        body=row.body,
        tags=list(extra.get("tags") or []),
        system_tags=list(extra.get("system_tags") or []),
        links=links,
        meta_json=extra,
    )
```

- [ ] **Step 3: Add a focused backend test for the announcement-detail contract**

Extend `backend/tests/test_search.py`.

```py
def test_announcement_detail_returns_body_and_metadata(client):
    created = client.post(
        "/api/v1/content",
        json={
            "category": "announcement",
            "title": "浙江大学 2026 年硕士研究生招生简章",
            "body": "这里是完整正文",
            "summary": "这里是摘要",
            "school_name": "浙江大学",
            "source_type": "crawler",
            "source_url": "https://example.com/zju-announcement",
            "extra": {
                "school_name": "浙江大学",
                "department_name": "计算机科学与技术学院",
                "notice_kind": "招生简章",
                "channel_label": "硕士招生",
                "channel_tier": "core",
                "tags": ["招生简章"],
                "system_tags": ["硕士招生"],
            },
        },
        headers={"X-Admin-Token": "test-admin-token"},
    )
    assert created.status_code == 200

    item_id = created.json()["id"]
    detail = client.get(f"/api/v1/search/announcements/items/{item_id}")

    assert detail.status_code == 200
    payload = detail.json()
    assert payload["title"] == "浙江大学 2026 年硕士研究生招生简章"
    assert payload["body"] == "这里是完整正文"
    assert payload["school_name"] == "浙江大学"
    assert payload["department_name"] == "计算机科学与技术学院"
    assert payload["source_url"] == "https://example.com/zju-announcement"
    assert payload["system_tags"] == ["硕士招生"]
```

- [ ] **Step 4: Add the frontend detail API and static detail page**

Add the frontend wrapper and the page route.

```ts
export const fetchAnnouncementDetail = (contentId: string) =>
  request<AnnouncementSearchDetailResponse>({
    method: "GET",
    url: `/search/announcements/items/${contentId}`,
    timeout: 30_000,
  });
```

```tsx
// web-ui/src/app/announcements/detail/page.tsx
import AnnouncementDetailPage from "@/components/announcements/AnnouncementDetailPage";

export default function AnnouncementsDetailRoute() {
  return <AnnouncementDetailPage />;
}
```

- [ ] **Step 5: Verify the backend contract before moving on**

Run:

```bash
npm run test:backend
```

Expected:

```text
PASS backend/tests/test_search.py
```

- [ ] **Step 6: Commit the announcement-detail contract**

```bash
git add backend/app/schemas.py backend/app/routers/search.py backend/tests/test_search.py web-ui/src/api/search.ts web-ui/src/lib/api.ts web-ui/src/app/announcements/detail/page.tsx web-ui/src/components/announcements/AnnouncementDetailPage.tsx
git commit -m "feat: add announcement detail contract"
```

### Task 4: Build the Announcement Hub as a Dedicated Page

**Files:**
- Create: `web-ui/src/components/announcements/AnnouncementHubPage.tsx`
- Create: `web-ui/src/components/announcements/announcement-page-data.ts`
- Modify: `web-ui/src/app/announcements/page.tsx`
- Modify: `web-ui/src/components/shared/FeedCard.tsx`

- [ ] **Step 1: Extract announcement query parsing and view mapping helpers**

Keep announcement-only state and URL parsing out of the page component.

```ts
export type AnnouncementPageState = {
  keywords: string;
  schoolName: string;
  systemTags: string[];
  startDate: string;
  endDate: string;
  page: number;
};

export function parseAnnouncementPageState(searchParams: URLSearchParams): AnnouncementPageState {
  return {
    keywords: searchParams.get("keywords") || "",
    schoolName: searchParams.get("school_name") || "",
    systemTags: searchParams.getAll("system_tags"),
    startDate: searchParams.get("start_date") || "",
    endDate: searchParams.get("end_date") || "",
    page: Number(searchParams.get("page") || 1),
  };
}

export function buildAnnouncementSearchPayload(state: AnnouncementPageState) {
  return {
    keywords: state.keywords.trim() || undefined,
    school_name: state.schoolName.trim() || undefined,
    system_tags: state.systemTags,
    published_from: state.startDate ? `${state.startDate}T00:00:00` : undefined,
    published_to: state.endDate ? `${state.endDate}T23:59:59` : undefined,
    page: state.page,
    page_size: 12,
  };
}
```

- [ ] **Step 2: Build the dedicated announcement page core**

Create a page that drops tab-switching and focuses on advanced retrieval.

```tsx
export default function AnnouncementHubPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const pageState = useMemo(
    () => parseAnnouncementPageState(new URLSearchParams(searchParams.toString())),
    [searchParams],
  );
  const searchMutation = useAnnouncementSearchMutation();

  useEffect(() => {
    searchMutation.mutate(buildAnnouncementSearchPayload(pageState));
  }, [pageState]);

  return (
    <div className="mx-auto w-full max-w-[1600px] px-6 pb-16 pt-8">
      <section className="rounded-[2rem] border border-slate-200/70 bg-white/90 p-6 shadow-[0_24px_80px_rgba(15,23,42,0.08)] backdrop-blur-xl">
        <div className="flex items-start justify-between gap-6">
          <div>
            <div className="text-[11px] font-bold uppercase tracking-[0.22em] text-cyan-600">Announcement Index</div>
            <h1 className="mt-2 text-3xl font-black tracking-tight text-slate-900">公告汇总</h1>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-500">这是首页风格下的正式公告检索页，重点是筛选、收敛和进入独立详情页。</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-right">
            <div className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Results</div>
            <div className="mt-1 text-2xl font-black text-slate-900">{searchMutation.data?.total ?? 0}</div>
          </div>
        </div>
        <div className="mt-6 grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)]">
          <div className="space-y-4 rounded-[1.5rem] border border-slate-200 bg-slate-50/80 p-4" />
          <div className="space-y-4 rounded-[1.5rem] border border-slate-200 bg-white/80 p-4" />
        </div>
      </section>
    </div>
  );
}
```

- [ ] **Step 3: Route cards into the dedicated announcement detail page**

Make result actions explicit.

```tsx
<FeedCard
  item={item}
  onClick={() => router.push(buildAnnouncementDetailHref(item.id))}
  actionLabel="查看详情"
/>
```

- [ ] **Step 4: Verify the announcement page**

Run:

```bash
cd web-ui && npm run lint
cd web-ui && npm run build
```

Manual smoke:

- `/announcements` loads without the global header search box
- query params drive the page-owned controls
- search results go to `/announcements/detail?id=<id>`

- [ ] **Step 5: Commit the announcement hub**

```bash
git add web-ui/src/components/announcements/AnnouncementHubPage.tsx web-ui/src/components/announcements/announcement-page-data.ts web-ui/src/app/announcements/page.tsx web-ui/src/components/shared/FeedCard.tsx
git commit -m "feat: add dedicated announcement hub page"
```

### Task 5: Build the Adjustment Hub and Static Detail Page

**Files:**
- Create: `web-ui/src/components/adjustments/AdjustmentHubPage.tsx`
- Create: `web-ui/src/components/adjustments/AdjustmentDetailPage.tsx`
- Create: `web-ui/src/components/adjustments/adjustment-page-data.ts`
- Create: `web-ui/src/app/adjustments/detail/page.tsx`
- Modify: `web-ui/src/app/adjustments/page.tsx`

- [ ] **Step 1: Extract adjustment-page helpers and preview gating rules**

Create a focused helper module so the page core stays readable.

```ts
export type AdjustmentPageSummary = {
  total: number;
  urgentCount: number;
  watchMatchCount: number;
  latestPublishedLabel: string | null;
};

export function buildAdjustmentPageSummary(items: SearchItem[], watchlistCount: number): AdjustmentPageSummary {
  return {
    total: items.length,
    urgentCount: items.filter((item) => (item.adjustment_vacancy_count ?? 0) > 0 && (item.adjustment_vacancy_count ?? 0) <= 5).length,
    watchMatchCount: watchlistCount,
    latestPublishedLabel: items[0]?.published_at || items[0]?.updated_at || null,
  };
}

export function requiresAdjustmentLogin(item: SearchItem, isAnonymous: boolean) {
  return isAnonymous && item.access_limited !== false;
}
```

- [ ] **Step 2: Build the adjustment hub around opportunity flow plus light diagnosis**

Create the new page core with one clear job.

```tsx
export default function AdjustmentHubPage() {
  const { portalAuth } = useAppStore();
  const isAnonymous = !portalAuth;
  const searchMutation = useAdjustmentSearchMutation();

  return (
    <div className="mx-auto w-full max-w-[1600px] px-6 pb-16 pt-8">
      <section className="rounded-[2rem] border border-slate-200/70 bg-white/90 p-6 shadow-[0_24px_80px_rgba(15,23,42,0.08)] backdrop-blur-xl">
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.5fr)_360px]">
          <div className="space-y-4 rounded-[1.5rem] border border-slate-200 bg-white/80 p-4" />
          <aside className="space-y-4 rounded-[1.5rem] border border-slate-200 bg-slate-50/80 p-4" />
        </div>
      </section>
    </div>
  );
}
```

- [ ] **Step 3: Wrap the existing adjustment detail API in a dedicated page**

Create the static detail route and parse `id` and `kind` from query params.

```tsx
export default function AdjustmentDetailPage() {
  const searchParams = useSearchParams();
  const itemId = searchParams.get("id") || "";
  const itemKind = (searchParams.get("kind") as "content" | "opportunity") || "content";

  const detailQuery = useQuery({
    queryKey: ["adjustment-detail", itemId, itemKind],
    queryFn: () => fetchAdjustmentDetail(itemId, itemKind),
    enabled: Boolean(itemId),
  });

  return <AdjustmentDetailLayout detail={detailQuery.data} isLoading={detailQuery.isLoading} />;
}
```

- [ ] **Step 4: Route adjustment cards into the new detail page**

```tsx
onClick={() => router.push(buildAdjustmentDetailHref(item.id, item.item_kind))}
```

- [ ] **Step 5: Verify the adjustment page**

Run:

```bash
cd web-ui && npm run lint
cd web-ui && npm run build
```

Manual smoke:

- `/adjustments` hides the global header search
- anonymous users can see preview cards
- gated actions request login
- card navigation lands on `/adjustments/detail?id=<item_id>&kind=<content|opportunity>`
- radar CTA points to `/radar`

- [ ] **Step 6: Commit the adjustment hub**

```bash
git add web-ui/src/components/adjustments/AdjustmentHubPage.tsx web-ui/src/components/adjustments/AdjustmentDetailPage.tsx web-ui/src/components/adjustments/adjustment-page-data.ts web-ui/src/app/adjustments/page.tsx web-ui/src/app/adjustments/detail/page.tsx
git commit -m "feat: add dedicated adjustment hub and detail page"
```

### Task 6: Refocus Radar, Watchlist, and Account Around Their New Responsibilities

**Files:**
- Modify: `web-ui/src/components/search/RadarCalculator.tsx`
- Modify: `web-ui/src/components/watchlist/WatchlistWorkspace.tsx`
- Modify: `web-ui/src/components/account/AccountSpacePage.tsx`
- Modify: `web-ui/src/components/account/AccountSpaceTabs.tsx`
- Modify: `web-ui/src/components/account/AccountFollowingTab.tsx`
- Modify: `web-ui/src/components/account/AccountRadarTab.tsx`

- [ ] **Step 1: Remove residual search-era and overlap copy from radar**

Keep radar focused on diagnosis.

```tsx
<div className="mb-2 text-[11px] font-bold uppercase tracking-[0.22em] text-slate-400">
  {isCalculating ? "System Calculating" : "Radar Strategy"}
</div>
<p className="max-w-md text-sm leading-7 text-slate-500">
  这里负责深度分数诊断和策略建议，不承担实时机会流浏览。想看真实调剂机会，请进入调剂汇总页。
</p>
```

```ts
const primaryHref = `/adjustments?${primaryParams.toString()}`;
```

- [ ] **Step 2: Convert watchlist into a light operations workspace**

Keep the operational density, drop the dark control-center skin, and reinforce the workspace role.

```tsx
<div className="min-h-screen px-6 pb-20 pt-8 text-slate-900">
  <div className="mx-auto max-w-[1600px]">
    <section className="rounded-[2rem] border border-slate-200/70 bg-white/90 p-8 shadow-[0_24px_80px_rgba(15,23,42,0.08)] backdrop-blur-xl">
      <div className="text-[11px] uppercase tracking-[0.32em] text-cyan-600">Watchlist Workspace</div>
      <h1 className="mt-3 text-4xl font-black tracking-tight text-slate-900">关注库</h1>
      <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-500">这里是纯操作台：收藏、监控范围、提醒命中和范围管理都在这里完成。</p>
    </section>
  </div>
</div>
```

- [ ] **Step 3: Narrow account page responsibilities**

Remove follow-management emphasis from account tabs and center account/membership/notification summary.

```tsx
const tabs = [
  { key: "activity", label: "动态摘要" },
  { key: "notifications", label: "通知历史" },
  { key: "account", label: "账号与会员" },
];
```

```tsx
<p className="text-sm leading-7 text-slate-500">
  我的空间只保留账号、会员、通知和个人摘要；关注操作统一回到关注库。
</p>
```

- [ ] **Step 4: Commit the responsibility-alignment task**

```bash
git add web-ui/src/components/search/RadarCalculator.tsx web-ui/src/components/watchlist/WatchlistWorkspace.tsx web-ui/src/components/account/AccountSpacePage.tsx web-ui/src/components/account/AccountSpaceTabs.tsx web-ui/src/components/account/AccountFollowingTab.tsx web-ui/src/components/account/AccountRadarTab.tsx
git commit -m "refactor: realign radar watchlist and account responsibilities"
```

### Task 7: Bring Admin Into the Homepage Visual System Without Losing Density

**Files:**
- Modify: `web-ui/src/app/admin/page.tsx`
- Modify: `web-ui/src/components/layout/Header.tsx`

- [ ] **Step 1: Replace the dark admin outer shell with the homepage shell language**

Keep panel density, but remove the black standalone-product framing.

```tsx
<div className="mx-auto w-full max-w-[1680px] px-6 pb-16 pt-8 text-slate-900">
  <section className="rounded-[2rem] border border-slate-200/70 bg-white/92 p-6 shadow-[0_24px_80px_rgba(15,23,42,0.08)] backdrop-blur-xl">
    <div className="flex items-start justify-between gap-6">
      <div>
        <div className="text-[11px] font-bold uppercase tracking-[0.22em] text-cyan-600">Admin Workspace</div>
        <h1 className="mt-2 text-3xl font-black tracking-tight text-slate-900">管理后台</h1>
        <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-500">外层语言与首页统一，内部继续保留治理、审计、工作流和高密度运维面板。</p>
      </div>
    </div>
  </section>
</div>
```

- [ ] **Step 2: Normalize mixed old copy in the admin section labels**

Keep the meaning, clean up the language.

```ts
const ADMIN_NAV_ITEMS = [
  { id: "overview", label: "总览", description: "健康、覆盖和关键状态", icon: LayoutDashboard },
  { id: "intelligence", label: "调剂情报", description: "多源数据图表", icon: WandSparkles },
  { id: "announcement-governance", label: "公告治理", description: "workflow / rebuild / explain", icon: TriangleAlert },
  { id: "users", label: "用户管理", description: "角色、密码和权益", icon: UserCog },
  { id: "audits", label: "审计事件", description: "管理员操作轨迹", icon: ScrollText },
  { id: "payments", label: "会员订单", description: "订单账本和授权", icon: CreditCard },
  { id: "selectors", label: "栏目治理", description: "discovery 与规则维护", icon: Settings2 },
  { id: "content-files", label: "PDF 队列", description: "解析状态和重试", icon: FileSearch },
  { id: "runtime", label: "运行状态", description: "服务状态和控制面板", icon: Activity },
] as const;
```

- [ ] **Step 3: Keep admin behind the role-aware shared nav item**

Only expose the admin entry when the current user is admin.

```tsx
{portalAuth?.isAdmin ? (
  <Link href="/admin" className="text-sm font-bold tracking-[0.01em] text-slate-700 transition-colors hover:text-slate-900">
    管理后台
  </Link>
) : null}
```

- [ ] **Step 4: Commit the admin-shell task**

```bash
git add web-ui/src/app/admin/page.tsx web-ui/src/components/layout/Header.tsx
git commit -m "refactor: align admin shell with homepage system"
```

### Task 8: Update Docs and Run Full Verification

**Files:**
- Modify: `docs/current_status_2026-03-18.md`
- Modify: `docs/homepage_frozen_ui_logic_integration_2026-03-28.md`

- [ ] **Step 1: Update the current-status doc for the new route model**

Add concise notes that the public IA has shifted away from `/search` and `/query`.

```md
- Public route architecture is now centered on `/announcements`, `/adjustments`, `/radar`, `/watchlist`, `/account`, and `/admin`.
- `/search` and `/query` are no longer active user-facing routes.
- The homepage is now one page inside the shared site shell rather than a shell exception.
```

- [ ] **Step 2: Update the homepage integration doc**

Record the route rewiring from the homepage shell.

```md
- Homepage actions now route into `/announcements`, `/adjustments`, `/radar`, `/watchlist`, and `/account`.
- Homepage no longer renders its own duplicate header; the shared header owns global navigation.
```

- [ ] **Step 3: Run backend tests**

Run:

```bash
npm run test:backend
```

Expected:

```text
PASS backend/tests/test_search.py
```

- [ ] **Step 4: Run frontend lint and build**

Run:

```bash
cd web-ui && npm run lint
cd web-ui && npm run build
```

Expected:

```text
No ESLint warnings or errors
Compiled successfully
Generating static pages
Exporting
```

- [ ] **Step 5: Run manual browser smoke across the full route map**

Check:

- `/` uses the shared header and still matches the approved homepage shell
- `/announcements` hides the global header search and owns its filters
- `/adjustments` hides the global header search and shows preview-safe anonymous behavior
- `/radar` links outward to the new pages
- `/watchlist` is light and reads as a pure operations page
- `/account` no longer competes with watchlist
- `/admin` keeps dense internals but no longer looks like a separate dark product
- no visible user journey still points to `/search` or `/query`
- `/announcements/detail?id=<content_id>` and `/adjustments/detail?id=<item_id>&kind=<content|opportunity>` both load

- [ ] **Step 6: Final commit and push**

```bash
git add docs/current_status_2026-03-18.md docs/homepage_frozen_ui_logic_integration_2026-03-28.md
git commit -m "docs: update route architecture and shell status"
git push origin codex/feat-homepage-site-redesign-spec
```

## Plan Self-Review

### Spec coverage

- shared homepage-based shell: Task 1
- remove `/search` and `/query` from visible IA: Task 2
- dedicated announcement and adjustment pages: Tasks 4 and 5
- independent detail pages: Tasks 3 and 5
- watchlist/account responsibility split: Task 6
- radar as deep analysis only: Task 6
- admin outer shell aligned to homepage language: Task 7
- docs and verification: Task 8

### Placeholder scan

- no `TODO`, `TBD`, or deferred pseudo-steps remain
- every task names exact files and concrete verification commands
- the static-export detail-page constraint is explicit instead of implied

### Type consistency

- route helpers live in `site-navigation.ts` and are reused instead of redefined
- announcement detail has one named backend/frontend contract
- announcement and adjustment hubs are split into separate page-core components instead of continuing the old dual-tab page
