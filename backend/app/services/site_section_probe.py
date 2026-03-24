from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass, field
import hashlib
import json
import re
from typing import Any, Callable
from urllib.parse import urljoin, urlparse

from lxml import etree, html

from ..config import get_settings

_SPACE_RE = re.compile(r"\s+")
_DETAIL_URL_PATTERNS = [
    r"/page\.htm(?:l)?$",
    r"/info/\d+/\d+\.htm(?:l)?$",
    r"/c\d+[a-z]?\d+/page\.htm(?:l)?$",
    r"/[a-z0-9_-]{0,12}\d{4,}\.htm(?:l)?$",
]
_LISTISH_URL_PATTERNS = [
    r"/list\d*\.htm(?:l)?$",
    r"/index\.htm(?:l)?$",
    r"/(notice|news|info|zhaosheng|admission|admissions|adjustment|tiaoji)/?$",
]
_BREADCRUMB_XPATH = (
    "//*[contains(@class, 'breadcrumb') or contains(@class, 'Bread') or contains(@class, 'path') or "
    "contains(@class, 'col_path') or contains(@class, 'crumb') or contains(text(), '当前位置')]"
)
_SELECTED_NAV_XPATH = (
    "//*[contains(@class, 'selected') or contains(@class, 'current') or contains(@class, 'active') or "
    "contains(@class, 'on') or @aria-current='page']"
)
_CANDIDATE_CONTAINER_XPATHS = [
    "//table[contains(@class, 'ArticleList')]",
    "//div[contains(@class, 'ArticleList')]",
    "//ul[contains(@class, 'news-list') or contains(@class, 'notice-list') or contains(@class, 'article-list') "
    "or contains(@class, 'news_list') or contains(@class, 'newslist') or contains(@class, 'list')]",
    "//div[contains(@class, 'news-list') or contains(@class, 'notice-list') or contains(@class, 'article-list') "
    "or contains(@class, 'content-list') or contains(@class, 'entry-list') or contains(@class, 'quick-link') "
    "or contains(@class, 'icon-list') or contains(@class, 'menu') or contains(@class, 'nav') "
    "or contains(@class, 'column') or contains(@class, 'link-list')]",
    "//section[count(.//a[@href]) >= 2]",
    "//nav[count(.//a[@href]) >= 2]",
    "//ul[count(.//a[@href]) >= 2]",
    "//table[count(.//a[@href]) >= 2]",
]
_HEADING_XPATH = (
    ".//h1[1] | .//h2[1] | .//h3[1] | .//h4[1] | .//caption[1] | "
    ".//*[contains(@class, 'title') or contains(@class, 'heading') or contains(@class, 'column-name') or "
    "contains(@class, 'module-title') or contains(@class, 'channel-name') or contains(@class, 'lanmu')][1]"
)
_CSR_MARKERS = [
    "__NUXT__",
    "__NEXT_DATA__",
    "createApp(",
    "ReactDOM.render(",
    "createRoot(",
    "axios.",
    "fetch(",
    "new Vue(",
    "v-cloak",
]
_URL_IN_SCRIPT_RE = re.compile(r"""(?P<quote>['"])(?P<url>(?:https?://|/)[^"' ]+)(?P=quote)""", re.IGNORECASE)
_SCRIPT_BLOCK_RE = re.compile(r"<script[^>]*>(?P<body>.*?)</script>", re.IGNORECASE | re.DOTALL)
_DEPARTMENT_TEXT_RE = re.compile(r"(学院|学部|系|研究院)")
_ADMISSIONS_GENERAL_TERMS = ("研究生招生", "招生信息", "招生动态", "招生简章", "专业目录", "录取", "复试")
_ADMISSIONS_MASTERS_TERMS = ("硕士", "硕士研究生", "推免", "推荐免试")
_ADMISSIONS_DOCTORAL_TERMS = ("博士", "博士研究生", "博士学位研究生", "博士招生")
_FAMILY_RULES: dict[str, dict[str, tuple[str, ...]]] = {
    "admissions": {
        "strong": ("硕士", "硕士研究生", "推免", "招生简章", "专业目录", "研究生招生"),
        "general": ("招生信息", "招生动态", "复试", "录取"),
        "hub": ("招生工作",),
    },
    "adjustment": {
        "strong": ("调剂", "预调剂", "意向采集", "缺额"),
        "general": ("调剂公告", "调剂通知"),
        "hub": ("调剂工作", "调剂信息"),
    },
    "notice": {
        "strong": ("通知公告", "公告通知"),
        "general": ("通知", "公告", "最新公告"),
        "hub": (),
    },
}


