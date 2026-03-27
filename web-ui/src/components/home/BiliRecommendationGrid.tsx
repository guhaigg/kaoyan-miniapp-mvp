"use client";

import Link from "next/link";
import { ArrowUpRight, Clock3, Flame, Sparkles } from "lucide-react";
import { motion } from "framer-motion";
import type { SearchItem } from "@/lib/api";

const accentPresets = [
  {
    panel: "bg-[linear-gradient(135deg,#0f172a_0%,#1d4ed8_60%,#38bdf8_100%)] text-white",
    badge: "bg-white/10 text-white border-white/15",
    glow: "bg-sky-200/40",
  },
  {
    panel: "bg-[linear-gradient(135deg,#4c0519_0%,#be185d_62%,#fb7185_100%)] text-white",
    badge: "bg-white/10 text-white border-white/15",
    glow: "bg-rose-200/40",
  },
  {
    panel: "bg-[linear-gradient(135deg,#172554_0%,#4338ca_58%,#c084fc_100%)] text-white",
    badge: "bg-white/10 text-white border-white/15",
    glow: "bg-indigo-200/40",
  },
  {
    panel: "bg-[linear-gradient(135deg,#422006_0%,#d97706_62%,#facc15_100%)] text-slate-950",
    badge: "bg-slate-950/10 text-slate-900 border-slate-900/15",
    glow: "bg-amber-200/50",
  },
] as const;

type BiliRecommendationGridProps = {
  items: SearchItem[];
  isLoading: boolean;
};

export default function BiliRecommendationGrid({
  items,
  isLoading,
}: BiliRecommendationGridProps) {
  if (isLoading) {
    return (
      <section className="mx-auto max-w-[1440px] px-4 pb-20 md:px-6">
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <div
              key={index}
              className={`rounded-[32px] border border-white/80 bg-white/80 p-4 shadow-[0_16px_40px_rgba(148,163,184,0.14)] ${
                index === 0 ? "xl:col-span-2" : ""
              }`}
            >
              <div className="h-44 animate-pulse rounded-[26px] bg-slate-200/80" />
              <div className="mt-5 h-6 w-3/4 animate-pulse rounded-full bg-slate-200/80" />
              <div className="mt-3 h-4 w-full animate-pulse rounded-full bg-slate-100" />
              <div className="mt-2 h-4 w-2/3 animate-pulse rounded-full bg-slate-100" />
            </div>
          ))}
        </div>
      </section>
    );
  }

  if (items.length === 0) {
    return (
      <section className="mx-auto max-w-[1440px] px-4 pb-20 md:px-6">
        <div className="rounded-[36px] border border-dashed border-slate-200 bg-white/85 px-8 py-12 text-center shadow-[0_16px_40px_rgba(148,163,184,0.1)]">
          <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-400">No Signals</div>
          <div className="mt-3 text-3xl font-black text-slate-900">首页推荐流正在等第一批真实公告。</div>
          <p className="mx-auto mt-4 max-w-2xl text-sm leading-7 text-slate-500">
            当前没有拿到可展示的公告结果。等到下一轮抓取写入后，这里会自动顶出值得先看的学校、院系和频道。
          </p>
          <Link
            href="/search?tab=announcements"
            className="mt-6 inline-flex items-center gap-2 rounded-full bg-[linear-gradient(90deg,#fb7185,#60a5fa)] px-5 py-3 text-sm font-semibold text-white shadow-[0_16px_30px_rgba(96,165,250,0.22)]"
          >
            <Sparkles size={16} />
            去公告检索页
          </Link>
        </div>
      </section>
    );
  }

  return (
    <section className="mx-auto max-w-[1440px] px-4 pb-20 md:px-6">
      <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
        {items.map((item, index) => (
          <RecommendationCard
            key={item.id}
            item={item}
            index={index}
            featured={index === 0}
          />
        ))}
      </div>
    </section>
  );
}

