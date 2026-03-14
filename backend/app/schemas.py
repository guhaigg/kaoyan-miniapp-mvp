from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class SilentLoginRequest(BaseModel):
    code: str = Field(min_length=1, max_length=255)


class SilentLoginResponse(BaseModel):
    visitor_token: str
    user_id: str
    user_state: Literal["shadow"]
    expires_in: int


class ContentIn(BaseModel):
    category: Literal["announcement", "adjustment"]
    title: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1)
    summary: str | None = None
    school_name: str | None = None
    source_url: str | None = None
    source_type: Literal["crawler", "manual"] = "crawler"
    published_at: datetime | None = None
    region: str | None = None
    major: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)
    raw_html: str | None = None


class ContentOut(BaseModel):
    id: str
    status: Literal["created", "updated"]


class ManualEntryRequest(BaseModel):
    action: Literal["upsert", "offline"] = "upsert"
    content: ContentIn | None = None
    content_id: str | None = None
    reason: str | None = None


class AdminSourceUpsertRequest(BaseModel):
    source_id: str | None = None
    school_name: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=255)
    base_url: str = Field(min_length=1, max_length=1024)
    source_type: Literal["official", "crawler"] = "official"
    enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)


class AdminSourceUpsertResponse(BaseModel):
    id: str
    status: Literal["created", "updated"]


class AdminSourceBulkResponse(BaseModel):
    created: int
    updated: int
    source_ids: list[str]


class SearchBaseRequest(BaseModel):
    school_name: str | None = None
    keywords: str | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    start_date: datetime | None = None
    end_date: datetime | None = None
    refresh: bool = False


class AnnouncementSearchRequest(SearchBaseRequest):
    pass


class AdjustmentSearchRequest(SearchBaseRequest):
    major: str | None = None
    region: str | None = None


class SearchItem(BaseModel):
    id: str
    category: str
    school_name: str | None
    title: str
    summary: str | None
    source_url: str | None
    source_type: str
    published_at: datetime | None
    region: str | None
    major: str | None
    updated_at: datetime


class SearchResponse(BaseModel):
    request_id: str
    mode: Literal["cache", "hybrid_refresh"]
    items: list[SearchItem]
    total: int
    page: int
    page_size: int
    source_breakdown: dict[str, int]
    last_updated_at: datetime | None
    refresh_job_id: str | None = None


class CrawlJobStatusResponse(BaseModel):
    id: str
    category: str
    status: str
    message: str | None = None
    query: dict[str, Any]
    requested_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class SchoolSuggestItem(BaseModel):
    id: str
    name: str
    province: str | None


class SchoolSuggestResponse(BaseModel):
    items: list[SchoolSuggestItem]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    app_env: str
    db: Literal["up", "down"]
    redis: Literal["up", "down"]
