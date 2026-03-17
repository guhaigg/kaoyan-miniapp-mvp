"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchPendingNotices } from "@/api/notifications";
import { mergeNoticeList, watchlistNoticeQueryKey } from "@/lib/notice-cache";
import type { NotificationEventItem } from "@/lib/api";
import { useAppStore } from "@/lib/store";

export function useWatchlistNoticesQuery(enabled: boolean) {
  const userId = useAppStore((state) => state.portalAuth?.userId);
  const queryClient = useQueryClient();
  const queryKey = watchlistNoticeQueryKey(userId);

  return useQuery({
    queryKey,
    queryFn: async () => {
      const existing = queryClient.getQueryData<NotificationEventItem[]>(queryKey);
      const response = await fetchPendingNotices();
      return mergeNoticeList(existing, response.items);
    },
    enabled: enabled && Boolean(userId),
    refetchOnWindowFocus: false,
  });
}
