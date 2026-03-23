"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createSubscriptionEntry, fetchSubscriptions, removeSubscriptionEntry } from "@/api/subscriptions";
import { type SubscriptionItem, type SubscriptionListResponse } from "@/lib/api";
import { useAppStore } from "@/lib/store";

export function useSubscriptionsQuery(enabled: boolean) {
  const userId = useAppStore((state) => state.portalAuth?.userId);
  return useQuery({
    queryKey: ["portal", "subscriptions", userId],
    queryFn: fetchSubscriptions,
    enabled: enabled && Boolean(userId),
  });
}

export function useAddSubscriptionMutation() {
  const queryClient = useQueryClient();
  const userId = useAppStore((state) => state.portalAuth?.userId);
  const queryKey = ["portal", "subscriptions", userId] as const;
  return useMutation({
    mutationFn: createSubscriptionEntry,
    onSuccess: (item: SubscriptionItem) => {
      queryClient.setQueryData<SubscriptionListResponse | undefined>(queryKey, (current) => {
        const existingItems = current?.items || [];
        const deduped = existingItems.filter((entry) => entry.id !== item.id);
        return {
          total: deduped.length + 1,
          items: [item, ...deduped],
        };
      });
      void queryClient.invalidateQueries({ queryKey });
    },
  });
}

export function useDeleteSubscriptionMutation() {
  const queryClient = useQueryClient();
  const userId = useAppStore((state) => state.portalAuth?.userId);
  const queryKey = ["portal", "subscriptions", userId] as const;
  return useMutation({
    mutationFn: removeSubscriptionEntry,
    onSuccess: (_result, subscriptionId: string) => {
      queryClient.setQueryData<SubscriptionListResponse | undefined>(queryKey, (current) => {
        if (!current) {
          return current;
        }
        const items = current.items.filter((item) => item.id !== subscriptionId);
        return {
          total: items.length,
          items,
        };
      });
      void queryClient.invalidateQueries({ queryKey });
    },
  });
}
