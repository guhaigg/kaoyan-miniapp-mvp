#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from sqlalchemy import or_
from sqlalchemy.orm import selectinload


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import SessionLocal
from app.models import Content, utcnow
from app.services.content_repair import (
    extract_content_published_at_from_body,
    looks_like_placeholder_content_title,
    repair_content_fields_from_body,
    resolve_content_display_fields,
)
from app.services.content_summary import summarize_text
from app.services.crawler import (
    _build_content_tags,
    _build_link_notice_content,
    _extract_detail_body,
    _extract_outbound_links,
    _extract_text,
    _extract_title,
    _fetch_with_retry,
    _is_pdf_url,
    _looks_like_link_notice,
)


def _needs_repair(row: Content) -> bool:
    return (
        looks_like_placeholder_content_title(row.title)
        or not str(row.summary or "").strip()
        or row.published_at is None
    )


def _can_refetch(row: Content) -> bool:
    source_url = str(row.source_url or "").strip()
    return bool(source_url) and source_url.startswith(("http://", "https://")) and not _is_pdf_url(source_url)


def _repair_row_by_snapshot(row: Content) -> list[str]:
    if not row.snapshots:
        return []

    snapshot = max(
        row.snapshots,
        key=lambda item: item.created_at or utcnow(),
    )
    raw_html = str(snapshot.raw_html or "").strip()
    raw_text = str(snapshot.raw_text or "").strip()
    extracted_body = ""
    extraction_method = None
    readability_title = None
    outbound_links: list[dict[str, str]] = []
    source_url = str(row.source_url or "").strip()
    raw_page_text = ""

    if raw_html:
        extracted_body, extraction_method, readability_title = _extract_detail_body(raw_html, detail_selector_config=None)
        raw_page_text = _extract_text(raw_html)
        if source_url:
            outbound_links = _extract_outbound_links(raw_html, base_url=source_url, current_url=source_url)

    body = str(extracted_body or raw_text or "").strip()
    if not body:
        return []

    title = readability_title or (_extract_title(raw_html) if raw_html else None) or row.title
    summary = summarize_text(body)
    extra = dict(row.extra or {})

    if raw_html and source_url and _looks_like_link_notice(body=body, raw_html=raw_html, outbound_links=outbound_links):
        body, summary = _build_link_notice_content(title, outbound_links)
        extra["notice_kind"] = "link_notice"
        extra["outbound_links"] = outbound_links

    display_title, display_summary, display_published_at = resolve_content_display_fields(
        title=title,
        summary=None,
        published_at=row.published_at,
        body=body,
    )
    display_summary = display_summary or summary
    if display_published_at is None:
        display_published_at = (
            extract_content_published_at_from_body(raw_text)
            or extract_content_published_at_from_body(raw_page_text)
        )

    changed_fields: list[str] = []
    if body != row.body:
        row.body = body
        changed_fields.append("body")
    if display_title and display_title != row.title:
        row.title = display_title
        changed_fields.append("title")
    if display_summary != row.summary:
        row.summary = display_summary
        changed_fields.append("summary")
    if display_published_at != row.published_at:
        row.published_at = display_published_at
        changed_fields.append("published_at")

    if extraction_method:
        extra["detail_extraction_method"] = extraction_method
    extra["tags"] = _build_content_tags(display_title, display_summary, body)
    repair_meta = dict(extra.get("repair_meta") or {})
    repair_meta["last_snapshot_repair_at"] = utcnow().isoformat()
    repair_meta["last_snapshot_repair_content_snapshot_id"] = snapshot.id
    extra["repair_meta"] = repair_meta
    row.extra = extra
    if changed_fields:
        changed_fields.append("extra")
    return changed_fields


