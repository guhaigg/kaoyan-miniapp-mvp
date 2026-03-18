from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class SilentLoginRequest(BaseModel):
    code: str = Field(min_length=1, max_length=255)


class SilentLoginResponse(BaseModel):
    visitor_token: str
    user_id: str
    user_state: Literal["shadow", "bound"]
    expires_in: int
    bind_required: bool
    shadow_user_id: str | None = None
    linked_portal_user_id: str | None = None
    token_type: Literal["bearer"] | None = None
    access_token: str | None = None
    access_expires_in: int | None = None
    refresh_token: str | None = None
    refresh_expires_in: int | None = None
    username: str | None = None
    nickname: str | None = None
    status: str | None = None
    is_admin: bool = False
    is_premium: bool = False
    role: Literal["user", "premium", "admin"] | None = None
    premium_expires_at: datetime | None = None


class WechatBindResponse(BaseModel):
    status: Literal["ok"]
    linked: bool
    user_id: str
    username: str
    nickname: str | None = None
    user_status: str
    identity_id: str
    identity_type: Literal["wechat_miniapp"] = "wechat_miniapp"
    provider_subject: str
    provider_unionid: str | None = None
    token_type: Literal["bearer"] = "bearer"
    access_token: str
    access_expires_in: int
    refresh_token: str
    refresh_expires_in: int
    is_admin: bool
    is_premium: bool
    role: Literal["user", "premium", "admin"]
    premium_expires_at: datetime | None = None


class WechatBindCodeResponse(BaseModel):
    status: Literal["ok"]
    code: str
    expires_at: datetime
    expires_in: int
    bind_type: Literal["wechat_miniapp"] = "wechat_miniapp"


class WechatBindCodeClaimRequest(BaseModel):
    code: str = Field(min_length=4, max_length=32)


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
    refresh_token: str | None = None
    refresh_expires_in: int
    user_id: str
    username: str


class UserRefreshRequest(BaseModel):
    refresh_token: str | None = Field(default=None, min_length=16, max_length=512)


class UserRefreshResponse(BaseModel):
    token_type: Literal["bearer"] = "bearer"
    access_token: str
    expires_in: int
    refresh_token: str | None = None
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
    is_admin: bool
    is_premium: bool
    role: Literal["user", "premium", "admin"]
    premium_expires_at: datetime | None = None


class UserIdentityItem(BaseModel):
    id: str
    identity_type: str
    status: str
    login_name: str | None = None
    provider_app_id: str | None = None
    verified_at: datetime | None = None
    last_login_at: datetime | None = None


class UserIdentityListResponse(BaseModel):
    total: int
    items: list[UserIdentityItem]


class UserRoleItem(BaseModel):
    role_code: str
    status: str
    source: str
    created_at: datetime


class UserEntitlementItem(BaseModel):
    entitlement_code: str
    status: str
    source: str
    starts_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    order_ref: str | None = None


class UserAccountOverviewResponse(BaseModel):
    user_id: str
    username: str
    nickname: str | None
    status: str
    is_admin: bool
    is_premium: bool
    role: Literal["user", "premium", "admin"]
    premium_expires_at: datetime | None = None
    identities: list[UserIdentityItem] = Field(default_factory=list)
    roles: list[UserRoleItem] = Field(default_factory=list)
    entitlements: list[UserEntitlementItem] = Field(default_factory=list)


class UserPaymentOrderCreateRequest(BaseModel):
    duration_days: Literal[30, 90, 365] = 30
    source: Literal["web_pay", "wechat_pay"] = "web_pay"


class UserPaymentOrderItem(BaseModel):
    id: str
    entitlement_code: str
    source: str
    status: str
    duration_days: int
    amount_cents: int
    currency: str
    order_ref: str
    provider_name: str | None = None
    provider_order_ref: str | None = None
    provider_payment_ref: str | None = None
    paid_at: datetime | None = None
    canceled_at: datetime | None = None
    created_at: datetime
    meta_json: dict[str, Any] = Field(default_factory=dict)


class UserPaymentOrderListResponse(BaseModel):
    total: int
    items: list[UserPaymentOrderItem]


class UserChangePasswordRequest(BaseModel):
    old_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=8, max_length=256)


class UserChangePasswordResponse(BaseModel):
    status: Literal["ok"]


class UserNotificationHistoryItem(BaseModel):
    id: str
    outbox_id: str
    channel: str
    status: str
    created_at: datetime
    sent_at: datetime | None = None
    last_error: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class UserNotificationHistoryResponse(BaseModel):
    total: int
    items: list[UserNotificationHistoryItem]


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


