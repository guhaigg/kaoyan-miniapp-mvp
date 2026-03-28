# 2026-03-28 Homepage-Based Site Redesign Design

## 1. Goal

Rebuild the site around the current homepage design language and turn the public product into a cleaner, route-driven experience.

This redesign is not a mockup refresh. It is a product-structure cleanup with three explicit outcomes:

- all user-visible pages and `/admin` share one homepage-based outer shell
- announcements and adjustments become separate first-class product pages
- old search-era information architecture is removed from the visible product

## 2. Decisions Locked In

### 2.1 Route model

The public-facing primary routes become:

- `/`
- `/announcements`
- `/adjustments`
- `/radar`
- `/watchlist`
- `/account`
- `/admin`
- `/login`
- `/register`

The following routes are removed from the visible product architecture:

- `/search`
- `/query`

They are not treated as active product pages anymore.

The application should not render normal public pages at these paths after the redesign lands.

### 2.2 Navigation model

The global navigation is standardized on the current homepage navigation style.

Primary navigation labels:

- `首页`
- `公告汇总`
- `调剂汇总`
- `雷达测算`
- `关注库`
- `我的空间`
- `管理后台` only when the current user has admin access

### 2.3 Search bar rule

The shared top navigation search bar follows strict route rules:

- visible on homepage
- visible on normal non-search pages in the shortened width variant
- hidden on `/announcements`
- hidden on `/adjustments`

Reason: those two pages own the main search experience and should not compete with a second search control in the global header.

### 2.4 Responsibility split

- `/announcements` is the formal announcement search and filtering page
- `/adjustments` is the real opportunity page with light diagnosis summary
- `/radar` is the deep score-diagnosis and strategy page
- `/watchlist` is a pure operations workspace
- `/account` is for account, membership, notifications, and personal summary

### 2.5 Detail view model

List results do not expand inline.

Dedicated detail routes are introduced:

- `/announcements/[id]`
- `/adjustments/[id]`

All list surfaces navigate into these standalone detail pages.

## 3. Design Principle

The homepage becomes the visual baseline for the whole site, but not every page copies the homepage layout.

The system uses:

- one shared visual shell
- one shared navigation system
- one shared spacing and width language
- separate page cores based on each page's actual task

This is intentionally not a "single template everywhere" redesign. Pages remain structurally distinct when their jobs are different.

## 4. Shared Shell

### 4.1 Outer shell

All routes, including `/admin`, render inside one shared application shell.

The shell is responsible for:

- global navigation
- background language
- width and padding system
- auth entry and user state entry point
- notification affordances
- route-aware search visibility

The homepage is no longer allowed to sit outside the shared shell.

### 4.2 Visual language

The baseline language is the current homepage language:

- light surfaces
- soft atmospheric background
- restrained borders
- controlled motion
- strong type hierarchy
- product-like, not dashboard-black, not cyberpunk

This language applies to both public pages and admin outer framing.

### 4.3 Density rule

A page may be denser than the homepage without changing the visual language.

That means:

- `/announcements` and `/adjustments` can be high-density work pages
- `/watchlist` can be operationally dense
- `/admin` can keep dense management panels

But density is expressed through layout and information organization, not through switching to a different product skin.

## 5. Page Designs

### 5.1 Homepage `/`

Purpose:

- brand landing page
- latest signals
- watchlist-related reminders
- fast navigation into deeper product pages

Homepage does not become the main heavy search page.

It keeps:

- current frozen homepage tone
- live announcement and adjustment previews
- watchlist-driven reminder previews
- quick route actions into the dedicated pages

### 5.2 Announcements `/announcements`

Purpose:

- advanced announcement retrieval
- filtering and narrowing
- structured browsing of graduate admissions announcements

Positioning:

- mixed product page, but more search-and-filter oriented than stream oriented

Structure:

- compact top control band instead of a large marketing hero
- page title, current query state, result volume, and lightweight summary metrics
- dedicated search/filter controls as the primary interaction area
- dense results list with stronger metadata clarity

