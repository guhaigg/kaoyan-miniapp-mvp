import axios, { AxiosError, AxiosRequestConfig, InternalAxiosRequestConfig } from "axios";
import { useAppStore } from "./store";

export const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL || "/api/v1").replace(/\/+$/, "");

export class ApiError extends Error {
  status: number;
  payload: unknown;

  constructor(message: string, status: number, payload: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 15_000,
  withCredentials: true,
});

let isRefreshing = false;
let failedQueue: Array<{ resolve: (token: string) => void; reject: (error: unknown) => void }> = [];

function processQueue(error: unknown, token: string | null = null) {
  failedQueue.forEach((promise) => {
    if (error) {
      promise.reject(error);
      return;
    }
    promise.resolve(token as string);
  });
  failedQueue = [];
}

function shouldSkipRefresh(originalRequest?: (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined) {
  const url = originalRequest?.url || "";
  if (!url) return true;
  if (url.includes("/admin/")) return true;
  if (url.includes("/auth/login")) return true;
  if (url.includes("/auth/register")) return true;
  if (url.includes("/auth/refresh")) return true;
  if (url.includes("/auth/logout")) return true;
  return false;
}

function extractMessage(payload: unknown, fallback: string) {
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
  }
  return fallback;
}

function normalizeApiError(error: unknown): ApiError {
  if (error instanceof ApiError) {
    return error;
  }
  if (axios.isAxiosError(error)) {
    const status = error.response?.status ?? 0;
    const payload = error.response?.data;
    const fallback = status ? `Request failed with status ${status}` : "Network request failed";
    return new ApiError(extractMessage(payload, fallback), status, payload);
  }
  return new ApiError("Network request failed", 0, null);
}

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = useAppStore.getState().portalAuth?.accessToken;
  if (token && config.headers) {
    config.headers["X-User-Token"] = token;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined;
    if (
      error.response?.status !== 401 ||
      !originalRequest ||
      originalRequest._retry ||
      shouldSkipRefresh(originalRequest)
    ) {
      return Promise.reject(error);
    }

    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        failedQueue.push({ resolve, reject });
      })
        .then((token) => {
          originalRequest.headers = originalRequest.headers || {};
          originalRequest.headers["X-User-Token"] = token;
          return api(originalRequest);
        })
        .catch((queueError) => Promise.reject(queueError));
    }

    originalRequest._retry = true;
    isRefreshing = true;

    try {
      const { data } = await axios.post<UserLoginResponse>(
        `${API_BASE}/auth/refresh`,
        {},
        {
          withCredentials: true,
          timeout: 15_000,
        },
      );

      useAppStore.getState().setPortalAuthFromToken({
        tokenType: data.token_type,
        accessToken: data.access_token,
        expiresIn: data.expires_in,
        refreshExpiresIn: data.refresh_expires_in,
        userId: data.user_id,
        username: data.username,
      });

      processQueue(null, data.access_token);
      originalRequest.headers = originalRequest.headers || {};
      originalRequest.headers["X-User-Token"] = data.access_token;
      return api(originalRequest);
    } catch (refreshError) {
      processQueue(refreshError, null);
      useAppStore.getState().logout();
      useAppStore.getState().showToast("会话已过期", "请重新接入系统", "urgent");
      return Promise.reject(refreshError);
    } finally {
      isRefreshing = false;
    }
  },
);

async function request<T>(config: AxiosRequestConfig): Promise<T> {
  try {
    const response = await api.request<T>(config);
    return response.data;
  } catch (error) {
    throw normalizeApiError(error);
  }
}

export type UserLoginResponse = {
  token_type: "bearer";
  access_token: string;
  expires_in: number;
  refresh_token?: string | null;
  refresh_expires_in: number;
  user_id: string;
  username: string;
};

export type UserRegisterResponse = {
  user_id: string;
  username: string;
  status: string;
};

export type UserMeResponse = {
  user_id: string;
  username: string;
  nickname: string | null;
  status: string;
  is_admin: boolean;
  is_premium: boolean;
  role: "user" | "premium" | "admin";
  premium_expires_at: string | null;
};

export type UserIdentityItem = {
  id: string;
  identity_type: string;
  status: string;
  login_name: string | null;
  provider_app_id: string | null;
  verified_at: string | null;
  last_login_at: string | null;
};

export type UserIdentityListResponse = {
  total: number;
  items: UserIdentityItem[];
};

export type UserRoleItem = {
  role_code: string;
  status: string;
  source: string;
  created_at: string;
};

