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
  const statusLabel = isUrgent ? "紧急缺额" : item.type === "adjustment" ? "常规调剂" : "常规公告";
  const tags = item.tags.slice(0, 2);

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

  const rowBody = (
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
                : "text-slate-600 hover:text-slate-400"
            } ${bookmarkBusy ? "cursor-not-allowed opacity-60" : ""}`}
          >
            <Star size={16} fill={item.bookmark.active ? "currentColor" : "none"} />
          </motion.button>
        ) : (
          <div className="h-6 w-6" />
        )}
        <div className="flex flex-col">
          <span className={`text-[10px] font-bold ${tone.accent}`}>{statusLabel}</span>
          <span className="text-[10px] font-mono text-slate-500">{timeAgo}</span>
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
                className="rounded bg-white/5 px-1.5 py-0.5 text-[10px] text-slate-400"
              >
                {tag}
              </span>
            ))}
          </div>
        </div>
        <p className="truncate text-xs text-slate-400">
          {item.subtitle || item.content}
        </p>
      </div>

      <div className="flex items-center gap-6 md:ml-auto md:shrink-0">
        <div className="flex flex-col items-start md:items-end">
          <span className="text-[10px] text-slate-500">
            {item.metricLabel || "摘要"}
          </span>
          <div className="flex items-baseline gap-1.5">
            <span className="text-sm font-bold font-mono text-white">
              {item.metricPrimary || "—"}
            </span>
            {item.metricSecondary ? (
              <span className="text-xs font-mono text-slate-500">/ {item.metricSecondary}</span>
            ) : null}
          </div>
        </div>

        {item.warningLabel ? (
          <div className="hidden items-center gap-1.5 rounded-md border border-red-500/20 bg-red-500/10 px-2 py-1 md:flex">
            <AlertCircle size={12} className="text-red-400" />
            <span className="text-[10px] text-red-400">{item.warningLabel}</span>
          </div>
        ) : null}

        <div className="hidden items-center gap-1 text-[11px] text-slate-500 md:flex">
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
      ) : (
        rowBody
      )}
    </motion.div>
  );
}

export function FeedRowSkeleton() {
  return (
    <div className="rounded-xl border border-white/5 bg-white/[0.02] px-5 py-3.5">
      <div className="flex flex-col gap-4 md:flex-row md:items-center">
        <div className="flex items-center gap-3 md:w-32 md:shrink-0">
          <div className="h-5 w-5 animate-pulse rounded bg-white/5" />
          <div className="space-y-1">
            <div className="h-2.5 w-12 animate-pulse rounded bg-white/10" />
            <div className="h-2.5 w-14 animate-pulse rounded bg-white/5" />
          </div>
        </div>
        <div className="min-w-0 flex-1">
          <div className="mb-2 h-4 w-56 animate-pulse rounded bg-white/10" />
          <div className="h-3 w-72 animate-pulse rounded bg-white/5" />
        </div>
        <div className="flex items-center gap-6 md:ml-auto">
          <div className="space-y-1">
            <div className="h-2.5 w-16 animate-pulse rounded bg-white/5" />
            <div className="h-3.5 w-24 animate-pulse rounded bg-white/10" />
          </div>
        </div>
      </div>
    </div>
  );
}