function RecommendationCard({
  item,
  index,
  featured,
}: {
  item: SearchItem;
  index: number;
  featured: boolean;
}) {
  const accent = accentPresets[index % accentPresets.length];
  const linkHref = item.source_url || buildFallbackHref(item);
  const labels = pickLabels(item);

  return (
    <motion.article
      whileHover={{ y: -4 }}
      transition={{ duration: 0.18, ease: "easeOut" }}
      className={`group rounded-[32px] border border-white/80 bg-white/88 p-4 shadow-[0_18px_42px_rgba(148,163,184,0.14)] ${
        featured ? "md:col-span-2 xl:col-span-2" : ""
      }`}
    >
      <a
        href={linkHref}
        target={item.source_url ? "_blank" : undefined}
        rel={item.source_url ? "noopener noreferrer" : undefined}
        className="block"
      >
        <div className={`relative overflow-hidden rounded-[28px] p-5 ${accent.panel}`}>
          <div className={`pointer-events-none absolute -right-10 -top-10 h-36 w-36 rounded-full blur-3xl ${accent.glow}`} />
          <div className="pointer-events-none absolute bottom-0 right-0 text-[92px] font-black uppercase tracking-[-0.06em] text-white/8">
            {buildCardStamp(item)}
          </div>

          <div className="relative flex min-h-[180px] flex-col justify-between gap-6">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <span className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] ${accent.badge}`}>
                  {item.school_name || "站内情报"}
                </span>
                {featured ? (
                  <span className={`inline-flex items-center gap-1 rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] ${accent.badge}`}>
                    <Flame size={12} />
                    推荐置顶
                  </span>
                ) : null}
              </div>
              <div className={`mt-5 max-w-3xl font-black leading-tight ${featured ? "text-3xl" : "text-2xl"}`}>
                {item.title}
              </div>
              <div className="mt-4 max-w-2xl text-sm leading-7 text-current/80">
                {item.summary || "暂无摘要，打开后查看完整正文与原始链接。"}
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              {labels.map((label) => (
                <span
                  key={label}
                  className={`rounded-full border px-3 py-1 text-xs font-medium ${accent.badge}`}
                >
                  {label}
                </span>
              ))}
            </div>
          </div>
        </div>

        <div className="mt-4 flex items-end justify-between gap-4">
          <div className="space-y-2">
            <div className="flex flex-wrap gap-2 text-xs text-slate-500">
              <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 font-medium">
                {item.department_name || item.channel_label || item.source_type}
              </span>
              <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-3 py-1 font-medium">
                <Clock3 size={12} />
                {formatRelativeTime(item.published_at || item.updated_at)}
              </span>
            </div>
            <div className="text-sm font-medium text-slate-600">
              {item.school_name || "站内推荐"} {item.major ? `· ${item.major}` : ""}
            </div>
          </div>
          <span className="inline-flex items-center gap-2 rounded-full bg-slate-950 px-4 py-2 text-sm font-semibold text-white transition-colors group-hover:bg-sky-500">
            立即查看
            <ArrowUpRight size={15} />
          </span>
        </div>
      </a>
    </motion.article>
  );
}

function buildCardStamp(item: SearchItem) {
  const source = item.school_name || item.source_type || "GW";
  return Array.from(source.replace(/\s+/g, ""))
    .slice(0, 3)
    .join("")
    .toUpperCase();
}

function buildFallbackHref(item: SearchItem) {
  const params = new URLSearchParams();
  params.set("tab", "announcements");
  params.set("q", item.school_name || item.title);
  return `/search?${params.toString()}`;
}

function pickLabels(item: SearchItem) {
  const base = item.system_tags.length > 0 ? item.system_tags : item.tags;
  const labels = [...base];
  if (item.channel_tier === "core") {
    labels.unshift("核心频道");
  }
  if (item.notice_kind) {
    labels.unshift(item.notice_kind);
  }
  return labels.filter(Boolean).slice(0, 4);
}

function formatRelativeTime(input: string | null) {
  if (!input) return "刚刚同步";
  const date = new Date(input);
  if (Number.isNaN(date.getTime())) return "刚刚同步";
  const diffMs = Date.now() - date.getTime();
  if (diffMs < 60 * 1000) return "刚刚更新";
  if (diffMs < 60 * 60 * 1000) return `${Math.floor(diffMs / (60 * 1000))} 分钟前`;
  if (diffMs < 24 * 60 * 60 * 1000) return `${Math.floor(diffMs / (60 * 60 * 1000))} 小时前`;
  return `${Math.floor(diffMs / (24 * 60 * 60 * 1000))} 天前`;
}
