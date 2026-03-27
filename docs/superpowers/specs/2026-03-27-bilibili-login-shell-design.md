# Bilibili-Style Login Shell Design

## Context

The current web experience uses a dark, data-dashboard visual language across the homepage, header, and authentication entry pages. The user wants the login and account entry experience rebuilt to closely mimic the visual structure, interaction rhythm, and spatial composition of Bilibili's desktop web experience shown in the provided screenshots.

This is a frontend-only redesign. Existing backend authentication APIs, session semantics, and account data sources remain the source of truth.

## Goals

1. Rebuild the public-facing homepage shell so the top navigation, search placement, hero banner, and login entry feel close to the referenced Bilibili experience.
2. Replace the current standalone login/register page presentation with a centered white modal over a Bilibili-style homepage scene.
3. Keep `username + password` login and registration fully functional against existing APIs.
4. Add a logged-in top-right user avatar entry with a Bilibili-style floating account card.
5. Rework `/account` so its first screen feels much closer to a Bilibili user space page while still showing our real account, subscription, and radar data.
6. Keep button labels, navigation labels, and business copy as our own wording rather than directly copying Bilibili text.

## Non-Goals

1. No backend auth contract changes.
2. No real QR-code login.
3. No real SMS login.
4. No real third-party OAuth for WeChat, QQ, or Weibo.
5. No fake video-platform metrics such as play count, likes, or fan count when we do not have real equivalents.
6. No attempt to literally import React Native screens from `JKVideo`; it is only a visual and structural reference.

## Product Direction

The target is a high-fidelity Bilibili-style shell:

- The overall visual structure, spacing, color palette, and motion should strongly resemble the screenshots.
- The product identity stays ours: our logo, our route destinations, our business data, and our copy.
- The experience should read as "Bilibili-like front stage, our real business underneath."

## User Experience Overview

### Logged-Out Homepage

The homepage becomes a bright, Bilibili-style landing shell:

- full-width illustrated banner background at the top
- semi-transparent top navigation over the banner
- centered search box
- right-side icon cluster and primary CTA
- category strip and recommendation-like card grid below the banner

The content cards continue to use our own announcement, school, and radar content, but are framed and spaced like a media platform homepage instead of a dark operations dashboard.

### Login Entry

The login entry is no longer a standalone full-page auth form.

- `/login` and `/register` render the same homepage shell backdrop
- a centered white modal becomes the main auth surface
- the modal uses a left/right split layout matching the reference rhythm
- left side presents QR visual treatment and illustration accents
- right side presents auth tabs

Supported auth behavior:

- `password login`: fully functional
- `register`: fully functional via existing register flow
- `SMS login`: visible but disabled / placeholder
- `QR login`, `WeChat`, `QQ`, `Weibo`: visible but placeholder-only

Placeholder interactions should use a soft productized response such as toast copy stating the feature is not yet available.

### Logged-In Header

After login:

- the top-right login button becomes an avatar trigger
- avatar interaction opens a floating account card similar to the provided Bilibili card
- the card displays real account identity and real business-derived counts

The floating account card should include:

- avatar
- nickname / username
- premium state
- summary counts based on real business data
- quick links to account center, following management, recommendations/services, theme, logout

Labels should be rewritten in our wording, but the visual composition should stay close to the reference.

### Account Space

`/account` should evolve from the current dashboard-like personal page into a Bilibili-space-style personal homepage:

- large cover/banner
- overlapping avatar and identity block
- secondary tab bar
- summary metrics on the right
- main content area on the left
- secondary profile/service cards on the right

The tabs remain our own business tabs, not copied Bilibili modules. The intended tab set is:

- `home`
- `activity`
- `following`
- `radar`
- `settings`

The main area should continue to render our real data: activity history, subscriptions, radar overview, and account utilities.

## Information Architecture

### Global Header

The existing dark sci-fi header is replaced with a new Bilibili-style global header shared by:

- `/`
- `/login`
- `/register`
- authenticated routes where the header remains visible

Header structure:

1. left: product logo
2. center-left: text navigation items
3. center: search box
4. right: icon entry cluster
5. far-right: primary CTA button or avatar trigger

Header behavior:

- transparent / translucent over hero banner
- bright text over banner
- subtle hover glow and underline motion
- sticky behavior preserved if already required by the layout

### Homepage Sections

Homepage layout should be reorganized into:

1. hero banner with navigation overlay
2. category strip / interest entry bar
3. recommendation grid using our announcement content
4. optional right-side utility rail or floating tools if needed

