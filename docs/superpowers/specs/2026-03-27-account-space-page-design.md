# Account Space Page Design

## Background

The current web account surface is functionally complete but visually reads like a settings dashboard. It mixes these concerns into one large page:

1. account identity and role status
2. premium billing
3. password and WeChat binding actions
4. notification history
5. account-facing summaries

This creates three product problems:

- The first screen does not feel like a personal destination.
- The most important user-facing signals, such as watched scopes and recent activity, are visually weaker than account management controls.
- The current page does not match the stronger Bilibili-inspired visual direction the user wants for the web experience.

The product direction for this redesign is explicit:

- The account page should feel more like a Bilibili personal space page.
- The first screen should prioritize subscriptions, radar, and recent activity.
- Membership, security, WeChat binding, and logout should move into secondary surfaces instead of dominating the page.

## Goal

Redesign the web account page into a space-style personal homepage that:

- feels clearly closer to a Bilibili personal space page
- uses the existing account, subscription, monitoring, and notification APIs
- defaults to a recent-activity view instead of a settings panel
- keeps account management available without making it the visual center
- works on both desktop and mobile without inventing fake Bilibili-only content types

## Non-Goals

- Adding new backend APIs or changing account/auth semantics
- Replacing the dedicated watchlist workspace or radar page
- Turning the account page into a full watchlist management console
- Introducing fake video-community concepts such as creator submissions, anime shelves, or collections when no corresponding product data exists
- Reworking portal auth, billing logic, or WeChat binding rules

## Considered Approaches

### 1. Dynamic homepage

Use the account page as a cleaner personal dashboard, with recent activity first and account controls second.

Pros:

- Safest implementation path
- Easy reuse of current account dashboard structure
- Low risk of overfitting to Bilibili styling

Cons:

- Still reads closer to a dashboard than a personal space page
- Does not go far enough toward the desired visual taste

### 2. Space homepage with strong Bilibili borrowing

Use a space-style cover, floating avatar block, top-level content tabs, and a dynamic feed as the main layout, while keeping Gewu-specific content and terminology.

Pros:

- Best matches the desired aesthetic
- Gives the account page a clear personal-home destination feel
- Naturally centers recent activity, follows, and radar signals

Cons:

- Requires more deliberate visual discipline to avoid becoming a shallow clone
- Needs stronger UI decomposition than the current single dashboard file

### 3. Minimal homepage plus side drawer utilities

Keep the main account page very light and push account operations into floating entrypoints and drawers.

Pros:

- Clean first screen
- Secondary actions stay out of the way

Cons:

- Important account controls become less discoverable
- Page can feel thin if feed density is low

## Selected Approach

Use approach 2: a space homepage with strong Bilibili borrowing.

This direction is intentionally more visually recognizable than the current page, but the product content must remain Gewu-specific:

- the page can borrow the cover, avatar, tab, card, and motion language
- the page must not borrow Bilibili product taxonomy
- all visible metrics and cards must map to real Gewu account data

The design target is:

- clearly inspired by a Bilibili personal space page at first glance
- clearly a Gewu research-notice account center after a few seconds of reading

## Information Architecture

The main `/account` page becomes a space homepage with four top-level tabs.

The implementation should render Chinese labels in the UI, but this spec refers to them with stable English names:

1. `Activity`
2. `Following`
3. `Radar`
4. `Account`

### Default tab

The default tab is `Activity`.

Reasoning:

- It best matches the expected feel of a personal space homepage.
- It lets users answer "what happened recently?" before "what can I configure?"
- It makes the first screen more content-driven and less operational.

### Tab responsibilities

`Activity`

- shows recent notification history
- shows recent radar hits and scoped announcement activity
- acts as the main personal activity feed

`Following`

- shows subscriptions and scope monitor targets
- uses card-based presentation, not a management table
- highlights what the user is tracking rather than every edit affordance

`Radar`

- shows recent signal overview, recent-window summaries, and high-signal scopes
- includes a clear handoff to the dedicated radar/workspace pages for deeper management

`Account`

- groups membership, WeChat binding, password change, session-related actions, and logout
- remains first-party and accessible, but visually secondary

## Layout Design

### Desktop structure

The account page uses a three-layer layout:

1. space cover header
2. top stats plus tab rail
3. main content area with left-primary and right-secondary columns

#### Cover header

The top of the page contains:

- a large gradient cover
- floating avatar
- nickname and username
- role or premium badge
- short signature/status text

The cover should feel intentionally close to the Bilibili personal-space pattern:

- horizontal hero band
- profile block overlapping the lower edge
- light, bright palette rather than dark admin chrome

#### Summary strip

Below the cover, show three real metrics:

- follow count
- radar scope count
- recent activity count

No fake creator metrics should be introduced.

#### Main columns

Left column:

- the active tab content
- feed-first density
- larger cards and content rhythm

Right column:

- membership card
- WeChat binding status
- account security summary
- lightweight quick actions

The right column should feel like a personal profile sidebar, not an admin menu.

### Mobile structure

On mobile:

- keep the cover and floating profile block
- keep the tab rail horizontally scrollable
- collapse the right sidebar content below the main tab content
- preserve the "space page" feeling without forcing a cramped two-column layout

## Visual Direction

### Desired similarity level

The approved direction is "strong space-page borrowing", not a near 1:1 copy.

This means:

- clearly similar cover and profile composition
- clearly similar bright pink-blue visual accent system
- clearly similar tab and card rhythm
- not a copy of Bilibili labels, categories, or content types

### Color system

Primary palette:

