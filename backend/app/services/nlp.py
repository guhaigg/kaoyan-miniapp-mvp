from __future__ import annotations

import re

import jieba
import jieba.analyse

_SYSTEM_KEYWORD_ALIASES: dict[str, tuple[str, ...]] = {
    "调剂": ("调剂", "调剂系统", "调剂公告", "调剂通知", "接收调剂", "调剂缺额"),
    "复试": ("复试", "复试安排", "复试公告", "复试通知", "复试名单", "复试细则"),
    "复试线": ("复试线", "复试分数线", "复试基本分数线", "基本分数线"),
    "拟录取": ("拟录取", "拟录取名单", "待录取"),
    "推免": ("推免", "推免生", "推荐免试", "免试研究生"),
    "夏令营": ("夏令营", "优秀大学生夏令营"),
    "招生简章": ("招生简章", "招生章程"),
    "录取名单": ("录取名单", "拟录取名单", "录取结果"),
    "缺额": ("缺额", "缺额信息", "缺额计划"),
    "非全日制": ("非全日制",),
    "全日制": ("全日制",),
    "专硕": ("专硕", "专业学位"),
    "学硕": ("学硕", "学术学位"),
    "电子信息": ("电子信息",),
    "0854": ("0854", "085400"),
}

_SYSTEM_KEYWORD_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "调剂": (
        re.compile(r"调剂"),
        re.compile(r"接收调剂"),
    ),
    "复试": (
        re.compile(r"复试"),
        re.compile(r"复试(安排|通知|名单|细则)"),
    ),
    "复试线": (
        re.compile(r"复试.*分数线"),
        re.compile(r"基本分数线"),
        re.compile(r"复试线"),
    ),
    "拟录取": (
        re.compile(r"拟录取"),
        re.compile(r"待录取"),
    ),
    "推免": (
        re.compile(r"推免"),
        re.compile(r"推荐免试"),
        re.compile(r"免试研究生"),
    ),
    "夏令营": (re.compile(r"夏令营"),),
    "招生简章": (
        re.compile(r"招生简章"),
        re.compile(r"招生章程"),
    ),
    "录取名单": (
        re.compile(r"录取名单"),
        re.compile(r"录取结果"),
    ),
    "缺额": (
        re.compile(r"缺额"),
        re.compile(r"缺额(信息|计划)"),
    ),
    "非全日制": (re.compile(r"非全日制"),),
    "全日制": (
        re.compile(r"(?<!非)全日制"),
        re.compile(r"全日制专业"),
    ),
    "专硕": (
        re.compile(r"专硕"),
        re.compile(r"专业学位"),
    ),
    "学硕": (
        re.compile(r"学硕"),
        re.compile(r"学术学位"),
    ),
    "电子信息": (re.compile(r"电子信息"),),
    "0854": (re.compile(r"\b0854(?:00)?\b"),),
}

_ADJUSTMENT_SIGNAL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"调剂"),
    re.compile(r"接收调剂"),
    re.compile(r"接受调剂"),
    re.compile(r"调剂系统"),
    re.compile(r"调剂公告"),
    re.compile(r"调剂通知"),
    re.compile(r"调剂复试"),
    re.compile(r"调剂考生"),
    re.compile(r"调剂志愿"),
    re.compile(r"调剂缺额"),
    re.compile(r"缺额(信息|计划|人数|名额)?"),
    re.compile(r"意向采集"),
)

_ALIAS_TO_CANONICAL = {
    alias.strip().lower(): canonical
    for canonical, aliases in _SYSTEM_KEYWORD_ALIASES.items()
    for alias in (canonical, *aliases)
}

_DOMAIN_WORDS = sorted({canonical for canonical in _SYSTEM_KEYWORD_ALIASES} | {"085400"})

