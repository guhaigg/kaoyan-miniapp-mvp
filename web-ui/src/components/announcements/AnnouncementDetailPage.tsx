"use client";

import { useMemo } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, ChevronLeft, FileText } from "lucide-react";
import { fetchAnnouncementDetail } from "@/api/search";

export default function AnnouncementDetailPage() {
  const searchParams = useSearchParams();
  const contentId = searchParams.get("id") || "";
  const detailQuery = useQuery({
    queryKey: ["announcement-detail", contentId],
    queryFn: () => fetchAnnouncementDetail(contentId),
    enabled: Boolean(contentId),
  });

  const publishedLabel = useMemo(() => {
    if (!detailQuery.data?.published_at) {
      return detailQuery.data?.updated_at ? new Date(detailQuery.data.updated_at).toLocaleString("zh-CN") : "未知时间";
    }
    return new Date(detailQuery.data.published_at).toLocaleString("zh-CN");
  }, [detailQuery.data?.published_at, detailQuery.data?.updated_at]);

  return (
    <div className="mx-auto w-full max-w-[1320px] px-6 pb-16 pt-8">
      <div className="rounded-[2rem] border border-slate-200/70 bg-white/92 p-6 shadow-[0_24px_80px_rgba(15,23,42,0.08)] backdrop-blur-xl md:p-8">
        <Link href="/announcements" className="inline-flex items-center gap-2 text-sm font-semibold text-slate-500 transition-colors hover:text-slate-900">
          <ChevronLeft size={16} />
          返回公告汇总
        </Link>

        {!contentId ? (
          <div className="py-16 text-center text-slate-500">缺少公告 ID。</div>
        ) : detailQuery.isLoading ? (
          <div className="mt-8 space-y-4">
            <div className="h-10 w-3/5 animate-pulse rounded-xl bg-slate-100" />
            <div className="h-6 w-1/3 animate-pulse rounded-xl bg-slate-100" />
            <div className="h-52 animate-pulse rounded-[1.5rem] bg-slate-50" />
          </div>
        ) : detailQuery.data ? (
          <>
            <div className="mt-6 flex flex-wrap items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-slate-400">
              <span className="inline-flex items-center gap-1 rounded-full bg-cyan-50 px-3 py-1 font-bold text-cyan-700">
                <FileText size={12} />
                {detailQuery.data.notice_kind || detailQuery.data.channel_label || "公告详情"}
              </span>
              <span>{detailQuery.data.school_name || "目标院校"}</span>
              {detailQuery.data.department_name ? <span>· {detailQuery.data.department_name}</span> : null}
              <span>· {publishedLabel}</span>
            </div>

            <h1 className="mt-4 text-3xl font-black tracking-tight text-slate-900 md:text-4xl">{detailQuery.data.title}</h1>
            {detailQuery.data.summary ? (
              <p className="mt-5 max-w-4xl text-base leading-8 text-slate-600">{detailQuery.data.summary}</p>
            ) : null}

            <div className="mt-6 flex flex-wrap gap-2">
              {[...detailQuery.data.tags, ...detailQuery.data.system_tags].slice(0, 8).map((tag) => (
                <span key={tag} className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-500">
                  {tag}
                </span>
              ))}
            </div>

            <article className="prose prose-slate mt-8 max-w-none rounded-[1.5rem] border border-slate-200/80 bg-slate-50/70 p-6 prose-p:leading-8">
              {detailQuery.data.body ? <div className="whitespace-pre-wrap text-sm text-slate-700">{detailQuery.data.body}</div> : <div className="text-sm text-slate-500">暂无正文内容。</div>}
            </article>

            {detailQuery.data.source_url ? (
              <div className="mt-6">
                <a
                  href={detailQuery.data.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition-colors hover:border-cyan-200 hover:text-cyan-700"
                >
                  查看原始链接
                  <ArrowUpRight size={15} />
                </a>
              </div>
            ) : null}
          </>
        ) : (
          <div className="py-16 text-center text-slate-500">公告详情不存在或暂不可见。</div>
        )}
      </div>
    </div>
  );
}
