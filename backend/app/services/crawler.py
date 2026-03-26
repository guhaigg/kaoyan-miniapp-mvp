import hashlib
import io
import re
import time
from copy import deepcopy
from contextlib import suppress
from datetime import timedelta
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from lxml import etree, html
from readability import Document
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import SessionLocal
from ..models import ContentFile, CrawlError, CrawlJob, SiteSection, SiteSectionLink, utcnow
from ..schemas import ContentIn
from .announcement_portal import (
    clear_announcement_portal_metadata,
    derive_announcement_system_tags,
    merge_announcement_tags,
    resolve_announcement_portal_metadata,
)
from .content import upsert_content
from .content_repair import extract_content_published_at_from_body
from .content_summary import summarize_text
from .nlp import extract_domain_tags
from .site_section_probe import resolve_candidate_links_for_section

with suppress(Exception):
    from pypdf import PdfReader

_UA = "Mozilla/5.0 (compatible; GeWuJianLuCrawler/0.1; +https://gewujl.cloud)"
_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_DEFAULT_EXCLUDE_TEXT_KEYWORDS = [
    "首页",
    "上一页",
    "下一页",
    "尾页",
    "末页",
    "返回",
    "关闭",
    "打印",
    "友情链接",
    "联系我们",
    "站点地图",
    "加入收藏",
    "学校首页",
]
_DEFAULT_EXCLUDE_URL_KEYWORDS = [
    "javascript:",
    "mailto:",
    "tel:",
    "/search",
    "search?",
    "login",
    "logout",
    "sso",
]
_DEFAULT_EXCLUDE_URL_SUFFIXES = [
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".zip",
    ".rar",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
]
_DEFAULT_LIST_CSS_SELECTOR = ", ".join(
    [
        ".ArticleList a[href]",
        ".article-list a[href]",
        ".news-list a[href]",
        ".notice-list a[href]",
        ".content-list a[href]",
        ".list a[href]",
        ".main a[href]",
        "article a[href]",
    ]
)
_DEFAULT_LIST_XPATH_SELECTOR = " | ".join(
    [
        "//table[contains(@class, 'ArticleList')]//a[@href]",
        "//div[contains(@class, 'article-list')]//a[@href]",
        "//ul[contains(@class, 'news-list')]//a[@href]",
        "//ul[contains(@class, 'notice-list')]//a[@href]",
        "//div[contains(@class, 'content-list')]//a[@href]",
        "//main//a[@href]",
        "//article//a[@href]",
    ]
)
_DEFAULT_DETAIL_CSS_SELECTOR = ", ".join(
    [
        "article",
        ".article",
        ".Article",
        ".article-content",
        ".wp_articlecontent",
        ".detail-content",
        ".content",
        ".news-content",
        ".entry-content",
        ".main-content",
    ]
)
_DEFAULT_DETAIL_XPATH_SELECTOR = " | ".join(
    [
        "//article",
        "//div[contains(@class, 'article')]",
        "//div[contains(@class, 'Article')]",
        "//div[contains(@class, 'wp_articlecontent')]",
        "//div[contains(@class, 'article-content')]",
        "//div[contains(@class, 'detail-content')]",
        "//div[contains(@class, 'news-content')]",
        "//div[contains(@class, 'entry-content')]",
        "//div[contains(@class, 'main-content')]",
    ]
)
_MIN_DETAIL_TEXT_LENGTH = 50
_MIN_PDF_TEXT_LENGTH = 50
_MAX_OUTBOUND_LINKS = 3
_MAX_OUTBOUND_LINK_TEXT_LENGTH = 80
_LINK_NOTICE_MAX_BODY_LENGTH = 120
_LINK_NOTICE_HINT_KEYWORDS = [
    "详见附件",
    "点击查看",
    "查看原文",
    "附件下载",
    "链接如下",
    "见附件",
    "查看详情",
]
_PUBLISHED_AT_LABEL_MARKERS = (
    "发布时间",
    "发布日期",
    "日期",
    "时间",
    "发文时间",
    "更新时间",
    "发布于",
)


class _AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[dict[str, str]] = []
        self._active_href: str | None = None
        self._active_chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attrs_map = {key.lower(): value for key, value in attrs}
        href = (attrs_map.get("href") or "").strip()
        if not href:
            return
        self._active_href = href
        self._active_chunks = []

    def handle_data(self, data: str) -> None:
        if self._active_href is None:
            return
        text = data.strip()
        if text:
            self._active_chunks.append(text)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or self._active_href is None:
            return
        self.links.append(
            {
                "href": self._active_href,
                "text": _SPACE_RE.sub(" ", " ".join(self._active_chunks)).strip(),
            }
        )
        self._active_href = None
        self._active_chunks = []


def _extract_title(raw_html: str) -> str | None:
    match = _TITLE_RE.search(raw_html)
    if not match:
        return None
    title = _SPACE_RE.sub(" ", unescape(match.group(1))).strip()
    return title or None


def _extract_text(raw_html: str) -> str:
    text = _TAG_RE.sub(" ", raw_html)
    text = _SPACE_RE.sub(" ", unescape(text)).strip()
    return text


def _coerce_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        normalized = text.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None
    return None


def _extract_links(raw_html: str) -> list[dict[str, str]]:
    parser = _AnchorParser()
    parser.feed(raw_html)
    return parser.links


def _is_pdf_url(url: str) -> bool:
    parsed = urlparse(url)
    path = (parsed.path or "").lower()
    return path.endswith(".pdf")


def _fallback_link_title(url: str) -> str:
    path = urlparse(url).path or url
    name = path.rstrip("/").split("/")[-1]
    return name or url


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _to_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            items.append(text)
    return items