@dataclass(slots=True)
class ProbeLinkSample:
    url: str
    text: str
    link_type: str

    def as_dict(self) -> dict[str, str]:
        return {"url": self.url, "text": self.text, "link_type": self.link_type}


@dataclass(slots=True)
class ContainerCandidate:
    page_url: str
    family: str
    audience_scope: str
    role: str
    container_selector: str | None
    container_xpath: str | None
    container_signature: str
    heading_text: str | None
    detail_link_count: int
    same_container_links: list[ProbeLinkSample] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    probe_source: str = "static"

    def as_dict(self) -> dict[str, Any]:
        return {
            "page_url": self.page_url,
            "family": self.family,
            "audience_scope": self.audience_scope,
            "role": self.role,
            "container_selector": self.container_selector,
            "container_xpath": self.container_xpath,
            "container_signature": self.container_signature,
            "heading_text": self.heading_text,
            "detail_link_count": self.detail_link_count,
            "same_container_links": [item.as_dict() for item in self.same_container_links],
            "evidence": dict(self.evidence),
            "probe_source": self.probe_source,
        }


@dataclass(slots=True)
class ProbeResult:
    page_url: str
    page_title: str | None
    candidates: list[ContainerCandidate] = field(default_factory=list)
    frontier_urls: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _normalize_text(value: Any) -> str:
    return _SPACE_RE.sub(" ", str(value or "")).strip()


def normalize_url(url: str) -> str:
    return str(url or "").strip().split("#", 1)[0]


def host_scope(host: str) -> str:
    labels = [label for label in host.lower().split(".") if label]
    if len(labels) >= 3 and labels[-2:] in (["edu", "cn"], ["ac", "cn"]):
        return ".".join(labels[-3:])
    if len(labels) >= 2:
        return ".".join(labels[-2:])
    return host.lower()


def is_related_site(base_url: str, target_url: str) -> bool:
    base_host = (urlparse(base_url).netloc or "").lower()
    target_host = (urlparse(target_url).netloc or "").lower()
    if not base_host or not target_host:
        return False
    return host_scope(base_host) == host_scope(target_host)


def looks_like_detail_page_url(url: str) -> bool:
    path = (urlparse(url).path or "").lower()
    if not path or path.endswith("/"):
        return False
    return any(re.search(pattern, path) for pattern in _DETAIL_URL_PATTERNS)


def looks_like_listish_page_url(url: str) -> bool:
    path = (urlparse(url).path or "").lower()
    if not path:
        return False
    if looks_like_detail_page_url(url):
        return False
    if path.endswith("/"):
        return True
    return any(re.search(pattern, path) for pattern in _LISTISH_URL_PATTERNS)


def family_to_section_type(family: str) -> str:
    if family in {"admissions", "adjustment", "notice"}:
        return family
    return "notice"


def family_to_discovery_category(family: str) -> str:
    return "adjustment" if family == "adjustment" else "announcement"


def _parse_document(raw_html: str) -> html.HtmlElement | None:
    if not raw_html.strip():
        return None
    try:
        return html.fromstring(raw_html)
    except (etree.ParserError, ValueError):
        return None


def _extract_page_title(document: html.HtmlElement | None, raw_html: str, provided_title: str | None) -> str | None:
    if provided_title and _normalize_text(provided_title):
        return _normalize_text(provided_title)
    if document is not None:
        title_nodes = document.xpath("//title/text()")
        if title_nodes:
            title = _normalize_text(title_nodes[0])
            if title:
                return title
    match = re.search(r"<title[^>]*>(.*?)</title>", raw_html, flags=re.IGNORECASE | re.DOTALL)
    if match:
        title = _normalize_text(match.group(1))
        if title:
            return title
    return None


