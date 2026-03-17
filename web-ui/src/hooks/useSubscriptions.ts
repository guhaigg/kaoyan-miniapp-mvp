"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createSubscriptionEntry, fetchSubscriptions, removeSubscriptionEntry } from "@/api/subscriptions";
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
  return useMutation({
    mutationFn: createSubscriptionEntry,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["portal", "subscriptions", userId] });
    },
  });
}

export function useDeleteSubscriptionMutation() {
  const queryClient = useQueryClient();
  const userId = useAppStore((state) => state.portalAuth?.userId);
  return useMutation({
    mutationFn: removeSubscriptionEntry,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["portal", "subscriptions", userId] });
    },
  });
}
