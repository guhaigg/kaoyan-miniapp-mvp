"use client";

import Link from "next/link";
import { ArrowRight, BellDot, Compass, Sparkles } from "lucide-react";
import { motion } from "framer-motion";
import type { SearchItem } from "@/lib/api";

type BiliHeroBannerProps = {
  indexedCount: number;
  featuredItem: SearchItem | null;
  lastUpdatedAt: string | null;
};

function formatRelativeTime(input: string | null) {
  if (!input) return "持续监测中";
  const date = new Date(input);
  if (Number.isNaN(date.getTime())) return "持续监测中";
  const diffMs = Date.now() - date.getTime();
  if (diffMs < 60 * 1000) return "刚刚更新";
  if (diffMs < 60 * 60 * 1000) return `${Math.floor(diffMs / (60 * 1000))} 分钟前`;
  if (diffMs < 24 * 60 * 60 * 1000) return `${Math.floor(diffMs / (60 * 60 * 1000))} 小时前`;
  return `${Math.floor(diffMs / (24 * 60 * 60 * 1000))} 天前`;
}

function pickHighlightLabels(featuredItem: SearchItem | null) {
  const labels = featuredItem?.system_tags?.length
    ? featuredItem.system_tags
    : featuredItem?.tags?.length
      ? featuredItem.tags
      : featuredItem?.channel_label
        ? [featuredItem.channel_label]
        : [];
  return labels.slice(0, 3);
}

