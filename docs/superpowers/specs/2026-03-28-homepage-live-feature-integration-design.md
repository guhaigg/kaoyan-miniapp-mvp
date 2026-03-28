# Homepage Live Feature Integration Design

## Goal

Keep the current homepage visual shell, but turn it into a real portal homepage backed by existing site features and live data:

- homepage stays a lightweight showcase, not a second workbench
- top navigation routes into the real feature pages
- homepage search redirects into the corresponding announcement or adjustment results page
- announcement and adjustment sections use real data
- each section supports `最新` and `我的关注`, defaulting to `最新`
- top micro charts switch from mock values to live data and get more expressive motion while staying borderless and lightweight

## Product Positioning

The homepage is not the place for full filtering, management, or detailed configuration. It should do three things well:

1. summarize what is happening now
2. surface what matters to the current user
3. hand off into the right full-feature page with minimal friction

This means the homepage should feel operational, but it must not duplicate `/search`, `/watchlist`, `/radar`, or `/account`.

## Existing Feature Mapping

The homepage should reuse the existing routes and capabilities already present in the web app:

- announcement search page: `/search?tab=announcements`
- adjustment search page: `/search?tab=adjustments`
- radar calculator page: `/radar`
- watchlist / monitoring workspace: `/watchlist`
- account space: `/account`

The homepage top nav can rename labels, but the actions should route into these existing pages instead of staying as dead links or local mock actions.

## Navigation Design

### Top nav labels and targets

The homepage local header keeps the current visual structure, but each nav item becomes a real route:

- `公告汇总` -> `/search?tab=announcements`
- `调剂汇总` -> `/search?tab=adjustments`
- `雷达测算` -> `/radar`

If admin entry remains visible for admins, it should point to `/admin`.

### Search box behavior

Homepage search should stop acting like an in-place filter and become a redirect launcher:

- when mode is `公告`, enter or mode-button submit navigates to `/search?tab=announcements&q=<keyword>`
- when mode is `调剂`, enter or mode-button submit navigates to `/search?tab=adjustments&q=<keyword>`
- clearing the input only clears the local input state; it does not need to refetch homepage sections

This keeps search intent aligned with the dedicated results pages.

### Right-side quick actions

- `SSE Live` becomes the visual entry for the user’s live reminder stream
- clicking it routes to `/watchlist`
- the status chip should show a real count or a real “online” summary derived from the user’s current pending notices

The account avatar / login area continues to use the existing auth behavior.

## Homepage Section Design

### Shared structure

The two main homepage sections remain:

- announcement column
- adjustment column

Each column gets lightweight section tabs:

- `最新`
- `我的关注`

Default tab is `最新` for both columns.

These are homepage-level view toggles, not deep filters. They should be visually light and remain within the current approved layout language.

## Announcement Column

### `最新`

`最新` announcements continue to use the existing live search path:

- `POST /api/v1/search/announcements`

Request shape remains simple:

- page 1
- page size 3
- no extra homepage-only backend requirements

The card content remains based on the existing mapped fields:

- notice type
- relative time
- school / department label
- title
- summary excerpt

### `我的关注`

`我的关注` announcements should use the user’s existing monitoring/reminder data, not a second public search.

Primary source order:

1. `GET /api/v1/notifications/pending`
2. `GET /api/v1/monitoring/targets`

Homepage behavior:

- show the latest reminder items tied to the user’s monitored schools / departments / sections
- if there are no pending items but there are active monitor targets, show a calm empty state such as “当前关注范围暂无新公告”
- if the user is not logged in, show a login prompt state
- if the user is logged in but has no watch targets, show a setup prompt linking to `/watchlist`

This keeps announcement personalization tied to the existing monitoring model instead of inventing a new home-only feed.

### Announcement column CTA

The right-side action in this column should become a real route:

- `高级检索` -> `/search?tab=announcements`

## Adjustment Column

### `最新`

`最新` adjustments continue to use the existing live search path:

- `POST /api/v1/search/adjustments`

Request shape remains:

- page 1
- page size 3

The mapped card should continue to show:

- school
- department / major context
- title
- tags
- vacancy count
- urgency emphasis when vacancy count is small

### `我的关注`

There is no dedicated adjustment “personal hit feed” API in the current web app equivalent to monitoring announcements, so the homepage should derive `我的关注` adjustments from the user’s existing saved focus set instead of inventing backend changes.

Primary source:

- `GET /api/v1/subscriptions`

Supported homepage focus sources:

- `radar` subscriptions first
- then `school`
- then `major`

Derived homepage rule:

- take the most recent usable focus item
- extract school / department / major hints from that saved item
- run one focused `POST /api/v1/search/adjustments` request using the strongest available filters
- label the section context clearly, for example “基于最近关注：东北大学 / 材料工程”

Fallback behavior:

- if the user is not logged in, show login prompt
- if the user has no usable adjustment focus item, show empty state with CTA to `/watchlist` or `/search?tab=adjustments`
- if the focused search returns no result, show a real empty state rather than silently falling back to global latest