class AdminChangePasswordRequest(BaseModel):
    old_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=8, max_length=256)


class AdminChangePasswordResponse(BaseModel):
    status: Literal["ok"]


class AdminResetUserPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=256)


class AdminResetUserPasswordResponse(BaseModel):
    status: Literal["ok"]
    user_id: str
    username: str


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


class AdminIdentityItem(BaseModel):
    id: str
    identity_type: str
    login_name: str | None
    status: str
    provider_subject: str | None = None
    provider_unionid: str | None = None
    verified_at: datetime | None = None
    last_login_at: datetime | None = None


class AdminRoleAssignmentItem(BaseModel):
    role_code: str
    status: str
    source: str
    created_at: datetime


class AdminEntitlementItem(BaseModel):
    entitlement_code: str
    status: str
    source: str
    starts_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    order_ref: str | None = None


class AdminPaymentOrderItem(BaseModel):
    id: str
    account_id: str
    username: str
    entitlement_code: str
    source: str
    status: str
    duration_days: int
    amount_cents: int
    currency: str
    order_ref: str
    provider_name: str | None = None
    provider_order_ref: str | None = None
    provider_payment_ref: str | None = None
    paid_at: datetime | None = None
    canceled_at: datetime | None = None
    created_at: datetime
    meta_json: dict[str, Any] = Field(default_factory=dict)


class AdminPaymentOrderListResponse(BaseModel):
    total: int
    items: list[AdminPaymentOrderItem]


class AdminMarkPaymentOrderPaidRequest(BaseModel):
    provider_payment_ref: str | None = Field(default=None, max_length=128)


class AdminUserItem(BaseModel):
    id: str
    username: str
    status: str
    is_admin: bool
    is_premium: bool
    premium_expires_at: datetime | None
    nickname: str | None
    identities: list[AdminIdentityItem] = Field(default_factory=list)
    roles: list[AdminRoleAssignmentItem] = Field(default_factory=list)
    entitlements: list[AdminEntitlementItem] = Field(default_factory=list)
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


class AdminUserPromoteRequest(BaseModel):
    target_role: Literal["premium", "admin"] = "admin"
    premium_days: int | None = Field(default=None, ge=1, le=3650)


class AdminUserDemoteRequest(BaseModel):
    target_role: Literal["user", "premium"] = "user"
    premium_days: int | None = Field(default=30, ge=1, le=3650)


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


class AdminContentFingerprintStatsResponse(BaseModel):
    total_contents: int
    fingerprinted_contents: int
    pending_contents: int
    collision_contents: int
    coverage_ratio: float


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
    detail_selector_config: dict[str, Any] = Field(default_factory=dict)


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
    detail_selector_config: dict[str, Any]
    suggested_list_selector_config: dict[str, Any]
    suggested_detail_selector_config: dict[str, Any]
    last_discovered_at: datetime | None
    last_discovery_status: str | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class SiteSectionListResponse(BaseModel):
    total: int
    items: list[SiteSectionItem]


class SiteSectionUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    section_type: str | None = Field(default=None, min_length=1, max_length=64)
    section_url: str | None = Field(default=None, min_length=1, max_length=2048)
    discovery_category: Literal["announcement", "adjustment"] | None = None
    source_id: str | None = None
    enabled: bool | None = None
    list_selector_config: dict[str, Any] | None = None
    detail_selector_config: dict[str, Any] | None = None


class SiteSectionDiscoverRequest(BaseModel):
    school_name: str | None = Field(default=None, max_length=255)
    department_name: str | None = Field(default=None, max_length=255)
    section_type: str | None = Field(default=None, max_length=64)
    enabled_only: bool = True


class SiteSectionDiscoverResponse(BaseModel):
    total_sections: int
    job_ids: list[str]


class SiteSectionBackfillSelectorConfigRequest(BaseModel):
    school_name: str | None = Field(default=None, max_length=255)
    department_name: str | None = Field(default=None, max_length=255)
    section_type: str | None = Field(default=None, max_length=64)
    enabled_only: bool = True
    overwrite_existing: bool = False


class SiteSectionBackfillSelectorConfigResponse(BaseModel):
    total_sections: int
    updated_sections: int
    items: list[SiteSectionItem]


class SiteSectionSelectorPreviewRequest(BaseModel):
    list_selector_config: dict[str, Any] | None = None
    detail_selector_config: dict[str, Any] | None = None
    sample_link_url: str | None = Field(default=None, max_length=2048)


