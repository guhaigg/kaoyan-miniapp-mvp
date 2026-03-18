"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  backfillSiteSectionSelectorConfig,
  createAdminPaymentOrderForUser,
  demoteAdminUser,
  fetchAdminContentFingerprintStats,
  fetchContentFiles,
  fetchAdminAudits,
  fetchAdminMe,
  fetchAdminPaymentOrders,
  fetchAdminUsers,
  fetchHealthStatus,
  fetchSiteSections,
  markAdminPaymentOrderPaid,
  previewSiteSectionSelectors,
  resetAdminUserPassword,
  promoteAdminUser,
  retryContentFileParse,
  updateSiteSection,
} from "@/api/admin";

const adminQueryKeys = {
  me: ["admin", "me"] as const,
  health: ["admin", "health"] as const,
  users: ["admin", "users"] as const,
  audits: ["admin", "audits"] as const,
  contentFingerprintStats: ["admin", "content-fingerprint-stats"] as const,
  paymentOrders: ["admin", "payment-orders"] as const,
  siteSections: ["admin", "site-sections"] as const,
  contentFiles: ["admin", "content-files"] as const,
};

export function useAdminMeQuery(enabled: boolean = true) {
  return useQuery({
    queryKey: adminQueryKeys.me,
    queryFn: fetchAdminMe,
    enabled,
    retry: false,
  });
}

export function useAdminHealthQuery(refetchEnabled: boolean = true) {
  return useQuery({
    queryKey: adminQueryKeys.health,
    queryFn: fetchHealthStatus,
    refetchInterval: refetchEnabled ? 20_000 : false,
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

export function useAdminContentFingerprintStatsQuery(enabled: boolean, refetchEnabled: boolean = true) {
  return useQuery({
    queryKey: adminQueryKeys.contentFingerprintStats,
    queryFn: fetchAdminContentFingerprintStats,
    enabled,
    refetchInterval: enabled && refetchEnabled ? 20_000 : false,
  });
}

export function useAdminPaymentOrdersQuery(enabled: boolean, refetchEnabled: boolean = true) {
  return useQuery({
    queryKey: adminQueryKeys.paymentOrders,
    queryFn: () => fetchAdminPaymentOrders({ limit: 20 }),
    enabled,
    refetchInterval: enabled && refetchEnabled ? 20_000 : false,
  });
}

export function useAdminSiteSectionsQuery(enabled: boolean) {
  return useQuery({
    queryKey: adminQueryKeys.siteSections,
    queryFn: () => fetchSiteSections({ enabled_only: false }),
    enabled,
  });
}

export function useAdminContentFilesQuery(enabled: boolean, refetchEnabled: boolean = true) {
  return useQuery({
    queryKey: adminQueryKeys.contentFiles,
    queryFn: () => fetchContentFiles({ file_type: "pdf", page_size: 20 }),
    enabled,
    refetchInterval: enabled && refetchEnabled ? 20_000 : false,
  });
}

export function useAdminPromoteMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { userId: string; targetRole: "premium" | "admin" }) =>
      promoteAdminUser(payload.userId, payload.targetRole),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: adminQueryKeys.users });
      await queryClient.invalidateQueries({ queryKey: adminQueryKeys.audits });
      await queryClient.invalidateQueries({ queryKey: adminQueryKeys.paymentOrders });
    },
  });
}

export function useAdminDemoteMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { userId: string; targetRole: "user" | "premium"; premiumDays?: number }) =>
      demoteAdminUser(payload.userId, payload.targetRole, payload.premiumDays ?? 30),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: adminQueryKeys.users });
      await queryClient.invalidateQueries({ queryKey: adminQueryKeys.audits });
      await queryClient.invalidateQueries({ queryKey: adminQueryKeys.paymentOrders });
      await queryClient.invalidateQueries({ queryKey: adminQueryKeys.me });
    },
  });
}

export function useAdminResetPasswordMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { userId: string; newPassword: string }) =>
      resetAdminUserPassword(payload.userId, payload.newPassword),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: adminQueryKeys.users });
      await queryClient.invalidateQueries({ queryKey: adminQueryKeys.audits });
      await queryClient.invalidateQueries({ queryKey: adminQueryKeys.paymentOrders });
    },
  });
}

export function useAdminSiteSectionUpdateMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      siteSectionId: string;
      listSelectorConfig?: Record<string, unknown>;
      detailSelectorConfig?: Record<string, unknown>;
    }) =>
      updateSiteSection(payload.siteSectionId, {
        list_selector_config: payload.listSelectorConfig,
        detail_selector_config: payload.detailSelectorConfig,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: adminQueryKeys.siteSections });
      await queryClient.invalidateQueries({ queryKey: adminQueryKeys.audits });
    },
  });
}

export function useAdminSiteSectionBackfillMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (overwriteExisting: boolean = false) =>
      backfillSiteSectionSelectorConfig({ overwrite_existing: overwriteExisting, enabled_only: false }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: adminQueryKeys.siteSections });
      await queryClient.invalidateQueries({ queryKey: adminQueryKeys.audits });
    },
  });
}

export function useAdminSiteSectionPreviewMutation() {
  return useMutation({
    mutationFn: (payload: {
      siteSectionId: string;
      listSelectorConfig?: Record<string, unknown>;
      detailSelectorConfig?: Record<string, unknown>;
      sampleLinkUrl?: string | null;
    }) =>
      previewSiteSectionSelectors(payload.siteSectionId, {
        list_selector_config: payload.listSelectorConfig,
        detail_selector_config: payload.detailSelectorConfig,
        sample_link_url: payload.sampleLinkUrl ?? null,
      }),
  });
}

export function useAdminContentFileRetryMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (contentFileId: string) => retryContentFileParse(contentFileId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: adminQueryKeys.contentFiles });
      await queryClient.invalidateQueries({ queryKey: adminQueryKeys.audits });
      await queryClient.invalidateQueries({ queryKey: adminQueryKeys.siteSections });
    },
  });
}

export function useAdminMarkPaymentOrderPaidMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { orderId: string; providerPaymentRef?: string }) =>
      markAdminPaymentOrderPaid(payload.orderId, payload.providerPaymentRef),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: adminQueryKeys.paymentOrders });
      await queryClient.invalidateQueries({ queryKey: adminQueryKeys.users });
      await queryClient.invalidateQueries({ queryKey: adminQueryKeys.audits });
    },
  });
}

export function useAdminCreatePaymentOrderMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { userId: string; durationDays?: number; amountCents?: number }) =>
      createAdminPaymentOrderForUser(payload.userId, {
        duration_days: payload.durationDays ?? 30,
        amount_cents: payload.amountCents ?? 0,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: adminQueryKeys.paymentOrders });
      await queryClient.invalidateQueries({ queryKey: adminQueryKeys.users });
      await queryClient.invalidateQueries({ queryKey: adminQueryKeys.audits });
    },
  });
}
