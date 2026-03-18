"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Search, SlidersHorizontal, Target } from "lucide-react";
import FilterDrawer, { type SchoolTier, type StudyMode } from "@/components/search/FilterDrawer";
import FeedCard, { FeedCardSkeleton } from "@/components/shared/FeedCard";
import { ApiError, SearchResponse } from "@/lib/api";
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
  const [schoolTiers, setSchoolTiers] = useState<SchoolTier[]>([]);
  const [studyMode, setStudyMode] = useState<StudyMode>("all");
  const [message, setMessage] = useState("");
  const [searchResult, setSearchResult] = useState<SearchResponse | null>(null);

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
    return searchResult.items.filter((item) => {
      const text = [item.school_name, item.title, item.summary, item.major].filter(Boolean).join(" ");
      const matchesTier =
        schoolTiers.length === 0 || schoolTiers.some((tier) => matchesSchoolTier(tier, text));
      const matchesMode = matchesStudyMode(studyMode, text, item.adjustment_study_modes);
      return matchesTier && matchesMode;
    });
  }, [schoolTiers, searchResult, studyMode]);

  const currentPage = searchResult?.page || 1;
  const totalPages = searchResult ? Math.max(1, Math.ceil(searchResult.total / searchResult.page_size)) : 1;
  const hasLocalFilters = schoolTiers.length > 0 || studyMode !== "all";
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

  async function triggerSearch(page = 1) {
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
              school_name: schoolName.trim() || undefined,
              page,
              page_size: 12,
            })
          : await adjustmentMutation.mutateAsync({
              keywords: keywords.trim() || undefined,
              school_name: schoolName.trim() || undefined,
              major: majorFilter.trim() || undefined,
              region: regionFilter.trim() || undefined,
              page,
              page_size: 12,
            });
      setSearchResult(payload);
      if (payload.total === 0) {
        setMessage("未匹配到确切坐标，请尝试提取核心关键词。");
      } else {
        setMessage("");
      }
    } catch (error) {
      if (error instanceof ApiError) {
        setMessage(`查询失败：${error.message}`);
      } else {
        setMessage("数据源响应超时，请稍后重连。");
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

  const isSearching = announcementMutation.isPending || adjustmentMutation.isPending;

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
              onClick={() => setQueryType("announcements")}
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
              type="text"
              placeholder="输入院校代码、名称或专业关键字..."
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
          <div className="mt-3 grid gap-2 md:grid-cols-4">
            <input
              value={schoolName}
              onChange={(event) => setSchoolName(event.target.value)}
              placeholder="院校名（可选）"
              className="rounded-xl border border-white/10 bg-black/30 px-4 py-2.5 text-sm text-white outline-none transition-colors focus:border-cyan-400"
            />
            <input
              value={majorFilter}
              onChange={(event) => setMajorFilter(event.target.value)}
              placeholder="专业（调剂模式可选）"
              className="rounded-xl border border-white/10 bg-black/30 px-4 py-2.5 text-sm text-white outline-none transition-colors focus:border-cyan-400"
            />
            <input
              value={regionFilter}
              onChange={(event) => setRegionFilter(event.target.value)}
              placeholder="地区（调剂模式可选）"
              className="rounded-xl border border-white/10 bg-black/30 px-4 py-2.5 text-sm text-white outline-none transition-colors focus:border-cyan-400"
            />
            <button
              type="button"
              onClick={() => {
                setKeywords("");
                setSchoolName("");
                setMajorFilter("");
                setRegionFilter("");
                setSchoolTiers([]);
                setStudyMode("all");
                setSearchResult(null);
                setMessage("");
              }}
              className="rounded-xl border border-white/20 bg-white/5 px-4 py-2.5 text-sm text-slate-200 transition-colors hover:bg-white/10"
            >
              清空筛选
            </button>
          </div>
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
                当前页筛后 <span className="text-cyan-300">{filteredItems.length}</span> 条
              </span>
              <span className="text-slate-500">/</span>
              <span>
                原始返回 <span className="text-white">{searchResult.items.length}</span> 条
              </span>
              <span className="text-slate-500">/</span>
              <span>
                总记录 <span className="text-white">{searchResult.total}</span>
              </span>
              {searchResult.access_limited ? (
                <>
                  <span className="text-slate-500">/</span>
                  <span className="text-amber-300">匿名预览仅展示前 {previewLimit} 条</span>
                </>
              ) : null}
              {hasLocalFilters ? (
                <>
                  <span className="text-slate-500">/</span>
                  <span className="text-cyan-300">前端高级筛选已生效</span>
                </>
              ) : null}
            </div>

            {filteredItems.length > 0 ? (
              <div className="grid gap-6 md:grid-cols-2">
                {filteredItems.map((item) => (
                  <FeedCard
                    key={item.id}
                    item={{
                      id: item.id,
                      type: item.category === "adjustment" ? "adjustment" : "announcement",
                      title: item.title,
                      content: item.summary || "暂无摘要，点击查看源站原文。",
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
            ) : (
              <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-8 text-sm text-slate-300">
                当前筛选条件下暂无匹配记录。你可以放宽院校层次或学习方式，重新聚合本页结果。
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
        ) : null}
      </div>

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

function matchesSchoolTier(tier: SchoolTier, text: string) {
  const ruleMap: Record<SchoolTier, RegExp> = {
    "985/211": /(985|211)/i,
    双一流: /(双一流|一流大学|一流学科)/i,
    科研院所: /(研究所|科学院|研究院|科研院所)/i,
    普通本科: /(学院|大学)/i,
  };
  return ruleMap[tier].test(text);
}

function matchesStudyMode(mode: StudyMode, text: string, structuredModes: string[] = []) {
  if (mode === "all") return true;
  if (mode === "fulltime") {
    return structuredModes.includes("fulltime") || /(全日制|full-time|fulltime)/i.test(text);
  }
  return structuredModes.includes("parttime") || /(非全日制|兼职|part-time|parttime)/i.test(text);
}