export type UserEntitlementItem = {
  entitlement_code: string;
  status: string;
  source: string;
  starts_at: string;
  expires_at: string | null;
  revoked_at: string | null;
  order_ref?: string | null;
};

export type UserAccountOverviewResponse = {
  user_id: string;
  username: string;
  nickname: string | null;
  status: string;
  is_admin: boolean;
  is_premium: boolean;
  role: "user" | "premium" | "admin";
  premium_expires_at: string | null;
  identities: UserIdentityItem[];
  roles: UserRoleItem[];
  entitlements: UserEntitlementItem[];
};

export type UserPaymentOrderItem = {
  id: string;
  entitlement_code: string;
  source: string;
  status: string;
  duration_days: number;
  amount_cents: number;
  currency: string;
  order_ref: string;
  provider_name: string | null;
  provider_order_ref: string | null;
  provider_payment_ref: string | null;
  paid_at: string | null;
  canceled_at: string | null;
  created_at: string;
  meta_json: Record<string, unknown>;
};

export type UserPaymentOrderListResponse = {
  total: number;
  items: UserPaymentOrderItem[];
};

export type UserPaymentOrderCreateRequest = {
  duration_days: 30 | 90 | 365;
  source?: "web_pay" | "wechat_pay";
};

export type WechatBindCodeResponse = {
  status: "ok";
  code: string;
  expires_at: string;
  expires_in: number;
  bind_type: "wechat_miniapp";
};

export type SearchItem = {
  id: string;
  category: string;
  school_name: string | null;
  title: string;
  summary: string | null;
  tags: string[];
  notice_kind: string | null;
  pdf_parse_status: string | null;
  source_url: string | null;
  source_type: string;
  published_at: string | null;
  region: string | null;
  major: string | null;
  adjustment_major_codes: string[];
  adjustment_study_modes: string[];
  adjustment_has_vacancy: boolean | null;
  historical_adjustment: {
    sample_years: number[];
    source_types: string[];
    sample_count: number;
    min_score: number | null;
    avg_score: number | null;
    max_score: number | null;
    candidate_score: number | null;
    outlook: "high" | "reach" | "cautious" | null;
    outlook_label: string | null;
    future_program_count: number | null;
  } | null;
  mentor_radar: {
    review_count: number;
    mentor_count: number;
    warning_count: number;
    positive_count: number;
    top_tags: string[];
    risk_label: string | null;
  } | null;
  release_timing: {
    sample_count: number;
    sample_years: number[];
    peak_hour: number | null;
    peak_hour_bucket: string | null;
    window_start_md: string | null;
    window_end_md: string | null;
    signal_label: string | null;
    signal_detail: string | null;
  } | null;
  updated_at: string;
};

export type SearchResponse = {
  request_id: string;
  mode: "cache" | "hybrid_refresh";
  authenticated: boolean;
  access_limited: boolean;
  preview_limit: number | null;
  items: SearchItem[];
  total: number;
  page: number;
  page_size: number;
  source_breakdown: Record<string, number>;
  last_updated_at: string | null;
  refresh_job_id: string | null;
};

export type SearchBaseRequest = {
  school_name?: string;
  keywords?: string;
  page?: number;
  page_size?: number;
  start_date?: string;
  end_date?: string;
  refresh?: boolean;
};

export type AdjustmentSearchRequest = SearchBaseRequest & {
  major?: string;
  region?: string;
  candidate_score?: number;
};

export type SchoolBulkImportResponse = {
  total_rows: number;
  created_schools: number;
  existing_schools: number;
  created_departments: number;
  existing_departments: number;
};

export type SchoolImportSeedSchoolItem = {
  rank: number | null;
  school_code: string | null;
  school_name: string;
  region_name: string | null;
  school_category: string | null;
  adjustment_count: number | null;
  top_departments: string[];
};

export type SchoolImportSeedSummaryItem = {
  source_key: string;
  title: string;
  description: string;
  total_rows: number;
  target_rows: number | null;
  unique_schools: number | null;
  import_endpoint: string | null;
  highlights: string[];
  top_schools: SchoolImportSeedSchoolItem[];
};

export type SchoolImportSeedSummaryListResponse = {
  items: SchoolImportSeedSummaryItem[];
};

export type RawDatasetArchiveItem = {
  id: string;
  dataset_key: string;
  title: string;
  dataset_type: string;
  source_filename: string;
  source_path: string | null;
  workbook_format: string;
  file_sha256: string;
  file_size_bytes: number;
  storage_encoding: string;
  sheet_names: string[];
  primary_sheet_name: string | null;
  total_rows: number | null;
  total_columns: number | null;
  header_row: string[];
  preview_rows: string[][];
  notes: string | null;
  created_at: string;
  updated_at: string;
};

