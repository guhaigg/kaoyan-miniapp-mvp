"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchAdminAudits,
  fetchAdminMe,
  fetchAdminUsers,
  fetchHealthStatus,
  loginAdminSession,
  logoutAdminSession,
  promoteAdminUser,
} from "@/api/admin";

const adminQueryKeys = {
  me: ["admin", "me"] as const,
  health: ["admin", "health"] as const,
  users: ["admin", "users"] as const,
  audits: ["admin", "audits"] as const,
};

export function useAdminMeQuery() {
  return useQuery({
    queryKey: adminQueryKeys.me,
    queryFn: fetchAdminMe,
    retry: false,
  });
}

export function useAdminHealthQuery() {
  return useQuery({
    queryKey: adminQueryKeys.health,
    queryFn: fetchHealthStatus,
    refetchInterval: 20_000,
  });
}

export function useAdminUsersQuery(enabled: boolean) {
  return useQuery({
    queryKey: adminQueryKeys.users,
    queryFn: () => fetchAdminUsers({ page: 1, page_size: 10 }),
    enabled,
  });
}

export function useAdminAuditsQuery(enabled: boolean) {
  return useQuery({
    queryKey: adminQueryKeys.audits,
    queryFn: () => fetchAdminAudits({ page: 1, page_size: 24, prefix: "admin." }),
    enabled,
  });
}

export function useAdminLoginMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: loginAdminSession,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: adminQueryKeys.me });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: adminQueryKeys.users }),
        queryClient.invalidateQueries({ queryKey: adminQueryKeys.audits }),
      ]);
    },
  });
}

export function useAdminLogoutMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: logoutAdminSession,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: adminQueryKeys.me });
      queryClient.removeQueries({ queryKey: adminQueryKeys.users });
      queryClient.removeQueries({ queryKey: adminQueryKeys.audits });
    },
  });
}

export function useAdminPromoteMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: promoteAdminUser,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: adminQueryKeys.users });
      await queryClient.invalidateQueries({ queryKey: adminQueryKeys.audits });
    },
  });
}