def _visible_node_text(node: Any) -> str:
    if node is None or not hasattr(node, "itertext"):
        return ""
    with suppress(Exception):
        return _normalize_text(" ".join(str(part or "") for part in node.itertext()))
    return ""


def _collect_texts(nodes: list[Any], limit: int = 6) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for node in nodes:
        text = _visible_node_text(node)
        if not text or text in seen:
            continue
        seen.add(text)
        items.append(text)
        if len(items) >= limit:
            break
    return items


def _collect_context(document: html.HtmlElement, page_url: str, page_title: str | None) -> dict[str, list[str] | str | None]:
    breadcrumb_nodes = document.xpath(_BREADCRUMB_XPATH)
    selected_nodes = document.xpath(_SELECTED_NAV_XPATH)
    heading_nodes = document.xpath("//h1 | //h2 | //h3")
    path = (urlparse(page_url).path or "").strip().lower()
    return {
        "page_title": page_title,
        "breadcrumbs": _collect_texts(breadcrumb_nodes),
        "selected_nav": _collect_texts(selected_nodes),
        "headings": _collect_texts(heading_nodes),
        "path": path,
    }


def _context_text(context: dict[str, list[str] | str | None], heading_text: str | None = None) -> str:
    parts: list[str] = []
    for key in ["page_title", "path"]:
        value = context.get(key)
        if isinstance(value, str) and value:
            parts.append(value)
    for key in ["breadcrumbs", "selected_nav", "headings"]:
        values = context.get(key) or []
        if isinstance(values, list):
            parts.extend(str(value) for value in values if str(value or "").strip())
    if heading_text:
        parts.append(heading_text)
    return _normalize_text(" ".join(parts))


def _weighted_keyword_score(text: str, keywords: tuple[str, ...], weight: int) -> int:
    normalized = _normalize_text(text).lower()
    score = 0
    for keyword in keywords:
        if keyword.lower() in normalized:
            score += weight
    return score


def _classify_family(stable_text: str, weak_text: str) -> tuple[str | None, dict[str, int]]:
    scores: dict[str, int] = {}
    for family, rules in _FAMILY_RULES.items():
        score = 0
        score += _weighted_keyword_score(stable_text, rules["strong"], 6)
        score += _weighted_keyword_score(stable_text, rules["general"], 3)
        score += _weighted_keyword_score(stable_text, rules["hub"], 1)
        score += _weighted_keyword_score(weak_text, rules["strong"], 2)
        score += _weighted_keyword_score(weak_text, rules["general"], 1)
        scores[family] = score
    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    if not ordered or ordered[0][1] <= 0:
        return None, scores
    return ordered[0][0], scores


def _classify_audience_scope(stable_text: str, family: str) -> str:
    normalized = _normalize_text(stable_text)
    if family != "admissions":
        return "general"
    has_masters = any(term in normalized for term in _ADMISSIONS_MASTERS_TERMS)
    has_doctoral = any(term in normalized for term in _ADMISSIONS_DOCTORAL_TERMS)
    has_general = any(term in normalized for term in _ADMISSIONS_GENERAL_TERMS)
    if has_masters and not has_doctoral:
        return "masters"
    if has_doctoral and not has_masters and any(
        term in normalized for term in ("博士研究生招生信息", "博士研究生", "博士学位研究生", "博士招生")
    ):
        return "doctoral"
    if has_general or has_masters or has_doctoral:
        return "general"
    return "unknown"


def _build_node_xpath(node: Any) -> str | None:
    if node is None or not hasattr(node, "getparent"):
        return None
    parts: list[str] = []
    current = node
    while current is not None and getattr(current, "tag", None) is not None:
        parent = current.getparent()
        if parent is None:
            parts.append(f"/{current.tag}")
            break
        same_tag_siblings = [sibling for sibling in parent if getattr(sibling, "tag", None) == current.tag]
        if len(same_tag_siblings) <= 1:
            parts.append(f"/{current.tag}")
        else:
            index = same_tag_siblings.index(current) + 1
            parts.append(f"/{current.tag}[{index}]")
        current = parent
    xpath = "".join(reversed(parts))
    return xpath or None


