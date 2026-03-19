import {
  request,
  type AdjustmentSearchDetailResponse,
  type AdjustmentSearchRequest,
  type SearchBaseRequest,
  type SearchResponse,
} from "@/lib/api";

export const fetchAnnouncementResults = (payload: SearchBaseRequest) =>
  request<SearchResponse>({
    method: "POST",
    url: "/search/announcements",
    data: payload,
  });

export const fetchAdjustmentResults = (payload: AdjustmentSearchRequest) =>
  request<SearchResponse>({
    method: "POST",
    url: "/search/adjustments",
    data: payload,
  });

export const fetchAdjustmentDetail = (itemId: string, itemKind: "content" | "opportunity") =>
  request<AdjustmentSearchDetailResponse>({
    method: "GET",
    url: `/search/adjustments/items/${itemId}`,
    params: { item_kind: itemKind },
  });