_STOP_WORDS = {
    "关于",
    "通知",
    "公告",
    "公示",
    "发布",
    "名单",
    "工作",
    "安排",
    "学校",
    "大学",
    "学院",
    "研究生院",
    "研究生",
    "相关",
    "要求",
    "办法",
    "一览",
    "附件",
    "下载",
    "点击",
    "详情",
    "首页",
    "阅读",
    "作者",
    "编辑",
    "访问量",
    "版权所有",
    "保留所有权利",
    "进行",
    "开展",
    "组织",
    "规定",
    "的",
    "了",
}

_ASCII_ALLOWLIST = {"mba", "mpa", "emba", "mpacc"}
_NOISE_TOKENS = {
    "https",
    "http",
    "www",
    "edu",
    "cn",
    "com",
    "net",
    "org",
    "html",
    "htm",
    "php",
    "jsp",
    "pdf",
    "doc",
    "docx",
    "xls",
    "xlsx",
    "graduate",
    "yjs",
    "yz",
    "news",
    "list",
    "view",
    "detail",
    "article",
    "auto",
    "captured",
}

_URL_RE = re.compile(r"http[s]?://(?:[a-zA-Z0-9]|[$\-_.+!*'(),]|(?:%[0-9a-fA-F]{2}))+")
_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_PATH_RE = re.compile(r"\b[a-zA-Z0-9_-]+\.(?:html?|pdf|docx?|xlsx?|jsp|php)\b")
_MULTISPACE_RE = re.compile(r"\s+")
_ASCII_WORD_RE = re.compile(r"^[a-zA-Z]+$")
_ALNUM_WORD_RE = re.compile(r"^[a-zA-Z0-9_-]+$")
_MAJOR_CODE_RE = re.compile(r"(?<!\d)(0\d{3,5})(?!\d)")

for _word in _DOMAIN_WORDS:
    jieba.add_word(_word, freq=10_000)


def clean_text_for_tagging(text: str) -> str:
    normalized = str(text or "").strip()
    if not normalized:
        return ""

    normalized = _URL_RE.sub(" ", normalized)
    normalized = _EMAIL_RE.sub(" ", normalized)
    normalized = _PATH_RE.sub(" ", normalized)
    normalized = re.sub(r"\b[a-zA-Z]{1,3}\b", " ", normalized)
    normalized = _MULTISPACE_RE.sub(" ", normalized)
    return normalized.strip()


def canonicalize_keyword(keyword: str | None) -> str:
    value = str(keyword or "").strip()
    if not value:
        return ""
    lowered = value.lower()
    return _ALIAS_TO_CANONICAL.get(lowered, value)


def extract_system_keywords(text: str, *, top_k: int | None = None) -> list[str]:
    normalized = clean_text_for_tagging(text)
    if not normalized:
        return []

    found: list[str] = []
    for canonical, patterns in _SYSTEM_KEYWORD_PATTERNS.items():
        if any(pattern.search(normalized) for pattern in patterns):
            found.append(canonical)

    if top_k is not None and top_k > 0:
        return found[:top_k]
    return found


def _is_noise_token(token: str) -> bool:
    lowered = token.lower()
    if lowered in _STOP_WORDS or lowered in _NOISE_TOKENS:
        return True
    if any(mark in token for mark in ("://", "/", "@", ".")):
        return True
    if _ASCII_WORD_RE.fullmatch(token):
        return lowered not in _ASCII_ALLOWLIST
    if token.isdigit():
        return not (token.startswith("0") and 4 <= len(token) <= 6)
    if _ALNUM_WORD_RE.fullmatch(token) and not any(ch.isdigit() for ch in token):
        return True
    return False


def normalize_tag(token: str | None) -> str:
    value = canonicalize_keyword(token)
    if not value:
        return ""
    if _is_noise_token(value):
        return ""
    return value.strip()


