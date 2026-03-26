# CHSI Foundation Enrich Fanout Design

## Background

The full `announcement_catalog_refresh` workflow currently spends too long inside the first CHSI step because that step does both of these jobs in one execution unit:

1. Fetch the full CHSI school catalog.
2. Enrich every school entry by fetching each CHSI school detail page and extracting:
   - `seed_hint_urls`
   - `department_page_url`
   - `major_page_url`

This coupling creates three operational problems:

- Full refresh latency is dominated by one long-running step.
- Retry granularity is too coarse; a single school failure can force replay of the whole CHSI stage.
- Workflow detail cannot explain per-school enrich progress or failures cleanly.

The recently added scoped `school_names` short-circuit makes small dry-runs usable, but it does not solve the full-refresh bottleneck.

## Goal

Refactor full CHSI foundation refresh so that:

- school-catalog fetch and per-school enrich are separated
- per-school enrich runs as workflow-managed child steps
- progress and failures are visible per school in workflow detail
- later steps do not consume a partially enriched school snapshot
- retries and stale-lease recovery happen per school instead of per full run

## Non-Goals

- Changing the downstream meaning of `major`, `department`, or `registry` artifacts
- Switching full refresh into a partially successful best-effort mode
- Reworking the entire foundation builder into a separate workflow family
- Replacing current JSON artifacts with database-backed foundation storage

## Considered Approaches

### 1. Controller step plus per-school child steps

This design keeps one foundation workflow run, adds a controller/enqueue barrier, fans out one enrich step per school, then adds a barrier/aggregation step before continuing.

Pros:

- Fits the current V2 step model
- Per-school retries and reclaim use the existing lease system
- Workflow detail remains centered on one top-level run
- Downstream steps can be gated behind one explicit barrier

Cons:

- Requires new step types and child-step aggregation logic

### 2. Separate workflow run per school

This design creates one child workflow run for each school instead of child steps.

Pros:

- Strong isolation per school
- Very fine-grained observability

Cons:

- Run explosion in admin views
- More complex correlation and dedupe
- More invasive changes to run-level orchestration

### 3. Keep one step and add internal checkpoint state

This design keeps a single step but stores per-school progress in JSON state or sidecar files.

Pros:

- Smallest schema-level change

Cons:

- Bypasses the existing step/retry model
- Weak parallelism
- Weak observability
- Harder to reason about stale recovery

## Selected Approach

Use approach 1: one foundation workflow run with controller steps and per-school enrich child steps.

This is the smallest change that still gives proper fanout, retry isolation, stale-lease recovery, and a strict downstream barrier.

## Workflow Design

The CHSI portion of `announcement_catalog_refresh` becomes:

1. `fetch_chsi_school_catalog`
2. `enqueue_chsi_school_enrich`
3. `enrich_chsi_school_snapshot` repeated once per school
4. `await_chsi_school_enrich`
5. `fetch_chsi_major_catalog`
6. `fetch_official_seed_rosters`
7. `fetch_school_homepages`
8. `build_department_candidates`
9. `merge_announcement_seed_registry`

### Step responsibilities

`fetch_chsi_school_catalog`

- Fetches and parses the CHSI school directory only
- Writes a base school catalog snapshot without the per-school enrich fields
- Returns `school_count`

`enqueue_chsi_school_enrich`

- Reads the base school catalog snapshot
- Creates one child step per school with a stable idempotency key
- Returns `queued_school_count`

`enrich_chsi_school_snapshot`

- Fetches one CHSI school detail page
- Extracts `seed_hint_urls`, `department_page_url`, and `major_page_url`
- Writes one per-school enrich artifact, not the final shared snapshot
- Returns the school identity and extracted field counts

`await_chsi_school_enrich`

- Waits until every enrich child step is terminal
- Aggregates per-school success/failure counts and failure summaries
- If any enrich child failed, marks the run failed at this barrier
- If all succeeded, merges per-school enrich artifacts into the final `school_catalog_snapshot.json`
- Only after successful merge does it queue `fetch_chsi_major_catalog`

## Strict Barrier Rule

The downstream rule is strict:

- `major / department / merge` must wait until all per-school enrich steps reach terminal state.
- Partial enrich results are not allowed to flow into downstream steps.
- If any school enrich fails, the workflow stops at `await_chsi_school_enrich` and exposes the failure summary in workflow detail.

