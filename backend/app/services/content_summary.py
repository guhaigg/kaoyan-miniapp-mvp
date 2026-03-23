import re

_SPACE_RE = re.compile(r"\s+")
_SUMMARY_MAX_LENGTH = 180


def normalize_text_whitespace(text: str | None) -> str | None:
    normalized = _SPACE_RE.sub(" ", str(text or "")).strip()
    return normalized or None


def summarize_text(text: str, *, max_length: int = _SUMMARY_MAX_LENGTH) -> str | None:
    normalized = normalize_text_whitespace(text)
    if not normalized:
        return None
    if len(normalized) <= max_length:
        return normalized
    return f"{normalized[: max_length - 1].rstrip()}..."
