"use client";

import { type MouseEvent, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle,
  ChevronRight,
  FileText,
  Share2,
  Star,
  Target,
} from "lucide-react";

export interface FeedItem {
  id: string;
  type: "adjustment" | "announcement";
  title: string;
  content: string;
  publishTime: string | Date;
  tags: string[];
  badges?: Array<{ label: string; tone: "sky" | "amber" }>;
  isUrgent?: boolean;
  href?: string | null;
  bookmark?: {
    active: boolean;
    available: boolean;
    label: string;
    onToggle: () => Promise<void> | void;
  };
}

export default function FeedCard({ item }: { item: FeedItem }) {
  const [copied, setCopied] = useState(false);
  const [bookmarkBusy, setBookmarkBusy] = useState(false);
  const [bookmarkFlash, setBookmarkFlash] = useState<"saved" | "removed" | null>(null);

  const isAdjustment = item.type === "adjustment";
  const isUrgent = Boolean(item.isUrgent);
  const themeColor = isUrgent ? "orange" : isAdjustment ? "purple" : "cyan";

  const colorMap = {
    cyan: {
      bg: "bg-white/5",
      border: "border-white/10 hover:border-cyan-400/50",
      glow: "bg-cyan-500/10",
      text: "text-cyan-400",
      badgeBg: "bg-[#2c3e50]",
    },
    orange: {
      bg: "bg-orange-950/20",
      border: "border-orange-500/30 hover:border-orange-500",
      glow: "bg-orange-500/10",
      text: "text-orange-400",
      badgeBg: "bg-orange-500/20",
    },
    purple: {
      bg: "bg-purple-950/10",
      border: "border-purple-500/20 hover:border-purple-400/50",
      glow: "bg-purple-500/10",
      text: "text-purple-400",
      badgeBg: "bg-purple-500/20",
    },
  };

  const style = colorMap[themeColor];
  const timeAgo = formatDistanceToNowZh(item.publishTime);

  const tags = item.tags.length > 0 ? item.tags : ["待补充"];
  const badges = item.badges || [];

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

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-50px" }}
      whileHover={{ y: -4 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className={`group relative overflow-hidden rounded-3xl border p-6 shadow-xl transition-all ${style.border} ${style.bg}`}
    >
      <div
        className={`absolute right-0 top-0 h-32 w-32 translate-x-1/2 -translate-y-1/2 rounded-full blur-3xl transition-transform duration-500 group-hover:scale-150 ${style.glow}`}
      />

      {item.href ? (
        <a
          href={item.href}
          target="_blank"
          rel="noopener noreferrer"
          className="relative z-10 flex h-full flex-col justify-between"
        >
          <CardBody
            bookmarkBusy={bookmarkBusy}
            copied={copied}
            handleBookmark={handleBookmark}
            handleShare={handleShare}
            isAdjustment={isAdjustment}
            isUrgent={isUrgent}
            item={item}
            style={style}
            badges={badges}
            tags={tags}
            timeAgo={timeAgo}
          />
        </a>
      ) : (
        <div className="relative z-10 flex h-full flex-col justify-between">
          <CardBody
            bookmarkBusy={bookmarkBusy}
            copied={copied}
            handleBookmark={handleBookmark}
            handleShare={handleShare}
            isAdjustment={isAdjustment}
            isUrgent={isUrgent}
            item={item}
            style={style}
            badges={badges}
            tags={tags}
            timeAgo={timeAgo}
          />
        </div>
      )}

      <AnimatePresence>
        {copied ? (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 10 }}
            className="absolute bottom-4 right-4 rounded-full border border-cyan-400/20 bg-cyan-500/10 px-3 py-1 text-xs text-cyan-300"
          >
            已复制分享链接
          </motion.div>
        ) : null}
        {bookmarkFlash ? (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 10 }}
            className={`absolute bottom-4 left-4 rounded-full border px-3 py-1 text-xs ${
              bookmarkFlash === "saved"
                ? "border-yellow-400/20 bg-yellow-500/10 text-yellow-200"
                : "border-white/10 bg-white/10 text-slate-200"
            }`}
          >
            {bookmarkFlash === "saved" ? "已收藏" : "已取消收藏"}
          </motion.div>
        ) : null}
      </AnimatePresence>
    </motion.div>
  );
}

