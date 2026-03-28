import type { AnnouncementSearchRequest, SearchItem } from "@/lib/api";

export type AnnouncementPageState = {
  keywords: string;
  schoolName: string;
  systemTags: string[];
  startDate: string;
  endDate: string;
  page: number;
};

export function parseAnnouncementPageState(searchParams: URLSearchParams): AnnouncementPageState {
  return {
    keywords: searchParams.get("keywords") || "",
    schoolName: searchParams.get("school_name") || "",
    systemTags: searchParams.getAll("system_tags"),
    startDate: searchParams.get("start_date") || "",
    endDate: searchParams.get("end_date") || "",
    page: Number(searchParams.get("page") || 1),
  };
}

export function buildAnnouncementSearchPayload(state: AnnouncementPageState): AnnouncementSearchRequest {
  return {
    keywords: state.keywords.trim() || undefined,
    school_name: state.schoolName.trim() || undefined,
    system_tags: state.systemTags.length ? state.systemTags : undefined,
    start_date: state.startDate ? `${state.startDate}T00:00:00` : undefined,
    end_date: state.endDate ? `${state.endDate}T23:59:59` : undefined,
    page: state.page,
    page_size: 12,
  };
}

export function buildAnnouncementMeta(item: SearchItem) {
  return {
    title: item.title,
    summary: item.summary || item.school_intelligence?.signal_detail || "点击查看完整公告详情。",
    school: item.school_name || item.department_name || "目标院校",
    department: item.department_name || null,
    tags: Array.from(new Set([...(item.tags || []), ...(item.system_tags || [])])).slice(0, 4),
    time: item.published_at || item.updated_at,
  };
}