export type RawDatasetArchiveListResponse = {
  total: number;
  items: RawDatasetArchiveItem[];
};

export type AdminMeResponse = {
  username: string;
  authenticated: boolean;
};

export type AdminIdentityItem = {
  id: string;
  identity_type: string;
  login_name: string | null;
  status: string;
  provider_subject?: string | null;
  provider_unionid?: string | null;
  verified_at?: string | null;
  last_login_at?: string | null;
};

export type AdminRoleAssignmentItem = {
  role_code: string;
  status: string;
  source: string;
  created_at: string;
};

export type AdminEntitlementItem = {
  entitlement_code: string;
  status: string;
  source: string;
  starts_at: string;
  expires_at: string | null;
  revoked_at?: string | null;
  order_ref?: string | null;
};

export type AdminPaymentOrderItem = {
  id: string;
  account_id: string;
  username: string;
  entitlement_code: string;
  source: string;
  status: string;
  duration_days: number;
  amount_cents: number;
  currency: string;
  order_ref: string;
  provider_name: string | null;
  provider_order_ref: string | null;
  provider_payment_ref: string | null;
  paid_at: string | null;
  canceled_at: string | null;
  created_at: string;
  meta_json: Record<string, unknown>;
};

export type AdminPaymentOrderListResponse = {
  total: number;
  items: AdminPaymentOrderItem[];
};

export type AdminUserItem = {
  id: string;
  username: string;
  status: string;
  is_admin: boolean;
  is_premium: boolean;
  premium_expires_at: string | null;
  nickname: string | null;
  identities: AdminIdentityItem[];
  roles: AdminRoleAssignmentItem[];
  entitlements: AdminEntitlementItem[];
  created_at: string;
  last_login_at: string | null;
};

export type AdminUserListResponse = {
  total: number;
  page: number;
  page_size: number;
  items: AdminUserItem[];
};

export type AdminAuditItem = {
  id: string;
  event_type: string;
  endpoint: string;
  event_data: Record<string, unknown>;
  ip: string | null;
  created_at: string;
};

export type AdminAuditListResponse = {
  total: number;
  page: number;
  page_size: number;
  items: AdminAuditItem[];
};

export type AdminContentFingerprintStatsResponse = {
  total_contents: number;
  fingerprinted_contents: number;
  pending_contents: number;
  collision_contents: number;
  coverage_ratio: number;
};

export type AdjustmentIntelligenceSourceItem = {
  source_key: string;
  title: string;
  total_rows: number;
  unique_schools: number | null;
  target_rows: number | null;
};

export type AdjustmentIntelligenceBreakdownItem = {
  label: string;
  count: number;
};

export type AdjustmentIntelligenceSchoolItem = {
  school_name: string;
  source_hits: number;
  score: number;
  sources: string[];
  categories: string[];
};

export type AdjustmentMentorRadarSchoolItem = {
  school_name: string;
  review_count: number;
  warning_count: number;
  mentor_count: number;
  top_tags: string[];
};

export type AdjustmentTimingSchoolItem = {
  school_name: string;
  sample_count: number;
  peak_hour: number | null;
  peak_hour_bucket: string | null;
  window_start_md: string | null;
  window_end_md: string | null;
};

export type AdjustmentIntelligenceResponse = {
  raw_dataset_total: number;
  raw_dataset_total_bytes: number;
  source_cards: AdjustmentIntelligenceSourceItem[];
  school_leaderboard: AdjustmentIntelligenceSchoolItem[];
  mentor_school_leaderboard: AdjustmentMentorRadarSchoolItem[];
  timing_school_leaderboard: AdjustmentTimingSchoolItem[];
  study_mode_breakdown: AdjustmentIntelligenceBreakdownItem[];
  province_breakdown: AdjustmentIntelligenceBreakdownItem[];
  verification_breakdown: AdjustmentIntelligenceBreakdownItem[];
  category_breakdown: AdjustmentIntelligenceBreakdownItem[];
  score_band_breakdown: AdjustmentIntelligenceBreakdownItem[];
  mentor_risk_breakdown: AdjustmentIntelligenceBreakdownItem[];
  mentor_tag_breakdown: AdjustmentIntelligenceBreakdownItem[];
  timing_hour_breakdown: AdjustmentIntelligenceBreakdownItem[];
};