This keeps the homepage honest: `我的关注` means “derived from your saved focus”, not “still the global feed”.

### Adjustment column CTA

The section-level action on the adjustment side should become a real route:

- `查看调剂汇总` -> `/search?tab=adjustments`

The small live status indicator may stay, but it should no longer imply a fake stream. It should describe the real watched state or recent activity.

## Top Micro-Data Strip

The top strip keeps its borderless layout and compact modules, but all three modules move to live data.

## Module 1: live trend line

### Data source

Use the same latest adjustment payload already fetched for the homepage.

### Meaning

Rename the concept away from a fake global crawler metric. The module should represent a real homepage-readable signal such as:

- `调剂更新节奏`
- or `近窗异动趋势`

### Calculation

Use the latest adjustment items’ `published_at` or `updated_at` values to build a short recent activity series.

Preferred shaping:

- sort latest adjustment results by effective timestamp
- build 8 to 12 buckets
- convert them into a cumulative or density-aware activity curve
- smooth the values enough that sparse real data still looks intentional

The number label should reflect a real summary, for example:

- latest adjustment count in the homepage sample
- or recent live adjustment hits in the current fetch window

### Motion

Keep the current small chart footprint, but enhance motion noticeably:

- path draw-in remains
- add a subtle sweep highlight moving across the line
- add a trailing glow near the tail
- add a more pronounced pulsing end-point beacon
- add tiny low-density floating particles near the live end of the curve

This should feel more vivid, but it must still read as a compact product chart, not a hero animation.

## Module 2: tier distribution bars

### Data source

Use the same latest adjustment payload as module 1.

### Meaning

Keep this as a quality / tier snapshot based on real adjustment items.

### Calculation

Derive buckets from `school_tier` and text fallbacks:

- `985`
- `211`
- `双一流`
- `其他`

Display:

- percentage for the targeted high-tier portion
- compact bars for the four groups

### Motion

Keep the current borderless mini-bar look, but enhance animation:

- stagger bar growth
- soft glow on hover
- light breathing / shimmer pass while idle
- subtle floating particles only for active hover or emphasized bars

## Module 3: `See Live`

### Data source

Use the real personalized reminder state:

- `GET /api/v1/notifications/pending`
- optionally combined with `GET /api/v1/monitoring/targets`

### Meaning

This module should stop pretending to be a generic SSE badge and become a personalized live reminder summary.

Examples:

- count of currently pending live reminders
- count of active watch targets plus latest hit
- latest watched-school reminder summary

Clicking it routes to `/watchlist`.

### Visual treatment

Keep it compact and border-light. It should stay in the existing small highlight-card slot, but its copy should reflect a real watch-state summary.

## Card Actions

### Announcement cards

Each announcement card should become actionable with real destinations:

- primary click opens the original source when `source_url` exists
- fallback can route to `/search?tab=announcements&q=<school-or-keyword>`

### Adjustment cards

Each adjustment card should support the existing saved-focus behavior:

- clicking the card opens the focused adjustment search page or original source context
- star action can reuse the existing subscription / radar save behavior where applicable

Homepage actions should reuse current mutations and routing instead of adding homepage-only state models.

## Logged-Out and Empty-State Behavior

### Logged out

- homepage defaults both columns to `最新`
- `我的关注` shows a login-required empty state
- `See Live` shows a login prompt treatment

### Logged in without focus data

- announcement `我的关注`: prompt to create monitor targets in `/watchlist`
- adjustment `我的关注`: prompt to create radar / school / major subscriptions

### Logged in with focus data but no current results

Show explicit and honest empty states:

- no new watched announcements
- no adjustment result matching current saved focus

Do not silently replace these with public latest results after the user has explicitly selected `我的关注`.

## Technical Boundaries

This work should stay concentrated in the homepage implementation and existing route wiring. It should not introduce a new backend contract unless implementation proves an unavoidable gap.

Expected primary touch points:

- homepage component
- existing homepage-local query hooks
- homepage routing logic
- existing subscription / monitoring / notification hooks

The dedicated feature pages remain the source of truth for full workflows.

## Error Handling

Homepage errors should degrade softly:

- public latest sections may show lightweight empty or retry states
- personalized sections should explain whether failure came from login state, missing focus data, or network failure
- chart modules should fall back to stable zero-data visuals rather than breaking layout

## Verification

Minimum completion evidence for implementation:

- homepage compiles with the existing routes and live data queries
- `cd web-ui && npm run lint`
- `cd web-ui && npm run build`
- manual browser validation on desktop:
  - top nav routes correctly
  - homepage search redirects correctly
  - `最新 / 我的关注` tabs switch correctly
  - announcement and adjustment cards show real data
  - `See Live` reflects real reminder state
  - top charts remain borderless and animate with the new enhanced style

## Out of Scope

These are intentionally not part of this homepage task:

- redesigning the overall homepage shell
- turning the homepage into a full workbench
- adding new backend endpoints solely for homepage polish, unless an implementation blocker makes it unavoidable
- changing the main dedicated `/search`, `/watchlist`, `/radar`, or `/account` information architecture
