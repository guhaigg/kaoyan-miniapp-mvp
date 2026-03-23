from __future__ import annotations

from datetime import datetime, timezone
import re

from ..models import Content
from .content_summary import normalize_text_whitespace, summarize_text

UTC = timezone.utc
NON_DETAIL_ANNOUNCEMENT_TITLES = frozenset(
    {
        "学工新闻",
        "研究生教育",
        "学院简介",
    }
)
NON_DETAIL_ANNOUNCEMENT_URL_SUFFIXES = (
    "/list.htm",
    "/list.html",
    "/list.shtm",
    "/list.shtml",
    "/list.psp",
    "/list.jsp",
    "/list.php",
    "/list.aspx",
    "/list.do",
)
NON_DETAIL_ANNOUNCEMENT_TEST_HOST_MARKERS = (
    "://smoke.example.com/",
)
NON_DETAIL_ANNOUNCEMENT_TEST_URL_MARKERS = (
    "unauth-test",
    "auth-after-fix",
)

PLACEHOLDER_CONTENT_TITLE_PATTERN = re.compile(r"^(?:[A-Za-z0-9_-]+|\d+)\.(?:s?html?|aspx?|php|jsp|do)$", re.IGNORECASE)
CONTENT_BODY_TITLE_PATTERN = re.compile(
    r"([\u4e00-\u9fa5A-Za-z0-9（）()《》“”·、\-—:：]{8,160}?(?:通知|公告|简章|章程|办法|须知|名单|安排|方案|信息))"
)
CONTENT_BODY_LABELED_PUBLISHED_AT_PATTERN = re.compile(
    r"(?:发布时间|发布时(?:间)?|发布日期|日期|时间|发文时间|更新(?:时间)?|发表于)[:：]?\s*(\d{4})[.\-/年](\d{1,2})[.\-/月](\d{1,2})(?:日)?"
)
CONTENT_BODY_TOP_DATE_PATTERN = re.compile(r"(?<!\d)(\d{4})[.\-/年](\d{1,2})[.\-/月](\d{1,2})(?:日)?(?!\d)")
CONTENT_SUMMARY_CUE_PATTERN = re.compile(r"(根据《|根据|现将|现就|为做好|为进一步|经研究|一、|请申请人|请考生|各位考生)")


def infer_non_detail_announcement_reason(
    *,
    title: str | None,
    body: str | None,
    source_url: str | None,
) -> str | None:
    normalized_title = normalize_text_whitespace(title)
    normalized_body = normalize_text_whitespace(body)
    normalized_url = str(source_url or "").strip().lower()

    if any(marker in normalized_url for marker in NON_DETAIL_ANNOUNCEMENT_TEST_HOST_MARKERS):
        return "test_domain"

    if any(marker in normalized_url for marker in NON_DETAIL_ANNOUNCEMENT_TEST_URL_MARKERS):
        return "test_fixture"

    if any(normalized_url.endswith(suffix) for suffix in NON_DETAIL_ANNOUNCEMENT_URL_SUFFIXES):
        return "list_page"

    if normalized_title in NON_DETAIL_ANNOUNCEMENT_TITLES and len(normalized_body) < 240:
        return "generic_section_page"

    return None


def looks_like_placeholder_content_title(title: str | None) -> bool:
    normalized = normalize_text_whitespace(title)
    if not normalized:
        return True
    return bool(PLACEHOLDER_CONTENT_TITLE_PATTERN.fullmatch(normalized))


def extract_content_title_from_body(body: str | None) -> str | None:
    normalized = normalize_text_whitespace(body)
    if not normalized:
        return None
    normalized = normalized.lstrip("\ufeff")
    match = CONTENT_BODY_TITLE_PATTERN.search(normalized[:240])
    if not match:
        return None
    candidate = re.sub(
        r"\s*[-|｜]\s*.*?(?:研究生招生信息网|研究生院|官网|网站|网)$",
        "",
        match.group(1),
    ).strip(" -|：:")
    if not candidate or looks_like_placeholder_content_title(candidate):
        return None
    return candidate


def extract_content_published_at_from_body(body: str | None) -> datetime | None:
    normalized = normalize_text_whitespace(body)
    if not normalized:
        return None
    search_windows = [normalized[:320], normalized[:160]]
    for index, pattern in enumerate((CONTENT_BODY_LABELED_PUBLISHED_AT_PATTERN, CONTENT_BODY_TOP_DATE_PATTERN)):
        window = search_windows[index] if index < len(search_windows) else normalized[:160]
        match = pattern.search(window)
        if not match:
            continue
        year, month, day = (int(part) for part in match.groups())
        try:
            return datetime(year, month, day, tzinfo=UTC)
        except ValueError:
            continue
    return None


def extract_content_summary_from_body(body: str | None, display_title: str | None) -> str | None:
    normalized = normalize_text_whitespace(body)
    if not normalized:
        return None
    normalized = normalized.lstrip("\ufeff")
    if display_title and normalized.startswith(display_title):
        normalized = normalized[len(display_title):].strip(" -|：:")
    published_match = CONTENT_BODY_LABELED_PUBLISHED_AT_PATTERN.search(normalized)
    if published_match:
        normalized = normalized[published_match.end():].strip(" -|：:")
    cue_match = CONTENT_SUMMARY_CUE_PATTERN.search(normalized)
    if cue_match and 0 < cue_match.start() <= 160:
        normalized = normalized[cue_match.start():].strip()
    return summarize_text(normalized)


def resolve_content_display_fields(
    *,
    title: str | None,
    summary: str | None,
    published_at: datetime | None,
    body: str | None,
) -> tuple[str, str | None, datetime | None]:
    display_title = normalize_text_whitespace(title) or title or ""
    if looks_like_placeholder_content_title(display_title):
        display_title = extract_content_title_from_body(body) or display_title
    display_summary = normalize_text_whitespace(summary) or extract_content_summary_from_body(body, display_title)
    display_published_at = published_at or extract_content_published_at_from_body(body)
    return display_title, display_summary, display_published_at


def repair_content_fields_from_body(content: Content) -> list[str]:
    display_title, display_summary, display_published_at = resolve_content_display_fields(
        title=content.title,
        summary=content.summary,
        published_at=content.published_at,
        body=content.body,
    )
    changed_fields: list[str] = []
    if display_title and display_title != content.title:
        content.title = display_title
        changed_fields.append("title")
    if display_summary != content.summary:
        content.summary = display_summary
        changed_fields.append("summary")
    if display_published_at != content.published_at:
        content.published_at = display_published_at
        changed_fields.append("published_at")
    return changed_fields