def extract_domain_tags(text: str, *, top_k: int = 5) -> list[str]:
    normalized = clean_text_for_tagging(text)
    if not normalized:
        return []

    items: list[str] = []
    seen: set[str] = set()

    for tag in extract_system_keywords(normalized):
        clean = normalize_tag(tag)
        if not clean or clean in seen:
            continue
        seen.add(clean)
        items.append(clean)
        if len(items) >= top_k:
            return items

    tags = jieba.analyse.extract_tags(normalized, topK=max(1, top_k * 4))
    for tag in tags:
        clean = normalize_tag(str(tag or "").strip())
        if not clean or clean in seen:
            continue
        seen.add(clean)
        items.append(clean)
        if len(items) >= top_k:
            break

    return items


def keyword_matches_content(keyword: str, content_text: str, content_tags: list[str] | tuple[str, ...] | set[str]) -> bool:
    normalized_keyword = str(keyword or "").strip().lower()
    if not normalized_keyword:
        return False

    normalized_text = str(content_text or "").strip().lower()
    canonical_keyword = canonicalize_keyword(normalized_keyword)
    canonical_lower = canonical_keyword.lower()
    tag_set = {normalize_tag(tag).lower() for tag in content_tags if normalize_tag(tag)}

    if normalized_keyword in normalized_text:
        return True
    if canonical_lower and canonical_lower in tag_set:
        return True

    for alias, canonical in _ALIAS_TO_CANONICAL.items():
        if canonical != canonical_keyword:
            continue
        if alias and alias in normalized_text:
            return True

    return False


def infer_content_category(
    *,
    title: str,
    summary: str | None = None,
    body: str,
    tags: list[str] | tuple[str, ...] | set[str] | None = None,
    existing_category: str | None = None,
) -> str:
    normalized_existing = str(existing_category or "").strip().lower()
    if normalized_existing == "adjustment":
        return "adjustment"

    normalized_text = clean_text_for_tagging(" ".join(part for part in [title, summary or "", body] if part))
    normalized_tags = {normalize_tag(tag) for tag in (tags or []) if normalize_tag(tag)}
    system_keywords = set(extract_system_keywords(normalized_text))

    score = 0
    if "调剂" in normalized_tags or "调剂" in system_keywords:
        score += 3
    if "缺额" in normalized_tags or "缺额" in system_keywords:
        score += 2

    if any(pattern.search(normalized_text) for pattern in _ADJUSTMENT_SIGNAL_PATTERNS):
        score += 2

    if "调剂" in normalized_text and ("复试" in normalized_text or "缺额" in normalized_text):
        score += 1

    if score >= 2:
        return "adjustment"
    return "announcement"


def extract_adjustment_meta(
    *,
    title: str,
    summary: str | None = None,
    body: str,
    tags: list[str] | tuple[str, ...] | set[str] | None = None,
) -> dict[str, object]:
    normalized_text = clean_text_for_tagging(" ".join(part for part in [title, summary or "", body] if part))
    normalized_tags = {normalize_tag(tag) for tag in (tags or []) if normalize_tag(tag)}

    major_codes: list[str] = []
    for matched in _MAJOR_CODE_RE.findall(normalized_text):
        if matched not in major_codes:
            major_codes.append(matched)
        if len(major_codes) >= 5:
            break

    study_modes: list[str] = []
    has_parttime = "非全日制" in normalized_text or "非全日制" in normalized_tags
    has_fulltime = (
        "全日制" in normalized_tags
        or ("全日制" in normalized_text and "非全日制" not in normalized_text)
    )
    if has_fulltime:
        study_modes.append("fulltime")
    if has_parttime:
        study_modes.append("parttime")

    has_vacancy = False
    if (
        "缺额" in normalized_text
        or "调剂缺额" in normalized_text
        or "缺额" in normalized_tags
        or "调剂" in normalized_tags
    ):
        has_vacancy = True

    return {
        "major_codes": major_codes,
        "study_modes": study_modes,
        "has_vacancy": has_vacancy,
    }
