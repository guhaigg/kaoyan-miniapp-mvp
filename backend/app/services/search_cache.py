import json
import threading
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any

from ..config import get_settings
from ..schemas import AdjustmentSearchRequest, AnnouncementSearchRequest, SearchResponse

try:
    from cachetools import TTLCache as _CachetoolsTTLCache
except Exception:  # pragma: no cover - local fallback for environments without cachetools installed
    _CachetoolsTTLCache = None


class _FallbackTTLCache:
    def __init__(self, maxsize: int, ttl: int) -> None:
        self.maxsize = maxsize
        self.ttl = ttl
        self._items: OrderedDict[str, tuple[datetime, Any]] = OrderedDict()

    def _purge_expired(self) -> None:
        now = datetime.now(timezone.utc)
        expired_keys = [key for key, (expires_at, _) in self._items.items() if expires_at <= now]
        for key in expired_keys:
            self._items.pop(key, None)

    def get(self, key: str, default: Any = None) -> Any:
        self._purge_expired()
        if key not in self._items:
            return default
        expires_at, value = self._items.pop(key)
        self._items[key] = (expires_at, value)
        return value

    def __setitem__(self, key: str, value: Any) -> None:
        self._purge_expired()
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=self.ttl)
        if key in self._items:
            self._items.pop(key, None)
        self._items[key] = (expires_at, value)
        while len(self._items) > self.maxsize:
            self._items.popitem(last=False)

    def clear(self) -> None:
        self._items.clear()


class SearchResponseCache:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._cache = self._build_cache()

    @staticmethod
    def _build_cache():
        settings = get_settings()
        cache_cls = _CachetoolsTTLCache or _FallbackTTLCache
        return cache_cls(maxsize=settings.search_cache_max_entries, ttl=settings.search_cache_ttl_seconds)

    def _should_cache(self, payload: AnnouncementSearchRequest | AdjustmentSearchRequest) -> bool:
        settings = get_settings()
        return not payload.refresh and payload.page <= settings.search_cache_max_page

    @staticmethod
    def _cache_key(category: str, payload: AnnouncementSearchRequest | AdjustmentSearchRequest) -> str:
        cache_payload = payload.model_dump(mode="json", exclude={"refresh"})
        normalized = {key: value for key, value in cache_payload.items() if value not in (None, "", [], {})}
        return json.dumps({"category": category, **normalized}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def get(
        self,
        category: str,
        payload: AnnouncementSearchRequest | AdjustmentSearchRequest,
        *,
        request_id: str,
    ) -> SearchResponse | None:
        if not self._should_cache(payload):
            return None
        key = self._cache_key(category, payload)
        with self._lock:
            cached = self._cache.get(key)
        if cached is None:
            return None
        response_payload = deepcopy(cached)
        response_payload["request_id"] = request_id
        response_payload["mode"] = "cache"
        return SearchResponse.model_validate(response_payload)

    def set(
        self,
        category: str,
        payload: AnnouncementSearchRequest | AdjustmentSearchRequest,
        response: SearchResponse,
    ) -> None:
        if not self._should_cache(payload):
            return
        key = self._cache_key(category, payload)
        cached_payload = response.model_dump(mode="json")
        with self._lock:
            self._cache[key] = cached_payload

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


search_response_cache = SearchResponseCache()