export default function BiliHeroBanner({
  indexedCount,
  featuredItem,
  lastUpdatedAt,
}: BiliHeroBannerProps) {
  const highlightLabels = pickHighlightLabels(featuredItem);

  return (
    <section className="relative mx-auto max-w-[1440px] px-4 pb-6 pt-6 md:px-6 lg:pt-8">
      <div className="relative overflow-hidden rounded-[40px] border border-white/80 bg-[linear-gradient(135deg,#fefefe_0%,#fff8fb_28%,#eef6ff_64%,#f8fbff_100%)] px-6 py-8 shadow-[0_36px_120px_rgba(71,85,105,0.16)] md:px-8 lg:px-10 lg:py-10">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(251,113,133,0.2),transparent_28%),radial-gradient(circle_at_top_right,rgba(96,165,250,0.18),transparent_30%),radial-gradient(circle_at_bottom_left,rgba(14,165,233,0.15),transparent_26%)]" />
        <div className="pointer-events-none absolute -left-12 top-8 h-52 w-52 rounded-full bg-rose-200/50 blur-3xl" />
        <div className="pointer-events-none absolute -right-10 bottom-0 h-60 w-60 rounded-full bg-sky-200/40 blur-3xl" />

        <div className="relative grid gap-8 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
          <motion.div
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45, ease: "easeOut" }}
            className="max-w-2xl"
          >
            <div className="inline-flex items-center gap-2 rounded-full border border-rose-100 bg-white/90 px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-600 shadow-[0_14px_30px_rgba(148,163,184,0.14)]">
              <span className="inline-flex h-2.5 w-2.5 rounded-full bg-[linear-gradient(135deg,#fb7185,#60a5fa)]" />
              Public Feed Shell
            </div>
            <h1 className="mt-5 max-w-3xl text-4xl font-black leading-[1.05] tracking-tight text-slate-950 md:text-5xl lg:text-6xl">
              把站内情报排成
              <br />
              像首页推荐流一样顺手。
            </h1>
            <p className="mt-5 max-w-xl text-sm leading-7 text-slate-600 md:text-base">
              首页不再是冷冰冰的时间线。现在会把最新公告、调剂情报和关注动静排成更像内容站首页的公共壳，
              让用户一进来就知道先看什么。
            </p>

            <div className="mt-6 flex flex-wrap gap-3">
              <Link
                href="/search?tab=announcements"
                className="inline-flex items-center gap-2 rounded-full bg-[linear-gradient(90deg,#fb7185,#f472b6)] px-5 py-3 text-sm font-semibold text-white shadow-[0_20px_34px_rgba(251,113,133,0.28)] transition-transform hover:scale-[1.02]"
              >
                <ArrowRight size={16} />
                直接进入公告流
              </Link>
              <Link
                href="/query"
                className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white/90 px-5 py-3 text-sm font-semibold text-slate-700 shadow-[0_14px_28px_rgba(148,163,184,0.14)] transition-colors hover:border-sky-200 hover:bg-sky-50"
              >
                <Compass size={16} />
                浏览站内入口
              </Link>
            </div>

            <div className="mt-8 grid gap-3 sm:grid-cols-3">
              <HeroMetric
                label="追踪条目"
                value={indexedCount > 0 ? indexedCount.toLocaleString("zh-CN") : "--"}
                detail="首页直接展示真实公告结果"
              />
              <HeroMetric label="最近更新" value={formatRelativeTime(lastUpdatedAt)} detail="共享搜索索引同一份数据" />
              <HeroMetric
                label="当前焦点"
                value={featuredItem?.school_name || "站内总览"}
                detail="优先露出最近值得先看的学校"
              />
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, x: 24 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.45, ease: "easeOut", delay: 0.08 }}
            className="relative"
          >
            <div className="relative overflow-hidden rounded-[32px] border border-white/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(247,250,255,0.96))] p-5 shadow-[0_28px_70px_rgba(96,165,250,0.16)]">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">
                    Featured Pulse
                  </div>
                  <div className="mt-2 text-xl font-black text-slate-900">
                    {featuredItem?.title || "今天的推荐情报正在汇总"}
                  </div>
                </div>
                <div className="rounded-full bg-[linear-gradient(135deg,#fde68a,#fb7185)] px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-white">
                  最新
                </div>
              </div>

              <div className="mt-5 rounded-[26px] bg-[linear-gradient(135deg,#0f172a_0%,#1e293b_38%,#1d4ed8_100%)] p-5 text-white shadow-[0_26px_60px_rgba(30,41,59,0.28)]">
                <div className="flex items-center justify-between gap-3 text-[11px] uppercase tracking-[0.18em] text-white/70">
                  <span>{featuredItem?.school_name || "推荐学校"}</span>
                  <span>{formatRelativeTime(featuredItem?.published_at || featuredItem?.updated_at || null)}</span>
                </div>
                <div className="mt-4 max-w-sm text-2xl font-black leading-tight">
                  {featuredItem?.summary || "把最值得先看的公告顶到首页第一屏。"}
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  {highlightLabels.length > 0 ? (
                    highlightLabels.map((label) => (
                      <span
                        key={label}
                        className="rounded-full border border-white/15 bg-white/10 px-3 py-1 text-xs font-medium text-white/90"
                      >
                        {label}
                      </span>
                    ))
                  ) : (
                    <span className="rounded-full border border-white/15 bg-white/10 px-3 py-1 text-xs font-medium text-white/90">
                      公告优先级重排中
                    </span>
                  )}
                </div>
              </div>

              <div className="mt-5 grid gap-3 sm:grid-cols-2">
                <MiniSignalCard
                  icon={<BellDot size={16} />}
                  label="实时感知"
                  value={featuredItem?.channel_label || "公告流更新"}
                  tone="rose"
                />
                <MiniSignalCard
                  icon={<Sparkles size={16} />}
                  label="推荐节奏"
                  value={featuredItem?.source_type || "共享索引"}
                  tone="sky"
                />
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}

function HeroMetric({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="rounded-[26px] border border-white/80 bg-white/85 p-4 shadow-[0_16px_36px_rgba(148,163,184,0.14)]">
      <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-400">{label}</div>
      <div className="mt-2 text-xl font-black text-slate-900">{value}</div>
      <div className="mt-2 text-xs leading-6 text-slate-500">{detail}</div>
    </div>
  );
}

function MiniSignalCard({
  icon,
  label,
  value,
  tone,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  tone: "rose" | "sky";
}) {
  const toneClass =
    tone === "rose"
      ? "bg-[linear-gradient(135deg,rgba(255,241,242,0.98),rgba(255,255,255,0.92))] text-rose-500"
      : "bg-[linear-gradient(135deg,rgba(239,246,255,0.98),rgba(255,255,255,0.92))] text-sky-500";

  return (
    <div className={`rounded-[22px] border border-white/80 p-4 shadow-[0_14px_30px_rgba(148,163,184,0.12)] ${toneClass}`}>
      <div className="flex items-center gap-2 text-sm font-semibold">
        {icon}
        {label}
      </div>
      <div className="mt-3 text-sm font-medium text-slate-700">{value}</div>
    </div>
  );
}
