"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  bootstrapAdminAnnouncementDepartment,
  bootstrapAdminAnnouncementSchool,
  backfillSiteSectionSelectorConfig,
  createAdminAnnouncementRebuild,
  createAdminPaymentOrderForUser,
  demoteAdminUser,
  fetchAdminContentExplain,
  fetchAdminAdjustmentIntelligence,
  fetchAdminContentFingerprintStats,
  fetchAdminRawDatasets,
  fetchAdminWorkflowDetail,
  fetchAdminWorkflows,
  fetchContentFiles,
  fetchAdminAudits,
  fetchAdminMe,
  fetchAdminPaymentOrders,
  fetchSchoolImportSeedSummaries,
  fetchAdminUsers,
  fetchHealthStatus,
  importAdjustmentPriorityTargets,
  importAdjustmentExpandedTargets,
  importAdjustmentSupplementalTargets,
  fetchSiteSections,
  markAdminPaymentOrderPaid,
  previewSiteSectionSelectors,
  reclassifyAdminContent,
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
  adjustmentIntelligence: ["admin", "adjustment-intelligence"] as const,
  contentFingerprintStats: ["admin", "content-fingerprint-stats"] as const,
  paymentOrders: ["admin", "payment-orders"] as const,
  siteSections: ["admin", "site-sections"] as const,
  contentFiles: ["admin", "content-files"] as const,
  schoolImportSeeds: ["admin", "school-import-seeds"] as const,
  rawDatasets: ["admin", "raw-datasets"] as const,
  workflows: (params: Record<string, unknown>) => ["admin", "workflows", params] as const,
  workflowDetail: (workflowRunId: string) => ["admin", "workflow-detail", workflowRunId] as const,
  contentExplain: (contentId: string) => ["admin", "content-explain", contentId] as const,
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

export function useAdminAdjustmentIntelligenceQuery(enabled: boolean) {
  return useQuery({
    queryKey: adminQueryKeys.adjustmentIntelligence,
    queryFn: fetchAdminAdjustmentIntelligence,
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

export function useAdminSchoolImportSeedSummariesQuery(enabled: boolean) {
  return useQuery({
    queryKey: adminQueryKeys.schoolImportSeeds,
    queryFn: fetchSchoolImportSeedSummaries,
    enabled,
  });
}

export function useAdminRawDatasetsQuery(enabled: boolean) {
  return useQuery({
    queryKey: adminQueryKeys.rawDatasets,
    queryFn: fetchAdminRawDatasets,
    enabled,
  });
}

export function useAdminWorkflowsQuery(
  enabled: boolean,
  params: {
    family?: string;
    scope_type?: string;
    scope_key?: string;
    status?: string;
    workflow_type?: string;
    host_key?: string;
    page?: number;
    page_size?: number;
  },
) {
  return useQuery({
    queryKey: adminQueryKeys.workflows(params),
    queryFn: () => fetchAdminWorkflows(params),
    enabled,
    refetchInterval: enabled ? 20_000 : false,
  });
}

export function useAdminWorkflowDetailQuery(enabled: boolean, workflowRunId: string | null) {
  return useQuery({
    queryKey: adminQueryKeys.workflowDetail(workflowRunId || ""),
    queryFn: () => fetchAdminWorkflowDetail(workflowRunId || ""),
    enabled: enabled && Boolean(workflowRunId),
    refetchInterval: enabled && workflowRunId ? 20_000 : false,
  });
}

export function useAdminContentExplainQuery(enabled: boolean, contentId: string | null) {
  return useQuery({
    queryKey: adminQueryKeys.contentExplain(contentId || ""),
    queryFn: () => fetchAdminContentExplain(contentId || ""),
    enabled: enabled && Boolean(contentId),
    retry: false,
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

export function useAdminAnnouncementSchoolBootstrapMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { schoolName: string; homepageUrl: string; seedUrls: string[]; maxSections: number }) =>
      bootstrapAdminAnnouncementSchool({
        school_name: payload.schoolName,
        homepage_url: payload.homepageUrl,
        seed_urls: payload.seedUrls,
        max_sections: payload.maxSections,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin", "workflows"] });
      await queryClient.invalidateQueries({ queryKey: adminQueryKeys.audits });
    },
  });
}

export function useAdminAnnouncementDepartmentBootstrapMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      schoolName: string;
      departmentName: string;
      departmentType: string;
      homepageUrl: string;
      seedUrls: string[];
      maxSections: number;
    }) =>
      bootstrapAdminAnnouncementDepartment({
        school_name: payload.schoolName,
        department_name: payload.departmentName,
        department_type: payload.departmentType,
        homepage_url: payload.homepageUrl,
        seed_urls: payload.seedUrls,
        max_sections: payload.maxSections,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin", "workflows"] });
      await queryClient.invalidateQueries({ queryKey: adminQueryKeys.audits });
    },
  });
}

export function useAdminAnnouncementRebuildMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      scopeType: "school" | "department";
      schoolName: string;
      departmentName?: string | null;
      homepageUrl?: string | null;
      seedUrls: string[];
      maxSections: number;
    }) =>
      createAdminAnnouncementRebuild({
        scope_type: payload.scopeType,
        school_name: payload.schoolName,
        department_name: payload.departmentName ?? null,
        homepage_url: payload.homepageUrl ?? null,
        seed_urls: payload.seedUrls,
        max_sections: payload.maxSections,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin", "workflows"] });
      await queryClient.invalidateQueries({ queryKey: adminQueryKeys.audits });
    },
  });
}

export function useAdminContentReclassifyMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (contentId: string) => reclassifyAdminContent(contentId),
    onSuccess: async (_result, contentId) => {
      await queryClient.invalidateQueries({ queryKey: ["admin", "workflows"] });
      await queryClient.invalidateQueries({ queryKey: adminQueryKeys.contentExplain(contentId) });
      await queryClient.invalidateQueries({ queryKey: adminQueryKeys.audits });
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

export function useAdminImportAdjustmentPriorityTargetsMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: importAdjustmentPriorityTargets,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: adminQueryKeys.audits });
      await queryClient.invalidateQueries({ queryKey: adminQueryKeys.schoolImportSeeds });
    },
  });
}

export function useAdminImportAdjustmentSupplementalTargetsMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: importAdjustmentSupplementalTargets,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: adminQueryKeys.audits });
      await queryClient.invalidateQueries({ queryKey: adminQueryKeys.schoolImportSeeds });
    },
  });
}

export function useAdminImportAdjustmentExpandedTargetsMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: importAdjustmentExpandedTargets,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: adminQueryKeys.audits });
      await queryClient.invalidateQueries({ queryKey: adminQueryKeys.schoolImportSeeds });
    },
  });
}
