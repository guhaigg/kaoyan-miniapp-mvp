"use client";

import { useMemo } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, ChevronLeft, LockKeyhole, Radar, Sparkles } from "lucide-react";
import { fetchAdjustmentDetail } from "@/api/search";
import { ApiError } from "@/lib/api";

export default function AdjustmentDetailPage() {
  const searchParams = useSearchParams();
  const itemId = searchParams.get("id") || "";
  const itemKind = (searchParams.get("kind") as "content" | "opportunity") || "content";
  const detailQuery = useQuery({
    queryKey: ["adjustment-detail", itemId, itemKind],
    queryFn: () => fetchAdjustmentDetail(itemId, itemKind),
    enabled: Boolean(itemId),
    retry: false,
  });

  const accessDenied =
    detailQuery.error instanceof ApiError &&
    detailQuery.error.status === 401;

  const publishedLabel = useMemo(() => {
    if (!detailQuery.data?.published_at) {
      return detailQuery.data?.updated_at ? new Date(detailQuery.data.updated_at).toLocaleString("zh-CN") : "未知时间";
    }
    return new Date(detailQuery.data.published_at).toLocaleString("zh-CN");
  }, [detailQuery.data?.published_at, detailQuery.data?.updated_at]);

  return (
    <div className="mx-auto w-full max-w-[1360px] px-6 pb-16 pt-8">
      <div className="rounded-[2rem] border border-slate-200/70 bg-white/92 p-6 shadow-[0_24px_80px_rgba(15,23,42,0.08)] backdrop-blur-xl md:p-8">
        <Link href="/adjustments" className="inline-flex items-center gap-2 text-sm font-semibold text-slate-500 transition-colors hover:text-slate-900">
          <ChevronLeft size={16} />
          返回调剂汇总
        </Link>

        {!itemId ? (
          <div className="py-16 text-center text-slate-500">缺少调剂 ID。</div>
        ) : detailQuery.isLoading ? (
          <div className="mt-8 space-y-4">
            <div className="h-10 w-3/5 animate-pulse rounded-xl bg-slate-100" />
            <div className="h-6 w-1/3 animate-pulse rounded-xl bg-slate-100" />
            <div className="h-60 animate-pulse rounded-[1.5rem] bg-slate-50" />
          </div>
        ) : accessDenied ? (
          <div className="mt-10 rounded-[1.6rem] border border-amber-200 bg-amber-50 px-6 py-12 text-center">
            <div className="inline-flex h-14 w-14 items-center justify-center rounded-full bg-amber-100 text-amber-700">
              <LockKeyhole size={24} />
            </div>
            <h2 className="mt-4 text-2xl font-black text-slate-900">登录后查看完整调剂详情</h2>
            <p className="mt-3 text-sm leading-7 text-slate-600">游客可以浏览调剂汇总预览，完整详情、缺额与收藏动作需要登录后解锁。</p>
            <Link href="/login" className="mt-6 inline-flex items-center gap-2 rounded-full bg-slate-900 px-5 py-3 text-sm font-bold text-white transition-colors hover:bg-slate-800">
              进入登录
              <ArrowUpRight size={15} />
            </Link>
          </div>
        ) : detailQuery.data ? (
          <>
            <div className="mt-6 flex flex-wrap items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-slate-400">
              <span className="inline-flex items-center gap-1 rounded-full bg-orange-50 px-3 py-1 font-bold text-orange-600">
                <Sparkles size={12} />
                {detailQuery.data.notice_kind || "调剂详情"}
              </span>
              <span>{detailQuery.data.school_name || "目标院校"}</span>
              {detailQuery.data.major ? <span>· {detailQuery.data.major}</span> : null}
              <span>· {publishedLabel}</span>
            </div>

            <h1 className="mt-4 text-3xl font-black tracking-tight text-slate-900 md:text-4xl">{detailQuery.data.title}</h1>
            {detailQuery.data.summary ? (
              <p className="mt-5 max-w-4xl text-base leading-8 text-slate-600">{detailQuery.data.summary}</p>
            ) : null}

            <div className="mt-6 grid gap-4 md:grid-cols-4">
              <MetricBox label="缺额" value={detailQuery.data.vacancy_count === null ? "—" : String(detailQuery.data.vacancy_count)} />
              <MetricBox label="初试最低" value={detailQuery.data.initial_score_min === null ? "—" : String(detailQuery.data.initial_score_min)} />
              <MetricBox label="历史最低" value={detailQuery.data.min_score === null ? "—" : String(detailQuery.data.min_score)} />
              <MetricBox label="学校层次" value={detailQuery.data.school_tier || "未标注"} />
            </div>

            <article className="prose prose-slate mt-8 max-w-none rounded-[1.5rem] border border-slate-200/80 bg-slate-50/70 p-6 prose-p:leading-8">
              {detailQuery.data.body ? <div className="whitespace-pre-wrap text-sm text-slate-700">{detailQuery.data.body}</div> : <div className="text-sm text-slate-500">暂无正文内容。</div>}
            </article>

            <div className="mt-8 grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
              <div className="rounded-[1.5rem] border border-slate-200 bg-white p-5">
                <div className="text-[11px] uppercase tracking-[0.2em] text-slate-400">辅助判断</div>
                <div className="mt-4 grid gap-4 md:grid-cols-3">
                  <InsightBox label="历史样本" value={String(detailQuery.data.historical_adjustment?.sample_count || 0)} />
                  <InsightBox label="导师评价" value={String(detailQuery.data.mentor_radar?.review_count || 0)} />
                  <InsightBox label="释放时机" value={detailQuery.data.release_timing?.signal_label || "暂无"} />
                </div>
              </div>

              <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50/70 p-5">
                <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.2em] text-slate-400">
                  <Radar size={14} className="text-cyan-600" />
                  深度诊断
                </div>
                <p className="mt-3 text-sm leading-7 text-slate-600">想把当前机会和你的分数、历史线差一起推演，建议继续进入雷达测算页做深度策略判断。</p>
                <Link href="/radar" className="mt-4 inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition-colors hover:border-cyan-200 hover:text-cyan-700">
                  去雷达测算
                  <ArrowUpRight size={15} />
                </Link>
                {detailQuery.data.source_url ? (
                  <a
                    href={detailQuery.data.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-3 inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition-colors hover:border-cyan-200 hover:text-cyan-700"
                  >
                    原始链接
                    <ArrowUpRight size={15} />
                  </a>
                ) : null}
              </div>
            </div>
          </>
        ) : (
          <div className="py-16 text-center text-slate-500">调剂详情不存在。</div>
        )}
      </div>
    </div>
  );
}

function MetricBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[1.3rem] border border-slate-200 bg-slate-50 p-4">
      <div className="text-[11px] uppercase tracking-[0.2em] text-slate-400">{label}</div>
      <div className="mt-2 text-2xl font-black text-slate-900">{value}</div>
    </div>
  );
}

function InsightBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[1.2rem] border border-slate-200 bg-slate-50/80 p-4">
      <div className="text-[11px] uppercase tracking-[0.2em] text-slate-400">{label}</div>
      <div className="mt-2 text-sm font-semibold text-slate-700">{value}</div>
    </div>
  );
}
