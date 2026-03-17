const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL || "/api/v1").replace(/\/+$/, "");

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

type RequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  token?: string;
  headers?: Record<string, string>;
};

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const url = `${API_BASE}${normalizedPath}`;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  if (options.token) {
    headers["X-User-Token"] = options.token;
  }

  const response = await fetch(url, {
    method: options.method || "GET",
    credentials: "include",
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    cache: "no-store",
  });

  let payload: unknown = null;
  const text = await response.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = text;
    }
  }

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    if (payload && typeof payload === "object" && "detail" in payload) {
      const detail = (payload as { detail?: unknown }).detail;
      if (typeof detail === "string" && detail.trim()) {
        message = detail;
      }
    }
    throw new ApiError(message, response.status, payload);
  }

  return payload as T;
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

export function registerUser(payload: {
  username: string;
  password: string;
  nickname?: string;
}) {
  return request<UserRegisterResponse>("/auth/register", {
    method: "POST",
    body: payload,
  });
}

export function loginUser(payload: { username: string; password: string }) {
  return request<UserLoginResponse>("/auth/login", {
    method: "POST",
    body: payload,
  });
}

export function refreshUserSession(refreshToken?: string) {
  return request<UserLoginResponse>("/auth/refresh", {
    method: "POST",
    body: refreshToken ? { refresh_token: refreshToken } : {},
  });
}

export function logoutUser(refreshToken?: string) {
  return request<{ status: "ok" }>("/auth/logout", {
    method: "POST",
    body: refreshToken ? { refresh_token: refreshToken } : {},
  });
}

export function getCurrentUser(token: string) {
  return request<UserMeResponse>("/auth/me", { token });
}

export function searchAnnouncements(payload: SearchBaseRequest) {
  return request<SearchResponse>("/search/announcements", {
    method: "POST",
    body: payload,
  });
}

export function searchAdjustments(payload: AdjustmentSearchRequest) {
  return request<SearchResponse>("/search/adjustments", {
    method: "POST",
    body: payload,
  });
}

export function adminLogin(payload: { username: string; password: string }) {
  return request<AdminLoginResponse>("/admin/auth/login", {
    method: "POST",
    body: payload,
  });
}

export function adminLogout() {
  return request<{ status: "ok" }>("/admin/auth/logout", {
    method: "POST",
  });
}

export function adminMe() {
  return request<AdminMeResponse>("/admin/auth/me");
}

export function adminUsers(payload: {
  page?: number;
  page_size?: number;
  state?: string;
  keyword?: string;
}) {
  const query = new URLSearchParams();
  if (payload.page) query.set("page", String(payload.page));
  if (payload.page_size) query.set("page_size", String(payload.page_size));
  if (payload.state) query.set("state", payload.state);
  if (payload.keyword) query.set("keyword", payload.keyword);
  const suffix = query.toString();
  return request<AdminUserListResponse>(`/admin/users${suffix ? `?${suffix}` : ""}`);
}

export function adminPromoteUser(userId: string) {
  return request<AdminUserItem>(`/admin/users/${encodeURIComponent(userId)}/promote`, {
    method: "POST",
  });
}

export function adminAudits(payload: {
  page?: number;
  page_size?: number;
  prefix?: string;
}) {
  const query = new URLSearchParams();
  if (payload.page) query.set("page", String(payload.page));
  if (payload.page_size) query.set("page_size", String(payload.page_size));
  if (payload.prefix) query.set("prefix", payload.prefix);
  const suffix = query.toString();
  return request<AdminAuditListResponse>(`/admin/audits${suffix ? `?${suffix}` : ""}`);
}

export function healthCheck() {
  return request<HealthResponse>("/health");
}

export function createSubscription(
  payload: {
    subscription_type: SubscriptionType;
    value: string;
    category?: SubscriptionCategory;
  },
  token: string,
) {
  return request<SubscriptionItem>("/subscriptions", {
    method: "POST",
    token,
    body: payload,
  });
}

export function listSubscriptions(token: string) {
  return request<SubscriptionListResponse>("/subscriptions", {
    token,
  });
}

export function deleteSubscription(subscriptionId: string, token: string) {
  return request<{ status: "ok" }>(`/subscriptions/${encodeURIComponent(subscriptionId)}`, {
    method: "DELETE",
    token,
  });
}
