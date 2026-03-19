"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type ReactNode, useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  CheckCircle2,
  ExternalLink,
  Clock3,
  History,
  Search,
  ShieldAlert,
  SlidersHorizontal,
  Target,
  TrendingUp,
  ChevronDown,
  X,
} from "lucide-react";
import FilterDrawer, { type SchoolTier, type StudyMode } from "@/components/search/FilterDrawer";
import FeedCard, { FeedCardSkeleton } from "@/components/shared/FeedCard";
import { AdjustmentSearchDetailResponse, ApiError, SearchItem, SearchResponse } from "@/lib/api";
import { fetchAdjustmentDetail } from "@/api/search";
import { useAdjustmentSearchMutation, useAnnouncementSearchMutation } from "@/hooks/useSearch";
import { useAddSubscriptionMutation, useDeleteSubscriptionMutation, useSubscriptionsQuery } from "@/hooks/useSubscriptions";
import { useAppStore } from "@/lib/store";

export default function SearchPage() {
  const router = useRouter();
  const { portalAuth } = useAppStore();
  const isAnonymous = !portalAuth;
  const [queryType, setQueryType] = useState<"announcements" | "adjustments">("announcements");
  const [isFilterOpen, setIsFilterOpen] = useState(false);
  const [keywords, setKeywords] = useState("");
  const [schoolName, setSchoolName] = useState("");
  const [majorFilter, setMajorFilter] = useState("");
  const [regionFilter, setRegionFilter] = useState("");
  const [cityFilter, setCityFilter] = useState("");
  const [yearFilter, setYearFilter] = useState("");
  const [schoolTierFilter, setSchoolTierFilter] = useState("");
  const [candidateScoreFilter, setCandidateScoreFilter] = useState("");
  const [advancedFiltersOpen, setAdvancedFiltersOpen] = useState(false);
  const [schoolTiers, setSchoolTiers] = useState<SchoolTier[]>([]);
  const [studyMode, setStudyMode] = useState<StudyMode>("all");
  const [onlyHistoryBacked, setOnlyHistoryBacked] = useState(false);
  const [onlyLongTrack, setOnlyLongTrack] = useState(false);
  const [onlyWithReferenceLinks, setOnlyWithReferenceLinks] = useState(false);
  const [hideMentorWarnings, setHideMentorWarnings] = useState(false);
  const [message, setMessage] = useState("");
  const [searchResult, setSearchResult] = useState<SearchResponse | null>(null);
  const [selectedAdjustmentItem, setSelectedAdjustmentItem] = useState<SearchItem | null>(null);
  const [adjustmentDetail, setAdjustmentDetail] = useState<AdjustmentSearchDetailResponse | null>(null);
  const [adjustmentDetailLoading, setAdjustmentDetailLoading] = useState(false);
  const [adjustmentDetailError, setAdjustmentDetailError] = useState("");

  const [score, setScore] = useState("");
  const [major, setMajor] = useState("");
  const [result, setResult] = useState<{ percent: number; text: string } | null>(null);

  const announcementMutation = useAnnouncementSearchMutation();
  const adjustmentMutation = useAdjustmentSearchMutation();
  const subscriptionsQuery = useSubscriptionsQuery(Boolean(portalAuth));
  const addSubscriptionMutation = useAddSubscriptionMutation();
  const deleteSubscriptionMutation = useDeleteSubscriptionMutation();

  const filteredItems = useMemo(() => {
    if (!searchResult) return [];
    const filtered = searchResult.items.filter((item) => {
      const text = [item.school_name, item.title, item.summary, item.major, item.city, item.school_tier].filter(Boolean).join(" ");
      const matchesTier =
        schoolTiers.length === 0 || schoolTiers.some((tier) => matchesSchoolTier(tier, item.school_tier, text));
      const matchesMode = matchesStudyMode(studyMode, text, item.adjustment_study_modes);
      return matchesTier && matchesMode;
    });
    if (queryType !== "adjustments") {
      return filtered;
    }
    return [...filtered].sort((left, right) => {
      const urgencyDelta = Number(isAdjustmentUrgent(right)) - Number(isAdjustmentUrgent(left));
      if (urgencyDelta !== 0) return urgencyDelta;
      const outlookDelta = adjustmentOutlookRank(right.historical_adjustment?.outlook) - adjustmentOutlookRank(left.historical_adjustment?.outlook);
      if (outlookDelta !== 0) return outlookDelta;
      const schoolDelta = schoolConfidenceRank(right.school_intelligence?.confidence_label) - schoolConfidenceRank(left.school_intelligence?.confidence_label);
      if (schoolDelta !== 0) return schoolDelta;
      const sampleDelta = (right.historical_adjustment?.sample_count || 0) - (left.historical_adjustment?.sample_count || 0);
      if (sampleDelta !== 0) return sampleDelta;
      const timingDelta = (right.release_timing?.sample_count || 0) - (left.release_timing?.sample_count || 0);
      if (timingDelta !== 0) return timingDelta;
      const referenceDelta =
        Number(Boolean(right.source_url || right.school_intelligence?.reference_urls?.length)) -
        Number(Boolean(left.source_url || left.school_intelligence?.reference_urls?.length));
      if (referenceDelta !== 0) return referenceDelta;
      const warningDelta = (left.mentor_radar?.warning_count || 0) - (right.mentor_radar?.warning_count || 0);
      if (warningDelta !== 0) return warningDelta;
      return new Date(right.published_at || right.updated_at).getTime() - new Date(left.published_at || left.updated_at).getTime();
    });
  }, [
    queryType,
    schoolTiers,
    searchResult,
    studyMode,
  ]);

  const currentPage = searchResult?.page || 1;
  const totalPages = searchResult ? Math.max(1, Math.ceil(searchResult.total / searchResult.page_size)) : 1;
  const hasLocalFilters =
    schoolTiers.length > 0 ||
    studyMode !== "all";
  const activeServerQuickFilters = [
    onlyHistoryBacked ? "有历史样本" : null,
    onlyLongTrack ? "连续活跃" : null,
    onlyWithReferenceLinks ? "带历史链接" : null,
    hideMentorWarnings ? "排除导师预警" : null,
  ].filter(Boolean) as string[];
  const hasServerQuickFilters = activeServerQuickFilters.length > 0;
  const showUpgradePanel = Boolean(portalAuth && !portalAuth.isAdmin && !portalAuth.isPremium);
  const adjustmentLocked = isAnonymous;
  const previewLimit = searchResult?.preview_limit ?? 2;
  const schoolSubscriptions = useMemo(() => {
    const map = new Map<string, string>();
    for (const item of subscriptionsQuery.data?.items || []) {
      if (item.subscription_type === "school" && item.status === "active") {
        map.set(item.value, item.id);
      }
    }
    return map;
  }, [subscriptionsQuery.data?.items]);

  const adjustmentQueryIntent = resolveAdjustmentQueryIntent({
    keywords,
    schoolName,
    majorFilter,
  });
  const resolvedSchoolName =
    queryType === "adjustments"
      ? adjustmentQueryIntent.schoolName
      : schoolName.trim() || (isSchoolLikeQuery(keywords.trim()) ? keywords.trim() : "");
  const resolvedMajorFilter =
    queryType === "adjustments" ? adjustmentQueryIntent.major : majorFilter.trim();
  const resolvedKeywords =
    queryType === "adjustments" ? adjustmentQueryIntent.keywords : keywords.trim();
  const primaryInputPlaceholder =
    queryType === "adjustments"
      ? "学校名、专业名或专业代码"
      : "输入院校代码、名称、学院或招生关键字...";
  const adjustmentIntent = getAdjustmentIntentMeta({
    keywords,
    schoolName,
    majorFilter,
  });
  const hasAdvancedAdjustmentFilters = Boolean(
    schoolName.trim() ||
      majorFilter.trim() ||
      regionFilter.trim() ||
      cityFilter.trim() ||
      yearFilter.trim() ||
      schoolTierFilter.trim() ||
      candidateScoreFilter.trim(),
  );

  const calculateMatch = () => {
    if (isAnonymous) {
      setMessage("调剂测算属于登录后的深度功能，请先登录。");
      return;
    }
    if (!score || !major) return;
    const diff = parseInt(score, 10) - (major === "工科" ? 273 : major === "理学" ? 279 : 346);
    setResult({
      percent: diff < 0 ? 5 : diff < 20 ? 45 : diff < 50 ? 75 : 95,
      text:
        diff < 0
          ? "低于国家A区线，建议重点关注B区偏远院校。"
          : diff < 50
            ? "初筛通过率较高，建议全力准备专业课复试。"
            : "高分段优势极大！可冲击优质调剂名额！",
    });
  };

  function buildAdjustmentQuickFilterPayload(overrides?: {
    historyBackedOnly?: boolean;
    longTrackOnly?: boolean;
    referenceLinksOnly?: boolean;
    hideMentorWarnings?: boolean;
  }) {
    return {
      history_backed_only: overrides?.historyBackedOnly ?? onlyHistoryBacked,
      long_track_only: overrides?.longTrackOnly ?? onlyLongTrack,
      reference_links_only: overrides?.referenceLinksOnly ?? onlyWithReferenceLinks,
      exclude_mentor_warnings: overrides?.hideMentorWarnings ?? hideMentorWarnings,
    };
  }

  async function triggerSearch(
    page = 1,
    overrides?: {
      historyBackedOnly?: boolean;
      longTrackOnly?: boolean;
      referenceLinksOnly?: boolean;
      hideMentorWarnings?: boolean;
    },
  ) {
    setMessage("");
    if (queryType === "adjustments" && isAnonymous) {
      setMessage("调剂检索属于登录后的深度功能，请先登录后继续。");
      return;
    }
    try {
      const payload =
        queryType === "announcements"
          ? await announcementMutation.mutateAsync({
              keywords: keywords.trim() || undefined,
              school_name: schoolName.trim() || (isSchoolLikeQuery(keywords.trim()) ? keywords.trim() : undefined),
              page,
              page_size: 12,
            })
          : await adjustmentMutation.mutateAsync({
              keywords: resolvedKeywords || undefined,
              school_name: resolvedSchoolName || undefined,
              major: resolvedMajorFilter || undefined,
              region: regionFilter.trim() || undefined,
              city: cityFilter.trim() || undefined,
              school_tier: schoolTierFilter.trim() || undefined,
              year: yearFilter.trim() ? Number(yearFilter.trim()) : undefined,
              candidate_score: candidateScoreFilter.trim() ? Number(candidateScoreFilter.trim()) : undefined,
              ...buildAdjustmentQuickFilterPayload(overrides),
              page,
              page_size: 12,
            });
      setSearchResult(payload);
      if (payload.total === 0) {
        setMessage(buildEmptyResultMessage(queryType, {
          keywords: resolvedKeywords,
          schoolName: resolvedSchoolName,
          majorFilter: resolvedMajorFilter,
          regionFilter,
          cityFilter,
          schoolTierFilter,
          yearFilter,
          candidateScoreFilter,
        }));
      } else {
        setMessage("");
      }
    } catch (error) {
      if (error instanceof ApiError) {
        setMessage(`查询失败：${error.message}`);
      } else {
        setMessage("查询失败：发生未识别的前端错误，请刷新页面后重试。");
      }
    }
  }

  async function handleSchoolBookmark(schoolName: string) {
    if (!portalAuth) {
      setMessage("登录后才能收藏院校并建立监控。");
      router.push("/login");
      return;
    }
    if (!portalAuth.isAdmin && !portalAuth.isPremium) {
      setMessage("院校收藏需要高级会员或管理员权限。");
      router.push("/account/billing");
      return;
    }

    const existingId = schoolSubscriptions.get(schoolName);
    try {
      if (existingId) {
        await deleteSubscriptionMutation.mutateAsync(existingId);
        setMessage(`已取消收藏 ${schoolName}`);
      } else {
        await addSubscriptionMutation.mutateAsync({
          subscription_type: "school",
          value: schoolName,
          category: "all",
        });
        setMessage(`已收藏 ${schoolName}`);
      }
    } catch (error) {
      if (error instanceof ApiError) {
        setMessage(`收藏失败：${error.message}`);
      } else {
        setMessage("收藏失败，请稍后重试。");
      }
    }
  }

  async function openAdjustmentDetail(item: SearchItem) {
    setSelectedAdjustmentItem(item);
    setAdjustmentDetail(null);
    setAdjustmentDetailError("");
    setAdjustmentDetailLoading(true);
    try {
      const detail = await fetchAdjustmentDetail(
        item.id,
        item.item_kind,
      );
      setAdjustmentDetail(detail);
    } catch (error) {
      if (error instanceof ApiError) {
        setAdjustmentDetailError(error.message);
      } else {
        setAdjustmentDetailError("详情加载失败，请稍后重试。");
      }
    } finally {
      setAdjustmentDetailLoading(false);
    }
  }

  function closeAdjustmentDetail() {
    setSelectedAdjustmentItem(null);
    setAdjustmentDetail(null);
    setAdjustmentDetailError("");
    setAdjustmentDetailLoading(false);
  }

  const isSearching = announcementMutation.isPending || adjustmentMutation.isPending;
  const adjustmentSummary = useMemo(() => {
    if (!searchResult || queryType !== "adjustments") return null;
    const items = filteredItems;
    const withHistory = items.filter((item) => item.historical_adjustment?.sample_count);
    const withWarnings = items.filter((item) => (item.mentor_radar?.warning_count || 0) > 0);
    const withLongTrack = items.filter((item) => item.school_intelligence?.confidence_label === "连续活跃");
    const nightReleases = items.filter((item) => {
      const value = item.published_at || item.updated_at;
      const hour = new Date(value).getHours();
      return Number.isFinite(hour) && hour >= 18;
    });
    return {
      hits: items.length,
      withHistory: withHistory.length,
      withWarnings: withWarnings.length,
      withLongTrack: withLongTrack.length,
      nightReleases: nightReleases.length,
    };
  }, [filteredItems, queryType, searchResult]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.98 }}
      transition={{ duration: 0.4 }}
      className="mx-auto max-w-6xl px-4 pb-20 pt-10"
    >
      <div className="mb-10 text-center">
        <h2 className="mb-4 text-4xl font-bold text-white">数据库全局检索</h2>
        <p className="font-mono text-sm text-slate-400">
          Indexed Records:{" "}
          <span className="text-cyan-400">{searchResult?.total ?? "点击检索后显示"}</span>
        </p>
      </div>

      <div className="mb-6 flex gap-4">
        <div className="flex-1 overflow-hidden rounded-3xl border border-white/10 bg-white/5 p-3 shadow-xl backdrop-blur-xl transition-colors hover:border-cyan-500/50">
          <div className="mb-3 grid grid-cols-2 gap-2 rounded-xl border border-white/10 bg-black/20 p-1 text-sm">
            <button
              type="button"
              className={`rounded-lg px-3 py-2 transition-colors ${
                queryType === "announcements"
                  ? "bg-cyan-500 text-white"
                  : "text-slate-300 hover:bg-white/10"
              }`}
              onClick={() => {
                setQueryType("announcements");
                setMessage("");
                setSearchResult(null);
              }}
            >
              公告检索
            </button>
            <button
              type="button"
              className={`rounded-lg px-3 py-2 transition-colors ${
                queryType === "adjustments"
                  ? "bg-cyan-500 text-white"
                  : "text-slate-300 hover:bg-white/10"
              } ${adjustmentLocked ? "cursor-not-allowed opacity-50 hover:bg-transparent" : ""}`}
              onClick={() => {
                if (adjustmentLocked) {
                  setMessage("调剂检索属于登录后的深度功能，请先登录。");
                  return;
                }
                setQueryType("adjustments");
                setMessage("");
                setSearchResult(null);
              }}
              disabled={adjustmentLocked}
            >
              调剂检索{adjustmentLocked ? " · 登录后开放" : ""}
            </button>
          </div>
          <div className="flex items-center gap-2">
            <Search className="ml-2 text-slate-400" />
            <input
              value={keywords}
              onChange={(event) => setKeywords(event.target.value)}
              onKeyDown={(event) => handleSearchInputKeyDown(event, () => triggerSearch(1))}
              type="text"
              placeholder={primaryInputPlaceholder}
              className="w-full border-none bg-transparent py-4 text-lg text-white placeholder-slate-500 focus:outline-none"
            />
            <button
              type="button"
              onClick={() => triggerSearch(1)}
              disabled={isSearching}
              className="rounded-2xl bg-cyan-600 px-8 py-3 font-bold text-white transition-colors hover:bg-cyan-500 active:scale-95 disabled:cursor-not-allowed disabled:opacity-70"
            >
              {isSearching ? "检索中..." : "检索"}
            </button>
          </div>
          <div className="mt-2 text-xs text-slate-500">
            {queryType === "adjustments"
              ? `当前识别：${adjustmentIntent.label}。${adjustmentIntent.description}`
              : "公告模式下，主搜索框适合输入学校简称、学院名或招生关键词。"}
          </div>
          {queryType === "adjustments" ? (
            <div className="mt-3 rounded-2xl border border-white/8 bg-black/15">
              <button
                type="button"
                onClick={() => setAdvancedFiltersOpen((value) => !value)}
                className="flex w-full items-center justify-between px-4 py-3 text-left text-sm text-slate-300"
              >
                <div>
                  <div className="font-semibold text-white">高级条件</div>
                  <div className="mt-1 text-xs text-slate-500">
                    用于精确限定院校、专业、地区和分数；不填也可以直接搜。
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  {hasAdvancedAdjustmentFilters ? (
                    <span className="rounded-full border border-cyan-400/20 bg-cyan-500/10 px-3 py-1 text-[11px] font-semibold text-cyan-200">
                    已启用 {[
                        schoolName.trim() && "院校",
                        majorFilter.trim() && "专业",
                        regionFilter.trim() && "地区",
                        cityFilter.trim() && "城市",
                        yearFilter.trim() && "年份",
                        schoolTierFilter.trim() && "院校类别",
                        candidateScoreFilter.trim() && "分数",
                      ]
                        .filter(Boolean)
                        .join(" / ")}
                    </span>
                  ) : null}
                  <ChevronDown
                    size={18}
                    className={`text-slate-400 transition-transform ${advancedFiltersOpen ? "rotate-180" : ""}`}
                  />
                </div>
              </button>
              {advancedFiltersOpen ? (
                <div className="grid gap-2 border-t border-white/8 px-4 pb-4 pt-3 md:grid-cols-7">
                  <input
                    value={schoolName}
                    onChange={(event) => setSchoolName(event.target.value)}
                    onKeyDown={(event) => handleSearchInputKeyDown(event, () => triggerSearch(1))}
                    placeholder="精确院校（可选）"
                    className="rounded-xl border border-white/10 bg-black/30 px-4 py-2.5 text-sm text-white outline-none transition-colors focus:border-cyan-400"
                  />
                  <input
                    value={majorFilter}
                    onChange={(event) => setMajorFilter(event.target.value)}
                    onKeyDown={(event) => handleSearchInputKeyDown(event, () => triggerSearch(1))}
                    placeholder="精确专业/代码（可选）"
                    className="rounded-xl border border-white/10 bg-black/30 px-4 py-2.5 text-sm text-white outline-none transition-colors focus:border-cyan-400"
                  />
                  <input
                    value={regionFilter}
                    onChange={(event) => setRegionFilter(event.target.value)}
                    onKeyDown={(event) => handleSearchInputKeyDown(event, () => triggerSearch(1))}
                    placeholder="地区（如 湖北、武汉）"
                    className="rounded-xl border border-white/10 bg-black/30 px-4 py-2.5 text-sm text-white outline-none transition-colors focus:border-cyan-400"
                  />
                  <input
                    value={cityFilter}
                    onChange={(event) => setCityFilter(event.target.value)}
                    onKeyDown={(event) => handleSearchInputKeyDown(event, () => triggerSearch(1))}
                    placeholder="城市（如 武汉、上海）"
                    className="rounded-xl border border-white/10 bg-black/30 px-4 py-2.5 text-sm text-white outline-none transition-colors focus:border-cyan-400"
                  />
                  <input
                    value={yearFilter}
                    onChange={(event) => setYearFilter(event.target.value)}
                    onKeyDown={(event) => handleSearchInputKeyDown(event, () => triggerSearch(1))}
                    placeholder="年份（如 2026）"
                    className="rounded-xl border border-white/10 bg-black/30 px-4 py-2.5 text-sm text-white outline-none transition-colors focus:border-cyan-400"
                  />
                  <select
                    value={schoolTierFilter}
                    onChange={(event) => setSchoolTierFilter(event.target.value)}
                    className="rounded-xl border border-white/10 bg-black/30 px-4 py-2.5 text-sm text-white outline-none transition-colors focus:border-cyan-400"
                  >
                    <option value="">院校类别（全部）</option>
                    <option value="985">985</option>
                    <option value="211">211</option>
                    <option value="双一流">双一流</option>
                    <option value="普本">普本</option>
                  </select>
                  <input
                    value={candidateScoreFilter}
                    onChange={(event) => setCandidateScoreFilter(event.target.value)}
                    onKeyDown={(event) => handleSearchInputKeyDown(event, () => triggerSearch(1))}
                    placeholder="你的分数（可选）"
                    className="rounded-xl border border-white/10 bg-black/30 px-4 py-2.5 text-sm text-white outline-none transition-colors focus:border-cyan-400"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      setKeywords("");
                      setSchoolName("");
                      setMajorFilter("");
                      setRegionFilter("");
                      setCityFilter("");
                      setYearFilter("");
                      setSchoolTierFilter("");
                      setCandidateScoreFilter("");
                      setSchoolTiers([]);
                      setStudyMode("all");
                      setOnlyHistoryBacked(false);
                      setOnlyLongTrack(false);
                      setOnlyWithReferenceLinks(false);
                      setHideMentorWarnings(false);
                      setSearchResult(null);
                      setMessage("");
                    }}
                    className="rounded-xl border border-white/20 bg-white/5 px-4 py-2.5 text-sm text-slate-200 transition-colors hover:bg-white/10"
                  >
                    清空筛选
                  </button>
                </div>
              ) : null}
            </div>
          ) : (
            <div className="mt-3 grid gap-2 md:grid-cols-3">
              <input
                value={schoolName}
                onChange={(event) => setSchoolName(event.target.value)}
                onKeyDown={(event) => handleSearchInputKeyDown(event, () => triggerSearch(1))}
                placeholder="院校名（可选）"
                className="rounded-xl border border-white/10 bg-black/30 px-4 py-2.5 text-sm text-white outline-none transition-colors focus:border-cyan-400"
              />
              <input
                value={majorFilter}
                onChange={(event) => setMajorFilter(event.target.value)}
                onKeyDown={(event) => handleSearchInputKeyDown(event, () => triggerSearch(1))}
                placeholder="专业（可选）"
                className="rounded-xl border border-white/10 bg-black/30 px-4 py-2.5 text-sm text-white outline-none transition-colors focus:border-cyan-400"
              />
              <button
                type="button"
                onClick={() => {
                  setKeywords("");
                  setSchoolName("");
                  setMajorFilter("");
                  setCityFilter("");
                  setYearFilter("");
                  setSchoolTierFilter("");
                  setSchoolTiers([]);
                  setStudyMode("all");
                  setOnlyHistoryBacked(false);
                  setOnlyLongTrack(false);
                  setOnlyWithReferenceLinks(false);
                  setHideMentorWarnings(false);
                  setSearchResult(null);
                  setMessage("");
                }}
                className="rounded-xl border border-white/20 bg-white/5 px-4 py-2.5 text-sm text-slate-200 transition-colors hover:bg-white/10"
              >
                清空筛选
              </button>
            </div>
          )}
        </div>

        <button
          type="button"
          onClick={() => setIsFilterOpen(true)}
          className="hidden rounded-3xl border border-white/10 bg-white/5 px-6 text-slate-300 shadow-xl transition-colors hover:bg-white/10 hover:text-white md:flex md:flex-col md:items-center md:justify-center md:gap-1"
        >
          <SlidersHorizontal size={20} />
          <span className="text-[10px] font-bold tracking-[0.18em]">筛选</span>
        </button>
      </div>

      <FilterDrawer
        isOpen={isFilterOpen}
        onClose={() => setIsFilterOpen(false)}
        tiers={schoolTiers}
        studyMode={studyMode}
        onToggleTier={(value) =>
          setSchoolTiers((prev) =>
            prev.includes(value) ? prev.filter((item) => item !== value) : [...prev, value],
          )
        }
        onStudyModeChange={setStudyMode}
        onReset={() => {
          setSchoolTiers([]);
          setStudyMode("all");
        }}
        resultCount={searchResult ? filteredItems.length : 0}
      />

      {showUpgradePanel ? (
        <div className="mb-8 overflow-hidden rounded-3xl border border-amber-400/20 bg-[linear-gradient(135deg,rgba(120,53,15,0.38),rgba(20,24,36,0.9))] p-6 shadow-2xl">
          <div className="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
            <div className="max-w-2xl">
              <div className="mb-2 text-xs font-semibold uppercase tracking-[0.28em] text-amber-300">Premium Access</div>
              <h3 className="text-2xl font-bold text-white">院校收藏和定时监控没有入口，不是你没找到，是我们埋得太深了。</h3>
              <p className="mt-2 text-sm leading-7 text-amber-50/85">
                现在普通账号想用院校收藏、实时提示和定时巡检，需要先开通高级会员。入口已经前置到这里，打开后可以直接创建会员订单。
              </p>
              <div className="mt-4 flex flex-wrap gap-2 text-xs text-amber-100/90">
                <span className="rounded-full border border-amber-300/20 bg-black/20 px-3 py-1">院校收藏</span>
                <span className="rounded-full border border-amber-300/20 bg-black/20 px-3 py-1">定时查询</span>
                <span className="rounded-full border border-amber-300/20 bg-black/20 px-3 py-1">新信息直推</span>
              </div>
            </div>
            <div className="flex shrink-0 flex-col gap-3">
              <Link
                href="/account/billing"
                className="rounded-2xl bg-amber-400 px-6 py-3 text-center text-sm font-bold text-black transition-colors hover:bg-amber-300"
              >
                立即开通高级会员
              </Link>
              <div className="text-center text-xs text-amber-100/70">订单创建后由后台确认支付并发放权益</div>
            </div>
          </div>
        </div>
      ) : null}

      {isAnonymous ? (
        <div className="mb-8 overflow-hidden rounded-3xl border border-cyan-400/20 bg-[linear-gradient(135deg,rgba(8,25,40,0.95),rgba(5,10,19,0.96))] p-6 shadow-2xl">
          <div className="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
            <div className="max-w-2xl">
              <div className="mb-2 text-xs font-semibold uppercase tracking-[0.28em] text-cyan-300">Visitor Preview</div>
              <h3 className="text-2xl font-bold text-white">未登录只开放公告预览，且最多显示前两条。</h3>
              <p className="mt-2 text-sm leading-7 text-slate-300">
                登录后才开放完整分页、院校收藏、调剂检索、调剂测算和后续定时监控。匿名态只保留最轻的预览入口。
              </p>
            </div>
            <div className="flex shrink-0 flex-col gap-3">
              <Link
                href="/login"
                className="rounded-2xl bg-cyan-500 px-6 py-3 text-center text-sm font-bold text-white transition-colors hover:bg-cyan-400"
              >
                登录查看完整结果
              </Link>
              <Link
                href="/register"
                className="rounded-2xl border border-white/15 bg-white/5 px-6 py-3 text-center text-sm font-semibold text-white transition-colors hover:bg-white/10"
              >
                注册新账号
              </Link>
            </div>
          </div>
        </div>
      ) : null}

      {message ? (
        <div className="mb-8 rounded-2xl border border-white/10 bg-black/30 p-4 text-sm text-slate-300">
          {message}
        </div>
      ) : null}

      {queryType === "adjustments" ? (
        <section className="mb-6 overflow-hidden rounded-[28px] border border-cyan-400/15 bg-[radial-gradient(circle_at_top_left,rgba(8,145,178,0.14),transparent_30%),linear-gradient(180deg,rgba(10,15,24,0.98),rgba(8,12,20,0.95))] shadow-2xl">
          <div className="border-b border-white/8 px-5 py-5 md:px-6">
            <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
              <div>
                <div className="mb-2 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.26em] text-cyan-300/80">
                  <Target size={14} className="text-cyan-400" />
                  GEWUJL 情报分析终端
                </div>
                <h3 className="text-2xl font-black tracking-tight text-white">调剂实时决策流</h3>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
                  把历史调剂分数、导师评价、发布时间信号和实时公告揉成一条决策流。当前不是简单全文检索，而是按“能不能报、值不值得报、何时容易出结果”来排视角。
                </p>
              </div>
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <IntelStatCard label="命中情报" value={`${adjustmentSummary?.hits || 0}`} accent="cyan" />
                <IntelStatCard label="历史样本" value={`${adjustmentSummary?.withHistory || 0}`} accent="emerald" />
                <IntelStatCard label="导师预警" value={`${adjustmentSummary?.withWarnings || 0}`} accent="amber" />
                <IntelStatCard label="连续活跃" value={`${adjustmentSummary?.withLongTrack || 0}`} accent="emerald" />
                <IntelStatCard label="晚间发布" value={`${adjustmentSummary?.nightReleases || 0}`} accent="violet" />
              </div>
            </div>
          </div>

          <div className="grid gap-4 px-5 py-5 md:px-6 xl:grid-cols-3">
            <IntelSignalCard
              icon={<TrendingUp size={16} className="text-emerald-300" />}
              title="分数胜率"
              description={
                candidateScoreFilter.trim()
                  ? `已按你的分数 ${candidateScoreFilter.trim()} 分做历史对比，优先展示有分数样本的院校。`
                  : "输入你的初试分数后，卡片会直接给出历史最低分和胜率分层。"
              }
              accent="emerald"
            />
            <IntelSignalCard
              icon={<ShieldAlert size={16} className="text-amber-300" />}
              title="导师雷达"
              description="如果该校命中过去公开评价里的高风险导师信号，卡片会直接点亮导师预警。"
              accent="amber"
            />
            <IntelSignalCard
              icon={<History size={16} className="text-indigo-300" />}
              title="发布时间"
              description="当前先基于真实发布时间和历史样本覆盖做发榜信号，后续再叠加更细的生物钟统计。"
              accent="violet"
            />
          </div>

          <div className="border-t border-white/8 px-5 py-4 md:px-6">
            <div className="mb-3 text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
              情报快筛
            </div>
            <div className="flex flex-wrap gap-2">
              <IntelFilterChip
                active={onlyHistoryBacked}
                onClick={() => {
                  const nextValue = !onlyHistoryBacked;
                  setOnlyHistoryBacked(nextValue);
                  if (searchResult) {
                    void triggerSearch(1, { historyBackedOnly: nextValue });
                  }
                }}
                label="只看有历史样本"
              />
              <IntelFilterChip
                active={onlyLongTrack}
                onClick={() => {
                  const nextValue = !onlyLongTrack;
                  setOnlyLongTrack(nextValue);
                  if (searchResult) {
                    void triggerSearch(1, { longTrackOnly: nextValue });
                  }
                }}
                label="只看连续活跃"
              />
              <IntelFilterChip
                active={onlyWithReferenceLinks}
                onClick={() => {
                  const nextValue = !onlyWithReferenceLinks;
                  setOnlyWithReferenceLinks(nextValue);
                  if (searchResult) {
                    void triggerSearch(1, { referenceLinksOnly: nextValue });
                  }
                }}
                label="只看带历史链接"
              />
              <IntelFilterChip
                active={hideMentorWarnings}
                onClick={() => {
                  const nextValue = !hideMentorWarnings;
                  setHideMentorWarnings(nextValue);
                  if (searchResult) {
                    void triggerSearch(1, { hideMentorWarnings: nextValue });
                  }
                }}
                label="排除导师预警"
              />
            </div>
          </div>
        </section>
      ) : null}

      <div className="mb-12 min-h-[400px] space-y-4">
        {isSearching ? (
          <div className="grid gap-6 md:grid-cols-2">
            <FeedCardSkeleton />
            <FeedCardSkeleton />
          </div>
        ) : searchResult ? (
          <>
            <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-white/10 bg-black/25 px-4 py-3 text-sm text-slate-300">
              <span>
                当前页返回 <span className="text-cyan-300">{filteredItems.length}</span> 条
              </span>
              <span className="text-slate-500">/</span>
              <span>
                实际返回 <span className="text-white">{searchResult.items.length}</span> 条
              </span>
              <span className="text-slate-500">/</span>
              <span>
                总记录 <span className="text-white">{searchResult.total}</span>
              </span>
              {hasServerQuickFilters ? (
                <>
                  <span className="text-slate-500">/</span>
                  <span className="text-emerald-300">服务端快筛：{activeServerQuickFilters.join(" / ")}</span>
                </>
              ) : null}
              {searchResult.access_limited ? (
                <>
                  <span className="text-slate-500">/</span>
                  <span className="text-amber-300">匿名预览仅展示前 {previewLimit} 条</span>
                </>
              ) : null}
              {hasLocalFilters ? (
                <>
                  <span className="text-slate-500">/</span>
                  <span className="text-cyan-300">本地筛选已生效</span>
                </>
              ) : null}
            </div>

            {filteredItems.length > 0 ? (
              queryType === "adjustments" ? (
                <div className="space-y-4">
                  {filteredItems.map((item) => (
                    <AdjustmentIntelCard
                      key={item.id}
                      item={item}
                      candidateScore={candidateScoreFilter.trim() ? Number(candidateScoreFilter.trim()) : undefined}
                      onOpenDetail={() => openAdjustmentDetail(item)}
                      bookmark={
                        item.school_name
                          ? {
                              active: schoolSubscriptions.has(item.school_name),
                              available: !isAnonymous && (portalAuth?.isAdmin || portalAuth?.isPremium),
                              label: isAnonymous
                                ? "登录后可收藏院校"
                                : portalAuth?.isAdmin || portalAuth?.isPremium
                                  ? `${schoolSubscriptions.has(item.school_name) ? "取消收藏" : "收藏院校"}：${item.school_name}`
                                  : "院校收藏需要高级会员",
                              onToggle: () => handleSchoolBookmark(item.school_name as string),
                            }
                          : undefined
                      }
                    />
                  ))}
                </div>
              ) : (
                <div className="grid gap-6 md:grid-cols-2">
                  {filteredItems.map((item) => (
                    <FeedCard
                      key={item.id}
                      item={{
                        id: item.id,
                        type: item.category === "adjustment" ? "adjustment" : "announcement",
                        title: item.title,
                        content:
                          item.category === "adjustment" && item.historical_adjustment
                            ? [
                                item.summary || "系统已命中调剂历史样本。",
                                item.historical_adjustment.initial_score_min !== null
                                  ? `初试 ${item.historical_adjustment.initial_score_min}-${item.historical_adjustment.initial_score_max ?? item.historical_adjustment.initial_score_min}`
                                  : null,
                                item.historical_adjustment.adjustment_score_min !== null
                                  ? `调剂 ${item.historical_adjustment.adjustment_score_min}-${item.historical_adjustment.adjustment_score_max ?? item.historical_adjustment.adjustment_score_min}`
                                  : null,
                                item.historical_adjustment.national_line_zone_a !== null
                                  ? `A/B线 ${item.historical_adjustment.national_line_zone_a}/${item.historical_adjustment.national_line_zone_b}`
                                  : null,
                                item.historical_adjustment.sample_count > 0
                                  ? `样本 ${item.historical_adjustment.sample_count}`
                                  : null,
                                getPrimaryMentorLabel(item),
                              ]
                                .filter(Boolean)
                                .join(" · ")
                            : item.summary || "暂无摘要，点击查看源站原文。",
                        badges: [
                          ...(item.notice_kind === "link_notice" ? [{ label: "链接型公告", tone: "sky" as const }] : []),
                          ...(item.pdf_parse_status === "needs_ocr"
                            ? [{ label: "扫描件待查看", tone: "amber" as const }]
                            : []),
                          ...(item.category === "adjustment" && item.adjustment_has_vacancy
                            ? [{ label: "有缺额信号", tone: "amber" as const }]
                            : []),
                          ...(item.category === "adjustment" && item.adjustment_study_modes.includes("fulltime")
                            ? [{ label: "全日制", tone: "sky" as const }]
                            : []),
                          ...(item.category === "adjustment" && item.adjustment_study_modes.includes("parttime")
                            ? [{ label: "非全日制", tone: "sky" as const }]
                            : []),
                          ...(item.category === "adjustment" && item.adjustment_major_codes.length > 0
                            ? [{ label: `专业代码 ${item.adjustment_major_codes[0]}`, tone: "sky" as const }]
                            : []),
                          ...(item.category === "adjustment" && item.historical_adjustment?.outlook_label
                            ? [{ label: item.historical_adjustment.outlook_label, tone: "amber" as const }]
                            : []),
                          ...(item.category === "adjustment" && item.historical_adjustment?.min_score !== null
                            ? [{ label: `历史最低 ${item.historical_adjustment?.min_score}`, tone: "sky" as const }]
                            : []),
                          ...(getMentorWarningCount(item) > 0
                            ? [{ label: `本学校预警 ${getMentorWarningCount(item)}`, tone: "amber" as const }]
                            : []),
                          ...(getMentorWarningCount(item) === 0
                            ? getMentorPresenceLabels(item).map((label) => ({ label, tone: "sky" as const }))
                            : []),
                        ],
                        publishTime: item.published_at || item.updated_at,
                        href: item.source_url,
                        isUrgent: /紧急|截止|补录|缺额/i.test(
                          `${item.title} ${item.summary || ""} ${item.major || ""}`,
                        ),
                        tags:
                          item.tags && item.tags.length > 0
                            ? item.tags
                            : [
                                item.category === "adjustment" ? "调剂动态" : "最新公告",
                                item.school_name || "未知院校",
                                item.region || "区域待补充",
                                item.major || "专业待补充",
                              ],
                        bookmark: item.school_name
                          ? {
                              active: schoolSubscriptions.has(item.school_name),
                              available: !isAnonymous && (portalAuth?.isAdmin || portalAuth?.isPremium),
                              label: isAnonymous
                                ? "登录后可收藏院校"
                                : portalAuth?.isAdmin || portalAuth?.isPremium
                                  ? `${schoolSubscriptions.has(item.school_name) ? "取消收藏" : "收藏院校"}：${item.school_name}`
                                  : "院校收藏需要高级会员",
                              onToggle: () => handleSchoolBookmark(item.school_name as string),
                            }
                          : undefined,
                      }}
                    />
                  ))}
                </div>
              )
            ) : (
              <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-8 text-sm text-slate-300">
                <div className="text-lg font-semibold text-white">
                  {buildEmptyStateTitle(queryType, Boolean(searchResult.total))}
                </div>
                <p className="mt-3 leading-7 text-slate-300">
                  {buildEmptyStateDetail(queryType, Boolean(searchResult.total), hasLocalFilters)}
                </p>
                <div className="mt-4 flex flex-wrap gap-2 text-xs text-slate-300">
                  {queryType === "adjustments" ? (
                    <>
                      <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1">先去掉一个筛选条件</span>
                      <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1">优先尝试学校名或专业代码</span>
                      <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1">城市和院校类别可单独试</span>
                      <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1">
                        {hasServerQuickFilters ? "必要时取消服务端情报快筛" : "必要时取消情报快筛"}
                      </span>
                    </>
                  ) : (
                    <>
                      <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1">缩短关键词</span>
                      <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1">先只搜学校名</span>
                      <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1">再叠加学院或招生词</span>
                    </>
                  )}
                </div>
              </div>
            )}

            {searchResult.access_limited ? (
              <div className="rounded-3xl border border-amber-400/20 bg-[linear-gradient(135deg,rgba(120,53,15,0.35),rgba(20,24,36,0.92))] p-6 text-sm text-amber-50/85">
                当前是匿名预览模式，只返回最前面的 {previewLimit} 条公告。继续查看完整结果、收藏院校或进入调剂链路，需要先登录。
                <div className="mt-4 flex flex-wrap gap-3">
                  <Link
                    href="/login"
                    className="rounded-xl bg-amber-400 px-4 py-2.5 font-semibold text-black transition-colors hover:bg-amber-300"
                  >
                    登录查看完整结果
                  </Link>
                  <Link
                    href="/register"
                    className="rounded-xl border border-white/15 bg-black/20 px-4 py-2.5 font-semibold text-white transition-colors hover:bg-black/30"
                  >
                    先注册账号
                  </Link>
                </div>
              </div>
            ) : null}

            <div className="flex items-center justify-between rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-sm">
              <span className="text-slate-300">
                第 {currentPage}/{totalPages} 页 · 共 {searchResult.total} 条
              </span>
              <div className="flex gap-2">
                <button
                  disabled={currentPage <= 1 || isSearching || searchResult.access_limited}
                  onClick={() => triggerSearch(currentPage - 1)}
                  className="rounded-lg border border-white/20 bg-white/5 px-3 py-1.5 text-slate-200 transition-colors hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  上一页
                </button>
                <button
                  disabled={currentPage >= totalPages || isSearching || searchResult.access_limited}
                  onClick={() => triggerSearch(currentPage + 1)}
                  className="rounded-lg border border-white/20 bg-white/5 px-3 py-1.5 text-slate-200 transition-colors hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  下一页
                </button>
              </div>
            </div>
          </>
        ) : queryType === "adjustments" ? (
          <div className="rounded-3xl border border-cyan-400/15 bg-[linear-gradient(180deg,rgba(10,15,24,0.92),rgba(8,12,20,0.92))] p-8 text-sm text-slate-300">
            <div className="max-w-3xl">
              <div className="mb-2 text-xs font-semibold uppercase tracking-[0.24em] text-cyan-300/80">
                Ready
              </div>
              <h4 className="text-xl font-bold text-white">输入院校、专业、地区或分数后开始检索。</h4>
              <p className="mt-3 leading-7 text-slate-400">
                这个页面现在会把实时调剂公告和历史分数、导师评价、发布时间规律一起给出。没点检索之前，不应该是空白页，只是还没有把结果流拉出来。
              </p>
              <div className="mt-4 flex flex-wrap gap-2 text-xs text-slate-300">
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1">支持初试分数</span>
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1">支持历史来源链接</span>
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1">支持导师预警筛除</span>
              </div>
            </div>
          </div>
        ) : null}
      </div>

      <AdjustmentDetailDrawer
        item={selectedAdjustmentItem}
        detail={adjustmentDetail}
        loading={adjustmentDetailLoading}
        error={adjustmentDetailError}
        onClose={closeAdjustmentDetail}
      />

      <div className={`relative overflow-hidden rounded-3xl border p-8 shadow-2xl backdrop-blur-xl ${isAnonymous ? "border-white/10 bg-white/[0.04]" : "border-cyan-500/20 bg-cyan-950/10"}`}>
        <div className="pointer-events-none absolute right-0 top-0 h-64 w-64 -translate-y-1/2 translate-x-1/2 rounded-full bg-cyan-500/10 blur-3xl" />
        <div className="relative z-10 flex flex-col items-center gap-8 md:flex-row">
          <div className="text-white md:w-1/3">
            <h3 className="mb-2 flex items-center gap-2 text-2xl font-bold">
              <Target className="text-cyan-400" /> 调剂雷达测算
            </h3>
            <p className="text-sm leading-relaxed text-slate-400">
              {isAnonymous ? "登录后开放调剂测算、调剂检索和更多深度能力。" : "系统将比对往年国家线及院系均分，测算你的初筛通过率。"}
            </p>
          </div>
          <div className="flex w-full flex-col gap-4 sm:flex-row md:w-2/3">
            <input
              type="number"
              placeholder="初试总分"
              value={score}
              onChange={(event) => setScore(event.target.value)}
              disabled={isAnonymous}
              className="w-full rounded-xl border border-white/10 bg-black/40 px-5 py-4 text-white outline-none transition-colors focus:border-cyan-400 sm:w-32"
            />
            <select
              value={major}
              onChange={(event) => setMajor(event.target.value)}
              disabled={isAnonymous}
              className="flex-1 appearance-none rounded-xl border border-white/10 bg-black/40 px-5 py-4 text-white outline-none transition-colors focus:border-cyan-400"
            >
              <option value="" disabled>
                选择门类
              </option>
              <option value="工科">工科(不含照顾) - 历年均线约 273</option>
              <option value="理学">理学 - 历年均线约 279</option>
            </select>
            <button
              type="button"
              onClick={calculateMatch}
              disabled={isAnonymous}
              className="whitespace-nowrap rounded-xl bg-cyan-500 px-8 py-4 font-bold text-white shadow-[0_0_15px_rgba(6,182,212,0.3)] transition-all hover:bg-cyan-400 active:scale-95 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isAnonymous ? "登录后开放" : "测算胜率"}
            </button>
          </div>
        </div>

        <AnimatePresence>
          {result ? (
            <motion.div
              initial={{ height: 0, opacity: 0, marginTop: 0 }}
              animate={{ height: "auto", opacity: 1, marginTop: 32 }}
              exit={{ height: 0, opacity: 0, marginTop: 0 }}
              className="overflow-hidden rounded-2xl border border-white/5 bg-black/40 p-6"
            >
              <div className="mb-3 flex items-end justify-between">
                <span className="text-sm text-slate-300">历史大数据预估通过率：</span>
                <span className="font-mono text-4xl font-bold text-cyan-400">
                  {result.percent}%
                </span>
              </div>
              <div className="h-4 w-full overflow-hidden rounded-full border border-white/5 bg-white/5 p-0.5">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${result.percent}%` }}
                  transition={{ duration: 1.2, ease: "easeOut" }}
                  className="h-full rounded-full bg-gradient-to-r from-blue-500 to-cyan-400 shadow-[0_0_10px_rgba(6,182,212,0.5)]"
                />
              </div>
              <p className="mt-4 font-mono text-sm text-slate-400">{result.text}</p>
            </motion.div>
          ) : null}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}

function IntelStatCard({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent: "cyan" | "emerald" | "amber" | "violet";
}) {
  const styles = {
    cyan: "border-cyan-400/15 bg-cyan-500/10 text-cyan-200",
    emerald: "border-emerald-400/15 bg-emerald-500/10 text-emerald-200",
    amber: "border-amber-400/15 bg-amber-500/10 text-amber-200",
    violet: "border-violet-400/15 bg-violet-500/10 text-violet-200",
  }[accent];
  return (
    <div className={`rounded-2xl border px-4 py-3 ${styles}`}>
      <div className="text-[11px] uppercase tracking-[0.22em] text-white/60">{label}</div>
      <div className="mt-1 text-2xl font-black text-white">{value}</div>
    </div>
  );
}

function IntelSignalCard({
  icon,
  title,
  description,
  accent,
}: {
  icon: ReactNode;
  title: string;
  description: string;
  accent: "emerald" | "amber" | "violet";
}) {
  const styles = {
    emerald: "border-emerald-400/15 bg-emerald-500/10",
    amber: "border-amber-400/15 bg-amber-500/10",
    violet: "border-violet-400/15 bg-violet-500/10",
  }[accent];
  return (
    <div className={`rounded-2xl border px-4 py-4 ${styles}`}>
      <div className="flex items-center gap-2 text-sm font-semibold text-white">
        {icon}
        {title}
      </div>
      <p className="mt-2 text-sm leading-6 text-slate-300">{description}</p>
    </div>
  );
}

function IntelFilterChip({
  active,
  onClick,
  label,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors ${
        active
          ? "border-cyan-400/40 bg-cyan-400/12 text-cyan-100"
          : "border-white/10 bg-white/5 text-slate-300 hover:bg-white/10"
      }`}
    >
      {label}
    </button>
  );
}

