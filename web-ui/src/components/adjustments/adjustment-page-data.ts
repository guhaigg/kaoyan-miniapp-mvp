import type { AdjustmentSearchRequest, SearchItem } from "@/lib/api";

export type AdjustmentPageState = {
  keywords: string;
  schoolName: string;
  major: string;
  schoolTier: string;
  candidateScore: string;
  historyBackedOnly: boolean;
  page: number;
};

export type AdjustmentPageSummary = {
  total: number;
  urgentCount: number;
  watchMatchCount: number;
  latestPublishedLabel: string | null;
};

export function parseAdjustmentPageState(searchParams: URLSearchParams): AdjustmentPageState {
  return {
    keywords: searchParams.get("keywords") || "",
    schoolName: searchParams.get("school_name") || "",
    major: searchParams.get("major") || "",
    schoolTier: searchParams.get("school_tier") || "",
    candidateScore: searchParams.get("candidate_score") || "",
    historyBackedOnly: searchParams.get("history_backed_only") === "1",
    page: Number(searchParams.get("page") || 1),
  };
}

export function buildAdjustmentSearchPayload(state: AdjustmentPageState): AdjustmentSearchRequest {
  return {
    keywords: state.keywords.trim() || undefined,
    school_name: state.schoolName.trim() || undefined,
    major: state.major.trim() || undefined,
    school_tier: state.schoolTier.trim() || undefined,
    candidate_score: state.candidateScore.trim() ? Number(state.candidateScore) : undefined,
    history_backed_only: state.historyBackedOnly || undefined,
    page: state.page,
    page_size: 12,
  };
}

export function buildAdjustmentPageSummary(items: SearchItem[], watchlistCount: number): AdjustmentPageSummary {
  return {
    total: items.length,
    urgentCount: items.filter((item) => (item.adjustment_vacancy_count ?? 0) > 0 && (item.adjustment_vacancy_count ?? 0) <= 5).length,
    watchMatchCount: watchlistCount,
    latestPublishedLabel: items[0]?.published_at || items[0]?.updated_at || null,
  };
}

export function requiresAdjustmentLogin(accessLimited: boolean, isAnonymous: boolean) {
  return isAnonymous && accessLimited;
}
