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
};

export type SearchItem = {
  id: string;
  category: string;
  school_name: string | null;
  title: string;
  summary: string | null;
  source_url: string | null;
  source_type: string;
  published_at: string | null;
  region: string | null;
  major: string | null;
  updated_at: string;
};

export type SearchResponse = {
  request_id: string;
  mode: "cache" | "hybrid_refresh";
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
};

export type AdminMeResponse = {
  username: string;
  authenticated: boolean;
};

export type AdminLoginResponse = {
  username: string;
  expires_in: number;
};

export type AdminUserItem = {
  id: string;
  username: string;
  status: string;
  is_admin: boolean;
  nickname: string | null;
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

export type HealthResponse = {
  status: "ok" | "degraded";
  app_env: string;
  db: "up" | "down";
  redis: "up" | "down";
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

export function searchAnnouncements(payload: SearchBaseRequest) {
  return request<SearchResponse>({
    url: "/search/announcements",
    method: "POST",
    data: payload,
  });
}

export function searchAdjustments(payload: AdjustmentSearchRequest) {
  return request<SearchResponse>({
    url: "/search/adjustments",
    method: "POST",
    data: payload,
  });
}

export function adminLogin(payload: { username: string; password: string }) {
  return request<AdminLoginResponse>({
    url: "/admin/auth/login",
    method: "POST",
    data: payload,
  });
}

export function adminLogout() {
  return request<{ status: "ok" }>({
    url: "/admin/auth/logout",
    method: "POST",
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

export function adminPromoteUser(userId: string) {
  return request<AdminUserItem>({
    url: `/admin/users/${encodeURIComponent(userId)}/promote`,
    method: "POST",
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

export function createSubscription(
  payload: {
    subscription_type: SubscriptionType;
    value: string;
    category?: SubscriptionCategory;
  },
  token: string,
) {
  return request<SubscriptionItem>({
    url: "/subscriptions",
    method: "POST",
    data: payload,
    headers: {
      "X-User-Token": token,
    },
  });
}

export function listSubscriptions(token: string) {
  return request<SubscriptionListResponse>({
    url: "/subscriptions",
    method: "GET",
    headers: {
      "X-User-Token": token,
    },
  });
}

export function deleteSubscription(subscriptionId: string, token: string) {
  return request<{ status: "ok" }>({
    url: `/subscriptions/${encodeURIComponent(subscriptionId)}`,
    method: "DELETE",
    headers: {
      "X-User-Token": token,
    },
  });
}

export function listPendingNotifications(token: string) {
  return request<NotificationPendingResponse>({
    url: "/notifications/pending",
    method: "GET",
    headers: {
      "X-User-Token": token,
    },
  });
}

export function notificationsStreamUrl() {
  return `${API_BASE}/notifications/stream`;
}