function AdjustmentIntelCard({
  item,
  candidateScore,
  onOpenDetail,
  bookmark,
}: {
  item: SearchItem;
  candidateScore?: number;
  onOpenDetail: () => void;
  bookmark?: {
    active: boolean;
    available: boolean;
    label: string;
    onToggle: () => Promise<void> | void;
  };
}) {
  const isUrgent = /紧急|截止|补录|缺额/i.test(`${item.title} ${item.summary || ""} ${item.major || ""}`);
  const probability = getAdjustmentProbability(
    candidateScore,
    item.historical_adjustment?.min_score ?? null,
    item.historical_adjustment?.max_score ?? null,
  );
  const releaseTime = formatIntelTime(item.published_at || item.updated_at);
  const mentorSignals = getMentorScopeSignals(item);
  const mentorWarning = getMentorWarningCount(item) > 0;
  const initialScore = formatScoreRange(
    item.historical_adjustment?.initial_score_min ?? item.historical_adjustment?.min_score,
    item.historical_adjustment?.initial_score_max ?? item.historical_adjustment?.max_score,
  );
  const adjustmentScore = formatScoreRange(
    item.historical_adjustment?.adjustment_score_min,
    item.historical_adjustment?.adjustment_score_max,
  );
  const primaryFacts = [
    { label: "学院", value: item.department_name || "待补充" },
    { label: "专业", value: item.major || "待补充" },
    { label: "代码", value: item.adjustment_major_codes[0] || "待补充" },
    { label: "初试分数", value: initialScore },
    { label: "调剂分数", value: adjustmentScore },
    { label: "调剂人数", value: item.adjustment_vacancy_count ? `${item.adjustment_vacancy_count}` : "待补充" },
    { label: "院校层级", value: item.school_tier || "待补充" },
    { label: "学习方式", value: formatStudyModeLabel(null, item.adjustment_study_modes) },
  ];

  async function handleBookmarkClick() {
    if (!bookmark) return;
    await bookmark.onToggle();
  }

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 20, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, scale: 0.96 }}
      transition={{ type: "spring", stiffness: 260, damping: 28 }}
      className={`relative overflow-hidden rounded-[26px] border bg-[linear-gradient(180deg,rgba(15,23,42,0.88),rgba(6,10,18,0.94))] shadow-[0_24px_80px_rgba(0,0,0,0.34)] ${isUrgent ? "border-cyan-400/25" : "border-white/10"}`}
    >
      {isUrgent ? <div className="absolute inset-y-0 left-0 w-1 bg-cyan-400 shadow-[0_0_16px_rgba(34,211,238,0.75)]" /> : null}
      <div className="absolute -right-12 top-0 h-32 w-32 rounded-full bg-cyan-500/10 blur-3xl" />
      <div className="relative space-y-5 p-5 md:p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="mb-1 text-xs font-semibold uppercase tracking-[0.18em] text-cyan-300/80">
              {item.adjustment_year || "年份待补充"} · {item.region || "地区待补充"}
            </div>
            <h3 className="text-2xl font-black tracking-tight text-white">{item.school_name || "未知院校"}</h3>
            <p className="mt-2 text-sm font-medium leading-6 text-slate-300">
              {[item.department_name, item.major, item.adjustment_major_codes[0]].filter(Boolean).join(" · ") || "学院与专业待补充"}
            </p>
          </div>
          <div className="shrink-0 text-right">
            <div className="flex items-center justify-end gap-1 text-xs font-mono text-slate-500">
              <Clock3 size={13} />
              {releaseTime}
            </div>
            <div className="mt-2 flex flex-wrap justify-end gap-2">
              {isUrgent ? (
                <span className="inline-flex rounded-full border border-cyan-400/30 bg-cyan-400/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.18em] text-cyan-200">
                  最新
                </span>
              ) : null}
              {mentorWarning ? (
                <span className="inline-flex rounded-full border border-red-400/25 bg-red-500/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.18em] text-red-200">
                  导师预警
                </span>
              ) : null}
            </div>
          </div>
        </div>

        <div className="grid gap-3 border-t border-white/8 pt-4 sm:grid-cols-2 xl:grid-cols-5">
          {primaryFacts.map((fact) => (
            <div key={fact.label} className="rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3">
              <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">{fact.label}</div>
              <div className="mt-2 text-base font-semibold text-white">{fact.value}</div>
            </div>
          ))}
          <div className={`rounded-2xl border px-4 py-3 ${probability.bg} ${probability.border}`}>
            <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-white/65">胜率判断</div>
            <div className={`mt-2 flex items-center gap-2 text-lg font-black ${probability.textClass}`}>
              <TrendingUp size={16} className={probability.iconClass} />
              {probability.label}
            </div>
          </div>
          <div className={`rounded-2xl border px-4 py-3 ${mentorWarning ? "border-red-400/20 bg-red-500/10" : "border-white/10 bg-white/[0.04]"}`}>
            <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-white/65">导师情况</div>
            <div className="mt-2 flex items-center gap-2 text-base font-semibold text-white">
              {mentorWarning ? <ShieldAlert size={16} className="text-red-300" /> : <CheckCircle2 size={16} className="text-emerald-300" />}
              {mentorWarning ? "有预警" : "可进一步看"}
            </div>
            <div className="mt-2 text-xs text-slate-300">
              {item.department_name ? `本学院 ${mentorSignals.department?.review_count ?? 0}` : "本学院 --"} / 本学校 {mentorSignals.school?.review_count ?? 0}
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-white/8 pt-4">
          <div className="text-xs text-slate-400">
            导师评价、发布时间、历史样本和来源链接都放在完整信息页里。
          </div>
          <div className="flex flex-wrap gap-2">
            {bookmark ? (
              <button
                type="button"
                onClick={handleBookmarkClick}
                className={`rounded-xl border px-3 py-2 text-sm font-semibold transition-colors ${
                  bookmark.active
                    ? "border-yellow-400/25 bg-yellow-500/10 text-yellow-200"
                    : bookmark.available
                      ? "border-white/15 bg-white/5 text-slate-200 hover:bg-white/10"
                      : "border-white/10 bg-white/[0.03] text-slate-400"
                }`}
                title={bookmark.label}
              >
                {bookmark.active ? "已收藏院校" : bookmark.available ? "收藏院校" : "收藏受限"}
              </button>
            ) : null}
            {item.source_url ? (
              <a
                href={item.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-xl bg-cyan-500 px-3 py-2 text-sm font-semibold text-white transition-colors hover:bg-cyan-400"
              >
                查看原文
              </a>
            ) : null}
            <button
              type="button"
              onClick={onOpenDetail}
              className="rounded-xl border border-white/15 bg-white/5 px-3 py-2 text-sm font-semibold text-slate-100 transition-colors hover:bg-white/10"
            >
              查看完整信息
            </button>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

function AdjustmentDetailDrawer({
  item,
  detail,
  loading,
  error,
  onClose,
}: {
  item: SearchItem | null;
  detail: AdjustmentSearchDetailResponse | null;
  loading: boolean;
  error: string;
  onClose: () => void;
}) {
  const [showAllMentorReviews, setShowAllMentorReviews] = useState(false);

  useEffect(() => {
    setShowAllMentorReviews(false);
  }, [item?.id, detail?.id]);

  const mentorSignals = detail ? getMentorScopeSignals(detail) : { department: null, school: null };
  const departmentMentorReviews = detail?.mentor_department_reviews || [];
  const schoolMentorReviews = detail?.mentor_school_reviews || detail?.mentor_reviews || [];
  const visibleDepartmentMentorReviews = showAllMentorReviews
    ? departmentMentorReviews
    : departmentMentorReviews.slice(0, 3);
  const visibleSchoolMentorReviews = showAllMentorReviews
    ? schoolMentorReviews
    : schoolMentorReviews.slice(0, 3);
  const summaryFacts = detail
    ? [
        { label: "学校", value: detail.school_name || "--" },
        { label: "学院", value: detail.department_name || "--" },
        { label: "专业", value: detail.major || "--" },
        { label: "专业代码", value: detail.major_code || "--" },
        { label: "初试分数", value: formatScoreRange(detail.initial_score_min ?? detail.min_score, detail.initial_score_max ?? detail.max_score) },
        { label: "调剂分数", value: formatScoreRange(detail.adjustment_score_min, detail.adjustment_score_max) },
        { label: "调剂人数", value: detail.vacancy_count?.toString() || "--" },
        { label: "院校层级", value: detail.school_tier || "--" },
        { label: "学习方式", value: formatStudyModeLabel(detail.study_mode, []) },
      ]
    : [];

  return (
    <AnimatePresence>
      {item ? (
        <motion.section
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 24 }}
          transition={{ type: "spring", stiffness: 220, damping: 28 }}
          className="fixed inset-0 z-50 overflow-y-auto bg-[radial-gradient(circle_at_top,rgba(8,145,178,0.14),transparent_26%),linear-gradient(180deg,rgba(5,8,16,0.98),rgba(8,11,19,0.99))]"
        >
          <div className="mx-auto max-w-7xl px-4 pb-10 pt-6 md:px-8">
            <div className="sticky top-4 z-10 mb-6 rounded-[28px] border border-white/10 bg-[linear-gradient(180deg,rgba(14,18,30,0.92),rgba(7,10,18,0.92))] p-5 shadow-[0_24px_80px_rgba(0,0,0,0.4)] backdrop-blur-xl">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-300/80">调剂完整信息页</div>
                  <h3 className="mt-2 text-3xl font-black tracking-tight text-white">
                    {detail?.school_name || item.school_name || "院校待补充"}
                  </h3>
                  <p className="mt-2 text-sm leading-6 text-slate-300">
                    {[detail?.department_name || item.department_name, detail?.major || item.major, detail?.major_code || item.adjustment_major_codes?.[0]].filter(Boolean).join(" · ")}
                  </p>
                  <p className="mt-2 text-sm leading-6 text-slate-400">
                    搜索页只保留首屏关键字段，导师评价、发布时间、历史样本和原始链接都在这里展开。
                  </p>
                </div>
                <button
                  type="button"
                  onClick={onClose}
                  className="rounded-2xl border border-white/10 bg-white/5 p-3 text-slate-300 transition-colors hover:bg-white/10 hover:text-white"
                >
                  <X size={18} />
                </button>
              </div>
              {detail ? (
                <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                  {summaryFacts.map((fact) => (
                    <div key={fact.label} className="rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3">
                      <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">{fact.label}</div>
                      <div className="mt-2 text-base font-semibold text-white">{fact.value}</div>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>

            {loading ? <div className="text-sm text-slate-400">详情加载中...</div> : null}
            {error ? <div className="rounded-2xl border border-red-400/20 bg-red-500/10 p-4 text-sm text-red-200">{error}</div> : null}

            {detail ? (
              <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
                <div className="space-y-6">
                  <DetailBlock title="基础信息">
                    <div className="grid gap-3 md:grid-cols-2">
                      <DetailRow label="院校" value={detail.school_name} />
                      <DetailRow label="学院" value={detail.department_name} />
                      <DetailRow label="专业" value={detail.major} />
                      <DetailRow label="专业代码" value={detail.major_code} />
                      <DetailRow label="地区" value={detail.region} />
                      <DetailRow label="城市" value={detail.city} />
                      <DetailRow label="院校层级" value={detail.school_tier} />
                      <DetailRow label="学校代码" value={detail.school_code} />
                      <DetailRow label="学习形式" value={detail.study_mode} />
                      <DetailRow label="验证状态" value={detail.verification_status} />
                    </div>
                  </DetailBlock>

                  <DetailBlock title="分数与判断">
                    <div className="grid gap-3 md:grid-cols-3">
                      <DetailStat label="初试最低" value={detail.initial_score_min ?? detail.min_score} />
                      <DetailStat label="初试最高" value={detail.initial_score_max ?? detail.max_score} />
                      <DetailStat label="调剂人数" value={detail.vacancy_count} />
                      <DetailStat label="调剂最低" value={detail.adjustment_score_min} />
                      <DetailStat label="调剂最高" value={detail.adjustment_score_max} />
                      <DetailStat
                        label={`等效到${detail.historical_adjustment?.national_line_year ?? "当前"}最低`}
                        value={detail.historical_adjustment?.min_score ?? detail.min_score}
                      />
                      <DetailStat
                        label={`等效到${detail.historical_adjustment?.national_line_year ?? "当前"}均值`}
                        value={detail.historical_adjustment?.avg_score ? Math.round(detail.historical_adjustment.avg_score) : null}
                      />
                      <DetailStat
                        label={`等效到${detail.historical_adjustment?.national_line_year ?? "当前"}最高`}
                        value={detail.historical_adjustment?.max_score ?? detail.max_score}
                      />
                    </div>
                    <div className="mt-4 rounded-2xl border border-cyan-400/15 bg-cyan-500/10 p-4 text-sm leading-7 text-slate-100">
                      {detail.historical_adjustment?.outlook_label
                        ? `历史样本判断：${detail.historical_adjustment.outlook_label}。`
                        : "当前没有足够历史分数样本，暂不输出胜率判断。"}{" "}
                      {detail.release_timing?.signal_detail || "发布时间规律样本不足。"}
                    </div>
                    <div className="mt-4 grid gap-3 md:grid-cols-2">
                      <DetailRow label="历史样本" value={`${detail.historical_adjustment?.sample_count ?? 0}`} />
                      <DetailRow label="覆盖年份" value={formatHistoricalYears(detail.historical_adjustment?.sample_years)} />
                      <DetailRow label="样本来源" value={formatHistoricalSourceTypes(detail.historical_adjustment?.source_types)} />
                      <DetailRow label="国家线" value={formatNationalLineDetail(detail.historical_adjustment)} />
                    </div>
                  </DetailBlock>

                  <DetailBlock title="真实内容">
                    <div className="space-y-3 text-sm leading-7 text-slate-300">
                      <p>{detail.summary || "暂无摘要。"}</p>
                      <p>
                        {detail.body ||
                          "这条结果来自结构化调剂表。当前可直接查看结构化字段、导师评价原文和真实来源；如果需要完整原始通知，请再打开底部原文来源。"}
                      </p>
                    </div>
                  </DetailBlock>

                  <DetailBlock title="来源与原文">
                    <div className="space-y-2">
                      {detail.links.length > 0 ? (
                        <>
                          <div className="text-sm leading-7 text-slate-400">
                            这里保留原始链接用于二次核验。正常使用时，优先看上面的结构化内容和导师评价。
                          </div>
                          {detail.links.map((link) => (
                            <a
                              key={`${link.source || "source"}-${link.url}`}
                              href={link.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="flex items-center justify-between rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-sm text-slate-200 transition-colors hover:bg-white/[0.08]"
                            >
                              <div>
                                <div className="font-semibold text-white">{link.label}</div>
                                <div className="mt-1 text-xs text-slate-400">{link.source || link.link_type || "source"}</div>
                              </div>
                              <ExternalLink size={16} className="text-slate-400" />
                            </a>
                          ))}
                        </>
                      ) : (
                        <div className="text-sm text-slate-500">当前没有可点击的原始链接。</div>
                      )}
                    </div>
                  </DetailBlock>
                </div>

                <div className="space-y-6">
                  <DetailBlock title="时间与状态">
                    <DetailRow label="发布时间" value={detail.published_at ? formatIntelTime(detail.published_at) : null} />
                    <DetailRow label="采集时间" value={detail.captured_at ? formatIntelTime(detail.captured_at) : null} />
                    <DetailRow label="更新时间" value={formatIntelTime(detail.updated_at)} />
                    <DetailRow label="活跃度" value={detail.school_intelligence?.confidence_label || null} />
                    <DetailRow label="发布时间规律" value={detail.release_timing?.signal_label || null} />
                    <DetailRow label="发榜样本年份" value={formatHistoricalYears(detail.release_timing?.sample_years)} />
                  </DetailBlock>

                  <DetailBlock title="导师雷达">
                    {detail.department_name ? (
                      <>
                        <DetailRow label="本学院风险" value={mentorSignals.department?.risk_label || "暂无明显预警"} />
                        <DetailRow label="本学院评价数" value={`${mentorSignals.department?.review_count ?? 0}`} />
                        <DetailRow label="本学院预警数" value={`${mentorSignals.department?.warning_count ?? 0}`} />
                      </>
                    ) : null}
                    <DetailRow label="本学校风险" value={mentorSignals.school?.risk_label || "暂无明显预警"} />
                    <DetailRow label="本学校评价数" value={`${mentorSignals.school?.review_count ?? 0}`} />
                    <DetailRow label="本学校预警数" value={`${mentorSignals.school?.warning_count ?? 0}`} />
                    <DetailRow
                      label="本学校高频标签"
                      value={mentorSignals.school?.top_tags?.slice(0, 4).join(" / ") || mentorSignals.department?.top_tags?.slice(0, 4).join(" / ") || "暂无"}
                    />
                  </DetailBlock>

                  <DetailBlock title="导师真实评价">
                    <div className="space-y-4">
                      {(departmentMentorReviews.length > 0 || schoolMentorReviews.length > 0) ? (
                        <>
                          <div className="rounded-2xl border border-amber-400/15 bg-amber-500/10 p-4 text-sm leading-7 text-amber-50">
                            这里先分开给你看本学院评价和本学校评价。本学校评价包含本学院评价，用来判断学院内外整体导师风格。
                          </div>
                          {detail.department_name ? (
                            <div className="space-y-3">
                              <div className="text-sm font-semibold text-slate-100">本学院评价</div>
                              {departmentMentorReviews.length > 0 ? visibleDepartmentMentorReviews.map((review, index) => (
                                <div key={`dept-${review.mentor_name}-${index}`} className="rounded-2xl border border-white/10 bg-black/20 p-4">
                                  <div className="flex flex-wrap items-center gap-2">
                                    <span className="text-sm font-semibold text-white">{review.mentor_name}</span>
                                    {review.department_name ? (
                                      <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[11px] text-slate-300">
                                        {review.department_name}
                                      </span>
                                    ) : null}
                                    {review.risk_level ? (
                                      <span
                                        className={`rounded-full px-2 py-0.5 text-[11px] ${
                                          review.risk_level === "warning"
                                            ? "border border-red-400/20 bg-red-500/10 text-red-200"
                                            : "border border-emerald-400/20 bg-emerald-500/10 text-emerald-200"
                                        }`}
                                      >
                                        {review.risk_level === "warning" ? "预警" : "正向"}
                                      </span>
                                    ) : null}
                                  </div>
                                  {review.review_tags.length > 0 ? (
                                    <div className="mt-2 flex flex-wrap gap-2">
                                      {review.review_tags.map((tag) => (
                                        <span key={tag} className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[11px] text-slate-300">
                                          {tag}
                                        </span>
                                      ))}
                                    </div>
                                  ) : null}
                                  <p className="mt-3 text-sm leading-7 text-slate-300">{review.review_text}</p>
                                </div>
                              )) : (
                                <div className="text-sm text-slate-500">当前没有可展示的本学院评价。</div>
                              )}
                            </div>
                          ) : null}
                          <div className="space-y-3">
                            <div className="text-sm font-semibold text-slate-100">本学校评价</div>
                            {schoolMentorReviews.length > 0 ? visibleSchoolMentorReviews.map((review, index) => (
                              <div key={`school-${review.mentor_name}-${index}`} className="rounded-2xl border border-white/10 bg-black/20 p-4">
                                <div className="flex flex-wrap items-center gap-2">
                                  <span className="text-sm font-semibold text-white">{review.mentor_name}</span>
                                  {review.department_name ? (
                                    <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[11px] text-slate-300">
                                      {review.department_name}
                                    </span>
                                  ) : null}
                                  {review.risk_level ? (
                                    <span
                                      className={`rounded-full px-2 py-0.5 text-[11px] ${
                                        review.risk_level === "warning"
                                          ? "border border-red-400/20 bg-red-500/10 text-red-200"
                                          : "border border-emerald-400/20 bg-emerald-500/10 text-emerald-200"
                                      }`}
                                    >
                                      {review.risk_level === "warning" ? "预警" : "正向"}
                                    </span>
                                  ) : null}
                                </div>
                                {review.review_tags.length > 0 ? (
                                  <div className="mt-2 flex flex-wrap gap-2">
                                    {review.review_tags.map((tag) => (
                                      <span key={tag} className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[11px] text-slate-300">
                                        {tag}
                                      </span>
                                    ))}
                                  </div>
                                ) : null}
                                <p className="mt-3 text-sm leading-7 text-slate-300">{review.review_text}</p>
                              </div>
                            )) : (
                              <div className="text-sm text-slate-500">当前没有可展示的本学校评价。</div>
                            )}
                          </div>
                          {(departmentMentorReviews.length > 3 || schoolMentorReviews.length > 3) ? (
                            <button
                              type="button"
                              onClick={() => setShowAllMentorReviews((value) => !value)}
                              className="rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-sm font-semibold text-slate-100 transition-colors hover:bg-white/[0.08]"
                            >
                              {showAllMentorReviews ? "收起更多评价" : "展开更多导师评价"}
                            </button>
                          ) : null}
                        </>
                      ) : (
                        <div className="text-sm text-slate-500">当前没有可展示的导师评价原文片段。</div>
                      )}
                    </div>
                  </DetailBlock>
                </div>
              </div>
            ) : null}
          </div>
        </motion.section>
      ) : null}
    </AnimatePresence>
  );
}

function DetailBlock({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-3xl border border-white/10 bg-white/[0.04] p-4">
      <div className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-cyan-300/80">{title}</div>
      <div className="space-y-2">{children}</div>
    </section>
  );
}

function DetailRow({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="flex items-start justify-between gap-4 text-sm">
      <span className="text-slate-500">{label}</span>
      <span className="text-right text-slate-200">{value || "--"}</span>
    </div>
  );
}

function DetailStat({ label, value }: { label: string; value: number | null | undefined }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
      <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">{label}</div>
      <div className="mt-2 text-2xl font-black text-white">{value ?? "--"}</div>
    </div>
  );
}

function getAdjustmentProbability(score?: number, min?: number | null, max?: number | null) {
  if (!score || min === null || min === undefined) {
    return {
      label: "等待评分",
      textClass: "text-slate-100",
      iconClass: "text-slate-300",
      bg: "bg-white/[0.04]",
      border: "border-white/10",
    };
  }
  if (score < min) {
    return {
      label: "炮灰警告",
      textClass: "text-red-300",
      iconClass: "text-red-300",
      bg: "bg-red-500/10",
      border: "border-red-400/20",
    };
  }
  if (max !== null && max !== undefined && score >= max) {
    return {
      label: "极大概率",
      textClass: "text-emerald-300",
      iconClass: "text-emerald-300",
      bg: "bg-emerald-500/10",
      border: "border-emerald-400/20",
    };
  }
  return {
    label: "过线可冲",
    textClass: "text-amber-300",
    iconClass: "text-amber-300",
    bg: "bg-amber-500/10",
    border: "border-amber-400/20",
  };
}

function formatScoreRange(min?: number | null, max?: number | null) {
  if (min === null || min === undefined) {
    return "--";
  }
  if (max === null || max === undefined || max === min) {
    return `${min}`;
  }
  return `${min}-${max}`;
}

function formatNationalLineDetail(historicalAdjustment: SearchItem["historical_adjustment"]) {
  if (!historicalAdjustment || historicalAdjustment.national_line_zone_a === null || historicalAdjustment.national_line_zone_a === undefined) {
    return null;
  }
  const parts = [
    historicalAdjustment.national_line_year ? `${historicalAdjustment.national_line_year}` : null,
    historicalAdjustment.national_line_major_category || null,
    `A/B ${historicalAdjustment.national_line_zone_a}/${historicalAdjustment.national_line_zone_b}`,
  ].filter(Boolean);
  return parts.join(" ");
}

function formatHistoricalYears(sampleYears: number[] | null | undefined) {
  if (!sampleYears || sampleYears.length === 0) {
    return "暂无";
  }
  return sampleYears.join(" / ");
}

function formatHistoricalSourceTypes(sourceTypes: string[] | null | undefined) {
  if (!sourceTypes || sourceTypes.length === 0) {
    return "暂无";
  }
  const labels = sourceTypes.map((sourceType) => {
    switch (sourceType) {
      case "adjustment_stats":
        return "调剂统计";
      case "landing":
        return "上岸名单";
      case "future_program":
        return "招生专业";
      case "notice_reference":
        return "公告索引";
      default:
        return sourceType;
    }
  });
  return Array.from(new Set(labels)).join(" / ");
}

function getMentorScopeSignals(source: {
  mentor_radar: SearchItem["mentor_radar"];
  mentor_department_radar?: SearchItem["mentor_radar"];
  mentor_school_radar?: SearchItem["mentor_radar"];
}) {
  return {
    department: source.mentor_department_radar || null,
    school: source.mentor_school_radar || source.mentor_radar || null,
  };
}

function getMentorPresenceLabels(source: {
  mentor_radar: SearchItem["mentor_radar"];
  mentor_department_radar?: SearchItem["mentor_radar"];
  mentor_school_radar?: SearchItem["mentor_radar"];
}) {
  const { department, school } = getMentorScopeSignals(source);
  const labels: string[] = [];
  if ((department?.review_count || 0) > 0) {
    labels.push(`本学院评价 ${department?.review_count}`);
  }
  if ((school?.review_count || 0) > 0) {
    labels.push(`本学校评价 ${school?.review_count}`);
  }
  return labels;
}

function getMentorWarningCount(source: {
  mentor_radar: SearchItem["mentor_radar"];
  mentor_department_radar?: SearchItem["mentor_radar"];
  mentor_school_radar?: SearchItem["mentor_radar"];
}) {
  const { school, department } = getMentorScopeSignals(source);
  return school?.warning_count ?? department?.warning_count ?? 0;
}

function getPrimaryMentorLabel(source: {
  mentor_radar: SearchItem["mentor_radar"];
  mentor_department_radar?: SearchItem["mentor_radar"];
  mentor_school_radar?: SearchItem["mentor_radar"];
}) {
  const warningCount = getMentorWarningCount(source);
  if (warningCount > 0) {
    return `本学校预警 ${warningCount}`;
  }
  const labels = getMentorPresenceLabels(source);
  return labels[0] || null;
}

function formatStudyModeLabel(studyMode: string | null | undefined, structuredModes: string[] = []) {
  if (structuredModes.includes("fulltime") && structuredModes.includes("parttime")) {
    return "全日制 / 非全日制";
  }
  if (structuredModes.includes("fulltime")) {
    return "全日制";
  }
  if (structuredModes.includes("parttime")) {
    return "非全日制";
  }
  if (!studyMode) {
    return "待补充";
  }
  if (/full[-\s]?time|全日制/i.test(studyMode)) {
    return "全日制";
  }
  if (/part[-\s]?time|非全日制/i.test(studyMode)) {
    return "非全日制";
  }
  return studyMode;
}

function formatIntelTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hour = String(date.getHours()).padStart(2, "0");
  const minute = String(date.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day} ${hour}:${minute}`;
}

function resolveAdjustmentQueryIntent(filters: {
  keywords: string;
  schoolName: string;
  majorFilter: string;
}) {
  const keyword = filters.keywords.trim();
  const schoolName = filters.schoolName.trim();
  const major = filters.majorFilter.trim();

  if (!keyword) {
    return {
      keywords: "",
      schoolName,
      major,
    };
  }

  if (schoolName || major) {
    return {
      keywords: keyword,
      schoolName,
      major,
    };
  }

  if (isSchoolLikeQuery(keyword)) {
    return {
      keywords: "",
      schoolName: keyword,
      major: "",
    };
  }

  if (isMajorCodeLikeQuery(keyword)) {
    return {
      keywords: "",
      schoolName: "",
      major: keyword,
    };
  }

  return {
    keywords: keyword,
    schoolName: "",
    major: "",
  };
}

function getAdjustmentIntentMeta(filters: {
  keywords: string;
  schoolName: string;
  majorFilter: string;
}) {
  const keyword = filters.keywords.trim();
  const schoolName = filters.schoolName.trim();
  const major = filters.majorFilter.trim();

  if (schoolName) {
    return {
      label: "精确院校",
      description: "院校名会作为精确筛选，主搜索框继续做补充匹配。",
    };
  }
  if (major) {
    return {
      label: "精确专业",
      description: "专业或专业代码会优先收窄结果，主搜索框保留宽匹配。",
    };
  }
  if (!keyword) {
    return {
      label: "宽匹配待输入",
      description: "直接输入学校名、专业名、专业代码或关键词即可开始检索。",
    };
  }
  if (isSchoolLikeQuery(keyword)) {
    return {
      label: "院校名",
      description: "已按学校名理解，同时会补充宽匹配学校名、标题和正文。",
    };
  }
  if (isMajorCodeLikeQuery(keyword)) {
    return {
      label: "专业代码",
      description: "已按专业代码理解，同时会兼容相关专业名和标题内容。",
    };
  }
  return {
    label: "宽匹配",
    description: "会同时匹配学校名、专业名、标题和正文；需要更准就展开高级条件。",
  };
}

function buildEmptyResultMessage(
  queryType: "announcements" | "adjustments",
  filters: {
    keywords: string;
    schoolName: string;
    majorFilter: string;
    regionFilter: string;
    cityFilter: string;
    schoolTierFilter: string;
    yearFilter: string;
    candidateScoreFilter: string;
  },
) {
  const keyword = filters.keywords.trim();
  const schoolName = filters.schoolName.trim();
  const majorFilter = filters.majorFilter.trim();
  const regionFilter = filters.regionFilter.trim();
  const cityFilter = filters.cityFilter.trim();
  const schoolTierFilter = filters.schoolTierFilter.trim();
  const yearFilter = filters.yearFilter.trim();
  const schoolLikeKeyword = isSchoolLikeQuery(keyword);
  if (queryType === "adjustments") {
    if (schoolName && majorFilter) {
      return "当前学校和专业组合下没有查到调剂结果，先去掉其中一个条件再试。";
    }
    if (regionFilter && majorFilter) {
      return "当前地区和专业条件过窄，没有命中调剂结果，建议先放宽地区或专业。";
    }
    if (cityFilter && schoolTierFilter) {
      return "当前城市和院校类别组合过窄，建议先去掉其中一个条件再试。";
    }
    if (yearFilter && schoolName) {
      return "当前年份和院校组合下没有命中调剂结果，建议切换年份，或先去掉年份看看该校其他年份机会。";
    }
    if (yearFilter && majorFilter) {
      return "当前年份和专业组合下没有命中调剂结果，建议切换年份，或先去掉专业看该年份整体机会。";
    }
    if (yearFilter) {
      return "当前年份下没有命中调剂结果，建议切换年份，或再补一个学校、专业或地区条件。";
    }
    if (schoolName) {
      return "当前精确院校条件没有命中调剂结果。先试学校简称，或清空院校名只保留主搜索词再试。";
    }
    if (schoolLikeKeyword) {
      return "当前学校名没有命中调剂结果。可以试学校简称、补一个专业条件，或改成地区范围先看机会。";
    }
    if (isMajorCodeLikeQuery(keyword)) {
      return "当前专业代码没有命中调剂结果。可以试四位代码、专业名称，或补一个学校/地区条件。";
    }
    if (keyword) {
      return "当前主搜索词没有命中调剂结果。系统已经按学校名、专业名、标题和正文做了宽匹配，建议换更短的词，或补一个学校/地区条件。";
    }
    return "暂时没有命中调剂结果，建议先输入学校、专业或地区，再逐步收窄条件。";
  }
  if (schoolLikeKeyword) {
    return "当前院校名没有命中公告，建议把学校名填到“院校名”里，或再补一个学院/招生关键词重试。";
  }
  if (schoolName && keyword) {
    return "当前学校和关键词组合没有命中公告，建议先保留学校名或只搜核心词。";
  }
  if (schoolName) {
    return "当前院校名没有命中公告，建议补一个学院或招生关键词，或先只搜更短的学校简称。";
  }
  if (keyword) {
    return "当前关键词没有命中公告，建议改成学校简称、学院名或更短的核心词。";
  }
  return "暂时没有命中公告结果，建议先输入学校名、学院名或招生关键词。";
}

function handleSearchInputKeyDown(
  event: React.KeyboardEvent<HTMLInputElement>,
  onSearch: () => void,
) {
  if (event.key === "Enter") {
    event.preventDefault();
    onSearch();
  }
}

function buildEmptyStateTitle(queryType: "announcements" | "adjustments", hasFilters: boolean) {
  if (queryType === "adjustments") {
    return hasFilters ? "当前筛选条件下没有调剂结果" : "还没有开始拉取调剂结果";
  }
  return hasFilters ? "当前筛选条件下没有公告结果" : "还没有开始拉取公告结果";
}

function buildEmptyStateDetail(
  queryType: "announcements" | "adjustments",
  hasFilters: boolean,
  hasLocalFilters: boolean,
) {
  if (queryType === "adjustments") {
    if (!hasFilters) {
      return "输入学校、专业、地区或分数后开始检索。调剂页现在会把历史分数、导师评价和发布时间规律一起带出来。";
    }
    return hasLocalFilters
      ? "后端结果已经返回，但被前端情报筛选或学校层次筛选拦掉了。先取消一部分筛选再看。"
      : "后端没有返回符合条件的调剂结果。建议先去掉学校、地区、专业中的一个条件，再重试。";
  }
  if (!hasFilters) {
    return "先输入学校名、学院名或关键词，再开始检索公告。";
  }
  return hasLocalFilters
    ? "后端结果已经返回，但被前端高级筛选拦掉了。先放宽学校层次或学习方式。"
    : "后端没有返回符合条件的公告结果。建议缩短关键词，或只保留学校名再试。";
}

function isSchoolLikeQuery(value: string) {
  if (!value) return false;
  return /(大学|学院|研究院|研究所|师范|医科|理工|科技大学|工业大学|农业大学|中医药大学)$/.test(value);
}

function isMajorCodeLikeQuery(value: string) {
  const compact = value.replace(/\s+/g, "");
  return /^\d{4,6}$/.test(compact);
}

function matchesSchoolTier(tier: SchoolTier, schoolTier: string | null, text: string) {
  const ruleMap: Record<SchoolTier, RegExp> = {
    "985/211": /(985|211)/i,
    双一流: /(双一流|一流大学|一流学科)/i,
    科研院所: /(研究所|科学院|研究院|科研院所)/i,
    普通本科: /(学院|大学)/i,
  };
  return ruleMap[tier].test([schoolTier || "", text].join(" "));
}

function matchesStudyMode(mode: StudyMode, text: string, structuredModes: string[] = []) {
  if (mode === "all") return true;
  if (mode === "fulltime") {
    return structuredModes.includes("fulltime") || /(全日制|full-time|fulltime)/i.test(text);
  }
  return structuredModes.includes("parttime") || /(非全日制|兼职|part-time|parttime)/i.test(text);
}

function isAdjustmentUrgent(item: SearchItem) {
  return /紧急|截止|补录|缺额/i.test(`${item.title} ${item.summary || ""} ${item.major || ""}`);
}

function adjustmentOutlookRank(outlook: "high" | "reach" | "cautious" | null | undefined) {
  if (outlook === "high") return 3;
  if (outlook === "reach") return 2;
  if (outlook === "cautious") return 1;
  return 0;
}

function schoolConfidenceRank(label: string | null | undefined) {
  if (label === "连续活跃") return 3;
  if (label === "持续关注") return 2;
  if (label === "样本有限") return 1;
  return 0;
}
