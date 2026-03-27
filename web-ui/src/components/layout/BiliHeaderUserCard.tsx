"use client";

import Link from "next/link";
import { Crown, LayoutGrid, LogOut, Palette, Sparkles, Star, UserRound } from "lucide-react";
import { motion } from "framer-motion";
import type { BiliHeaderSummary } from "./bili-header-data";

type BiliHeaderUserCardProps = {
  summary: BiliHeaderSummary;
  username: string;
  onClose: () => void;
  onLogout: () => void;
  onThemeClick: () => void;
};

const numberFormatter = new Intl.NumberFormat("zh-CN");

function buildAvatarLabel(name: string) {
  const trimmed = name.trim();
  if (!trimmed) {
    return "GW";
  }
  const glyphs = Array.from(trimmed);
  return glyphs.slice(0, glyphs.length > 2 ? 1 : 2).join("").toUpperCase();
}

export default function BiliHeaderUserCard({
  summary,
  username,
  onClose,
  onLogout,
  onThemeClick,
}: BiliHeaderUserCardProps) {
  const actions = [
    {
      label: "账户中心",
      description: "查看个人空间、通知和安全设置",
      href: "/account",
      icon: UserRound,
    },
    {
      label: "关注管理",
      description: "继续维护订阅、栏目和雷达范围",
      href: "/watchlist",
      icon: Star,
    },
    {
      label: "内容推荐",
      description: "回到导航页，重新挑选入口和功能",
      href: "/query",
      icon: Sparkles,
    },
    {
      label: "会员与服务",
      description: "查看权益、订单和后续升级入口",
      href: "/account?tab=account&panel=billing",
      icon: Crown,
    },
  ] as const;

  return (
    <motion.div
      initial={{ opacity: 0, y: 14, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 10, scale: 0.97 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
      className="w-[320px] max-w-[calc(100vw-1.5rem)] rounded-[28px] border border-slate-200/90 bg-white p-4 text-slate-900 shadow-[0_24px_70px_rgba(15,23,42,0.18)]"
    >
      <div className="rounded-[24px] bg-[linear-gradient(135deg,#fdf2f8_0%,#eff6ff_52%,#f8fafc_100%)] p-4">
        <div className="flex items-start gap-3">
          <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-[22px] bg-[linear-gradient(135deg,#fb7185,#60a5fa)] text-xl font-black text-white shadow-[0_14px_30px_rgba(96,165,250,0.28)]">
            {buildAvatarLabel(summary.displayName)}
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <div className="truncate text-lg font-black text-slate-900">{summary.displayName}</div>
              <span className="rounded-full bg-slate-900 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-white">
                {summary.levelLabel}
              </span>
            </div>
            <div className="mt-1 text-sm text-slate-500">@{username}</div>
            <div className="mt-3 inline-flex items-center gap-2 rounded-full border border-sky-100 bg-white/85 px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-[0_10px_24px_rgba(148,163,184,0.14)]">
              <span
                className={`h-2.5 w-2.5 rounded-full ${summary.isPremium ? "bg-amber-400" : "bg-slate-300"}`}
              />
              {summary.isPremium ? "高级权益已生效" : "当前为基础账户"}
            </div>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-3 gap-2">
          {summary.counters.map((item) => (
            <div key={item.label} className="rounded-[20px] bg-white/80 px-3 py-3 shadow-[0_10px_24px_rgba(148,163,184,0.1)]">
              <div className="text-[11px] font-medium text-slate-500">{item.label}</div>
              <div className="mt-1 text-lg font-black text-slate-900">{numberFormatter.format(item.value)}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-4 space-y-2">
        {actions.map((action) => {
          const Icon = action.icon;
          return (
            <Link
              key={action.label}
              href={action.href}
              onClick={onClose}
              className="flex items-center gap-3 rounded-[20px] border border-slate-200 bg-slate-50 px-3 py-3 transition-colors hover:border-sky-200 hover:bg-sky-50"
            >
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-white text-slate-700 shadow-[0_8px_18px_rgba(148,163,184,0.12)]">
                <Icon size={18} />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-semibold text-slate-900">{action.label}</span>
                <span className="mt-0.5 block text-xs leading-5 text-slate-500">{action.description}</span>
              </span>
            </Link>
          );
        })}

        <div className="grid grid-cols-2 gap-2 pt-1">
          <button
            type="button"
            onClick={() => {
              onClose();
              onThemeClick();
            }}
            className="flex items-center justify-center gap-2 rounded-[18px] border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-700 transition-colors hover:border-sky-200 hover:bg-sky-50"
          >
            <Palette size={16} />
            外观主题
          </button>
          <button
            type="button"
            onClick={() => {
              onClose();
              onLogout();
            }}
            className="flex items-center justify-center gap-2 rounded-[18px] border border-rose-100 bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-600 transition-colors hover:bg-rose-100"
          >
            <LogOut size={16} />
            退出登录
          </button>
        </div>
      </div>

      <div className="mt-4 flex items-center gap-2 rounded-[18px] bg-slate-950 px-3 py-3 text-xs text-slate-200">
        <LayoutGrid size={15} className="shrink-0" />
        <span>这个卡片只显示当前账号的真实订阅、雷达和提醒数量，不拼接虚构指标。</span>
      </div>
    </motion.div>
  );
}