def _build_node_selector(node: Any) -> str | None:
    if node is None or getattr(node, "tag", None) is None:
        return None
    node_id = _normalize_text(node.get("id"))
    if node_id:
        return f"#{node_id}"
    classes = [part for part in _normalize_text(node.get("class")).split(" ") if part]
    if classes:
        return f"{node.tag}." + ".".join(classes[:3])
    return node.tag


def _extract_heading_text(node: Any) -> str | None:
    if node is None or not hasattr(node, "xpath"):
        return None
    texts = _collect_texts(node.xpath(_HEADING_XPATH), limit=1)
    if texts:
        return texts[0][:255]
    sibling = node.getprevious() if hasattr(node, "getprevious") else None
    hops = 0
    while sibling is not None and hops < 3:
        text = _visible_node_text(sibling)
        if 2 <= len(text) <= 120:
            return text[:255]
        sibling = sibling.getprevious()
        hops += 1
    return None


def _fallback_link_text(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    return path.split("/")[-1] or url


def _extract_node_links(node: Any, page_url: str) -> list[ProbeLinkSample]:
    samples: list[ProbeLinkSample] = []
    seen_urls: set[str] = set()
    if node is None or not hasattr(node, "xpath"):
        return samples
    for anchor in node.xpath(".//a[@href]"):
        href = _normalize_text(anchor.get("href"))
        if not href or href.startswith("javascript:") or href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
            continue
        absolute_url = normalize_url(urljoin(page_url, href))
        if not absolute_url or absolute_url in seen_urls:
            continue
        seen_urls.add(absolute_url)
        text = _normalize_text(" ".join(str(part or "") for part in anchor.itertext())) or _fallback_link_text(absolute_url)
        samples.append(
            ProbeLinkSample(
                url=absolute_url,
                text=text[:255],
                link_type="pdf" if absolute_url.lower().endswith(".pdf") else "html",
            )
        )
    return samples


def _split_container_links(links: list[ProbeLinkSample], page_url: str) -> tuple[list[ProbeLinkSample], list[ProbeLinkSample]]:
    detail_links: list[ProbeLinkSample] = []
    section_links: list[ProbeLinkSample] = []
    for link in links:
        if not is_related_site(page_url, link.url):
            continue
        if link.link_type == "pdf" or looks_like_detail_page_url(link.url):
            detail_links.append(link)
            continue
        normalized_text = _normalize_text(link.text)
        if looks_like_listish_page_url(link.url):
            section_links.append(link)
            continue
        if link.link_type == "html" and len(normalized_text) >= 6:
            detail_links.append(link)
            continue
        if _DEPARTMENT_TEXT_RE.search(normalized_text) or any(
            keyword in normalized_text for keyword in ("通知", "公告", "调剂", "招生", "简章", "目录")
        ):
            section_links.append(link)
    return detail_links, section_links


def _script_link_samples(raw_html: str, page_url: str) -> list[ProbeLinkSample]:
    samples: list[ProbeLinkSample] = []
    seen_urls: set[str] = set()
    for block in _SCRIPT_BLOCK_RE.finditer(raw_html):
        script_body = block.group("body") or ""
        for match in _URL_IN_SCRIPT_RE.finditer(script_body):
            absolute_url = normalize_url(urljoin(page_url, match.group("url")))
            if not absolute_url or absolute_url in seen_urls:
                continue
            if not is_related_site(page_url, absolute_url):
                continue
            seen_urls.add(absolute_url)
            samples.append(
                ProbeLinkSample(
                    url=absolute_url,
                    text=_fallback_link_text(absolute_url),
                    link_type="pdf" if absolute_url.lower().endswith(".pdf") else "html",
                )
            )
    return samples


def _json_link_samples(payload: Any, page_url: str) -> list[ProbeLinkSample]:
    samples: list[ProbeLinkSample] = []
    seen_urls: set[str] = set()
    stack: list[Any] = [payload]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            url_value = current.get("url") or current.get("href") or current.get("link")
            if isinstance(url_value, str):
                absolute_url = normalize_url(urljoin(page_url, url_value))
                if absolute_url and absolute_url not in seen_urls and is_related_site(page_url, absolute_url):
                    seen_urls.add(absolute_url)
                    label = (
                        _normalize_text(current.get("title"))
                        or _normalize_text(current.get("name"))
                        or _normalize_text(current.get("text"))
                        or _fallback_link_text(absolute_url)
                    )
                    samples.append(
                        ProbeLinkSample(
                            url=absolute_url,
                            text=label[:255],
                            link_type="pdf" if absolute_url.lower().endswith(".pdf") else "html",
                        )
                    )
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
    return samples


def _build_signature(*parts: str) -> str:
    raw = "|".join(_normalize_text(part) for part in parts if _normalize_text(part))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _build_candidate(
    *,
    page_url: str,
    page_context: dict[str, list[str] | str | None],
    heading_text: str | None,
    links: list[ProbeLinkSample],
    detail_links: list[ProbeLinkSample],
    section_links: list[ProbeLinkSample],
    role: str,
    container_selector: str | None,
    container_xpath: str | None,
    probe_source: str,
    family_filter: set[str] | None,
) -> ContainerCandidate | None:
    stable_text = _context_text(page_context, heading_text=heading_text)
    weak_text = _normalize_text(" ".join(link.text for link in links[:8]))
    family, family_scores = _classify_family(stable_text, weak_text)
    if family is None:
        return None
    if family_filter and family not in family_filter:
        return None
    audience_scope = _classify_audience_scope(stable_text, family)
    sample_links = detail_links if role == "leaf" else section_links
    signature = _build_signature(page_url, family, role, probe_source, container_xpath or "", heading_text or "")
    evidence = {
        "stable_text": stable_text[:500],
        "weak_text": weak_text[:500],
        "family_scores": family_scores,
        "section_like_count": len(section_links),
        "probe_source": probe_source,
    }
    return ContainerCandidate(
        page_url=page_url,
        family=family,
        audience_scope=audience_scope,
        role=role,
        container_selector=container_selector,
        container_xpath=container_xpath,
        container_signature=signature,
        heading_text=heading_text,
        detail_link_count=len(detail_links),
        same_container_links=sample_links[:12],
        evidence=evidence,
        probe_source=probe_source,
    )


def _filter_nested_candidates(candidates: list[ContainerCandidate]) -> list[ContainerCandidate]:
    filtered: list[ContainerCandidate] = []
    for candidate in sorted(
        candidates,
        key=lambda item: (
            item.probe_source != "browser",
            0 if item.role == "leaf" else 1,
            -(item.detail_link_count or 0),
            -len(item.container_xpath or ""),
        ),
    ):
        candidate_xpath = candidate.container_xpath or ""
        if candidate_xpath and any(
            other.page_url == candidate.page_url
            and other.family == candidate.family
            and other.role == candidate.role
            and other.container_xpath
            and other.container_xpath.startswith(candidate_xpath + "/")
            for other in filtered
        ):
            continue
        filtered.append(candidate)
    return filtered


def _probe_document_candidates(
    *,
    page_url: str,
    raw_html: str,
    page_title: str | None,
    family_filter: set[str] | None,
    probe_source: str,
) -> ProbeResult:
    document = _parse_document(raw_html)
    result = ProbeResult(page_url=page_url, page_title=_extract_page_title(document, raw_html, page_title))
    if document is None:
        return result

    page_context = _collect_context(document, page_url, result.page_title)
    raw_candidates: list[ContainerCandidate] = []
    frontier_urls: list[str] = []
    seen_frontier: set[str] = set()

    seen_nodes: set[int] = set()
    candidate_nodes: list[Any] = []
    for xpath in _CANDIDATE_CONTAINER_XPATHS:
        with suppress(Exception):
            for node in document.xpath(xpath):
                node_id = id(node)
                if node_id in seen_nodes:
                    continue
                seen_nodes.add(node_id)
                candidate_nodes.append(node)

    for node in candidate_nodes:
        links = _extract_node_links(node, page_url)
        if len(links) < 2:
            continue
        detail_links, section_links = _split_container_links(links, page_url)
        role: str | None = None
        if len(detail_links) >= 2:
            role = "leaf"
        elif len(section_links) >= 2:
            role = "hub"
        if role is None:
            continue
        candidate = _build_candidate(
            page_url=page_url,
            page_context=page_context,
            heading_text=_extract_heading_text(node),
            links=links,
            detail_links=detail_links,
            section_links=section_links,
            role=role,
            container_selector=_build_node_selector(node),
            container_xpath=_build_node_xpath(node),
            probe_source=probe_source,
            family_filter=family_filter,
        )
        if candidate is None:
            continue
        raw_candidates.append(candidate)
        if candidate.role == "hub":
            for link in candidate.same_container_links:
                if link.url not in seen_frontier:
                    seen_frontier.add(link.url)
                    frontier_urls.append(link.url)

    if not raw_candidates:
        all_links = _extract_node_links(document, page_url)
        detail_links, section_links = _split_container_links(all_links, page_url)
        if len(section_links) >= 1:
            fallback_candidate = _build_candidate(
                page_url=page_url,
                page_context=page_context,
                heading_text=result.page_title,
                links=all_links,
                detail_links=detail_links,
                section_links=section_links,
                role="hub",
                container_selector="body",
                container_xpath="/html/body",
                probe_source=probe_source,
                family_filter=family_filter,
            )
            if fallback_candidate is not None:
                raw_candidates.append(fallback_candidate)
                for link in section_links[:20]:
                    if link.url not in seen_frontier:
                        seen_frontier.add(link.url)
                        frontier_urls.append(link.url)

    script_links = _script_link_samples(raw_html, page_url)
    if script_links:
        detail_links, section_links = _split_container_links(script_links, page_url)
        role = "leaf" if len(detail_links) >= 2 else ("hub" if len(section_links) >= 2 else None)
        if role is not None:
            script_candidate = _build_candidate(
                page_url=page_url,
                page_context=page_context,
                heading_text=result.page_title,
                links=script_links,
                detail_links=detail_links,
                section_links=section_links,
                role=role,
                container_selector=None,
                container_xpath=None,
                probe_source="static",
                family_filter=family_filter,
            )
            if script_candidate is not None:
                script_candidate.evidence["signal_source"] = "script"
                raw_candidates.append(script_candidate)
                if script_candidate.role == "hub":
                    for link in script_candidate.same_container_links:
                        if link.url not in seen_frontier:
                            seen_frontier.add(link.url)
                            frontier_urls.append(link.url)

    result.candidates = _filter_nested_candidates(raw_candidates)
    result.frontier_urls = frontier_urls
    return result


def _looks_like_csr_page(raw_html: str) -> bool:
    normalized = _normalize_text(raw_html)
    if not normalized:
        return False
    return any(marker.lower() in normalized.lower() for marker in _CSR_MARKERS)


def _maybe_probe_iframes(
    *,
    page_url: str,
    raw_html: str,
    fetch_html: Callable[[str], tuple[str, str | None]] | None,
    family_filter: set[str] | None,
) -> ProbeResult:
    result = ProbeResult(page_url=page_url, page_title=None)
    if fetch_html is None:
        return result
    document = _parse_document(raw_html)
    if document is None:
        return result
    seen_urls: set[str] = set()
    for node in document.xpath("//iframe[@src]"):
        iframe_url = normalize_url(urljoin(page_url, _normalize_text(node.get("src"))))
        if not iframe_url or iframe_url in seen_urls:
            continue
        if not is_related_site(page_url, iframe_url):
            continue
        seen_urls.add(iframe_url)
        try:
            iframe_html, iframe_title = fetch_html(iframe_url)
        except Exception as exc:
            result.warnings.append(f"iframe probe failed: {exc}")
            continue
        child_result = _probe_document_candidates(
            page_url=iframe_url,
            raw_html=iframe_html,
            page_title=iframe_title,
            family_filter=family_filter,
            probe_source="iframe",
        )
        result.candidates.extend(child_result.candidates)
        result.frontier_urls.extend(child_result.frontier_urls)
        result.warnings.extend(child_result.warnings)
    return result


def _maybe_probe_browser(page_url: str, family_filter: set[str] | None) -> ProbeResult:
    settings = get_settings()
    result = ProbeResult(page_url=page_url, page_title=None)
    if not getattr(settings, "enable_site_section_browser_probe", True):
        return result
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - optional dependency
        result.warnings.append(f"browser probe unavailable: {exc}")
        return result

    xhr_samples: list[ProbeLinkSample] = []
    try:  # pragma: no cover - browser runtime dependent
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()

            def _handle_response(response) -> None:
                if response.request.resource_type not in {"xhr", "fetch"}:
                    return
                content_type = (response.headers or {}).get("content-type", "")
                if "json" not in content_type:
                    return
                try:
                    payload = response.json()
                except Exception:
                    return
                xhr_samples.extend(_json_link_samples(payload, page_url))

            page.on("response", _handle_response)
            page.goto(page_url, wait_until="domcontentloaded", timeout=int(settings.site_section_browser_probe_timeout_seconds * 1000))
            with suppress(Exception):
                page.wait_for_load_state("networkidle", timeout=int(settings.site_section_browser_probe_timeout_seconds * 1000))

            main_html = page.content()
            main_result = _probe_document_candidates(
                page_url=page.url,
                raw_html=main_html,
                page_title=page.title(),
                family_filter=family_filter,
                probe_source="browser",
            )
            result.page_title = main_result.page_title
            result.candidates.extend(main_result.candidates)
            result.frontier_urls.extend(main_result.frontier_urls)
            result.warnings.extend(main_result.warnings)

            for frame in page.frames:
                if frame == page.main_frame or not frame.url or frame.url == "about:blank":
                    continue
                if not is_related_site(page_url, frame.url):
                    continue
                with suppress(Exception):
                    frame_html = frame.content()
                    frame_result = _probe_document_candidates(
                        page_url=frame.url,
                        raw_html=frame_html,
                        page_title=frame.title() if hasattr(frame, "title") else None,
                        family_filter=family_filter,
                        probe_source="iframe",
                    )
                    result.candidates.extend(frame_result.candidates)
                    result.frontier_urls.extend(frame_result.frontier_urls)
                    result.warnings.extend(frame_result.warnings)

            browser.close()
    except Exception as exc:  # pragma: no cover - browser runtime dependent
        result.warnings.append(f"browser probe failed: {exc}")
        return result

    if xhr_samples:
        stable_text = result.page_title or (urlparse(page_url).path or page_url)
        detail_links, section_links = _split_container_links(xhr_samples, page_url)
        role = "leaf" if len(detail_links) >= 2 else ("hub" if len(section_links) >= 2 else None)
        if role is not None:
            candidate = _build_candidate(
                page_url=page_url,
                page_context={
                    "page_title": result.page_title,
                    "breadcrumbs": [],
                    "selected_nav": [],
                    "headings": [],
                    "path": urlparse(page_url).path or "",
                },
                heading_text=_normalize_text(stable_text),
                links=xhr_samples,
                detail_links=detail_links,
                section_links=section_links,
                role=role,
                container_selector=None,
                container_xpath=None,
                probe_source="xhr",
                family_filter=family_filter,
            )
            if candidate is not None:
                candidate.evidence["signal_source"] = "xhr"
                result.candidates.append(candidate)
                if candidate.role == "hub":
                    result.frontier_urls.extend(link.url for link in candidate.same_container_links)

    result.candidates = _filter_nested_candidates(result.candidates)
    deduped_frontier: list[str] = []
    seen_urls: set[str] = set()
    for url in result.frontier_urls:
        normalized = normalize_url(url)
        if not normalized or normalized in seen_urls:
            continue
        seen_urls.add(normalized)
        deduped_frontier.append(normalized)
    result.frontier_urls = deduped_frontier
    return result


def probe_section_page(
    page_url: str,
    *,
    raw_html: str | None = None,
    page_title: str | None = None,
    fetch_html: Callable[[str], tuple[str, str | None]] | None = None,
    family_filter: set[str] | None = None,
    allow_browser: bool = True,
) -> ProbeResult:
    normalized_url = normalize_url(page_url)
    if raw_html is None:
        if fetch_html is None:
            raise ValueError("fetch_html is required when raw_html is not provided")
        raw_html, page_title = fetch_html(normalized_url)

    result = _probe_document_candidates(
        page_url=normalized_url,
        raw_html=raw_html or "",
        page_title=page_title,
        family_filter=family_filter,
        probe_source="static",
    )
    iframe_result = _maybe_probe_iframes(
        page_url=normalized_url,
        raw_html=raw_html or "",
        fetch_html=fetch_html,
        family_filter=family_filter,
    )
    result.candidates.extend(iframe_result.candidates)
    result.frontier_urls.extend(iframe_result.frontier_urls)
    result.warnings.extend(iframe_result.warnings)
    result.candidates = _filter_nested_candidates(result.candidates)

    if allow_browser and (not any(candidate.role == "leaf" for candidate in result.candidates)) and _looks_like_csr_page(raw_html or ""):
        browser_result = _maybe_probe_browser(normalized_url, family_filter)
        result.candidates.extend(browser_result.candidates)
        result.frontier_urls.extend(browser_result.frontier_urls)
        result.warnings.extend(browser_result.warnings)
        result.candidates = _filter_nested_candidates(result.candidates)

    deduped_frontier: list[str] = []
    seen_frontier: set[str] = set()
    for url in result.frontier_urls:
        normalized = normalize_url(url)
        if not normalized or normalized == normalized_url or normalized in seen_frontier:
            continue
        seen_frontier.add(normalized)
        deduped_frontier.append(normalized)
    result.frontier_urls = deduped_frontier
    return result


def build_list_selector_overrides(candidate: ContainerCandidate) -> dict[str, Any]:
    overrides: dict[str, Any] = {
        "container_selector": candidate.container_selector or "",
        "container_xpath": candidate.container_xpath or "",
        "container_signature": candidate.container_signature,
        "probe_family": candidate.family,
        "probe_scope": candidate.audience_scope,
        "probe_role": candidate.role,
        "probe_source": candidate.probe_source,
        "probe_evidence": dict(candidate.evidence),
        "probe_heading": candidate.heading_text or "",
        "fallback_to_all_links": False,
    }
    if candidate.container_selector:
        overrides["css_selector"] = f"{candidate.container_selector} a[href]"
    if candidate.container_xpath:
        overrides["xpath_selector"] = f"{candidate.container_xpath}//a[@href]"
    if candidate.same_container_links:
        overrides["probe_sample_links"] = [item.as_dict() for item in candidate.same_container_links]
    return overrides


def resolve_candidate_links_for_section(
    page_url: str,
    list_config: dict[str, Any],
    *,
    raw_html: str | None = None,
    fetch_html: Callable[[str], tuple[str, str | None]] | None = None,
    family_hint: str | None = None,
    allow_browser: bool = True,
) -> list[dict[str, str]]:
    family_filter = {family_hint} if family_hint else None
    result = probe_section_page(
        page_url,
        raw_html=raw_html,
        fetch_html=fetch_html,
        family_filter=family_filter,
        allow_browser=allow_browser,
    )

    signature = _normalize_text(list_config.get("container_signature"))
    container_selector = _normalize_text(list_config.get("container_selector"))
    container_xpath = _normalize_text(list_config.get("container_xpath"))
    probe_family = _normalize_text(list_config.get("probe_family"))
    probe_scope = _normalize_text(list_config.get("probe_scope"))

    matched = None
    for candidate in result.candidates:
        if candidate.role != "leaf":
            continue
        if signature and candidate.container_signature == signature:
            matched = candidate
            break
        if container_xpath and candidate.container_xpath == container_xpath:
            matched = candidate
            break
        if container_selector and candidate.container_selector == container_selector:
            matched = candidate
            break
    if matched is None:
        for candidate in result.candidates:
            if candidate.role != "leaf":
                continue
            if probe_family and candidate.family != probe_family:
                continue
            if probe_scope and probe_scope not in {"", "unknown"} and candidate.audience_scope != probe_scope:
                continue
            matched = candidate
            break
    if matched is None:
        sample_links = list_config.get("probe_sample_links") or []
        if isinstance(sample_links, list):
            items: list[dict[str, str]] = []
            for item in sample_links:
                if not isinstance(item, dict):
                    continue
                url = normalize_url(str(item.get("url") or item.get("href") or ""))
                text = _normalize_text(item.get("text") or "")
                if url and text:
                    items.append({"href": url, "text": text})
            return items
        return []
    return [{"href": link.url, "text": link.text} for link in matched.same_container_links]
