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


class UserRegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=256)
    nickname: str | None = Field(default=None, max_length=120)


class UserRegisterResponse(BaseModel):
    user_id: str
    username: str
    status: str


class UserLoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=256)


class UserLoginResponse(BaseModel):
    token_type: Literal["bearer"] = "bearer"
    access_token: str
    expires_in: int
    refresh_expires_in: int
    user_id: str
    username: str


class UserRefreshRequest(BaseModel):
    refresh_token: str | None = Field(default=None, min_length=16, max_length=512)


class UserRefreshResponse(BaseModel):
    token_type: Literal["bearer"] = "bearer"
    access_token: str
    expires_in: int
    refresh_expires_in: int
    user_id: str
    username: str


class UserLogoutResponse(BaseModel):
    status: Literal["ok"]


class UserMeResponse(BaseModel):
    user_id: str
    username: str
    nickname: str | None
    status: str


class BarkNotificationSettingsRequest(BaseModel):
    enabled: bool = True
    bark_key: str | None = Field(default=None, max_length=255)


class BarkNotificationSettingsResponse(BaseModel):
    enabled: bool
    bark_key_configured: bool
    bark_endpoint: str | None


class SubscriptionCreateRequest(BaseModel):
    subscription_type: Literal["school", "major", "keyword", "region"] = "school"
    value: str = Field(min_length=1, max_length=255)
    category: Literal["all", "announcement", "adjustment"] = "all"


class SubscriptionItem(BaseModel):
    id: str
    subscription_type: str
    value: str
    category: str
    status: str
    created_at: datetime
    updated_at: datetime


class SubscriptionListResponse(BaseModel):
    total: int
    items: list[SubscriptionItem]


class AdminLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class AdminLoginResponse(BaseModel):
    username: str
    expires_in: int


class AdminChangePasswordRequest(BaseModel):
    old_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=8, max_length=256)


class AdminChangePasswordResponse(BaseModel):
    status: Literal["ok"]


class AdminRegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=256)


class AdminRegisterResponse(BaseModel):
    user_id: str
    username: str
    promoted: bool
    bootstrap: bool


class AdminMeResponse(BaseModel):
    username: str
    authenticated: bool


class AdminUserItem(BaseModel):
    id: str
    username: str
    status: str
    is_admin: bool
    nickname: str | None
    created_at: datetime
    last_login_at: datetime | None


class AdminUserListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[AdminUserItem]


class AdminUserUpdateRequest(BaseModel):
    status: Literal["active", "blocked"] | None = None
    nickname: str | None = Field(default=None, max_length=120)


class AdminAuditItem(BaseModel):
    id: str
    event_type: str
    endpoint: str
    event_data: dict[str, Any]
    ip: str | None
    created_at: datetime


class AdminAuditListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[AdminAuditItem]


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


class CrawlJobCreateRequest(BaseModel):
    category: Literal["announcement", "adjustment"]
    query: dict[str, Any] = Field(default_factory=dict)


class CrawlJobCreateResponse(BaseModel):
    job_id: str
    status: Literal["pending"]


class CrawlJobItem(BaseModel):
    id: str
    category: str
    query: dict[str, Any]
    status: Literal["pending", "running", "done", "failed"]
    message: str | None
    requested_by_user_id: str | None
    requested_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class CrawlJobListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[CrawlJobItem]


class SiteSectionCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    section_type: str = Field(min_length=1, max_length=64)
    section_url: str = Field(min_length=1, max_length=2048)
    school_name: str | None = Field(default=None, max_length=255)
    department_name: str | None = Field(default=None, max_length=255)
    department_type: str = Field(default="college", min_length=1, max_length=64)
    discovery_category: Literal["announcement", "adjustment"] = "announcement"
    source_id: str | None = None
    enabled: bool = True
    list_selector_config: dict[str, Any] = Field(default_factory=dict)


class SiteSectionItem(BaseModel):
    id: str
    name: str
    section_type: str
    section_url: str
    school_name: str | None
    department_name: str | None
    department_type: str | None
    discovery_category: str
    enabled: bool
    list_selector_config: dict[str, Any]
    last_discovered_at: datetime | None
    last_discovery_status: str | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class SiteSectionListResponse(BaseModel):
    total: int
    items: list[SiteSectionItem]


class SiteSectionDiscoverRequest(BaseModel):
    school_name: str | None = Field(default=None, max_length=255)
    department_name: str | None = Field(default=None, max_length=255)
    section_type: str | None = Field(default=None, max_length=64)
    enabled_only: bool = True


class SiteSectionDiscoverResponse(BaseModel):
    total_sections: int
    job_ids: list[str]


class SiteSectionLinkItem(BaseModel):
    id: str
    site_section_id: str
    link_url: str
    title: str | None
    link_type: Literal["html", "pdf"]
    status: str
    crawl_job_id: str | None
    published_at: datetime | None
    snapshot_meta: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class SiteSectionLinkListResponse(BaseModel):
    total: int
    items: list[SiteSectionLinkItem]


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
