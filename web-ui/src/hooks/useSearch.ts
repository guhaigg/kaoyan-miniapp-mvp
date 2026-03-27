"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { fetchAdjustmentResults, fetchAnnouncementResults } from "@/api/search";
import type { AdjustmentSearchRequest, AnnouncementSearchRequest } from "@/lib/api";

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

export function useHomeAnnouncementsQuery(payload: AnnouncementSearchRequest) {
  return useQuery({
    queryKey: ["home", "announcements", payload],
    queryFn: () => fetchAnnouncementResults(payload),
  });
}

export function useHomeAdjustmentsQuery(payload: AdjustmentSearchRequest, enabled: boolean) {
  return useQuery({
    queryKey: ["home", "adjustments", payload],
    queryFn: () => fetchAdjustmentResults(payload),
    enabled,
  });
}

export type AnnouncementSearchInput = AnnouncementSearchRequest;
export type AdjustmentSearchInput = AdjustmentSearchRequest;