This preserves deterministic artifact meaning and avoids half-enriched snapshot consumption.

## Data and Artifact Design

### Shared artifacts

Existing artifact filenames remain:

- `school_catalog_snapshot.json`
- `department_catalog_snapshot.json`
- `major_catalog_snapshot.json`
- `announcement_official_seed_candidates.json`
- `announcement_school_homepages.json`
- `announcement_department_seed_candidates.json`
- `announcement_seed_registry_diff.json`
- `announcement_seed_registry.json`

### New intermediate enrich storage

Per-school enrich results should be written as workflow-managed intermediate artifacts rather than directly mutating the shared snapshot during fanout.

Required properties:

- keyed by `school_code` or normalized `school_name`
- idempotent overwrite per school
- mergeable by the barrier step
- safe to rebuild after worker restart

Implementation can use either:

- `parse_artifacts` / `raw_artifacts` payloads tied to enrich steps, or
- a dedicated temporary JSON directory under the existing foundation data dir

The preferred choice is workflow-tied artifacts because they naturally stay attached to step history.

### Final school snapshot write

Only `await_chsi_school_enrich` writes the final enriched `school_catalog_snapshot.json`.

This guarantees downstream steps always see one of these states:

- old complete snapshot
- new complete snapshot

They never see a partially enriched in-progress snapshot.

## Retry and Recovery Model

### Per-school retry

Each `enrich_chsi_school_snapshot` step retries independently according to step policy.

This means:

- one school timeout does not replay completed schools
- stale leases reclaim one school step at a time
- operators can inspect exactly which schools failed

### Run recovery

`await_chsi_school_enrich` must be safe to execute repeatedly. It should:

- query child step state fresh each time
- aggregate current terminal/non-terminal counts
- avoid double-queueing downstream steps
- fail deterministically when any child step failed

## Concurrency Model

`enrich_chsi_school_snapshot` uses the CHSI host key so concurrency remains bounded.

Recommended initial policy:

- keep `host_key=yz.chsi.com.cn`
- raise host concurrency from serial execution to a conservative small number such as `3`

This gives meaningful fanout while avoiding aggressive CHSI pressure.

If production evidence shows instability, the host limit can be tuned independently of workflow shape.

## Admin Observability

Workflow detail should make the enrich barrier inspectable without SQL:

- total schools queued
- schools done
- schools failed
- schools still pending/running
- failed school names and error summaries

The barrier step result payload should include:

- `total_school_count`
- `succeeded_school_count`
- `failed_school_count`
- `failed_schools`
- `pending_school_count`

Each per-school enrich step result payload should include:

- `school_code`
- `school_name`
- `seed_hint_count`
- `has_department_page`
- `has_major_page`

## Testing Strategy

### Unit / service tests

- base catalog step writes a non-enriched snapshot
- enqueue step creates one child step per school
- enrich step produces per-school artifact payload
- barrier step merges all success artifacts into final school snapshot

### Workflow tests

- all enrich child steps done -> barrier queues `fetch_chsi_major_catalog`
- one enrich child step failed -> barrier fails the run and does not queue downstream steps
- mixed pending/running/done enrich child steps -> barrier stays pending/running and does not advance
- stale enrich child step can be reclaimed without corrupting final merge

### Regression tests

- existing scoped `school_names` short-circuit behavior remains intact
- major catalog continues to read the final enriched school snapshot

## Rollout Plan

1. Add new step types and policies.
2. Split current CHSI stage into fetch, enqueue, enrich, and barrier steps.
3. Add tests covering the barrier semantics.
4. Run full backend tests.
5. Deploy to production.
6. Validate with one scoped dry-run and one full dry-run.

## Risks

### Risk: downstream step double-queue

Mitigation:

- barrier step must create the next step exactly once using existing dedupe/idempotency patterns

### Risk: partial intermediate artifact accumulation

Mitigation:

- barrier merge should only read the latest successful enrich artifact for each school
- reruns should overwrite per-school intermediate data deterministically

### Risk: CHSI host pressure after fanout

Mitigation:

- keep low host limit initially
- inspect production timings before increasing concurrency further

## Open Decisions Already Resolved

- Downstream steps must wait for all per-school enrich steps to reach terminal state.
- Partial success does not automatically continue into `major / department / merge`.
- Failure summaries belong in workflow detail so operators can decide whether to rerun or adjust policy.
