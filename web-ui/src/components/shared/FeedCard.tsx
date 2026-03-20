"use client";

import { type MouseEvent, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { AlertCircle, ArrowUpRight, Info, Share2, Star, TrendingUp } from "lucide-react";

export interface FeedItem {
  id: string;
  type: "adjustment" | "announcement";
  title: string;
  content: string;
  subtitle?: string;
  publishTime: string | Date;
  tags: string[];
  badges?: Array<{ label: string; tone: "sky" | "amber" }>;
  isUrgent?: boolean;
  metricLabel?: string;
  metricPrimary?: string | null;
  metricSecondary?: string | null;
  warningLabel?: string | null;
  href?: string | null;
  onOpen?: () => void;
  bookmark?: {
    active: boolean;
    available: boolean;
    label: string;
    onToggle: () => Promise<void> | void;
  };
}

const toneMap = {
  calm: {
    card: "bg-[#0a0f1a]/82 border-white/6 hover:border-cyan-500/35",
    glow: "bg-cyan-500/10",
    accent: "text-cyan-300",
  },
  urgent: {
    card: "bg-orange-950/12 border-orange-500/20 hover:border-orange-500/45",
    glow: "bg-orange-500/10",
    accent: "text-orange-300",
  },
};

export default function FeedCard({ item }: { item: FeedItem }) {
  const [copied, setCopied] = useState(false);
  const [bookmarkBusy, setBookmarkBusy] = useState(false);
  const [bookmarkFlash, setBookmarkFlash] = useState<"saved" | "removed" | null>(null);

  const isUrgent = Boolean(item.isUrgent);
  const tone = isUrgent ? toneMap.urgent : toneMap.calm;
  const tags = item.tags.slice(0, 4);
  const badges = item.badges || [];
  const timeAgo = formatDistanceToNowZh(item.publishTime);
  const statusLabel = isUrgent ? "紧急缺额" : item.type === "adjustment" ? "调剂动态" : "最新公告";

  async function handleShare(event: MouseEvent<HTMLButtonElement>) {
    event.preventDefault();
    event.stopPropagation();
    const shareUrl = item.href || (typeof window !== "undefined" ? window.location.href : "");

    try {
      if (navigator.share && item.href) {
        await navigator.share({ title: item.title, text: item.content, url: shareUrl });
      } else if (shareUrl && navigator.clipboard) {
        await navigator.clipboard.writeText(shareUrl);
      }
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1200);
    } catch {
      setCopied(false);
    }
  }

  async function handleBookmark(event: MouseEvent<HTMLButtonElement>) {
    event.preventDefault();
    event.stopPropagation();
    if (!item.bookmark || bookmarkBusy) return;
    const nextFlash = item.bookmark.active ? "removed" : "saved";
    setBookmarkBusy(true);
    try {
      await item.bookmark.onToggle();
      setBookmarkFlash(nextFlash);
      window.setTimeout(() => setBookmarkFlash(null), 1200);
    } finally {
      setBookmarkBusy(false);
    }
  }

  const cardContent = (
    <CardBody
      item={item}
      copied={copied}
      bookmarkBusy={bookmarkBusy}
      onShare={handleShare}
      onBookmark={handleBookmark}
      statusLabel={statusLabel}
      timeAgo={timeAgo}
      tags={tags}
      badges={badges}
      tone={tone}
    />
  );

  return (
    <motion.article
      initial={{ opacity: 0, y: 15 }}
      whileInView={{ opacity: 1, y: 0 }}
      whileHover={{ y: -2 }}
      viewport={{ once: true, margin: "-48px" }}
      transition={{ duration: 0.28, ease: "easeOut" }}
      className={`group relative overflow-hidden rounded-2xl border p-4 shadow-lg backdrop-blur-xl transition-all md:p-5 ${tone.card}`}
    >
      <div className={`absolute right-0 top-0 h-24 w-24 translate-x-1/2 -translate-y-1/2 rounded-full blur-3xl opacity-50 transition-transform duration-500 group-hover:scale-125 ${tone.glow}`} />

      {item.href ? (
        <a
          href={item.href}
          target="_blank"
          rel="noopener noreferrer"
          className="relative z-10 flex h-full flex-col"
        >
          {cardContent}
        </a>
      ) : (
        <div className="relative z-10 flex h-full flex-col">{cardContent}</div>
      )}

      <AnimatePresence>
        {copied ? (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8 }}
            className="absolute bottom-3 right-3 rounded-full border border-cyan-400/20 bg-cyan-500/10 px-2.5 py-1 text-[10px] text-cyan-200"
          >
            已复制
          </motion.div>
        ) : null}
        {bookmarkFlash ? (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8 }}
            className={`absolute bottom-3 left-3 rounded-full border px-2.5 py-1 text-[10px] ${
              bookmarkFlash === "saved"
                ? "border-yellow-400/20 bg-yellow-500/10 text-yellow-200"
                : "border-white/10 bg-white/10 text-slate-200"
            }`}
          >
            {bookmarkFlash === "saved" ? "已收藏" : "已取消收藏"}
          </motion.div>
        ) : null}
      </AnimatePresence>
    </motion.article>
  );
}

