import { api, type AdjustmentSearchRequest, type SearchBaseRequest, type SearchResponse } from "@/lib/api";

export const fetchAnnouncementResults = (payload: SearchBaseRequest) =>
  api.post<SearchResponse>("/search/announcements", payload).then((response) => response.data);

export const fetchAdjustmentResults = (payload: AdjustmentSearchRequest) =>
  api.post<SearchResponse>("/search/adjustments", payload).then((response) => response.data);
