import {
  api,
  type AdminAuditListResponse,
  type AdminLoginResponse,
  type AdminMeResponse,
  type AdminUserItem,
  type AdminUserListResponse,
  type HealthResponse,
} from "@/lib/api";

export const loginAdminSession = (payload: { username: string; password: string }) =>
  api.post<AdminLoginResponse>("/admin/auth/login", payload).then((response) => response.data);

export const logoutAdminSession = () =>
  api.post<{ status: "ok" }>("/admin/auth/logout").then((response) => response.data);

export const fetchAdminMe = () =>
  api.get<AdminMeResponse>("/admin/auth/me").then((response) => response.data);

export const fetchAdminUsers = (params?: {
  page?: number;
  page_size?: number;
  state?: string;
  keyword?: string;
}) => api.get<AdminUserListResponse>("/admin/users", { params }).then((response) => response.data);

export const promoteAdminUser = (userId: string) =>
  api
    .post<AdminUserItem>(`/admin/users/${encodeURIComponent(userId)}/promote`)
    .then((response) => response.data);

export const fetchAdminAudits = (params?: {
  page?: number;
  page_size?: number;
  prefix?: string;
}) => api.get<AdminAuditListResponse>("/admin/audits", { params }).then((response) => response.data);

export const fetchHealthStatus = () =>
  api.get<HealthResponse>("/health").then((response) => response.data);
