import {
  api,
  type MonitorScopeDepartmentListResponse,
  type MonitorScopeSectionListResponse,
  type MonitorTargetItem,
  type MonitorTargetListResponse,
  type MonitorTargetScopeType,
} from "@/lib/api";

type CreateMonitorTargetPayload = {
  scope_type: MonitorTargetScopeType;
  school_id?: string;
  school_name?: string;
  department_id?: string;
  department_name?: string;
  site_section_id?: string;
  site_section_name?: string;
  status?: "active" | "paused" | "deleted";
  check_interval_minutes?: number;
};

export const fetchMonitorTargets = () =>
  api.get<MonitorTargetListResponse>("/monitoring/targets").then((response) => response.data);

export const createMonitorTarget = (payload: CreateMonitorTargetPayload) =>
  api.post<MonitorTargetItem>("/monitoring/targets", payload).then((response) => response.data);

export const removeMonitorTarget = (targetId: string) =>
  api
    .patch<MonitorTargetItem>(`/monitoring/targets/${encodeURIComponent(targetId)}`, { status: "deleted" })
    .then((response) => response.data);

export const searchMonitorScopeSections = (params?: {
  school_name?: string;
  department_name?: string;
  section_name?: string;
  limit?: number;
}) => api.get<MonitorScopeSectionListResponse>("/monitoring/scope-sections", { params }).then((response) => response.data);

export const searchMonitorScopeDepartments = (params?: {
  school_name?: string;
  department_name?: string;
  limit?: number;
}) => api.get<MonitorScopeDepartmentListResponse>("/monitoring/scope-departments", { params }).then((response) => response.data);
