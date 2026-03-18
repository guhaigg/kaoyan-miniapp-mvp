import {
  api,
  type AdminAuditListResponse,
  type AdminContentFingerprintStatsResponse,
  type ContentFileListResponse,
  type ContentFileRetryParseResponse,
  type AdminMeResponse,
  type AdminUserItem,
  type AdminUserListResponse,
  type HealthResponse,
  type SiteSectionItem,
  type SiteSectionBackfillSelectorConfigResponse,
  type SiteSectionListResponse,
  type SiteSectionSelectorPreviewResponse,
  type SiteSectionSelectorConfig,
  type SchoolBulkImportResponse,
  adminCreateUserPaymentOrder,
  adminMarkPaymentOrderPaid,
  adminPaymentOrders,
  adminResetUserPassword,
} from "@/lib/api";

export const fetchAdminMe = () =>
  api.get<AdminMeResponse>("/admin/auth/me").then((response) => response.data);

export const fetchAdminUsers = (params?: {
  page?: number;
  page_size?: number;
  state?: string;
  keyword?: string;
}) => api.get<AdminUserListResponse>("/admin/users", { params }).then((response) => response.data);

export const promoteAdminUser = (userId: string, targetRole: "premium" | "admin" = "admin") =>
  api
    .post<AdminUserItem>(`/admin/users/${encodeURIComponent(userId)}/promote`, {
      target_role: targetRole,
    })
    .then((response) => response.data);

export const demoteAdminUser = (userId: string, targetRole: "user" | "premium" = "user", premiumDays = 30) =>
  api
    .post<AdminUserItem>(`/admin/users/${encodeURIComponent(userId)}/demote`, {
      target_role: targetRole,
      premium_days: premiumDays,
    })
    .then((response) => response.data);

export const resetAdminUserPassword = (userId: string, newPassword: string) =>
  adminResetUserPassword(userId, newPassword);

export const fetchAdminPaymentOrders = (params?: {
  status?: string;
  user_id?: string;
  limit?: number;
}) => adminPaymentOrders(params);

export const markAdminPaymentOrderPaid = (orderId: string, providerPaymentRef?: string) =>
  adminMarkPaymentOrderPaid(orderId, providerPaymentRef);

export const createAdminPaymentOrderForUser = (userId: string, payload?: { duration_days?: number; amount_cents?: number }) =>
  adminCreateUserPaymentOrder(userId, payload);

export const fetchAdminAudits = (params?: {
  page?: number;
  page_size?: number;
  prefix?: string;
}) => api.get<AdminAuditListResponse>("/admin/audits", { params }).then((response) => response.data);

export const fetchAdminContentFingerprintStats = () =>
  api.get<AdminContentFingerprintStatsResponse>("/admin/content-fingerprint-stats").then((response) => response.data);

export const fetchHealthStatus = () =>
  api.get<HealthResponse>("/health").then((response) => response.data);

export const fetchSiteSections = (params?: {
  school_name?: string;
  department_name?: string;
  section_type?: string;
  enabled_only?: boolean;
}) => api.get<SiteSectionListResponse>("/site-sections", { params }).then((response) => response.data);

export const updateSiteSection = (
  siteSectionId: string,
  payload: {
    list_selector_config?: SiteSectionSelectorConfig;
    detail_selector_config?: SiteSectionSelectorConfig;
  },
) => api.patch<SiteSectionItem>(`/site-sections/${encodeURIComponent(siteSectionId)}`, payload).then((response) => response.data);

export const previewSiteSectionSelectors = (
  siteSectionId: string,
  payload: {
    list_selector_config?: SiteSectionSelectorConfig;
    detail_selector_config?: SiteSectionSelectorConfig;
    sample_link_url?: string | null;
  },
) =>
  api
    .post<SiteSectionSelectorPreviewResponse>(`/site-sections/${encodeURIComponent(siteSectionId)}/preview-selectors`, payload)
    .then((response) => response.data);

export const backfillSiteSectionSelectorConfig = (payload?: {
  school_name?: string | null;
  department_name?: string | null;
  section_type?: string | null;
  enabled_only?: boolean;
  overwrite_existing?: boolean;
}) =>
  api
    .post<SiteSectionBackfillSelectorConfigResponse>("/site-sections/backfill-selector-config", payload || {})
    .then((response) => response.data);

export const fetchContentFiles = (params?: {
  parse_status?: string;
  ocr_status?: string;
  site_section_id?: string;
  file_type?: string;
  page_size?: number;
}) => api.get<ContentFileListResponse>("/site-sections/content-files", { params }).then((response) => response.data);

export const retryContentFileParse = (contentFileId: string) =>
  api.post<ContentFileRetryParseResponse>(`/site-sections/content-files/${encodeURIComponent(contentFileId)}/retry-parse`).then((response) => response.data);

export const importAdjustmentPriorityTargets = () =>
  api.post<SchoolBulkImportResponse>("/schools/import/adjustment-priority-targets").then((response) => response.data);