function CardBody({
  item,
  copied,
  bookmarkBusy,
  onShare,
  onBookmark,
  statusLabel,
  timeAgo,
  tags,
  badges,
  tone,
}: {
  item: FeedItem;
  copied: boolean;
  bookmarkBusy: boolean;
  onShare: (event: MouseEvent<HTMLButtonElement>) => Promise<void>;
  onBookmark: (event: MouseEvent<HTMLButtonElement>) => Promise<void>;
  statusLabel: string;
  timeAgo: string;
  tags: string[];
  badges: Array<{ label: string; tone: "sky" | "amber" }>;
  tone: {
    card: string;
    glow: string;
    accent: string;
  };
}) {
  return (
    <>
      <div className="mb-2 flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className={`mb-1 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] ${tone.accent}`}>
            {item.isUrgent ? <AlertCircle size={12} /> : <Info size={12} />}
            <span>{statusLabel}</span>
          </div>
          <h3 className="line-clamp-2 text-lg font-bold leading-tight text-white transition-colors group-hover:text-cyan-50 md:text-[1.1rem]">
            {item.title}
          </h3>
          <p className="mt-1 text-xs text-slate-400">{timeAgo}</p>
        </div>

        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={onShare}
            className="rounded-md p-1.5 text-slate-500 transition-colors hover:bg-white/8 hover:text-slate-200"
            aria-label="分享"
          >
            <Share2 size={14} />
          </button>
          {item.bookmark ? (
            <motion.button
              type="button"
              whileTap={{ scale: 0.78 }}
              disabled={bookmarkBusy}
              title={item.bookmark.label}
              onClick={onBookmark}
              className={`rounded-md p-1.5 transition-colors ${
                item.bookmark.active
                  ? "text-yellow-400"
                  : item.bookmark.available
                    ? "text-slate-500 hover:bg-white/8 hover:text-slate-200"
                    : "text-slate-600 hover:bg-white/8 hover:text-slate-400"
              } ${bookmarkBusy ? "cursor-not-allowed opacity-60" : ""}`}
            >
              <Star
                size={15}
                fill={item.bookmark.active ? "currentColor" : "none"}
                className={item.bookmark.active ? "drop-shadow-[0_0_8px_rgba(250,204,21,0.5)]" : undefined}
              />
            </motion.button>
          ) : null}
        </div>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-1.5">
        {tags.length > 0
          ? tags.map((tag, index) => (
              <span
                key={`${item.id}-${tag}-${index}`}
                className="rounded-md border border-white/5 bg-white/5 px-1.5 py-0.5 text-[10px] text-slate-300"
              >
                {tag}
              </span>
            ))
          : (
            <span className="rounded-md border border-white/5 bg-white/5 px-1.5 py-0.5 text-[10px] text-slate-500">
              待补充
            </span>
          )}
        {badges.slice(0, 2).map((badge) => (
          <span
            key={`${item.id}-${badge.label}`}
            className={
              badge.tone === "amber"
                ? "rounded-md border border-amber-500/20 bg-amber-500/10 px-1.5 py-0.5 text-[10px] text-amber-200"
                : "rounded-md border border-cyan-500/20 bg-cyan-500/10 px-1.5 py-0.5 text-[10px] text-cyan-200"
            }
          >
            {badge.label}
          </span>
        ))}
      </div>

      <p className="line-clamp-3 text-sm leading-6 text-slate-400">{item.content}</p>

      <div className="mt-4 flex-1" />

      <div className="mt-auto flex items-center justify-between border-t border-white/5 pt-3">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1 text-[10px] text-slate-400">
            <TrendingUp size={12} className="text-slate-500" />
            <span>{item.type === "adjustment" ? "调剂情报" : "公告正文"}</span>
          </div>
          <div className="h-3 w-px bg-white/10" />
          <div className="text-[10px] text-slate-500">{copied ? "链接已复制" : "点击查看详情"}</div>
        </div>
        <div className="flex items-center gap-1 text-[11px] font-medium text-slate-400 transition-colors group-hover:text-slate-200">
          查看
          <ArrowUpRight size={14} className="transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
        </div>
      </div>
    </>
  );
}

