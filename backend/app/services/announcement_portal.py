from __future__ import annotations

from collections.abc import Iterable
import re
from typing import Any

PORTAL_SCOPE_GRADUATE_ADMISSIONS = "graduate_admissions"

PORTAL_ENTRY_KEYWORDS = (
    "研究生招生",
    "研究生院",
    "研招",
    "招生信息网",
    "招生工作",
)

GRADUATE_ADMISSIONS_PAGE_HINTS = (
    "研究生招生",
    "研究生院",
    "研工部",
    "招生工作",
    "硕士招生",
    "博士招生",
    "招生简章",
    "专业目录",
    "通知公告",
)

_SPACE_RE = re.compile(r"\s+")

_CHANNEL_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "label": "硕士招生",
        "tier": "core",
        "keywords": ("硕士招生", "硕士研究生", "推免", "推荐免试"),
        "path_keywords": ("sszs", "master"),
    },
    {
        "label": "博士招生",
        "tier": "core",
        "keywords": ("博士招生", "博士研究生", "博士学位研究生", "硕博连读", "申请-考核"),
        "path_keywords": ("bszs", "doctor"),
    },
    {
        "label": "招生简章",
        "tier": "core",
        "keywords": ("招生简章",),
        "path_keywords": ("zsjz",),
    },
    {
        "label": "专业目录",
        "tier": "core",
        "keywords": ("专业目录", "招生专业目录", "专业信息表", "参考书目", "考试大纲"),
        "path_keywords": ("zyml", "catalog"),
    },
    {
        "label": "通知公告",
        "tier": "core",
        "keywords": ("通知公告", "公告通知", "通知", "公告"),
        "path_keywords": ("tzgg", "notice"),
    },
    {
        "label": "政策文件",
        "tier": "core",
        "keywords": ("政策文件", "政策法规", "政策通知"),
        "path_keywords": ("policy", "zcwj"),
    },
    {
        "label": "调剂",
        "tier": "core",
        "keywords": ("调剂", "预调剂", "意向采集", "缺额"),
        "path_keywords": ("tiaoji", "adjustment"),
    },
    {
        "label": "招生信息",
        "tier": "core",
        "keywords": ("招生信息", "招生动态", "复试", "录取", "拟录取", "成绩查询", "报名", "复核"),
        "path_keywords": ("zhaosheng", "admission"),
    },
    {
        "label": "工作动态",
        "tier": "supplemental",
        "keywords": ("工作动态", "新闻动态", "动态新闻"),
        "path_keywords": ("dongtai", "news"),
    },
    {
        "label": "信息公开",
        "tier": "supplemental",
        "keywords": ("信息公开",),
        "path_keywords": ("gongkai", "public"),
    },
    {
        "label": "招生宣传",
        "tier": "supplemental",
        "keywords": ("招生宣传", "宣传咨询", "招生宣讲", "研招宣传"),
        "path_keywords": ("xuanchuan",),
    },
)

_SYSTEM_TAG_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "label": "硕士招生",
        "keywords": ("硕士招生", "硕士研究生", "推免", "推荐免试"),
    },
    {
        "label": "博士招生",
        "keywords": ("博士招生", "博士研究生", "博士学位研究生", "硕博连读", "申请-考核"),
    },
    {
        "label": "招生简章",
        "keywords": ("招生简章",),
    },
    {
        "label": "专业目录",
        "keywords": ("专业目录", "招生专业目录", "专业信息表", "参考书目", "考试大纲"),
    },
    {
        "label": "通知公告",
        "keywords": ("通知公告", "公告通知", "通知", "公告"),
    },
    {
        "label": "政策文件",
        "keywords": ("政策文件", "政策法规", "政策通知"),
    },
    {
        "label": "调剂",
        "keywords": ("调剂", "预调剂", "意向采集", "缺额"),
    },
    {
        "label": "招生信息",
        "keywords": ("招生信息", "招生动态", "复试", "录取", "拟录取", "成绩查询", "报名", "复核"),
    },
    {
        "label": "工作动态",
        "keywords": ("工作动态", "新闻动态", "动态新闻"),
    },
    {
        "label": "信息公开",
        "keywords": ("信息公开",),
    },
    {
        "label": "招生宣传",
        "keywords": ("招生宣传", "宣传咨询", "招生宣讲", "研招宣传"),
    },
)

DEFAULT_ANNOUNCEMENT_SYSTEM_TAGS = [
    "硕士招生",
    "博士招生",
    "招生简章",
    "专业目录",
    "通知公告",
    "政策文件",
    "调剂",
    "招生信息",
    "工作动态",
    "信息公开",
    "招生宣传",
]

_SUPPLEMENTAL_GATEWAY_TAGS = {
    "硕士招生",
    "博士招生",
    "招生简章",
    "专业目录",
    "通知公告",
    "政策文件",
    "调剂",
    "招生信息",
    "招生宣传",
}


def normalize_portal_text(value: Any) -> str:
    return _SPACE_RE.sub(" ", str(value or "")).strip()