class SiteSectionSelectorPreviewLinkItem(BaseModel):
    url: str
    text: str
    link_type: Literal["html", "pdf"]


class SiteSectionSelectorPreviewResponse(BaseModel):
    section_url: str
    suggested_list_selector_config: dict[str, Any]
    suggested_detail_selector_config: dict[str, Any]
    list_match_count: int
    list_preview_items: list[SiteSectionSelectorPreviewLinkItem]
    detail_preview_url: str | None
    detail_title: str | None
    detail_excerpt: str | None
    detail_extraction_method: Literal["selector", "readability", "plain_text"] | None
    warnings: list[str]


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


class ContentFileItem(BaseModel):
    id: str
    content_id: str | None
    site_section_link_id: str | None
    site_section_id: str | None
    site_section_name: str | None
    school_name: str | None
    link_title: str | None
    content_title: str | None
    file_url: str
    file_type: str
    mime_type: str | None
    text_excerpt: str | None
    parse_status: str
    ocr_status: str
    file_meta: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ContentFileListResponse(BaseModel):
    total: int
    items: list[ContentFileItem]


class ContentFileRetryParseResponse(BaseModel):
    content_file_id: str
    job_id: str
    status: Literal["queued", "existing"]
    parse_status: str


class MonitorTargetCreateRequest(BaseModel):
    scope_type: Literal["school", "department", "section"]
    school_id: str | None = None
    school_name: str | None = Field(default=None, max_length=255)
    department_id: str | None = None
    department_name: str | None = Field(default=None, max_length=255)
    site_section_id: str | None = None
    status: Literal["active", "paused", "deleted"] | None = None
    check_interval_minutes: int = Field(default=60, ge=5, le=10080)


class MonitorTargetUpdateRequest(BaseModel):
    scope_type: Literal["school", "department", "section"] | None = None
    school_id: str | None = None
    school_name: str | None = Field(default=None, max_length=255)
    department_id: str | None = None
    department_name: str | None = Field(default=None, max_length=255)
    site_section_id: str | None = None
    status: Literal["active", "paused", "deleted"] | None = None
    check_interval_minutes: int | None = Field(default=None, ge=5, le=10080)


class MonitorTargetItem(BaseModel):
    id: str
    user_id: str
    scope_type: str
    school_id: str | None
    department_id: str | None
    site_section_id: str | None
    status: str
    check_interval_minutes: int
    last_checked_at: datetime | None
    last_hit_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MonitorTargetListResponse(BaseModel):
    total: int
    items: list[MonitorTargetItem]


class MonitorKeywordCreateRequest(BaseModel):
    keyword: str = Field(min_length=1, max_length=255)
    match_mode: Literal["contains"] = "contains"
    weight: int = Field(default=1, ge=1, le=100)


class MonitorKeywordBatchCreateRequest(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    match_mode: Literal["contains"] = "contains"
    weight: int = Field(default=1, ge=1, le=100)


class MonitorKeywordUpdateRequest(BaseModel):
    status: Literal["active", "disabled"] | None = None
    weight: int | None = Field(default=None, ge=1, le=100)


class MonitorKeywordItem(BaseModel):
    id: str
    user_id: str
    monitor_target_id: str
    keyword: str
    match_mode: str
    weight: int
    status: str
    created_at: datetime
    updated_at: datetime


class MonitorKeywordListResponse(BaseModel):
    total: int
    items: list[MonitorKeywordItem]


class MonitorHitItem(BaseModel):
    id: str
    user_id: str
    monitor_target_id: str
    content_id: str
    site_section_id: str | None
    matched_keywords: list[str]
    match_score: int
    hit_reason: str | None
    pushed_inapp: bool
    pushed_bark: bool
    created_at: datetime
    content_title: str | None = None
    content_category: str | None = None


class MonitorHitListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[MonitorHitItem]


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
    tags: list[str] = Field(default_factory=list)
    notice_kind: str | None = None
    pdf_parse_status: str | None = None
    source_url: str | None
    source_type: str
    published_at: datetime | None
    region: str | None
    major: str | None
    updated_at: datetime


class SearchResponse(BaseModel):
    request_id: str
    mode: Literal["cache", "hybrid_refresh"]
    authenticated: bool = False
    access_limited: bool = False
    preview_limit: int | None = None
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


class SchoolBulkImportResponse(BaseModel):
    total_rows: int
    created_schools: int
    existing_schools: int
    created_departments: int
    existing_departments: int


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    app_env: str
    db: Literal["up", "down"]
    redis: Literal["up", "down"]