export function FeedCardSkeleton() {
  return (
    <div className="relative h-[188px] overflow-hidden rounded-2xl border border-white/5 bg-white/[0.02] p-4 md:p-5">
      <motion.div
        initial={{ x: "-100%" }}
        animate={{ x: "220%" }}
        transition={{ repeat: Infinity, duration: 1.4, ease: "linear" }}
        className="absolute inset-y-0 z-10 w-1/2 skew-x-12 bg-gradient-to-r from-transparent via-white/5 to-transparent"
      />
      <div className="mb-3 flex items-start justify-between">
        <div className="space-y-2">
          <div className="h-3 w-16 animate-pulse rounded-full bg-white/10" />
          <div className="h-5 w-52 animate-pulse rounded-lg bg-white/10" />
          <div className="h-3 w-20 animate-pulse rounded bg-white/5" />
        </div>
        <div className="h-7 w-7 animate-pulse rounded-md bg-white/5" />
      </div>
      <div className="mb-3 flex gap-2">
        <div className="h-5 w-12 animate-pulse rounded-md bg-white/10" />
        <div className="h-5 w-12 animate-pulse rounded-md bg-white/5" />
        <div className="h-5 w-12 animate-pulse rounded-md bg-white/5" />
      </div>
      <div className="space-y-2">
        <div className="h-3.5 w-full animate-pulse rounded bg-white/5" />
        <div className="h-3.5 w-5/6 animate-pulse rounded bg-white/5" />
        <div className="h-3.5 w-2/3 animate-pulse rounded bg-white/5" />
      </div>
      <div className="absolute bottom-4 left-4 right-4 flex items-center justify-between border-t border-white/5 pt-3 md:bottom-5 md:left-5 md:right-5">
        <div className="h-3 w-28 animate-pulse rounded bg-white/5" />
        <div className="h-3 w-12 animate-pulse rounded bg-white/5" />
      </div>
    </div>
  );
}

export function formatDistanceToNowZh(input: string | Date) {
  const date = new Date(input);
  if (Number.isNaN(date.getTime())) return "时间未知";
  const diffMs = Date.now() - date.getTime();
  if (diffMs < 60 * 1000) return "刚刚";
  if (diffMs < 60 * 60 * 1000) return `${Math.max(1, Math.floor(diffMs / 60000))} 分钟前`;
  if (diffMs < 24 * 60 * 60 * 1000) return `${Math.max(1, Math.floor(diffMs / 3600000))} 小时前`;
  return `${Math.max(1, Math.floor(diffMs / 86400000))} 天前`;
}