def _to_optional_string(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _normalize_probe_sample_links(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    items: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or item.get("href") or "").strip()
        text = str(item.get("text") or item.get("title") or "").strip()
        if not url:
            continue
        link_type = str(item.get("link_type") or ("pdf" if url.lower().endswith(".pdf") else "html")).strip() or "html"
        items.append({"url": url, "text": text, "link_type": link_type})
    return items


def _derive_auto_include_url_regexes(section_url: str) -> list[str]:
    path = (urlparse(section_url).path or "").strip().lower()
    match = re.search(r"/(?P<column_id>\d+)/list\d*\.htm(?:l)?$", path)
    if not match:
        return []
    column_id = match.group("column_id")
    return [
        rf"/c{column_id}[a-z]?\d+/page\.htm(?:l)?$",
        rf"/info/{column_id}/\d+\.htm(?:l)?$",
    ]


def _has_manual_selector(raw_config: dict[str, Any]) -> bool:
    return bool(_to_optional_string(raw_config.get("css_selector")) or _to_optional_string(raw_config.get("xpath_selector")))


def _suggest_default_list_selector_config(_section: SiteSection) -> dict[str, Any]:
    return {
        "css_selector": _DEFAULT_LIST_CSS_SELECTOR,
        "xpath_selector": _DEFAULT_LIST_XPATH_SELECTOR,
        "fallback_to_all_links": True,
        "link_attribute": "href",
    }


def _suggest_default_detail_selector_config(_section: SiteSection) -> dict[str, Any]:
    return {
        "css_selector": _DEFAULT_DETAIL_CSS_SELECTOR,
        "xpath_selector": _DEFAULT_DETAIL_XPATH_SELECTOR,
        "fallback_to_full_text": True,
    }


def build_site_section_list_selector_config(section: SiteSection, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    base_config: dict[str, Any] = {
        "same_host_only": True,
        "min_text_length": 2,
        "exclude_text_keywords": list(_DEFAULT_EXCLUDE_TEXT_KEYWORDS),
        "exclude_url_keywords": list(_DEFAULT_EXCLUDE_URL_KEYWORDS),
        "exclude_url_suffixes": list(_DEFAULT_EXCLUDE_URL_SUFFIXES),
        "allowed_path_prefixes": [],
        "include_url_keywords": [],
        "include_text_keywords": [],
        "include_url_regexes": [],
        "exclude_url_regexes": [],
        "include_text_regexes": [],
        "exclude_text_regexes": [],
        "css_selector": "",
        "xpath_selector": "",
        "link_attribute": "href",
        "fallback_to_all_links": True,
        "container_selector": "",
        "container_xpath": "",
        "container_signature": "",
        "probe_family": "",
        "probe_scope": "",
        "probe_role": "",
        "probe_source": "",
        "probe_heading": "",
        "probe_evidence": {},
        "probe_sample_links": [],
        "portal_scope": "",
        "portal_entry_url": "",
        "channel_label": "",
        "channel_tier": "",
        "channel_keywords": [],
        "portal_path_evidence": {},
    }

    raw_config = overrides if overrides is not None else (section.list_selector_config or {})
    if not isinstance(raw_config, dict):
        return base_config

    default_selector_config = _suggest_default_list_selector_config(section)
    config = dict(base_config)
    manual_selector = _has_manual_selector(raw_config)
    config.update(default_selector_config if not manual_selector else {})
    for key in [
        "allowed_path_prefixes",
        "include_url_keywords",
        "exclude_url_keywords",
        "include_text_keywords",
        "exclude_text_keywords",
        "include_url_regexes",
        "exclude_url_regexes",
        "include_text_regexes",
        "exclude_text_regexes",
        "exclude_url_suffixes",
        "allowed_hosts",
        "channel_keywords",
    ]:
        if key in raw_config:
            config[key] = _to_string_list(raw_config.get(key))

    for key in ["css_selector", "xpath_selector", "link_attribute"]:
        if key in raw_config:
            config[key] = _to_optional_string(raw_config.get(key)) or ""

    for key in [
        "container_selector",
        "container_xpath",
        "container_signature",
        "probe_family",
        "probe_scope",
        "probe_role",
        "probe_source",
        "probe_heading",
        "portal_scope",
        "portal_entry_url",
        "channel_label",
        "channel_tier",
    ]:
        if key in raw_config:
            config[key] = _to_optional_string(raw_config.get(key)) or ""

    if "same_host_only" in raw_config:
        config["same_host_only"] = bool(raw_config.get("same_host_only"))
    if "min_text_length" in raw_config:
        try:
            config["min_text_length"] = max(0, int(raw_config.get("min_text_length") or 0))
        except (TypeError, ValueError):
            pass
    if "fallback_to_all_links" in raw_config:
        config["fallback_to_all_links"] = bool(raw_config.get("fallback_to_all_links"))
    if isinstance(raw_config.get("probe_evidence"), dict):
        config["probe_evidence"] = dict(raw_config.get("probe_evidence") or {})
    if "probe_sample_links" in raw_config:
        config["probe_sample_links"] = _normalize_probe_sample_links(raw_config.get("probe_sample_links"))
    if isinstance(raw_config.get("portal_path_evidence"), dict):
        config["portal_path_evidence"] = dict(raw_config.get("portal_path_evidence") or {})

    for pattern in _derive_auto_include_url_regexes(str(getattr(section, "section_url", "") or "")):
        if pattern not in config["include_url_regexes"]:
            config["include_url_regexes"].append(pattern)
    return config


def build_site_section_detail_selector_config(section: SiteSection, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    base_config: dict[str, Any] = {
        "css_selector": "",
        "xpath_selector": "",
        "fallback_to_full_text": True,
    }

    raw_config = overrides if overrides is not None else (section.detail_selector_config or {})
    if not isinstance(raw_config, dict):
        return base_config

    config = dict(base_config)
    if not _has_manual_selector(raw_config):
        config.update(_suggest_default_detail_selector_config(section))

    for key in ["css_selector", "xpath_selector"]:
        if key in raw_config:
            config[key] = _to_optional_string(raw_config.get(key)) or ""

    if "fallback_to_full_text" in raw_config:
        config["fallback_to_full_text"] = bool(raw_config.get("fallback_to_full_text"))
    return config


def _selector_config_has_probe_replay(config: dict[str, Any]) -> bool:
    return bool(
        _to_optional_string(config.get("container_signature"))
        or _to_optional_string(config.get("container_selector"))
        or _to_optional_string(config.get("container_xpath"))
        or _to_optional_string(config.get("probe_family"))
        or _normalize_probe_sample_links(config.get("probe_sample_links"))
    )


def _matches_keyword_list(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords if keyword)


def _matches_regex_list(text: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        try:
            if re.search(pattern, text, flags=re.IGNORECASE):
                return True
        except re.error:
            continue
    return False


def _path_allowed(path: str, prefixes: list[str]) -> bool:
    if not prefixes:
        return True
    return any(path.startswith(prefix) for prefix in prefixes)


def _matches_include_rules(*, url_text: str, normalized_text: str, config: dict[str, Any]) -> tuple[bool, bool]:
    matched = False
    has_rules = False

    include_url_keywords = config.get("include_url_keywords") or []
    if include_url_keywords:
        has_rules = True
        matched = matched or _matches_keyword_list(url_text, include_url_keywords)

    include_text_keywords = config.get("include_text_keywords") or []
    if include_text_keywords:
        has_rules = True
        matched = matched or _matches_keyword_list(normalized_text, include_text_keywords)

    include_url_regexes = config.get("include_url_regexes") or []
    if include_url_regexes:
        has_rules = True
        matched = matched or _matches_regex_list(url_text, include_url_regexes)

    include_text_regexes = config.get("include_text_regexes") or []
    if include_text_regexes:
        has_rules = True
        matched = matched or _matches_regex_list(normalized_text, include_text_regexes)

    return has_rules, matched


def _link_matches_selector_config(*, section_url: str, absolute_url: str, text: str, config: dict[str, Any]) -> bool:
    parsed_target = urlparse(absolute_url)
    parsed_section = urlparse(section_url)
    target_host = (parsed_target.netloc or "").lower()
    section_host = (parsed_section.netloc or "").lower()
    target_path = (parsed_target.path or "").strip()
    normalized_text = _SPACE_RE.sub(" ", text).strip()

    if config.get("same_host_only") and target_host and section_host and target_host != section_host:
        return False

    allowed_hosts = [host.lower() for host in config.get("allowed_hosts") or []]
    if allowed_hosts and target_host not in allowed_hosts:
        return False

    min_text_length = int(config.get("min_text_length") or 0)
    if min_text_length > 0 and len(normalized_text) < min_text_length:
        return False

    url_text = absolute_url.lower()
    if _matches_keyword_list(url_text, config.get("exclude_url_keywords") or []):
        return False
    if _matches_keyword_list(normalized_text, config.get("exclude_text_keywords") or []):
        return False
    if _matches_regex_list(url_text, config.get("exclude_url_regexes") or []):
        return False
    if _matches_regex_list(normalized_text, config.get("exclude_text_regexes") or []):
        return False

    suffixes = [suffix.lower() for suffix in config.get("exclude_url_suffixes") or []]
    if any(target_path.lower().endswith(suffix) for suffix in suffixes):
        return False

    has_include_rules, matched_include_rules = _matches_include_rules(
        url_text=url_text,
        normalized_text=normalized_text,
        config=config,
    )

    if not _path_allowed(target_path, config.get("allowed_path_prefixes") or []) and not matched_include_rules:
        return False

    if has_include_rules and not matched_include_rules:
        return False

    return True


def _parse_html_document(raw_html: str) -> html.HtmlElement | None:
    if not raw_html.strip():
        return None
    try:
        return html.fromstring(raw_html)
    except (etree.ParserError, ValueError):
        return None


def _collect_anchor_nodes(results: list[Any]) -> list[Any]:
    anchors: list[Any] = []
    seen_ids: set[int] = set()

    for result in results:
        if not hasattr(result, "xpath"):
            continue
        nodes = [result] if getattr(result, "tag", None) == "a" else result.xpath(".//a[@href]")
        for node in nodes:
            node_id = id(node)
            if node_id in seen_ids:
                continue
            seen_ids.add(node_id)
            anchors.append(node)
    return anchors


def _collect_text_nodes(results: list[Any]) -> list[Any]:
    nodes: list[Any] = []
    seen_ids: set[int] = set()

    for result in results:
        if not hasattr(result, "itertext"):
            continue
        node_id = id(result)
        if node_id in seen_ids:
            continue
        seen_ids.add(node_id)
        nodes.append(result)

    filtered: list[Any] = []
    for node in nodes:
        if any(node in other.iterancestors() for other in nodes if other is not node):
            continue
        filtered.append(node)
    return filtered


def _extract_links_by_selector(raw_html: str, config: dict[str, Any]) -> list[dict[str, str]]:
    document = _parse_html_document(raw_html)
    if document is None:
        return []

    selected_nodes: list[Any] = []
    css_selector = _to_optional_string(config.get("css_selector"))
    xpath_selector = _to_optional_string(config.get("xpath_selector"))
    if css_selector:
        try:
            selected_nodes.extend(document.cssselect(css_selector))
        except Exception:
            pass
    if xpath_selector:
        try:
            selected_nodes.extend(document.xpath(xpath_selector))
        except Exception:
            pass

    if not selected_nodes:
        return []

    link_attribute = _to_optional_string(config.get("link_attribute")) or "href"
    items: list[dict[str, str]] = []
    for node in _collect_anchor_nodes(selected_nodes):
        href = str(node.get(link_attribute) or "").strip()
        if not href:
            continue
        text = _SPACE_RE.sub(" ", " ".join(node.itertext())).strip()
        items.append({"href": href, "text": text})
    return items


def _sanitize_selected_node(node: Any) -> Any:
    if not hasattr(node, "xpath"):
        return node
    try:
        sanitized = deepcopy(node)
    except Exception:
        return node
    for noisy in sanitized.xpath(".//style | .//script | .//noscript"):
        parent = noisy.getparent()
        if parent is not None:
            parent.remove(noisy)
    for comment in sanitized.xpath(".//comment()"):
        parent = comment.getparent()
        if parent is not None:
            parent.remove(comment)
    return sanitized


def _extract_text_by_selector(raw_html: str, config: dict[str, Any]) -> str:
    document = _parse_html_document(raw_html)
    if document is None:
        return ""

    selected_nodes: list[Any] = []
    css_selector = _to_optional_string(config.get("css_selector"))
    xpath_selector = _to_optional_string(config.get("xpath_selector"))
    if css_selector:
        try:
            selected_nodes.extend(document.cssselect(css_selector))
        except Exception:
            pass
    if xpath_selector:
        try:
            selected_nodes.extend(document.xpath(xpath_selector))
        except Exception:
            pass

    chunks: list[str] = []
    for node in _collect_text_nodes(selected_nodes):
        node = _sanitize_selected_node(node)
        if hasattr(node, "itertext"):
            text = _SPACE_RE.sub(" ", " ".join(node.itertext())).strip()
        else:
            text = _SPACE_RE.sub(" ", str(node or "")).strip()
        if text:
            chunks.append(text)
    return _SPACE_RE.sub(" ", " ".join(chunks)).strip()


def _extract_published_at_from_raw_html(raw_html: str) -> datetime | None:
    normalized = _extract_text(raw_html)
    if not normalized:
        return None
    for marker in _PUBLISHED_AT_LABEL_MARKERS:
        index = normalized.find(marker)
        if index < 0:
            continue
        candidate = extract_content_published_at_from_body(normalized[index : index + 160])
        if candidate is not None:
            return candidate
    return None


def _extract_text_by_readability(raw_html: str) -> tuple[str | None, str]:
    if not raw_html.strip():
        return None, ""

    try:
        doc = Document(raw_html)
        title = _SPACE_RE.sub(" ", str(doc.short_title() or "")).strip() or None
        summary_html = str(doc.summary() or "").strip()
        if not summary_html:
            return title, ""
        return title, _extract_text(summary_html)
    except Exception:
        return None, ""


def _extract_detail_body(
    raw_html: str,
    *,
    detail_selector_config: dict[str, Any] | None,
) -> tuple[str, str, str | None]:
    selected_text = _extract_text_by_selector(raw_html, detail_selector_config or {}) if detail_selector_config else ""
    allow_fallback = bool((detail_selector_config or {}).get("fallback_to_full_text", True))
    if selected_text and (len(selected_text) >= _MIN_DETAIL_TEXT_LENGTH or not allow_fallback):
        return selected_text, "selector", None

    if not allow_fallback:
        return selected_text, "selector", None

    readability_title, readability_text = _extract_text_by_readability(raw_html)
    if len(readability_text) >= _MIN_DETAIL_TEXT_LENGTH:
        return readability_text, "readability", readability_title

    parsed_text = _extract_text(raw_html)
    return parsed_text, "plain_text", readability_title


def _build_content_tags(*parts: str | None, top_k: int = 5) -> list[str]:
    merged = " ".join(_SPACE_RE.sub(" ", str(part or "")).strip() for part in parts if str(part or "").strip())
    return extract_domain_tags(merged, top_k=top_k)


def _normalize_link_text(text: str, url: str) -> str:
    normalized = _SPACE_RE.sub(" ", str(text or "")).strip()
    if not normalized:
        normalized = _fallback_link_title(url)
    return normalized[:_MAX_OUTBOUND_LINK_TEXT_LENGTH].rstrip()


def _extract_outbound_links(raw_html: str, *, base_url: str, current_url: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    current = current_url.split("#", 1)[0]

    for item in _extract_links(raw_html):
        href = str(item.get("href") or "").strip()
        if not href or href.startswith("#") or href.startswith("javascript:") or href.startswith("mailto:") or href.startswith("tel:"):
            continue

        absolute_url = urljoin(base_url, href).split("#", 1)[0]
        if not absolute_url or absolute_url == current or absolute_url in seen_urls:
            continue

        text = _normalize_link_text(str(item.get("text") or ""), absolute_url)
        if _matches_keyword_list(text, _DEFAULT_EXCLUDE_TEXT_KEYWORDS):
            continue
        if _matches_keyword_list(absolute_url, _DEFAULT_EXCLUDE_URL_KEYWORDS):
            continue

        seen_urls.add(absolute_url)
        items.append(
            {
                "url": absolute_url,
                "text": text,
                "link_type": "pdf" if _is_pdf_url(absolute_url) else "html",
            }
        )
        if len(items) >= _MAX_OUTBOUND_LINKS:
            break

    return items


def _looks_like_link_notice(*, body: str, raw_html: str, outbound_links: list[dict[str, str]]) -> bool:
    if not outbound_links:
        return False

    normalized_body = _SPACE_RE.sub(" ", str(body or "")).strip()
    normalized_page = _SPACE_RE.sub(" ", f"{raw_html} {normalized_body}").lower()
    has_hint = any(keyword.lower() in normalized_page for keyword in _LINK_NOTICE_HINT_KEYWORDS)
    return has_hint or len(normalized_body) <= _LINK_NOTICE_MAX_BODY_LENGTH


def _build_link_notice_content(title: str, outbound_links: list[dict[str, str]]) -> tuple[str, str]:
    pdf_count = sum(1 for item in outbound_links if item.get("link_type") == "pdf")
    html_count = len(outbound_links) - pdf_count
    target_label = "附件" if pdf_count and not html_count else "链接" if html_count and not pdf_count else "链接和附件"
    summary = f"该公告正文较短，系统判断核心内容在{target_label}中，已保留目标地址供继续查看。"

    lines = [
        f"系统识别《{title}》为链接型公告。",
        "页面可直接读取的正文较少，核心信息更可能位于以下链接或附件中。",
        "建议优先打开下列目标地址查看完整公告：",
    ]
    for index, item in enumerate(outbound_links, start=1):
        type_label = "PDF附件" if item.get("link_type") == "pdf" else "目标链接"
        lines.append(f"{index}. {item.get('text') or '未命名链接'}（{type_label}）: {item.get('url')}")
    lines.append("如页面仅提供跳转入口，请以目标链接中的完整正文或附件为准。")
    return "\n".join(lines), summary


def _build_scan_pdf_notice_content(title: str, file_url: str) -> tuple[str, str]:
    summary = "系统识别到该 PDF 可用文字过少，疑似图片型或扫描件，已保留原文件链接供继续查看。"
    body = "\n".join(
        [
            f"系统已发现《{title}》对应的 PDF 附件。",
            "当前提取到的可用文字过少，判断该文件更像图片型或扫描件。",
            "MVP 阶段暂不进行 OCR，以避免额外占用服务器 CPU 和内存。",
            f"请点击原文件查看完整内容：{file_url}",
        ]
    )
    return body, summary


def _fetch_with_retry(url: str) -> httpx.Response:
    settings = get_settings()
    attempts = max(1, int(settings.crawl_retry_attempts))
    backoff_seconds = max(0.0, float(settings.crawl_retry_backoff_seconds))
    timeout = max(1.0, float(settings.crawl_fetch_timeout_seconds))
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            response = httpx.get(
                url,
                timeout=timeout,
                follow_redirects=True,
                headers={"User-Agent": _UA},
            )
            response.raise_for_status()
            return response
        except Exception as exc:
            last_error = exc
            if attempt >= attempts:
                break
            delay = backoff_seconds * (2 ** (attempt - 1))
            if delay > 0:
                time.sleep(delay)

    if last_error is None:
        raise RuntimeError("fetch failed without exception")
    raise last_error


def _download_binary_with_retry(url: str) -> tuple[bytes, str | None]:
    response = _fetch_with_retry(url)
    raw_bytes = getattr(response, "content", None)
    if raw_bytes is None:
        raw_bytes = str(getattr(response, "text", "") or "").encode("utf-8", errors="ignore")
    headers = getattr(response, "headers", {}) or {}
    mime_type = str(headers.get("content-type") or "").strip() or None
    return bytes(raw_bytes), mime_type


def _extract_pdf_text_from_bytes(file_bytes: bytes) -> str:
    if not file_bytes:
        return ""
    if "PdfReader" not in globals():
        raise RuntimeError("pypdf is not installed")

    try:
        reader = PdfReader(io.BytesIO(file_bytes))  # type: ignore[name-defined]
        chunks: list[str] = []
        for page in reader.pages:
            page_text = _SPACE_RE.sub(" ", str(page.extract_text() or "")).strip()
            if page_text:
                chunks.append(page_text)
        return "\n".join(chunks).strip()
    except Exception as exc:
        raise RuntimeError(f"pdf text extraction failed: {exc}") from exc


def _scope_meta_from_query(db: Session, query: dict[str, Any]) -> dict[str, str]:
    meta: dict[str, str] = {}
    school_id = str(query.get("school_id") or "").strip()
    department_id = str(query.get("department_id") or "").strip()
    site_section_id = str(query.get("site_section_id") or "").strip()

    if school_id:
        meta["school_id"] = school_id
    if department_id:
        meta["department_id"] = department_id
    if site_section_id:
        meta["site_section_id"] = site_section_id
        section = db.query(SiteSection).filter(SiteSection.id == site_section_id).one_or_none()
        if section is not None:
            if section.name:
                meta["site_section_name"] = str(section.name)
            if section.school_id and "school_id" not in meta:
                meta["school_id"] = section.school_id
            if section.department_id and "department_id" not in meta:
                meta["department_id"] = section.department_id
    return meta


def _finalize_ingest_extra(
    db: Session,
    *,
    category: str,
    title: str,
    summary: str | None,
    body: str,
    extra: dict[str, Any],
    query: dict[str, Any],
    section: SiteSection | None = None,
) -> dict[str, Any]:
    normalized_extra = dict(extra or {})
    normalized_extra.update(_scope_meta_from_query(db, query))
    if category != "announcement":
        return normalized_extra

    prefer_channel_label_first = bool(section is not None or str(normalized_extra.get("channel_label") or "").strip())
    preserved_scope_meta = {
        key: str(normalized_extra.get(key) or "").strip()
        for key in ("site_section_id", "site_section_name")
        if str(normalized_extra.get(key) or "").strip()
    }
    normalized_extra = clear_announcement_portal_metadata(normalized_extra)
    normalized_extra.update(preserved_scope_meta)
    normalized_extra.update(
        resolve_announcement_portal_metadata(
            source_url=str(query.get("source_url") or ""),
            title=title,
            summary=summary,
            body=body,
            section_config=dict(section.list_selector_config or {}) if section is not None else None,
            site_section_id=section.id if section is not None else None,
            site_section_name=section.name if section is not None else None,
        )
    )
    normalized_extra.update(preserved_scope_meta)
    system_tags = derive_announcement_system_tags(
        title,
        summary,
        body,
        channel_label=str(normalized_extra.get("channel_label") or ""),
        channel_tier=str(normalized_extra.get("channel_tier") or ""),
        channel_keywords=[
            str(item)
            for item in (normalized_extra.get("channel_keywords") or [])
            if str(item or "").strip()
        ],
    )
    normalized_extra["system_tags"] = system_tags
    normalized_extra["tags"] = merge_announcement_tags(
        normalized_extra.get("tags") or _build_content_tags(title, summary, body),
        system_tags,
        channel_label=str(normalized_extra.get("channel_label") or ""),
        prepend_channel_label=prefer_channel_label_first,
    )
    return normalized_extra


def _annotate_ingest_extra(
    extra: dict[str, Any],
    *,
    work_item_kind: str,
    work_item_id: str,
    crawl_mode: str,
    run_id: str | None = None,
) -> dict[str, Any]:
    next_extra = dict(extra)
    next_extra["crawl_mode"] = crawl_mode
    if work_item_kind == "crawl_job":
        next_extra["crawl_job_id"] = work_item_id
    elif work_item_kind == "workflow_step":
        next_extra["workflow_step_id"] = work_item_id
        if run_id:
            next_extra["workflow_run_id"] = run_id
    return next_extra


def ingest_url_work_item(
    db: Session,
    *,
    category: str,
    query: dict[str, Any],
    source_url: str,
    work_item_kind: str,
    work_item_id: str,
    run_id: str | None = None,
) -> tuple[str, str]:
    response = _fetch_with_retry(source_url)
    raw_html = response.text or ""
    detail_selector_config: dict[str, Any] | None = None
    site_section_id = str(query.get("site_section_id") or "").strip()
    section: SiteSection | None = None
    if site_section_id:
        section = db.query(SiteSection).filter(SiteSection.id == site_section_id).one_or_none()
        if section is not None:
            detail_selector_config = build_site_section_detail_selector_config(section)
    extracted_body, extraction_method, readability_title = _extract_detail_body(
        raw_html,
        detail_selector_config=detail_selector_config,
    )
    body = str(query.get("body") or "").strip() or extracted_body
    if not body:
        raise ValueError("parsed body is empty")

    title = (
        str(query.get("title") or "").strip()
        or readability_title
        or _extract_title(raw_html)
        or f"{category} crawl {work_item_id[:8]}"
    )
    summary = str(query.get("summary") or "").strip() or summarize_text(body)
    extra = dict(query.get("extra") or {})
    outbound_links = _extract_outbound_links(raw_html, base_url=source_url, current_url=source_url)
    if _looks_like_link_notice(body=body, raw_html=raw_html, outbound_links=outbound_links):
        body, summary = _build_link_notice_content(title, outbound_links)
        extra["notice_kind"] = "link_notice"
        extra["outbound_links"] = outbound_links
    extra = _annotate_ingest_extra(
        extra,
        work_item_kind=work_item_kind,
        work_item_id=work_item_id,
        crawl_mode="url_fetch",
        run_id=run_id,
    )
    if detail_selector_config:
        extra["detail_selector_applied"] = extraction_method == "selector"
    extra["detail_extraction_method"] = extraction_method
    extra["tags"] = _build_content_tags(title, summary, body)
    extra = _finalize_ingest_extra(
        db,
        category=category,
        title=title,
        summary=summary,
        body=body,
        extra=extra,
        query=query,
        section=section,
    )

    payload = ContentIn(
        category=category,
        title=title,
        body=body,
        summary=summary,
        school_name=(str(query.get("school_name") or "").strip() or None),
        source_url=source_url,
        source_type="crawler",
        published_at=(
            _coerce_datetime(query.get("published_at"))
            or _extract_published_at_from_raw_html(raw_html)
        ),
        region=(str(query.get("region") or "").strip() or None),
        major=(str(query.get("major") or "").strip() or None),
        extra=extra,
        raw_html=raw_html,
    )
    content, status = upsert_content(db, payload)
    return content.id, status


def ingest_file_work_item(
    db: Session,
    *,
    category: str,
    query: dict[str, Any],
    file_record: ContentFile,
    work_item_kind: str,
    work_item_id: str,
    run_id: str | None = None,
) -> tuple[str, str]:
    file_url = str(query.get("source_url") or file_record.file_url or "").strip()
    if not file_url:
        raise ValueError("file url is empty")

    link = file_record.site_section_link
    title = (
        str(query.get("title") or "").strip()
        or (str(link.title).strip() if link and link.title else "")
        or _fallback_link_title(file_url)
    )

    file_bytes, mime_type = _download_binary_with_retry(file_url)
    extracted_text = _extract_pdf_text_from_bytes(file_bytes)
    summary = None
    extra = dict(query.get("extra") or {})
    extra = _annotate_ingest_extra(
        extra,
        work_item_kind=work_item_kind,
        work_item_id=work_item_id,
        crawl_mode="pdf_file",
        run_id=run_id,
    )
    extra["content_file_id"] = file_record.id
    if link is not None:
        extra["site_section_link_id"] = link.id

    if len(extracted_text) >= _MIN_PDF_TEXT_LENGTH:
        body = extracted_text
        summary = summarize_text(extracted_text)
        extra["pdf_parse_status"] = "done"
        extra["pdf_text_extracted"] = True
    else:
        body, summary = _build_scan_pdf_notice_content(title, file_url)
        extra["pdf_parse_status"] = "needs_ocr"
        extra["pdf_text_extracted"] = False

    extra["tags"] = _build_content_tags(title, summary, extracted_text or body)
    extra = _finalize_ingest_extra(
        db,
        category=category,
        title=title,
        summary=summary,
        body=extracted_text or body,
        extra=extra,
        query=query,
        section=link.site_section if link is not None else None,
    )

    payload = ContentIn(
        category=category,
        title=title,
        body=body,
        summary=summary,
        school_name=(str(query.get("school_name") or "").strip() or None),
        source_url=file_url,
        source_type="crawler",
        published_at=_coerce_datetime(query.get("published_at")),
        region=(str(query.get("region") or "").strip() or None),
        major=(str(query.get("major") or "").strip() or None),
        extra=extra,
        raw_html=None,
    )
    content, status = upsert_content(db, payload)

    file_record.content_id = content.id
    file_record.mime_type = mime_type or file_record.mime_type or "application/pdf"
    file_record.text_extracted = extracted_text or None
    file_record.parse_status = "done" if len(extracted_text) >= _MIN_PDF_TEXT_LENGTH else "needs_ocr"
    file_record.ocr_status = "not_started" if len(extracted_text) >= _MIN_PDF_TEXT_LENGTH else "skipped_mvp"
    file_record.file_meta = {
        **dict(file_record.file_meta or {}),
        ("parse_job_id" if work_item_kind == "crawl_job" else "parse_workflow_step_id"): work_item_id,
        **({"parse_workflow_run_id": run_id} if work_item_kind == "workflow_step" and run_id else {}),
        "pdf_text_extracted": bool(extracted_text and len(extracted_text) >= _MIN_PDF_TEXT_LENGTH),
    }
    if link is not None:
        link.status = "parsed" if file_record.parse_status == "done" else "file_needs_ocr"

    return content.id, f"{status}:pdf_{file_record.parse_status}"


def discover_site_section_work_item(
    db: Session,
    *,
    section: SiteSection,
    source_url: str,
    work_item_kind: str,
    work_item_id: str,
    run_id: str | None = None,
) -> dict[str, Any]:
    if not str(source_url or "").strip():
        raise ValueError("site section url is empty")

    response = _fetch_with_retry(source_url)
    raw_html = response.text or ""
    selector_config = build_site_section_list_selector_config(section)
    discovered_links: list[dict[str, str]] = []
    if _selector_config_has_probe_replay(selector_config):

        def _fetch_probe_html(url: str) -> tuple[str, str | None]:
            probe_response = _fetch_with_retry(url)
            probe_html = probe_response.text or ""
            return probe_html, _extract_title(probe_html)

        discovered_links = resolve_candidate_links_for_section(
            source_url,
            selector_config,
            raw_html=raw_html,
            fetch_html=_fetch_probe_html,
            family_hint=str(selector_config.get("probe_family") or section.section_type or "").strip() or None,
            allow_browser=True,
        )

    if not discovered_links:
        discovered_links = _extract_links_by_selector(raw_html, selector_config)
    if not discovered_links and selector_config.get("fallback_to_all_links"):
        discovered_links = _extract_links(raw_html)
    if not discovered_links:
        section.last_discovered_at = utcnow()
        section.last_discovery_status = "done"
        section.last_error = None
        return {
            "new_links": 0,
            "html_jobs": 0,
            "pdf_files": 0,
            "workflow_run_ids": [],
            "workflow_step_ids": [],
        }

    existing_url_hashes = {
        row[0]
        for row in db.query(SiteSectionLink.link_url_hash)
        .filter(SiteSectionLink.site_section_id == section.id)
        .all()
    }
    html_jobs = 0
    pdf_files = 0
    new_links = 0
    workflow_run_ids: list[str] = []
    workflow_step_ids: list[str] = []

    for item in discovered_links:
        href = (item.get("href") or "").strip()
        if not href or href.startswith("javascript:") or href.startswith("#"):
            continue

        absolute_url = urljoin(source_url, href)
        link_text = (item.get("text") or "").strip()
        if not _link_matches_selector_config(
            section_url=source_url,
            absolute_url=absolute_url,
            text=link_text,
            config=selector_config,
        ):
            continue
        url_hash = _url_hash(absolute_url)
        if url_hash in existing_url_hashes:
            continue

        link_type = "pdf" if _is_pdf_url(absolute_url) else "html"
        title = link_text or _fallback_link_title(absolute_url)
        snapshot_meta = {
            "section_url": source_url,
            "section_type": section.section_type,
        }
        if work_item_kind == "crawl_job":
            snapshot_meta["crawl_job_id"] = work_item_id
        else:
            snapshot_meta["section_discovery_workflow_step_id"] = work_item_id
            if run_id:
                snapshot_meta["section_discovery_workflow_run_id"] = run_id
        link = SiteSectionLink(
            site_section_id=section.id,
            link_url=absolute_url,
            link_url_hash=url_hash,
            title=title,
            link_type=link_type,
            status="discovered",
            snapshot_meta=snapshot_meta,
        )
        db.add(link)
        db.flush()
        existing_url_hashes.add(url_hash)
        new_links += 1

        if link_type == "pdf":
            file_record = ContentFile(
                site_section_link_id=link.id,
                file_url=absolute_url,
                file_url_hash=_url_hash(absolute_url),
                file_type="pdf",
                mime_type="application/pdf",
                parse_status="pending",
                ocr_status="not_started",
                file_meta={
                    "site_section_id": section.id,
                    "section_url": source_url,
                    **({"crawl_job_id": work_item_id} if work_item_kind == "crawl_job" else {}),
                    **(
                        {
                            "section_discovery_workflow_step_id": work_item_id,
                            **({"section_discovery_workflow_run_id": run_id} if run_id else {}),
                        }
                        if work_item_kind == "workflow_step"
                        else {}
                    ),
                },
            )
            db.add(file_record)
            db.flush()
            if section.discovery_category == "announcement":
                from .workflow_v2 import queue_file_parse_retry

                run, step = queue_file_parse_retry(db, file_record=file_record, actor_username=None)
                workflow_run_ids.append(run.id)
                workflow_step_ids.append(step.id)
            else:
                child_job = CrawlJob(
                    category=section.discovery_category,
                    status="pending",
                    requested_at=utcnow(),
                    message=f"queued pdf parse by site section discovery {section.id}",
                    query={
                        "job_kind": "file_parse",
                        "content_file_id": file_record.id,
                        "site_section_id": section.id,
                        "site_section_link_id": link.id,
                        "source_url": absolute_url,
                        "title": title,
                        "school_name": section.school.name if section.school else None,
                        "department_name": section.department.name if section.department else None,
                        "section_type": section.section_type,
                    },
                )
                db.add(child_job)
                db.flush()
                link.crawl_job_id = child_job.id
                file_record.file_meta = {
                    **dict(file_record.file_meta or {}),
                    "parse_job_id": child_job.id,
                }
            link.status = "file_recorded"
            pdf_files += 1
            continue

        if section.discovery_category == "announcement":
            from .workflow_v2 import queue_detail_fetch_retry

            run, step = queue_detail_fetch_retry(db, link=link, actor_username=None)
            workflow_run_ids.append(run.id)
            workflow_step_ids.append(step.id)
            html_jobs += 1
            continue

        child_job = CrawlJob(
            category=section.discovery_category,
            status="pending",
            requested_at=utcnow(),
            message=f"queued by site section discovery {section.id}",
            query={
                "job_kind": "detail_fetch",
                "site_section_id": section.id,
                "site_section_link_id": link.id,
                "source_url": absolute_url,
                "title": title,
                "school_name": section.school.name if section.school else None,
                "department_name": section.department.name if section.department else None,
                "section_type": section.section_type,
            },
        )
        db.add(child_job)
        db.flush()
        link.crawl_job_id = child_job.id
        link.status = "enqueued"
        html_jobs += 1

    section.last_discovered_at = utcnow()
    section.last_discovery_status = "done"
    section.last_error = None
    return {
        "new_links": new_links,
        "html_jobs": html_jobs,
        "pdf_files": pdf_files,
        "workflow_run_ids": workflow_run_ids,
        "workflow_step_ids": workflow_step_ids,
    }


class CrawlEngine:
    def process_job_batch(self) -> int:
        settings = get_settings()
        locked_ids = self._lock_pending_rows(settings.crawl_batch_size)
        if not locked_ids:
            return 0

        processed = 0
        for job_id in locked_ids:
            with SessionLocal() as db:
                job = db.query(CrawlJob).filter(CrawlJob.id == job_id).one_or_none()
                if job is None:
                    continue
                try:
                    content_id, result = self._process_single_job(db, job)
                    job.status = "done"
                    job.finished_at = utcnow()
                    if content_id:
                        job.message = f"{result}: {content_id}"
                    else:
                        job.message = result
                    db.commit()
                    processed += 1
                except Exception as exc:
                    db.rollback()
                    self._mark_failed(job_id, exc)
                    processed += 1
        return processed

    def _lock_pending_rows(self, batch_size: int) -> list[str]:
        with SessionLocal() as db:
            settings = get_settings()
            stale_cutoff = utcnow() - timedelta(seconds=max(1, int(settings.crawl_processing_timeout_seconds)))
            query = (
                db.query(CrawlJob)
                .filter(
                    or_(
                        CrawlJob.status == "pending",
                        and_(
                            CrawlJob.status == "running",
                            CrawlJob.finished_at.is_(None),
                            CrawlJob.updated_at <= stale_cutoff,
                        ),
                    )
                )
                .order_by(CrawlJob.requested_at.asc())
                .limit(batch_size)
            )
            dialect_name = (db.bind.dialect.name if db.bind else "").lower()
            if dialect_name != "sqlite":
                query = query.with_for_update(skip_locked=True)
            rows = query.all()
            if not rows:
                return []

            now = utcnow()
            for row in rows:
                was_stale_running = row.status == "running"
                if was_stale_running:
                    query_payload = dict(row.query or {})
                    reclaim_count = int(query_payload.get("_lease_reclaim_count") or 0) + 1
                    query_payload["_lease_reclaim_count"] = reclaim_count
                    query_payload["_last_lease_reclaimed_at"] = now.isoformat()
                    row.query = query_payload
                row.status = "running"
                row.started_at = now
                row.finished_at = None
                row.updated_at = now
                row.message = "worker reclaimed expired lease" if was_stale_running else "worker picked up"
            db.commit()
            return [row.id for row in rows]

    def _process_single_job(self, db: Session, job: CrawlJob) -> tuple[str | None, str]:
        query = dict(job.query or {})
        source_url = str(query.get("source_url") or "").strip()
        content_payload = query.get("content")
        job_kind = str(query.get("job_kind") or "").strip()

        if job_kind == "family_discovery":
            from .school_cold_start import run_family_discovery_job

            return run_family_discovery_job(db, job, query)
        if job.category == "announcement" and job_kind in {"site_section_discovery", "detail_fetch", "file_parse"}:
            return self._handoff_announcement_job_to_v2(db, job, query, job_kind=job_kind)
        if job_kind == "site_section_discovery":
            return self._discover_site_section(db, job, query)
        if job_kind == "file_parse":
            return self._ingest_from_file(db, job, query)

        if query.get("simulate") is True:
            return self._ingest_simulated(db, job, query)

        if source_url:
            return self._ingest_from_url(db, job, query, source_url)

        if isinstance(content_payload, dict):
            return self._ingest_from_content_dict(db, job, query, content_payload)

        return None, "done(noop): no crawl source provided"

    def _handoff_announcement_job_to_v2(
        self,
        db: Session,
        job: CrawlJob,
        query: dict[str, Any],
        *,
        job_kind: str,
    ) -> tuple[None, str]:
        from .workflow_v2 import queue_detail_fetch_retry, queue_file_parse_retry, queue_section_discovery_retry

        next_query = dict(job.query or {})
        next_query["workflow_handoff"] = "v2"
        if job_kind == "site_section_discovery":
            site_section_id = str(query.get("site_section_id") or "").strip()
            section = db.query(SiteSection).filter(SiteSection.id == site_section_id).one_or_none()
            if section is None:
                raise ValueError("site section not found")
            run, step = queue_section_discovery_retry(
                db,
                section=section,
                actor_username=None,
                source_crawl_job_id=job.id,
            )
            next_query["result_state"] = "workflow_handoff"
            next_query["workflow_run_id"] = run.id
            next_query["workflow_step_id"] = step.id
            next_query["result_job_ids"] = [run.id]
            job.query = next_query
            return None, f"site section discovery handed off to crawler v2 workflow {run.id}"
        if job_kind == "detail_fetch":
            site_section_link_id = str(query.get("site_section_link_id") or "").strip()
            if not site_section_link_id:
                raise ValueError("site_section_link_id is required for announcement detail handoff")
            link = db.query(SiteSectionLink).filter(SiteSectionLink.id == site_section_link_id).one_or_none()
            if link is None:
                raise ValueError("site section link not found")
            run, step = queue_detail_fetch_retry(db, link=link, actor_username=None)
            next_query["result_state"] = "workflow_handoff"
            next_query["workflow_run_id"] = run.id
            next_query["workflow_step_id"] = step.id
            next_query["result_job_ids"] = [run.id]
            job.query = next_query
            return None, f"detail fetch handed off to crawler v2 workflow {run.id}"
        if job_kind == "file_parse":
            content_file_id = str(query.get("content_file_id") or "").strip()
            if not content_file_id:
                raise ValueError("content_file_id is required for announcement file parse handoff")
            file_record = db.query(ContentFile).filter(ContentFile.id == content_file_id).one_or_none()
            if file_record is None:
                raise ValueError("content file not found")
            run, step = queue_file_parse_retry(db, file_record=file_record, actor_username=None)
            next_query["result_state"] = "workflow_handoff"
            next_query["workflow_run_id"] = run.id
            next_query["workflow_step_id"] = step.id
            next_query["result_job_ids"] = [run.id]
            job.query = next_query
            return None, f"file parse handed off to crawler v2 workflow {run.id}"
        raise ValueError(f"unsupported announcement crawl job handoff: {job_kind}")

    def _discover_site_section(self, db: Session, job: CrawlJob, query: dict[str, Any]) -> tuple[None, str]:
        site_section_id = str(query.get("site_section_id") or "").strip()
        if not site_section_id:
            raise ValueError("site_section_id is required for discovery job")

        section = db.query(SiteSection).filter(SiteSection.id == site_section_id).one_or_none()
        if section is None:
            raise ValueError("site section not found")

        section_url = str(query.get("source_url") or section.section_url or "").strip()
        if not section_url:
            raise ValueError("site section url is empty")
        result = discover_site_section_work_item(
            db,
            section=section,
            source_url=section_url,
            work_item_kind="crawl_job",
            work_item_id=job.id,
        )
        return (
            None,
            f"discovery done: {result['new_links']} links, {result['html_jobs']} html jobs, {result['pdf_files']} pdf files",
        )

    def _ingest_from_url(
        self,
        db: Session,
        job: CrawlJob,
        query: dict[str, Any],
        source_url: str,
    ) -> tuple[str, str]:
        return ingest_url_work_item(
            db,
            category=job.category,
            query=query,
            source_url=source_url,
            work_item_kind="crawl_job",
            work_item_id=job.id,
        )

    def _ingest_from_file(
        self,
        db: Session,
        job: CrawlJob,
        query: dict[str, Any],
    ) -> tuple[str, str]:
        content_file_id = str(query.get("content_file_id") or "").strip()
        if not content_file_id:
            raise ValueError("content_file_id is required for file parse job")

        file_record = db.query(ContentFile).filter(ContentFile.id == content_file_id).one_or_none()
        if file_record is None:
            raise ValueError("content file not found")
        return ingest_file_work_item(
            db,
            category=job.category,
            query=query,
            file_record=file_record,
            work_item_kind="crawl_job",
            work_item_id=job.id,
        )

    def _ingest_from_content_dict(
        self,
        db: Session,
        job: CrawlJob,
        query: dict[str, Any],
        content_data: dict[str, Any],
    ) -> tuple[str, str]:
        category = str(content_data.get("category") or "").strip() or job.category
        title = str(content_data.get("title") or "").strip()
        body = str(content_data.get("body") or "").strip()
        if not title or not body:
            raise ValueError("content.title and content.body are required")

        source_url = str(content_data.get("source_url") or "").strip() or f"crawl-job://{job.id}"
        raw_html = str(content_data.get("raw_html") or "").strip() or None
        summary = str(content_data.get("summary") or "").strip() or summarize_text(body)
        extra = dict(content_data.get("extra") or {})
        extra["crawl_job_id"] = job.id
        extra["crawl_mode"] = "content_payload"
        extra["tags"] = _build_content_tags(title, summary, body)
        extra = _finalize_ingest_extra(
            db,
            category=category,
            title=title,
            summary=summary,
            body=body,
            extra=extra,
            query=query,
            section=(
                db.query(SiteSection).filter(SiteSection.id == str(query.get("site_section_id") or "").strip()).one_or_none()
                if str(query.get("site_section_id") or "").strip()
                else None
            ),
        )

        payload = ContentIn(
            category=category,
            title=title,
            body=body,
            summary=summary,
            school_name=(str(content_data.get("school_name") or "").strip() or None),
            source_url=source_url,
            source_type="crawler",
            published_at=_coerce_datetime(content_data.get("published_at")),
            region=(str(content_data.get("region") or "").strip() or None),
            major=(str(content_data.get("major") or "").strip() or None),
            extra=extra,
            raw_html=raw_html,
        )
        content, status = upsert_content(db, payload)
        return content.id, status

    def _ingest_simulated(self, db: Session, job: CrawlJob, query: dict[str, Any]) -> tuple[str, str]:
        title = str(query.get("title") or "").strip() or f"模拟抓取任务 {job.id[:8]}"
        body = str(query.get("body") or "").strip() or f"模拟抓取正文，任务 {job.id}"
        source_url = str(query.get("source_url") or "").strip() or f"crawl-job://{job.id}"
        raw_html = str(query.get("raw_html") or "").strip() or f"<html><body><h1>{title}</h1><p>{body}</p></body></html>"
        extra = dict(query.get("extra") or {})
        extra["crawl_job_id"] = job.id
        extra["crawl_mode"] = "simulate"
        extra["tags"] = _build_content_tags(title, query.get("summary"), body)
        extra = _finalize_ingest_extra(
            db,
            category=job.category,
            title=title,
            summary=str(query.get("summary") or "").strip() or summarize_text(body),
            body=body,
            extra=extra,
            query=query,
            section=(
                db.query(SiteSection).filter(SiteSection.id == str(query.get("site_section_id") or "").strip()).one_or_none()
                if str(query.get("site_section_id") or "").strip()
                else None
            ),
        )

        payload = ContentIn(
            category=job.category,
            title=title,
            body=body,
            summary=(str(query.get("summary") or "").strip() or summarize_text(body)),
            school_name=(str(query.get("school_name") or "").strip() or None),
            source_url=source_url,
            source_type="crawler",
            published_at=_coerce_datetime(query.get("published_at")),
            region=(str(query.get("region") or "").strip() or None),
            major=(str(query.get("major") or "").strip() or None),
            extra=extra,
            raw_html=raw_html,
        )
        content, status = upsert_content(db, payload)
        return content.id, status

    def _mark_failed(self, job_id: str, exc: Exception) -> None:
        with SessionLocal() as db:
            job = db.query(CrawlJob).filter(CrawlJob.id == job_id).one_or_none()
            if job is None:
                return
            query_payload = dict(job.query or {})
            source_url = str(query_payload.get("source_url") or "").strip() or None
            site_section_id = str(query_payload.get("site_section_id") or "").strip() or None
            content_file_id = str(query_payload.get("content_file_id") or "").strip() or None
            db.add(
                CrawlError(
                    source_id=None,
                    content_id=None,
                    source_url=source_url,
                    error_type=exc.__class__.__name__,
                    error_message=str(exc)[:2000],
                    payload={"crawl_job_id": job.id, "query": query_payload},
                )
            )
            if site_section_id and query_payload.get("job_kind") == "site_section_discovery":
                section = db.query(SiteSection).filter(SiteSection.id == site_section_id).one_or_none()
                if section is not None:
                    section.last_discovered_at = utcnow()
                    section.last_discovery_status = "failed"
                    section.last_error = str(exc)[:1000]
            if content_file_id and query_payload.get("job_kind") == "file_parse":
                file_record = db.query(ContentFile).filter(ContentFile.id == content_file_id).one_or_none()
                if file_record is not None:
                    file_record.parse_status = "failed"
                    file_record.file_meta = {
                        **dict(file_record.file_meta or {}),
                        "parse_error": str(exc)[:1000],
                    }
                    if file_record.site_section_link is not None:
                        file_record.site_section_link.status = "parse_failed"
            if query_payload.get("job_kind") == "family_discovery":
                query_payload["result_state"] = "failed"
                job.query = query_payload
            job.status = "failed"
            job.finished_at = utcnow()
            job.message = str(exc)[:1000]
            db.commit()


crawl_engine = CrawlEngine()