export type HealthResponse = {
  status: "ok" | "degraded";
  app_env: string;
  db: "up" | "down";
  redis: "up" | "down";
};

export type SiteSectionSelectorConfig = Record<string, unknown>;

export type SiteSectionItem = {
  id: string;
  name: string;
  section_type: string;
  section_url: string;
  school_name: string | null;
  department_name: string | null;
  department_type: string | null;
  discovery_category: "announcement" | "adjustment";
  enabled: boolean;
  list_selector_config: SiteSectionSelectorConfig;
  detail_selector_config: SiteSectionSelectorConfig;
  suggested_list_selector_config: SiteSectionSelectorConfig;
  suggested_detail_selector_config: SiteSectionSelectorConfig;
  last_discovered_at: string | null;
  last_discovery_status: string | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
};

export type SiteSectionListResponse = {
  total: number;
  items: SiteSectionItem[];
};

export type SiteSectionBackfillSelectorConfigResponse = {
  total_sections: number;
  updated_sections: number;
  items: SiteSectionItem[];
};

export type SiteSectionSelectorPreviewLinkItem = {
  url: string;
  text: string;
  link_type: "html" | "pdf";
};

export type SiteSectionSelectorPreviewResponse = {
  section_url: string;
  suggested_list_selector_config: SiteSectionSelectorConfig;
  suggested_detail_selector_config: SiteSectionSelectorConfig;
  list_match_count: number;
  list_preview_items: SiteSectionSelectorPreviewLinkItem[];
  detail_preview_url: string | null;
  detail_title: string | null;
  detail_excerpt: string | null;
  detail_extraction_method: "selector" | "readability" | "plain_text" | null;
  warnings: string[];
  suggestions: string[];
};