def _repair_row_by_refetch(row: Content) -> list[str]:
    source_url = str(row.source_url or "").strip()
    response = _fetch_with_retry(source_url)
    raw_html = response.text or ""
    raw_page_text = _extract_text(raw_html)
    extracted_body, extraction_method, readability_title = _extract_detail_body(raw_html, detail_selector_config=None)
    body = str(extracted_body or "").strip()
    if not body:
        return []

    title = readability_title or _extract_title(raw_html) or row.title
    summary = summarize_text(body)
    outbound_links = _extract_outbound_links(raw_html, base_url=source_url, current_url=source_url)
    extra = dict(row.extra or {})

    if _looks_like_link_notice(body=body, raw_html=raw_html, outbound_links=outbound_links):
        body, summary = _build_link_notice_content(title, outbound_links)
        extra["notice_kind"] = "link_notice"
        extra["outbound_links"] = outbound_links

    display_title, display_summary, display_published_at = resolve_content_display_fields(
        title=title,
        summary=None,
        published_at=row.published_at,
        body=body,
    )
    display_summary = display_summary or summary
    if display_published_at is None:
        display_published_at = extract_content_published_at_from_body(raw_page_text)

    changed_fields: list[str] = []
    if body != row.body:
        row.body = body
        changed_fields.append("body")
    if display_title and display_title != row.title:
        row.title = display_title
        changed_fields.append("title")
    if display_summary != row.summary:
        row.summary = display_summary
        changed_fields.append("summary")
    if display_published_at != row.published_at:
        row.published_at = display_published_at
        changed_fields.append("published_at")

    extra["detail_extraction_method"] = extraction_method
    extra["tags"] = _build_content_tags(display_title, display_summary, body)
    repair_meta = dict(extra.get("repair_meta") or {})
    repair_meta["last_refetch_at"] = utcnow().isoformat()
    repair_meta["last_refetch_source_url"] = source_url
    extra["repair_meta"] = repair_meta
    row.extra = extra
    if changed_fields:
        changed_fields.append("extra")
    return changed_fields


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair stale announcement title / summary / published_at fields.")
    parser.add_argument("--limit", type=int, default=0, help="Optional row limit.")
    parser.add_argument("--dry-run", action="store_true", help="Show would-be changes without committing.")
    parser.add_argument("--skip-refetch", action="store_true", help="Only repair from existing body, do not refetch unresolved URLs.")
    parser.add_argument("--source-url", type=str, default="", help="Repair only a specific source_url.")
    parser.add_argument("--unresolved-sample-limit", type=int, default=5, help="How many unresolved rows to print for diagnosis.")
    args = parser.parse_args()

    with SessionLocal() as db:
        query = db.query(Content).options(selectinload(Content.snapshots)).filter(Content.category == "announcement")
        if args.source_url.strip():
            query = query.filter(Content.source_url == args.source_url.strip())
        else:
            query = query.filter(
                or_(
                    Content.published_at.is_(None),
                    Content.summary.is_(None),
                    Content.summary == "",
                    Content.title.like("%.htm"),
                    Content.title.like("%.html"),
                    Content.title.like("%.jsp"),
                    Content.title.like("%.php"),
                    Content.title.like("%.aspx"),
                    Content.title.like("%.do"),
                )
            )
        query = query.order_by(Content.updated_at.asc(), Content.id.asc())
        if args.limit > 0:
            query = query.limit(args.limit)

        scanned = 0
        body_repaired = 0
        snapshot_repaired = 0
        refetch_repaired = 0
        unresolved = 0
        skipped = 0
        refetch_failed = 0
        unresolved_missing_title = 0
        unresolved_missing_summary = 0
        unresolved_missing_published_at = 0
        unresolved_samples: list[dict[str, str | None]] = []

        for row in query.all():
            scanned += 1
            initial_needs_repair = _needs_repair(row)
            if not initial_needs_repair:
                skipped += 1
                continue

            body_changes = repair_content_fields_from_body(row)
            if body_changes:
                body_repaired += 1

            if _needs_repair(row):
                snapshot_changes = _repair_row_by_snapshot(row)
                if snapshot_changes:
                    snapshot_repaired += 1

            if _needs_repair(row) and not args.skip_refetch and _can_refetch(row):
                try:
                    refetch_changes = _repair_row_by_refetch(row)
                except Exception:
                    refetch_failed += 1
                    refetch_changes = []
                if refetch_changes:
                    refetch_repaired += 1

            if _needs_repair(row):
                unresolved += 1
                if looks_like_placeholder_content_title(row.title):
                    unresolved_missing_title += 1
                if not str(row.summary or "").strip():
                    unresolved_missing_summary += 1
                if row.published_at is None:
                    unresolved_missing_published_at += 1
                if len(unresolved_samples) < max(args.unresolved_sample_limit, 0):
                    unresolved_samples.append(
                        {
                            "source_url": row.source_url,
                            "title": row.title,
                            "body_preview": str(row.body or "").strip().replace("\n", " ")[:160],
                        }
                    )

        if args.dry_run:
            db.rollback()
        else:
            db.commit()

    print(
        " ".join(
            [
                f"scanned={scanned}",
                f"body_repaired={body_repaired}",
                f"snapshot_repaired={snapshot_repaired}",
                f"refetch_repaired={refetch_repaired}",
                f"unresolved={unresolved}",
                f"refetch_failed={refetch_failed}",
                f"skipped={skipped}",
                f"unresolved_missing_title={unresolved_missing_title}",
                f"unresolved_missing_summary={unresolved_missing_summary}",
                f"unresolved_missing_published_at={unresolved_missing_published_at}",
                f"dry_run={args.dry_run}",
            ]
        )
    )
    if unresolved_samples:
        print(f"unresolved_samples={json.dumps(unresolved_samples, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
