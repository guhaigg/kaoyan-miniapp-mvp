"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Activity, ArrowUpRight, ChevronRight, LockKeyhole, Radar, ShieldCheck, Sparkles } from "lucide-react";
import { fetchAdjustmentResults } from "@/api/search";
import { buildAdjustmentDetailHref } from "@/components/layout/site-navigation";
import { useSubscriptionsQuery } from "@/hooks/useSubscriptions";
import { useAppStore } from "@/lib/store";
import {
  buildAdjustmentPageSummary,
  buildAdjustmentSearchPayload,
  parseAdjustmentPageState,
  requiresAdjustmentLogin,
  type AdjustmentPageState,
} from "./adjustment-page-data";

const tierOptions = ["", "985", "211", "985/211", "双一流", "普通本科"];

export default function AdjustmentHubPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const portalAuth = useAppStore((state) => state.portalAuth);
  const setAuthOpen = useAppStore((state) => state.setAuthOpen);
  const showToast = useAppStore((state) => state.showToast);
  const pageState = useMemo(
    () => parseAdjustmentPageState(new URLSearchParams(searchParams.toString())),
    [searchParams],
  );
  const [draft, setDraft] = useState<AdjustmentPageState>(pageState);
  const subscriptionsQuery = useSubscriptionsQuery(Boolean(portalAuth));

  useEffect(() => {
    setDraft(pageState);
  }, [pageState]);

  const payload = useMemo(() => buildAdjustmentSearchPayload(pageState), [pageState]);
  const adjustmentQuery = useQuery({
    queryKey: ["adjustments", payload, portalAuth?.userId || "anonymous"],
    queryFn: () => fetchAdjustmentResults(payload),
    retry: false,
  });

  const summary = useMemo(
    () => buildAdjustmentPageSummary(adjustmentQuery.data?.items || [], subscriptionsQuery.data?.items.length || 0),
    [adjustmentQuery.data?.items, subscriptionsQuery.data?.items.length],
  );
  const anonymousPreview = requiresAdjustmentLogin(Boolean(adjustmentQuery.data?.access_limited), !portalAuth);

  function pushState(next: AdjustmentPageState) {
    const params = new URLSearchParams();
    if (next.keywords.trim()) params.set("keywords", next.keywords.trim());
    if (next.schoolName.trim()) params.set("school_name", next.schoolName.trim());
    if (next.major.trim()) params.set("major", next.major.trim());
    if (next.schoolTier.trim()) params.set("school_tier", next.schoolTier.trim());
    if (next.candidateScore.trim()) params.set("candidate_score", next.candidateScore.trim());
    if (next.historyBackedOnly) params.set("history_backed_only", "1");
    if (next.page > 1) params.set("page", String(next.page));
    const query = params.toString();
    router.push(query ? `/adjustments?${query}` : "/adjustments");
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    pushState({ ...draft, page: 1 });
  }

  function promptLogin() {
    setAuthOpen(true, "login");
    showToast("请先登录", "登录后查看完整缺额、详情与收藏动作。", "info");
  }

  return (
    <div className="mx-auto w-full max-w-[1680px] px-6 pb-16 pt-8">
      <section className="rounded-[2rem] border border-slate-200/70 bg-white/90 p-6 shadow-[0_24px_80px_rgba(15,23,42,0.08)] backdrop-blur-xl">
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.55fr)_360px]">
          <div className="space-y-6">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
              <div>
                <div className="text-[11px] font-bold uppercase tracking-[0.22em] text-orange-500">Adjustment Flow</div>
                <h1 className="mt-2 text-3xl font-black tracking-tight text-slate-900">调剂汇总</h1>
                <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-500">
                  这里负责真实调剂机会流。游客可看预览，登录后解锁完整缺额、详情与收藏动作；深度诊断统一进入雷达测算页。
                </p>
              </div>
              <LinkToRadar />
            </div>

            <form onSubmit={handleSubmit} className="rounded-[1.6rem] border border-slate-200 bg-slate-50/70 p-4">
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
                <input
                  value={draft.keywords}
                  onChange={(event) => setDraft((current) => ({ ...current, keywords: event.target.value }))}
                  placeholder="关键词"
                  className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800 outline-none placeholder:text-slate-400"
                />
                <input
                  value={draft.schoolName}
                  onChange={(event) => setDraft((current) => ({ ...current, schoolName: event.target.value }))}
                  placeholder="院校"
                  className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800 outline-none placeholder:text-slate-400"
                />
                <input
                  value={draft.major}
                  onChange={(event) => setDraft((current) => ({ ...current, major: event.target.value }))}
                  placeholder="专业"
                  className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800 outline-none placeholder:text-slate-400"
                />
                <select
                  value={draft.schoolTier}
                  onChange={(event) => setDraft((current) => ({ ...current, schoolTier: event.target.value }))}
                  className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800 outline-none"
                >
                  {tierOptions.map((item) => (
                    <option key={item || "all"} value={item}>
                      {item || "院校层次"}
                    </option>
                  ))}
                </select>
                <input
                  value={draft.candidateScore}
                  onChange={(event) => setDraft((current) => ({ ...current, candidateScore: event.target.value }))}
                  placeholder="分数"
                  className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800 outline-none placeholder:text-slate-400"
                />
              </div>

              <div className="mt-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <label className="inline-flex items-center gap-2 text-sm text-slate-600">
                  <input
                    type="checkbox"
                    checked={draft.historyBackedOnly}
                    onChange={(event) => setDraft((current) => ({ ...current, historyBackedOnly: event.target.checked }))}
                    className="h-4 w-4 rounded border-slate-300"
                  />
                  只看历史样本充分的机会
                </label>
                <button
                  type="submit"
                  className="inline-flex items-center justify-center gap-2 rounded-2xl bg-slate-900 px-5 py-3 text-sm font-bold text-white transition-colors hover:bg-slate-800"
                >
                  执行检索
                  <ChevronRight size={15} />
                </button>
              </div>
            </form>

            {anonymousPreview ? (
              <div className="rounded-[1.4rem] border border-amber-200 bg-amber-50/80 px-4 py-3 text-sm text-amber-800">
                当前是游客预览模式。登录后可查看完整缺额、独立详情与收藏动作。
              </div>
            ) : null}

            <div className="space-y-4">
              {adjustmentQuery.isLoading ? (
                Array.from({ length: 6 }, (_, index) => (
                  <div key={index} className="h-[168px] animate-pulse rounded-[1.5rem] border border-slate-100 bg-slate-50/70" />
                ))
              ) : adjustmentQuery.data?.items.length ? (
                adjustmentQuery.data.items.map((item) => (
                  <button
                    key={`${item.item_kind}:${item.id}`}
                    type="button"
                    onClick={() =>
                      anonymousPreview ? promptLogin() : router.push(buildAdjustmentDetailHref(item.id, item.item_kind))
                    }
                    className="group block w-full rounded-[1.6rem] border border-slate-200/80 bg-white p-5 text-left transition-all hover:border-cyan-300 hover:shadow-[0_14px_40px_rgba(6,182,212,0.08)]"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <div className="mb-2 flex flex-wrap items-center gap-2 text-[11px] text-slate-400">
                          <span className="inline-flex items-center gap-1 rounded-full bg-orange-50 px-2.5 py-1 font-semibold text-orange-600">
                            <Activity size={12} />
                            {item.notice_kind || "调剂机会"}
                          </span>
                          <span>{item.school_name || "目标院校"}</span>
                          {item.major ? <span>· {item.major}</span> : null}
                        </div>
                        <h2 className="text-lg font-black text-slate-900 transition-colors group-hover:text-cyan-700">{item.title}</h2>
                        <p className="mt-3 line-clamp-3 text-sm leading-7 text-slate-500">
                          {item.summary || item.school_intelligence?.signal_detail || item.release_timing?.signal_detail || "点击查看该机会的完整说明与研判。"}
                        </p>
                        <div className="mt-4 flex flex-wrap gap-2">
                          {[...(item.tags || []), ...(item.system_tags || [])].slice(0, 4).map((tag) => (
                            <span key={`${item.id}-${tag}`} className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] text-slate-500">
                              {tag}
                            </span>
                          ))}
                        </div>
                      </div>

                      <div className="shrink-0 text-right">
                        <div className="text-[11px] font-semibold text-slate-400">
                          {item.published_at ? new Date(item.published_at).toLocaleDateString("zh-CN") : "未知时间"}
                        </div>
                        <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                          <div className="text-[10px] uppercase tracking-[0.18em] text-slate-400">缺额</div>
                          <div className="mt-1 text-right text-2xl font-black text-slate-900">
                            {anonymousPreview ? "登录可见" : item.adjustment_vacancy_count ?? "—"}
                          </div>
                        </div>
                        <div className="mt-3 inline-flex h-10 w-10 items-center justify-center rounded-full border border-slate-200 bg-slate-50 text-slate-500 transition-colors group-hover:border-cyan-200 group-hover:text-cyan-700">
                          {anonymousPreview ? <LockKeyhole size={16} /> : <ArrowUpRight size={16} />}
                        </div>
                      </div>
                    </div>
                  </button>
                ))
              ) : (
                <div className="rounded-[1.6rem] border border-dashed border-slate-200 bg-slate-50/60 px-6 py-12 text-center">
                  <div className="text-base font-bold text-slate-700">当前筛选没有命中调剂机会</div>
                  <p className="mt-3 text-sm leading-7 text-slate-500">可以放宽院校层次、专业或分数条件，或者先去雷达测算页拿一版策略建议。</p>
                </div>
              )}
            </div>
          </div>

          <aside className="space-y-4 rounded-[1.5rem] border border-slate-200 bg-slate-50/80 p-4">
            <SummaryCard label="实时机会" value={String(summary.total)} icon={Sparkles} />
            <SummaryCard label="紧急机会" value={String(summary.urgentCount)} icon={ShieldCheck} accent="orange" />
            <SummaryCard label="关注命中" value={String(summary.watchMatchCount)} icon={Radar} />
            <div className="rounded-[1.4rem] border border-slate-200 bg-white p-4">
              <div className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Latest Signal</div>
              <div className="mt-3 text-sm font-semibold text-slate-700">
                {summary.latestPublishedLabel ? new Date(summary.latestPublishedLabel).toLocaleString("zh-CN") : "当前暂无最近时间戳"}
              </div>
              <p className="mt-3 text-sm leading-7 text-slate-500">
                调剂页负责机会流与轻量摘要。需要分数策略和历史线差分析时，再进入雷达测算页做深度推演。
              </p>
            </div>
          </aside>
        </div>
      </section>
    </div>
  );
}

function LinkToRadar() {
  return (
    <button
      type="button"
      onClick={() => {
        window.location.href = "/radar";
      }}
      className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-4 py-2 text-sm font-semibold text-slate-700 transition-colors hover:border-cyan-200 hover:text-cyan-700"
    >
      进入雷达测算
      <ChevronRight size={15} />
    </button>
  );
}

function SummaryCard({
  label,
  value,
  icon: Icon,
  accent = "cyan",
}: {
  label: string;
  value: string;
  icon: typeof Sparkles;
  accent?: "cyan" | "orange";
}) {
  return (
    <div className="rounded-[1.4rem] border border-slate-200 bg-white p-4">
      <div className="flex items-center gap-3">
        <div className={`inline-flex h-10 w-10 items-center justify-center rounded-2xl ${accent === "orange" ? "bg-orange-50 text-orange-600" : "bg-cyan-50 text-cyan-600"}`}>
          <Icon size={18} />
        </div>
        <div>
          <div className="text-[11px] uppercase tracking-[0.2em] text-slate-400">{label}</div>
          <div className="mt-1 text-2xl font-black text-slate-900">{value}</div>
        </div>
      </div>
    </div>
  );
}
