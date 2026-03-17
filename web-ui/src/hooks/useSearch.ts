"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { fetchAdjustmentResults, fetchAnnouncementResults } from "@/api/search";
import type { AdjustmentSearchRequest, SearchBaseRequest } from "@/lib/api";

export function useAnnouncementSearchMutation() {
  return useMutation({
    mutationFn: fetchAnnouncementResults,
  });
}

export function useAdjustmentSearchMutation() {
  return useMutation({
    mutationFn: fetchAdjustmentResults,
  });
}

export function useHomeAnnouncementsQuery(payload: SearchBaseRequest) {
  return useQuery({
    queryKey: ["home", "announcements", payload],
    queryFn: () => fetchAnnouncementResults(payload),
  });
}

export type AnnouncementSearchInput = SearchBaseRequest;
export type AdjustmentSearchInput = AdjustmentSearchRequest;
