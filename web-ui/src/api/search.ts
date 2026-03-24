import {
  request,
  type AdjustmentSearchDetailResponse,
  type AdjustmentSearchRequest,
  type AnnouncementSearchRequest,
  type SearchResponse,
} from "@/lib/api";

export const fetchAnnouncementResults = (payload: AnnouncementSearchRequest) =>
  request<SearchResponse>({
    method: "POST",
    url: "/search/announcements",
    data: payload,
    timeout: 30_000,
  });

export const fetchAdjustmentResults = (payload: AdjustmentSearchRequest) =>
  request<SearchResponse>({
    method: "POST",
    url: "/search/adjustments",
    data: payload,
    timeout: 45_000,
  });

export const fetchAdjustmentDetail = (itemId: string, itemKind: "content" | "opportunity") =>
  request<AdjustmentSearchDetailResponse>({
    method: "GET",
    url: `/search/adjustments/items/${itemId}`,
    params: { item_kind: itemKind },
    timeout: 30_000,
  });