export type ContentFileItem = {
  id: string;
  content_id: string | null;
  site_section_link_id: string | null;
  site_section_id: string | null;
  site_section_name: string | null;
  school_name: string | null;
  link_title: string | null;
  content_title: string | null;
  file_url: string;
  file_type: string;
  mime_type: string | null;
  text_excerpt: string | null;
  parse_status: string;
  ocr_status: string;
  file_meta: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type ContentFileListResponse = {
  total: number;
  items: ContentFileItem[];
};

export type ContentFileRetryParseResponse = {
  content_file_id: string;
  job_id: string;
  status: "queued" | "existing";
  parse_status: string;
};

export type SubscriptionType = "school" | "major" | "keyword" | "region";
export type SubscriptionCategory = "all" | "announcement" | "adjustment";

export type SubscriptionItem = {
  id: string;
  subscription_type: SubscriptionType;
  value: string;
  category: SubscriptionCategory;
  status: string;
  created_at: string;
  updated_at: string;
};

export type SubscriptionListResponse = {
  total: number;
  items: SubscriptionItem[];
};

export type NotificationPayload = {
  content_id?: string;
  category?: string;
  title?: string;
  body?: string;
  summary?: string;
  tags?: string[];
  school_name?: string;
  major?: string;
  region?: string;
  source_url?: string;
  published_at?: string | null;
  status?: string;
};

export type NotificationEventItem = {
  id: string;
  outbox_id: string;
  created_at: string;
  payload: NotificationPayload;
};

export type NotificationPendingResponse = {
  total: number;
  items: NotificationEventItem[];
};

export type UserNotificationHistoryItem = {
  id: string;
  outbox_id: string;
  channel: string;
  status: string;
  created_at: string;
  sent_at: string | null;
  last_error: string | null;
  payload: NotificationPayload;
};

export type UserNotificationHistoryResponse = {
  total: number;
  items: UserNotificationHistoryItem[];
};

export function registerUser(payload: {
  username: string;
  password: string;
  nickname?: string;
}) {
  return request<UserRegisterResponse>({
    url: "/auth/register",
    method: "POST",
    data: payload,
  });
}

export function loginUser(payload: { username: string; password: string }) {
  return request<UserLoginResponse>({
    url: "/auth/login",
    method: "POST",
    data: payload,
  });
}

export function refreshUserSession(refreshToken?: string) {
  return request<UserLoginResponse>({
    url: "/auth/refresh",
    method: "POST",
    data: refreshToken ? { refresh_token: refreshToken } : {},
  });
}

export function logoutUser(refreshToken?: string) {
  return request<{ status: "ok" }>({
    url: "/auth/logout",
    method: "POST",
    data: refreshToken ? { refresh_token: refreshToken } : {},
  });
}

export function getCurrentUser(token: string) {
  return request<UserMeResponse>({
    url: "/auth/me",
    method: "GET",
    headers: {
      "X-User-Token": token,
    },
  });
}

export function getCurrentUserIdentities(token: string) {
  return request<UserIdentityListResponse>({
    url: "/auth/me/identities",
    method: "GET",
    headers: {
      "X-User-Token": token,
    },
  });
}

export function getCurrentUserAccountOverview(token: string) {
  return request<UserAccountOverviewResponse>({
    url: "/auth/me/account",
    method: "GET",
    headers: {
      "X-User-Token": token,
    },
  });
}

export function getCurrentUserPaymentOrders(token: string) {
  return request<UserPaymentOrderListResponse>({
    url: "/auth/me/premium-orders",
    method: "GET",
    headers: {
      "X-User-Token": token,
    },
  });
}

export function createCurrentUserPaymentOrder(token: string, payload: UserPaymentOrderCreateRequest) {
  return request<UserPaymentOrderItem>({
    url: "/auth/me/premium-orders",
    method: "POST",
    data: payload,
    headers: {
      "X-User-Token": token,
    },
  });
}

export function changeCurrentUserPassword(token: string, payload: { old_password: string; new_password: string }) {
  return request<{ status: "ok" }>({
    url: "/auth/me/change-password",
    method: "POST",
    data: payload,
    headers: {
      "X-User-Token": token,
    },
  });
}

export function getCurrentUserNotificationHistory(token: string, limit = 20) {
  return request<UserNotificationHistoryResponse>({
    url: "/auth/me/notifications/history",
    method: "GET",
    params: { limit },
    headers: {
      "X-User-Token": token,
    },
  });
}

export function createWechatBindCode(token: string) {
  return request<WechatBindCodeResponse>({
    url: "/auth/wechat/bind-code",
    method: "POST",
    headers: {
      "X-User-Token": token,
    },
  });
}

export function adminMe() {
  return request<AdminMeResponse>({
    url: "/admin/auth/me",
    method: "GET",
  });
}

export function adminUsers(payload: {
  page?: number;
  page_size?: number;
  state?: string;
  keyword?: string;
}) {
  return request<AdminUserListResponse>({
    url: "/admin/users",
    method: "GET",
    params: payload,
  });
}

export function adminPromoteUser(userId: string, targetRole: "premium" | "admin" = "admin") {
  return request<AdminUserItem>({
    url: `/admin/users/${encodeURIComponent(userId)}/promote`,
    method: "POST",
    data: { target_role: targetRole },
  });
}

export function adminDemoteUser(userId: string, targetRole: "user" | "premium" = "user", premiumDays = 30) {
  return request<AdminUserItem>({
    url: `/admin/users/${encodeURIComponent(userId)}/demote`,
    method: "POST",
    data: { target_role: targetRole, premium_days: premiumDays },
  });
}

export function adminResetUserPassword(userId: string, newPassword: string) {
  return request<{ status: "ok"; user_id: string; username: string }>({
    url: `/admin/users/${encodeURIComponent(userId)}/reset-password`,
    method: "POST",
    data: { new_password: newPassword },
  });
}

export function adminPaymentOrders(payload?: { status?: string; user_id?: string; limit?: number }) {
  return request<AdminPaymentOrderListResponse>({
    url: "/admin/payment-orders",
    method: "GET",
    params: payload,
  });
}

export function adminMarkPaymentOrderPaid(orderId: string, providerPaymentRef?: string) {
  return request<AdminPaymentOrderItem>({
    url: `/admin/payment-orders/${encodeURIComponent(orderId)}/mark-paid`,
    method: "POST",
    data: { provider_payment_ref: providerPaymentRef || null },
  });
}

export function adminCreateUserPaymentOrder(userId: string, payload?: { duration_days?: number; amount_cents?: number }) {
  return request<AdminPaymentOrderItem>({
    url: `/admin/users/${encodeURIComponent(userId)}/payment-orders`,
    method: "POST",
    params: {
      duration_days: payload?.duration_days ?? 30,
      amount_cents: payload?.amount_cents ?? 0,
    },
  });
}

export function adminAudits(payload: {
  page?: number;
  page_size?: number;
  prefix?: string;
}) {
  return request<AdminAuditListResponse>({
    url: "/admin/audits",
    method: "GET",
    params: payload,
  });
}

export function healthCheck() {
  return request<HealthResponse>({
    url: "/health",
    method: "GET",
  });
}

export function notificationsStreamUrl() {
  return `${API_BASE}/notifications/stream`;
}