function CardBody({
  bookmarkBusy,
  copied,
  handleBookmark,
  handleShare,
  isAdjustment,
  isUrgent,
  item,
  style,
  badges,
  tags,
  timeAgo,
}: {
  bookmarkBusy: boolean;
  copied: boolean;
  handleBookmark: (event: MouseEvent<HTMLButtonElement>) => Promise<void>;
  handleShare: (event: MouseEvent<HTMLButtonElement>) => Promise<void>;
  isAdjustment: boolean;
  isUrgent: boolean;
  item: FeedItem;
  style: {
    bg: string;
    border: string;
    glow: string;
    text: string;
    badgeBg: string;
  };
  badges: Array<{ label: string; tone: "sky" | "amber" }>;
  tags: string[];
  timeAgo: string;
}) {
  return (
    <>
      <div>
        <div className="mb-3 flex items-center justify-between">
          <div className={`flex items-center gap-1.5 text-xs font-mono ${style.text}`}>
            {isUrgent ? (
              <span className="h-2 w-2 rounded-full bg-orange-500 shadow-[0_0_8px_#f97316] animate-pulse" />
            ) : null}
            {isUrgent ? (
              <AlertTriangle size={14} />
            ) : isAdjustment ? (
              <Target size={14} />
            ) : (
              <FileText size={14} />
            )}
            {isUrgent ? "紧急缺额" : isAdjustment ? "调剂动态" : "最新公告"}
            <span className="ml-2 text-slate-500">· {timeAgo}</span>
          </div>

          <div className="flex gap-2 opacity-0 transition-opacity group-hover:opacity-100">
            <button
              type="button"
              onClick={handleShare}
              className="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-white/10 hover:text-white"
            >
              <Share2 size={16} />
            </button>
            {item.bookmark ? (
              <motion.button
                type="button"
                whileTap={{ scale: 0.8 }}
                disabled={bookmarkBusy}
                title={item.bookmark.label}
                onClick={handleBookmark}
                className={`rounded-lg p-1.5 transition-colors ${
                  item.bookmark.active
                    ? "text-yellow-400 hover:bg-yellow-400/10"
                    : item.bookmark.available
                      ? "text-slate-400 hover:bg-white/10 hover:text-white"
                      : "text-slate-500 hover:bg-white/10 hover:text-slate-300"
                } ${bookmarkBusy ? "cursor-not-allowed opacity-60" : ""}`}
              >
                <Star
                  size={16}
                  fill={item.bookmark.active ? "currentColor" : "none"}
                  className={item.bookmark.active ? "drop-shadow-[0_0_8px_rgba(250,204,21,0.6)]" : undefined}
                />
              </motion.button>
            ) : null}
          </div>
        </div>

        <h3 className="mb-2 text-xl font-bold leading-snug text-white transition-colors group-hover:text-cyan-50">
          {item.title}
        </h3>
        {badges.length > 0 ? (
          <div className="mb-3 flex flex-wrap gap-2">
            {badges.map((badge) => (
              <span
                key={`${item.id}-${badge.label}`}
                className={
                  badge.tone === "amber"
                    ? "rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-[11px] font-semibold text-amber-200"
                    : "rounded-full border border-sky-500/30 bg-sky-500/10 px-2.5 py-1 text-[11px] font-semibold text-sky-200"
                }
              >
                {badge.label}
              </span>
            ))}
          </div>
        ) : null}
        <p className="mb-5 line-clamp-2 text-sm leading-relaxed text-slate-400">
          {item.content}
        </p>
      </div>

      <div className="mt-2 flex items-center justify-between border-t border-white/5 pt-4">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          {tags.map((tag, index) => (
            <span
              key={`${item.id}-${tag}-${index}`}
              className={`rounded px-2 py-1 text-white ${
                index === 0 ? style.badgeBg : "bg-white/5 text-slate-300"
              }`}
            >
              {tag}
            </span>
          ))}
        </div>
        <div className="flex items-center gap-1 text-sm font-medium text-slate-400 transition-colors group-hover:text-white">
          {copied ? "链接已复制" : "查看详情"}
          <ChevronRight size={16} className="transition-transform group-hover:translate-x-1" />
        </div>
      </div>
    </>
  );
}

export function FeedCardSkeleton() {
  return (
    <div className="relative h-[220px] overflow-hidden rounded-3xl border border-white/5 bg-white/[0.02] p-6">
      <motion.div
        initial={{ x: "-100%" }}
        animate={{ x: "200%" }}
        transition={{ repeat: Infinity, duration: 1.5, ease: "linear" }}
        className="absolute bottom-0 top-0 z-10 w-1/2 skew-x-12 bg-gradient-to-r from-transparent via-white/5 to-transparent"
      />
      <div className="mb-4 flex items-center justify-between">
        <div className="h-4 w-24 animate-pulse rounded-full bg-white/10" />
        <div className="h-6 w-16 animate-pulse rounded-lg bg-white/5" />
      </div>
      <div className="mb-3 h-6 w-3/4 animate-pulse rounded-lg bg-white/10" />
      <div className="mb-2 h-4 w-full animate-pulse rounded-lg bg-white/5" />
      <div className="h-4 w-4/5 animate-pulse rounded-lg bg-white/5" />
      <div className="absolute bottom-6 left-6 right-6 flex gap-2 border-t border-white/5 pt-4">
        <div className="h-6 w-16 animate-pulse rounded bg-white/10" />
        <div className="h-6 w-16 animate-pulse rounded bg-white/5" />
      </div>
    </div>
  );
}

function formatDistanceToNowZh(input: string | Date) {
  const date = new Date(input);
  if (Number.isNaN(date.getTime())) return "时间未知";
  const diffMs = Date.now() - date.getTime();
  if (diffMs < 60 * 1000) return "刚刚";
  if (diffMs < 60 * 60 * 1000) return `${Math.max(1, Math.floor(diffMs / 60000))} 分钟前`;
  if (diffMs < 24 * 60 * 60 * 1000) return `${Math.max(1, Math.floor(diffMs / 3600000))} 小时前`;
  return `${Math.max(1, Math.floor(diffMs / 86400000))} 天前`;
}