The existing "data timeline" hero should not remain as the primary homepage first impression.

### Auth Modal

The auth modal becomes a reusable shared surface used by:

- explicit login route
- explicit register route
- header login trigger

Its responsibilities:

- mode switching between login and register
- visual tabs for password vs SMS
- password submit
- register entry
- placeholder entry points for not-yet-supported methods

The modal should be implemented as a composable shell rather than hard-coded directly into the page file.

### Floating User Card

The floating user card is a shared header-attached component responsible for:

- showing identity summary
- offering quick links
- exposing logout
- matching the reference card feel

It should support both hover-friendly desktop behavior and click-safe behavior.

## Data Mapping

The redesign must use real existing data wherever possible.

### Real Data Sources

- auth/session state from the existing store
- current user profile from existing auth profile fetch
- notification history
- subscriptions / watchlist data
- monitor target / radar overview data
- premium state and identity badges already derived in app state

### Replacements for Bilibili-Style Metrics

We must not fabricate irrelevant platform metrics. The visual slots can remain, but values should map to our actual business metrics, for example:

- follow count -> followed schools / followed scopes
- fans count -> active radar scopes or linked identities
- dynamic count -> recent account activity count

If a slot has no truthful counterpart, it should be removed rather than faked.

## Route Strategy

### `/`

Becomes the primary public Bilibili-style shell.

### `/login`

Renders the shared homepage shell plus the auth modal opened in login mode.

### `/register`

Renders the shared homepage shell plus the auth modal opened in register mode.

### `/account`

Retains the route but shifts its presentation closer to a Bilibili user space.

## Component Plan

The redesign should likely introduce or refactor the following frontend units:

- new shared Bilibili-style header shell component
- homepage hero/banner shell
- homepage content shelf / card layout components
- auth modal shell component
- auth modal tab strip and placeholder social login block
- logged-in floating user card component
- account space banner / stats / tab shell components

Existing likely touchpoints:

- `web-ui/src/components/layout/Header.tsx`
- `web-ui/src/app/page.tsx`
- `web-ui/src/components/shared/AuthEntryPage.tsx`
- `web-ui/src/app/login/page.tsx`
- `web-ui/src/app/register/page.tsx`
- `web-ui/src/components/account/AccountSpacePage.tsx`

The refactor should prefer focused components rather than letting one giant page component absorb all behavior.

## Motion and Styling Rules

The visual language should strongly track the references:

- bright, pastel-leaning palette with pink and sky-blue accents
- white modal surfaces
- translucent banner header treatment
- rounded controls with Bilibili-like softness
- hover lift and underline motion on nav items
- polished entrance motion for modal and panels
- soft shadow depth instead of dark dashboard glow

The implementation should still preserve accessibility basics:

- keyboard focus visibility
- accessible dialog semantics
- form labels and error states
- responsive behavior that does not collapse on smaller screens

## Placeholder Feature Behavior

Unsupported auth methods should not dead-click.

Expected behavior:

- visually present and styled
- interactable if useful for perceived completeness
- on interaction, show a clear "not available yet" response

This includes:

- QR login
- SMS login submission
- WeChat login
- QQ login
- Weibo login
- optional icon shortcuts that imply future capability but do not yet map to a live route

## Testing and Validation

Required validation for this implementation:

- `cd web-ui && npm run lint`
- `cd web-ui && npm run build`

Manual browser validation should cover:

1. homepage logged-out state
2. login modal open/close
3. login success via password flow
4. register entry visibility and route behavior
5. logged-in avatar floating card
6. `/account` first screen visual structure
7. desktop layout
8. basic mobile non-breakage

No backend validation is required unless implementation unexpectedly touches backend code.

## Documentation Impact

If the final implementation materially changes the current description of the account page, homepage, or authentication entry experience, the relevant status documentation should be updated in the same task.

Most likely doc targets:

- `docs/current_status_2026-03-18.md`
- any frontend/account rollout notes if the implementation meaningfully supersedes them

## Acceptance Criteria

The work is complete when all of the following are true:

1. The public homepage, top nav, login modal, and logged-in account entry clearly evoke the Bilibili reference structure and motion.
2. The text labels and business copy are ours rather than direct Bilibili wording.
3. Password login works with the existing backend flow.
4. Registration remains available.
5. Unsupported auth methods are visually present but clearly non-live.
6. The top-right user avatar opens a Bilibili-style floating account card.
7. `/account` first-screen experience feels closer to a Bilibili user space than the current dashboard-like layout.
8. Frontend lint and build pass.
