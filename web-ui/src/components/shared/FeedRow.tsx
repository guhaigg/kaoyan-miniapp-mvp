"use client";

import { type MouseEvent, useState } from "react";
import { motion } from "framer-motion";
import { AlertCircle, ArrowUpRight, Star } from "lucide-react";
import { type FeedItem, formatDistanceToNowZh } from "@/components/shared/FeedCard";

const rowToneMap = {
  calm: {
    surface: "bg-white/[0.02] hover:bg-white/[0.05] border-white/5 hover:border-cyan-500/30",
    accent: "text-cyan-400",
  },
  urgent: {
    surface: "bg-orange-950/10 hover:bg-orange-950/20 border-orange-500/20 hover:border-orange-500/50",
    accent: "text-orange-400",
  },
};

export default function FeedRow({ item }: { item: FeedItem }) {
  const [bookmarkBusy, setBookmarkBusy] = useState(false);
  const isUrgent = Boolean(item.isUrgent);
  const tone = isUrgent ? rowToneMap.urgent : rowToneMap.calm;
  const timeAgo = formatDistanceToNowZh(item.publishTime);
  const statusLabel = isUrgent ? "紧急缺额" : item.type === "adjustment" ? "常规调剂" : "最新公告";
  const tags = item.tags.slice(0, item.type === "announcement" ? 3 : 2);
  const badges = item.badges || [];

  async function handleBookmark(event: MouseEvent<HTMLButtonElement>) {
    event.preventDefault();
    event.stopPropagation();
    if (!item.bookmark || bookmarkBusy) return;
    setBookmarkBusy(true);
    try {
      await item.bookmark.onToggle();
    } finally {
      setBookmarkBusy(false);
    }
  }

  const rowBody =
    item.type === "announcement" ? (
      <div className={`relative flex flex-col gap-3 rounded-[22px] border px-5 py-4 transition-all duration-200 ${tone.surface}`}>
        <div className="flex items-start gap-4">
          <div className="flex min-w-0 flex-1 gap-4">
            <div className="flex items-start gap-3 md:w-40 md:shrink-0">
              {item.bookmark ? (
                <motion.button
                  type="button"
                  whileTap={{ scale: 0.7 }}
                  disabled={bookmarkBusy}
                  onClick={handleBookmark}
                  title={item.bookmark.label}
                  className={`mt-0.5 rounded-full border border-white/10 bg-white/[0.04] p-2 transition-colors ${
                    item.bookmark.active
                      ? "text-yellow-300 shadow-[0_0_18px_rgba(250,204,21,0.18)]"
                      : "text-slate-400 hover:border-white/20 hover:bg-white/[0.08] hover:text-white"
                  } ${bookmarkBusy ? "cursor-not-allowed opacity-60" : ""}`}
                >
                  <Star size={15} fill={item.bookmark.active ? "currentColor" : "none"} />
                </motion.button>
              ) : null}
              <div className="space-y-1.5">
                <div className={`inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] ${
                  isUrgent
                    ? "border-orange-400/25 bg-orange-500/10 text-orange-200"
                    : "border-cyan-400/20 bg-cyan-500/10 text-cyan-200"
                }`}>
                  <span className={`h-1.5 w-1.5 rounded-full ${isUrgent ? "bg-orange-300" : "bg-cyan-300"}`} />
                  {statusLabel}
                </div>
                <div className="text-[11px] font-medium text-slate-400">{timeAgo}</div>
              </div>
            </div>

            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-start gap-2.5">
                <h3 className="min-w-0 flex-1 text-[17px] font-semibold leading-6 text-white transition-colors group-hover:text-cyan-50">
                  {item.title}
                </h3>
                <div className="hidden flex-wrap gap-2 lg:flex">
                  {tags.map((tag) => (
                    <span
                      key={`${item.id}-${tag}`}
                      className="rounded-full bg-white/[0.10] px-2.5 py-1 text-[11px] font-medium text-slate-200"
                    >
                      {tag}
                    </span>
                  ))}
                  {badges.slice(0, 2).map((badge) => (
                    <span
                      key={`${item.id}-${badge.label}`}
                      className={
                        badge.tone === "amber"
                          ? "rounded-full bg-amber-500/12 px-2.5 py-1 text-[11px] font-medium text-amber-100"
                          : "rounded-full bg-cyan-500/12 px-2.5 py-1 text-[11px] font-medium text-cyan-100"
                      }
                    >
                      {badge.label}
                    </span>
                  ))}
                </div>
              </div>
              <p className="mt-2 line-clamp-2 text-sm leading-6 text-slate-300">
                {item.content}
              </p>
              <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-400">
                {item.subtitle ? <span className="font-medium text-slate-300">{item.subtitle}</span> : null}
                {item.warningLabel ? (
                  <span className="inline-flex items-center gap-1 rounded-full bg-red-500/10 px-2.5 py-1 text-[11px] font-medium text-red-200">
                    <AlertCircle size={12} className="text-red-300" />
                    {item.warningLabel}
                  </span>
                ) : null}
              </div>
              <div className="mt-3 flex flex-wrap gap-2 lg:hidden">
                {tags.map((tag) => (
                  <span
                    key={`${item.id}-${tag}-mobile`}
                    className="rounded-full bg-white/[0.10] px-2.5 py-1 text-[11px] font-medium text-slate-200"
                  >
                    {tag}
                  </span>
                ))}
                {badges.slice(0, 2).map((badge) => (
                  <span
                    key={`${item.id}-${badge.label}-mobile`}
                    className={
                      badge.tone === "amber"
                        ? "rounded-full bg-amber-500/12 px-2.5 py-1 text-[11px] font-medium text-amber-100"
                        : "rounded-full bg-cyan-500/12 px-2.5 py-1 text-[11px] font-medium text-cyan-100"
                    }
                  >
                    {badge.label}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <div className="hidden shrink-0 md:flex md:items-center">
            <div className="flex h-11 w-11 items-center justify-center rounded-full border border-white/10 bg-white/[0.04] text-slate-300 transition-all duration-200 group-hover:translate-x-1 group-hover:border-cyan-400/30 group-hover:bg-cyan-500/10 group-hover:text-cyan-100">
              <ArrowUpRight size={17} />
            </div>
          </div>
        </div>
      </div>
    ) : (
      <div className={`relative flex flex-col gap-4 rounded-xl border px-5 py-3.5 transition-colors md:flex-row md:items-center ${tone.surface}`}>
        <div className="flex items-center gap-3 md:w-32 md:shrink-0">
          {item.bookmark ? (
            <motion.button
              type="button"
              whileTap={{ scale: 0.7 }}
              disabled={bookmarkBusy}
              onClick={handleBookmark}
              title={item.bookmark.label}
              className={`rounded p-1 transition-colors ${
                item.bookmark.active
                  ? "text-yellow-400"
                  : "text-slate-500 hover:text-slate-200"
              } ${bookmarkBusy ? "cursor-not-allowed opacity-60" : ""}`}
            >
              <Star size={16} fill={item.bookmark.active ? "currentColor" : "none"} />
            </motion.button>
          ) : (
            <div className="h-6 w-6" />
          )}
          <div className="flex flex-col">
            <span className={`text-[10px] font-bold ${tone.accent}`}>{statusLabel}</span>
            <span className="text-[10px] font-mono text-slate-400">{timeAgo}</span>
          </div>
        </div>

        <div className="min-w-0 flex-1">
          <div className="mb-0.5 flex items-center gap-2">
            <h3 className="truncate text-base font-bold text-white transition-colors group-hover:text-cyan-50">
              {item.title}
            </h3>
            <div className="hidden shrink-0 md:flex md:gap-1.5">
              {tags.map((tag) => (
                <span
                  key={`${item.id}-${tag}`}
                  className="rounded-full bg-white/[0.10] px-2 py-0.5 text-[10px] font-medium text-slate-200"
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>
          <p className="truncate text-xs text-slate-300">
            {item.subtitle || item.content}
          </p>
        </div>

        <div className="flex items-center gap-6 md:ml-auto md:shrink-0">
          <div className="flex flex-col items-start md:items-end">
            <span className="text-[10px] text-slate-400">
              {item.metricLabel || "摘要"}
            </span>
            <div className="flex items-baseline gap-1.5">
              <span className="text-sm font-bold font-mono text-white">
                {item.metricPrimary || "—"}
              </span>
              {item.metricSecondary ? (
                <span className="text-xs font-mono text-slate-400">/ {item.metricSecondary}</span>
              ) : null}
            </div>
          </div>

          {item.warningLabel ? (
            <div className="hidden items-center gap-1.5 rounded-md border border-red-500/20 bg-red-500/10 px-2 py-1 md:flex">
              <AlertCircle size={12} className="text-red-400" />
              <span className="text-[10px] text-red-400">{item.warningLabel}</span>
            </div>
          ) : null}

          <div className="hidden items-center gap-1 text-[11px] text-slate-400 md:flex">
            查看
            <ArrowUpRight size={13} />
          </div>
        </div>
      </div>
    );

  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.2 }}
      className="group"
    >
      {item.href ? (
        <a href={item.href} target="_blank" rel="noopener noreferrer" className="block">
          {rowBody}
        </a>
      ) : item.onOpen ? (
        <div
          role="button"
          tabIndex={0}
          onClick={item.onOpen}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              item.onOpen?.();
            }
          }}
          className="block focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/60"
        >
          {rowBody}
        </div>
      ) : (
        rowBody
      )}
    </motion.div>
  );
}

export function FeedRowSkeleton() {
  return (
    <div className="rounded-[22px] border border-white/6 bg-white/[0.03] px-5 py-4">
      <div className="flex flex-col gap-4 md:flex-row md:items-center">
        <div className="flex items-start gap-3 md:w-40 md:shrink-0">
          <div className="h-9 w-9 animate-pulse rounded-full bg-white/6" />
          <div className="space-y-1">
            <div className="h-5 w-20 animate-pulse rounded-full bg-white/10" />
            <div className="h-3 w-14 animate-pulse rounded bg-white/5" />
          </div>
        </div>
        <div className="min-w-0 flex-1">
          <div className="mb-2 h-5 w-56 animate-pulse rounded bg-white/10" />
          <div className="mb-3 flex gap-2">
            <div className="h-6 w-16 animate-pulse rounded-full bg-white/10" />
            <div className="h-6 w-16 animate-pulse rounded-full bg-white/5" />
          </div>
          <div className="h-3.5 w-5/6 animate-pulse rounded bg-white/5" />
          <div className="mt-3 h-3 w-48 animate-pulse rounded bg-white/5" />
        </div>
        <div className="hidden h-11 w-11 animate-pulse rounded-full bg-white/6 md:block" />
      </div>
    </div>
  );
}