Behavior:

- no shared header search box
- all primary querying happens inside the page-level control area
- results link to `/announcements/[id]`

### 5.3 Adjustments `/adjustments`

Purpose:

- browse real adjustment opportunities
- filter by opportunity characteristics
- surface a small amount of diagnostic context without replacing radar analysis

Positioning:

- opportunity page first
- light diagnostic summary second

Structure:

- top opportunity summary panel
- stronger emphasis on filters such as region, level, urgency, study mode, and subject direction
- opportunity card stream as the page core
- small diagnosis summary zone near the result controls or result summary area

Access model:

- anonymous users can browse preview lists
- key fields and follow/save actions require login

Behavior:

- no shared header search box
- results link to `/adjustments/[id]`
- the page links clearly to `/radar` for deep analysis but does not absorb radar responsibilities

### 5.4 Radar `/radar`

Purpose:

- deep score diagnosis
- strategy suggestions
- structured interpretation of score position and next-step actions

Responsibilities removed from radar:

- real opportunity browsing
- real-time opportunity stream behavior

This keeps radar focused and prevents overlap with `/adjustments`.

### 5.5 Watchlist `/watchlist`

Purpose:

- operate existing follows and monitoring targets
- manage reminders and active monitoring scope

Positioning:

- pure operations workspace

Responsibilities explicitly not centered here:

- personal profile identity
- membership center
- broad product overview
- primary search for new opportunities

Visual treatment:

- same homepage-based shell and light language
- no dark command-center skin
- denser internal workspace sections are allowed

### 5.6 Account `/account`

Purpose:

- account summary
- membership and billing state
- notification history
- security and identity status

Positioning:

- personal space page, not a follow-management console

Relationship to watchlist:

- `关注库` handles operations
- `我的空间` handles identity, entitlement, and personal summary

### 5.7 Admin `/admin`

Purpose:

- management and governance workspace

Visual rule:

- outer framing aligns with homepage language
- inner workspace may remain denser and more segmented

This is a deliberate middle ground:

- not a black standalone control center
- not a consumer-light page with removed management density

Structure:

- homepage-style outer shell
- admin-specific internal section navigation
- high-density tables, panels, and governance tools preserved where needed

## 6. Route Entry Rewiring

All in-app entry points must move to the new route model.

This includes:

- homepage navigation
- homepage search actions
- quick links
- user menu shortcuts
- login and register post-auth routing
- account quick actions
- watchlist and notification shortcuts

The redesign is considered incomplete if any normal user journey still treats `/search` or `/query` as primary destinations.

## 7. Data and API Boundaries

This redesign is primarily an information architecture and page-structure change.

Default rule:

- reuse current live business APIs where possible
- do not invent parallel data paths just because the page shapes change

Expected live data reuse:

- homepage announcement and adjustment previews remain real
- `/announcements` continues to use the announcement search backend
- `/adjustments` continues to use the adjustment search backend
- `/radar` continues to use radar prediction interfaces
- `/watchlist` continues to use subscriptions, monitoring targets, and pending notices
- `/account` continues to use current account, membership, and notification history endpoints
- `/admin` continues to use the existing governance and admin APIs

## 8. Non-Goals

This redesign does not attempt to:

- redesign backend business rules
- merge adjustment browsing into radar
- keep `/search` and `/query` as public-facing IA
- preserve the current dark `watchlist` or dark `admin` skins
- keep inline result expansion as the dominant detail experience

## 9. Acceptance Criteria

The redesign is successful when all of the following are true:

- the user-visible site and `/admin` use one homepage-based shell
- announcements and adjustments are separate product pages with separate route identities
- `/search` and `/query` are removed from the visible information architecture
- `/announcements` and `/adjustments` hide the global header search box
- `/watchlist` and `/account` no longer overlap in responsibility
- `/radar` focuses on deep analysis, while `/adjustments` remains the opportunity page
- detail navigation uses dedicated detail pages instead of inline expansion
- existing live APIs continue to power the rebuilt pages without a regression to mock data
