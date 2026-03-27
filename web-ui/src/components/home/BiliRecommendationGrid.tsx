"use client";

import { Clock3, FileText } from "lucide-react";
import type { SearchItem } from "@/lib/api";

export default function BiliRecommendationGrid({
  items,
  loading,
}: {
  items: SearchItem[];
  loading: boolean;
}) {
  if (loading) {
    return (
      <section className="mx-auto max-w-[1440px] px-4 py-8 md:px-6">
        <div className="bili-surface p-6 text-sm text-slate-500">正在加载推荐公告...</div>
      </section>
    );
  }

  if (!items.length) {
    return (
      <section className="mx-auto max-w-[1440px] px-4 py-8 md:px-6">
        <div className="bili-surface p-6 text-sm text-slate-500">暂无最新公告，抓取任务正在持续同步。</div>
      </section>
    );
  }

  return (
    <section className="mx-auto grid max-w-[1440px] gap-5 px-4 py-8 md:grid-cols-2 md:px-6 xl:grid-cols-3">
      {items.map((item) => (
        <article key={item.id} className="bili-surface overflow-hidden">
          <div className="relative aspect-[16/10] bg-[linear-gradient(135deg,#dfefff,#ffe2ee)]">
            <div className="absolute left-3 top-3 inline-flex items-center gap-1 rounded-full bg-white/85 px-2.5 py-1 text-xs font-semibold text-slate-600">
              <FileText size={12} />
              {item.source_type || "公告"}
            </div>
          </div>
          <div className="p-4">
            <h3 className="line-clamp-2 text-base font-semibold leading-7 text-[#18191c]">{item.title}</h3>
            <p className="mt-2 line-clamp-2 text-sm text-[#61666d]">{item.summary || "暂无摘要，点击查看原文。"}</p>
            <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
              <span className="truncate pr-2">{item.school_name ?? "院校待补充"}</span>
              <span className="inline-flex items-center gap-1">
                <Clock3 size={12} />
                {formatRelativeTime(item.published_at || item.updated_at)}
              </span>
            </div>
            <a
              href={item.source_url || "#"}
              target={item.source_url ? "_blank" : undefined}
              rel={item.source_url ? "noopener noreferrer" : undefined}
              className="mt-4 inline-flex rounded-full bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white"
            >
              查看详情
            </a>
          </div>
        </article>
      ))}
    </section>
  );
}

function formatRelativeTime(input: string | null): string {
  if (!input) return "时间未知";
  const date = new Date(input);
  if (Number.isNaN(date.getTime())) return "时间未知";
  const diffMs = Date.now() - date.getTime();
  if (diffMs < 60 * 1000) return "刚刚";
  if (diffMs < 60 * 60 * 1000) return `${Math.floor(diffMs / (60 * 1000))} 分钟前`;
  if (diffMs < 24 * 60 * 60 * 1000) return `${Math.floor(diffMs / (60 * 60 * 1000))} 小时前`;
  return `${Math.floor(diffMs / (24 * 60 * 60 * 1000))} 天前`;
}