- Bilibili-like pink accent
- bright sky-blue accent
- white and light gray surfaces

Recommended usage:

- cover gradients and tab indicators use pink-blue blends
- cards remain mostly light with subtle borders
- badges and small highlights use accent color, not full-surface saturation everywhere

The page should not keep the current "dark dashboard" look as the dominant visual language.

### Card language

Cards should use:

- soft white backgrounds
- faint borders
- medium-large radius
- restrained shadows
- cleaner spacing than the current dense dashboard blocks

The result should feel more like a modern personal feed than a console.

### Motion language

The motion direction should be light and polished:

- cover and profile block enter with soft slide/fade
- tab indicator glides instead of snapping harshly
- feed cards lift slightly on hover
- key metrics appear in short staggered timing

Motion should feel closer to Bilibili's polished consumer UI, but still restrained enough for an information product.

## Data Model and Reuse

The redesign should stay on existing APIs.

### Existing data sources to reuse

- account overview via `GET /api/v1/auth/me/account`
- notification history via `GET /api/v1/auth/me/notifications/history`
- subscriptions via existing subscription queries/hooks
- monitor targets via existing monitoring target queries/hooks
- recent signal overview from monitoring target responses

### Real-data mapping

The homepage metrics and cards must be sourced from real data:

- follow count from subscriptions plus scoped monitor targets, or shown separately if clearer
- radar scope count from monitor target count
- recent activity count from current feed-window item count
- premium badge from account overview / entitlement state
- WeChat binding state from account identities

### No fake content units

Do not add:

- creator submission count
- play count
- collection shelf
- follower relationship module

unless the product later gains real data that justifies them.

## Component Decomposition

The current `AccountDashboard.tsx` is too large to remain the single implementation surface.

The redesign should split the page into smaller focused components. Recommended decomposition:

- `AccountSpacePage` or equivalent page-level container
- `AccountSpaceHero`
- `AccountSpaceTabs`
- `AccountActivityFeed`
- `AccountFollowGrid`
- `AccountRadarOverview`
- `AccountSidebar`
- `AccountMembershipCard`
- `AccountSecurityPanel`
- `AccountWechatBindingCard`

Shared cards and badges can be extracted where useful, but the implementation should avoid generic over-abstraction.

## Route and Compatibility Strategy

The redesign should preserve route compatibility while making `/account` the new primary space homepage.

### Primary behavior

- `/account` becomes the new space homepage
- tab switching is driven by URL query state so deep links and tab persistence are explicit

### Existing secondary routes

Existing routes such as:

- `/account/security`
- `/account/billing`
- `/account/notifications`

should remain valid during the first implementation pass.

The compatibility strategy is explicit:

- `/account/security` redirects to `/account?tab=account&panel=security`
- `/account/billing` redirects to `/account?tab=account&panel=billing`
- `/account/notifications` redirects to `/account?tab=activity&panel=notifications`

This keeps legacy entrypoints alive while making `/account` the single canonical account homepage.

## State Design

### Logged-out state

When the user is not authenticated:

- preserve the space-page shell
- show the cover, profile placeholder, and tab framing
- replace feed content with a clear login/register invitation

This avoids a hard layout collapse and keeps the page identity consistent.

### Empty-data state

For a newly registered user with no follows or signals:

- do not show a blank feed
- show helpful empty states with three obvious actions:
  - go search and follow a school
  - set up radar scope
  - bind WeChat

### Non-premium state

Non-premium users should still see the page structure, but radar areas can:

- show partial signal context if available
- explain what premium unlocks
- offer a clear path to the membership page or upgrade action

### Error state

If one secondary data source fails:

- the entire page should not collapse
- affected sections should show local fallback/error states
- account identity and hero sections should still render if primary auth/account data is available

## Interaction Model

### Dynamic feed

The `Activity` tab should unify:

- delivered notification history
- recent radar-relevant signals
- latest monitored-scope notice activity

The UI treatment should be a single feed language, even if the underlying items come from more than one source.

### Follow tab

The `Following` tab should present:

- subscriptions
- scope monitor targets

as personal follow cards, not operator rows.

Actions such as delete or manage can exist, but should not dominate the card layout.

### Radar tab

The `Radar` tab should show:

- recent-signal overview
- active target count
- recent recruiting-signal count
- selected high-signal targets or latest hits

It should feel like a compressed signal board, with a handoff to the full radar/watchlist workspace for detailed management.

### Account tab

The `Account` tab should contain:

- premium status and orders
- WeChat binding
- password change
- logout

These remain fully functional but visually secondary to the space homepage.

## Testing Strategy

### UI behavior tests

- `/account` renders the new hero, tabs, and default `Activity` view
- logged-out state renders a stable shell with login prompts
- empty-data state renders guidance cards instead of blank areas
- non-premium state still renders the page with upgrade messaging

### Interaction tests

- tab switching updates visible content correctly
- sidebar actions remain reachable on desktop and mobile
- legacy secondary account routes still behave as designed

### Regression checks

- account overview still loads from the same API contract
- password change and WeChat bind flows still work
- premium order flow remains reachable
- notification history still appears in the new dynamic feed

## Acceptance Criteria

The redesign is complete when all of these are true:

1. `/account` reads visually as a personal space page instead of a settings dashboard.
2. The page is recognizably closer to a Bilibili-style space page than the current account UI.
3. The default experience prioritizes recent activity, follows, and radar over account controls.
4. The design uses real Gewu account data only.
5. Membership, WeChat binding, password change, and logout remain available without dominating the first screen.
6. Desktop and mobile layouts both preserve the same "space homepage" identity.
