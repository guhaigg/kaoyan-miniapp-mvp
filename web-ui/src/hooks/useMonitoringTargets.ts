"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchSchoolSuggestions } from "@/api/schools";
import {
  createMonitorTarget,
  fetchMonitorTargets,
  removeMonitorTarget,
  searchMonitorScopeDepartments,
  searchMonitorScopeSections,
} from "@/api/monitoring";
import { type MonitorTargetItem, type MonitorTargetListResponse } from "@/lib/api";
import { useAppStore } from "@/lib/store";

export function useMonitorTargetsQuery(enabled: boolean) {
  const userId = useAppStore((state) => state.portalAuth?.userId);
  return useQuery({
    queryKey: ["portal", "monitor-targets", userId],
    queryFn: fetchMonitorTargets,
    enabled: enabled && Boolean(userId),
  });
}

export function useAddMonitorTargetMutation() {
  const queryClient = useQueryClient();
  const userId = useAppStore((state) => state.portalAuth?.userId);
  const queryKey = ["portal", "monitor-targets", userId] as const;
  return useMutation({
    mutationFn: createMonitorTarget,
    onSuccess: (item: MonitorTargetItem) => {
      queryClient.setQueryData<MonitorTargetListResponse | undefined>(queryKey, (current) => {
        const existingItems = current?.items || [];
        const deduped = existingItems.filter((entry) => entry.id !== item.id);
        return {
          total: deduped.length + 1,
          items: [item, ...deduped],
          recent_signal_overview: current?.recent_signal_overview,
        };
      });
      void queryClient.invalidateQueries({ queryKey });
    },
  });
}

export function useDeleteMonitorTargetMutation() {
  const queryClient = useQueryClient();
  const userId = useAppStore((state) => state.portalAuth?.userId);
  const queryKey = ["portal", "monitor-targets", userId] as const;
  return useMutation({
    mutationFn: removeMonitorTarget,
    onSuccess: (_result, targetId: string) => {
      queryClient.setQueryData<MonitorTargetListResponse | undefined>(queryKey, (current) => {
        if (!current) {
          return current;
        }
        const items = current.items.filter((item) => item.id !== targetId);
        return {
          total: items.length,
          items,
          recent_signal_overview: current.recent_signal_overview,
        };
      });
      void queryClient.invalidateQueries({ queryKey });
    },
  });
}

export function useMonitorScopeSectionsQuery(
  params: {
    school_name?: string;
    department_name?: string;
    section_name?: string;
    limit?: number;
  },
  enabled: boolean,
) {
  const userId = useAppStore((state) => state.portalAuth?.userId);
  return useQuery({
    queryKey: ["portal", "monitor-scope-sections", userId, params.school_name, params.department_name, params.section_name, params.limit],
    queryFn: () => searchMonitorScopeSections(params),
    enabled: enabled && Boolean(userId),
  });
}

export function useMonitorScopeDepartmentsQuery(
  params: {
    school_name?: string;
    department_name?: string;
    limit?: number;
  },
  enabled: boolean,
) {
  const userId = useAppStore((state) => state.portalAuth?.userId);
  return useQuery({
    queryKey: ["portal", "monitor-scope-departments", userId, params.school_name, params.department_name, params.limit],
    queryFn: () => searchMonitorScopeDepartments(params),
    enabled: enabled && Boolean(userId),
  });
}

export function useSchoolSuggestionsQuery(
  params: {
    q?: string;
    limit?: number;
  },
  enabled: boolean,
) {
  return useQuery({
    queryKey: ["portal", "school-suggestions", params.q, params.limit],
    queryFn: () => fetchSchoolSuggestions(params),
    enabled,
  });
}