def _dedupe_strings(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    items: list[str] = []
    for value in values:
        normalized = normalize_portal_text(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        items.append(normalized)
    return items


def normalize_portal_tags(values: Iterable[Any] | None) -> list[str]:
    if values is None:
        return []
    return _dedupe_strings(str(value or "") for value in values)


def is_graduate_portal_entry_text(text: str) -> bool:
    normalized = normalize_portal_text(text)
    if not normalized:
        return False
    return any(keyword in normalized for keyword in PORTAL_ENTRY_KEYWORDS)


def page_looks_like_graduate_admissions_portal(*texts: str | None) -> bool:
    haystack = normalize_portal_text(" ".join(str(text or "") for text in texts if str(text or "").strip()))
    if not haystack:
        return False
    return any(keyword in haystack for keyword in GRADUATE_ADMISSIONS_PAGE_HINTS)


def classify_announcement_channel(*texts: str | None) -> dict[str, Any] | None:
    normalized_text = normalize_portal_text(" ".join(str(text or "") for text in texts if str(text or "").strip()))
    lowered = normalized_text.lower()
    if not normalized_text:
        return None

    for definition in _CHANNEL_DEFINITIONS:
        keyword_hits = [keyword for keyword in definition["keywords"] if keyword in normalized_text]
        path_hits = [keyword for keyword in definition.get("path_keywords", ()) if keyword in lowered]
        if not keyword_hits and not path_hits:
            continue
        return {
            "label": definition["label"],
            "tier": definition["tier"],
            "keywords": _dedupe_strings([*keyword_hits, *path_hits]),
        }
    return None


def derive_announcement_system_tags(
    title: str | None,
    summary: str | None,
    body: str | None,
    *,
    channel_label: str | None = None,
    channel_tier: str | None = None,
    channel_keywords: list[str] | None = None,
) -> list[str]:
    combined = normalize_portal_text(
        " ".join(
            part
            for part in [
                str(title or ""),
                str(summary or ""),
                str(body or "")[:1600],
                str(channel_label or ""),
                " ".join(str(item or "") for item in (channel_keywords or [])),
            ]
            if str(part or "").strip()
        )
    )
    if not combined:
        return []

    tags: list[str] = []
    if channel_label:
        tags.append(channel_label)

    for definition in _SYSTEM_TAG_DEFINITIONS:
        if any(keyword in combined for keyword in definition["keywords"]):
            tags.append(definition["label"])

    if channel_tier == "supplemental" and channel_label and channel_label not in tags:
        tags.insert(0, channel_label)

    return _dedupe_strings(tags)


def merge_announcement_tags(
    tags: Iterable[Any] | None,
    system_tags: Iterable[Any] | None,
    *,
    channel_label: str | None = None,
) -> list[str]:
    merged: list[str] = []
    if channel_label:
        merged.append(channel_label)
    merged.extend(str(tag or "") for tag in (tags or []))
    merged.extend(str(tag or "") for tag in (system_tags or []))
    return _dedupe_strings(merged)


def extract_announcement_portal_metadata(
    config: dict[str, Any] | None,
    *,
    site_section_id: str | None = None,
    site_section_name: str | None = None,
) -> dict[str, Any]:
    if not isinstance(config, dict):
        return {}

    metadata: dict[str, Any] = {}
    for key in ("portal_scope", "portal_entry_url", "channel_label", "channel_tier"):
        value = normalize_portal_text(config.get(key))
        if value:
            metadata[key] = value

    channel_keywords = normalize_portal_tags(config.get("channel_keywords") or [])
    if channel_keywords:
        metadata["channel_keywords"] = channel_keywords

    portal_path_evidence = config.get("portal_path_evidence")
    if isinstance(portal_path_evidence, dict) and portal_path_evidence:
        metadata["portal_path_evidence"] = dict(portal_path_evidence)

    if site_section_id:
        metadata["site_section_id"] = normalize_portal_text(site_section_id)
    if site_section_name:
        metadata["site_section_name"] = normalize_portal_text(site_section_name)
    return metadata


def supplemental_content_is_visible(channel_tier: str | None, system_tags: Iterable[str]) -> bool:
    if channel_tier != "supplemental":
        return True
    normalized_tags = {normalize_portal_text(tag) for tag in system_tags if normalize_portal_text(tag)}
    return bool(normalized_tags & _SUPPLEMENTAL_GATEWAY_TAGS)


def announcement_content_is_visible(
    *,
    portal_scope: str | None,
    channel_tier: str | None,
    system_tags: Iterable[Any] | None,
    department_id: str | None = None,
    department_name: str | None = None,
    default_visible: bool = True,
) -> bool:
    if normalize_portal_text(department_id) or normalize_portal_text(department_name):
        return True

    normalized_scope = normalize_portal_text(portal_scope)
    if not normalized_scope:
        return default_visible
    if normalized_scope != PORTAL_SCOPE_GRADUATE_ADMISSIONS:
        return False
    return supplemental_content_is_visible(normalize_portal_text(channel_tier), normalize_portal_tags(system_tags))


def announcement_extra_is_visible(extra: dict[str, Any] | None, *, default_visible: bool = True) -> bool:
    payload = dict(extra or {})
    system_tags = payload.get("system_tags")
    if not isinstance(system_tags, list):
        system_tags = payload.get("tags") or []
    return announcement_content_is_visible(
        portal_scope=str(payload.get("portal_scope") or ""),
        channel_tier=str(payload.get("channel_tier") or ""),
        system_tags=system_tags,
        department_id=str(payload.get("department_id") or ""),
        department_name=str(payload.get("department_name") or ""),
        default_visible=default_visible,
    )
