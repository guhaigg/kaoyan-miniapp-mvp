"use client";

import Link from "next/link";
import { Crown, LogOut, Radar, Search, Sparkles, Star } from "lucide-react";
import type { BiliHeaderSummary } from "./bili-header-data";

type Props = {
  summary: BiliHeaderSummary;
  membershipLabel: string;
  onLogout: () => void;
  onNavigate: () => void;
};

export default function BiliHeaderUserCard({ summary, membershipLabel, onLogout, onNavigate }: Props) {
  return (
    <div className="bili-surface absolute right-0 top-14 w-[340px] p-5 text-slate-900">
      <div className="flex flex-col items-center text-center">
        <div className="flex h-20 w-20 items-center justify-center rounded-full border-4 border-white bg-[linear-gradient(135deg,#ffd7e5,#d7f2ff)] text-2xl font-black text-slate-700 shadow-[0_14px_30px_rgba(148,163,184,0.28)]">
          {summary.displayName.slice(0, 1).toUpperCase()}
        </div>
        <h3 className="mt-3 text-2xl font-black text-[#18191c]">{summary.displayName}</h3>
        <p className="mt-1 inline-flex items-center gap-1 rounded-full bg-[#fff1f6] px-3 py-1 text-xs font-semibold text-[#fb7299]">
          <Crown size={13} />
          {membershipLabel} · {summary.levelLabel}
        </p>
      </div>

      <div className="mt-4 grid grid-cols-3 gap-2">
        {summary.counters.map((item) => (
          <div key={item.label} className="rounded-xl border border-black/5 bg-slate-50/80 px-2 py-3 text-center">
            <div className="text-lg font-black text-slate-900">{item.value}</div>
            <div className="text-xs text-slate-500">{item.label}</div>
          </div>
        ))}
      </div>

      <div className="mt-4 grid gap-2">
        <Link
          href="/account"
          onClick={onNavigate}
          className="inline-flex items-center gap-2 rounded-xl border border-black/5 bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-50"
        >
          <Sparkles size={15} />
          我的空间
        </Link>
        <Link
          href="/watchlist"
          onClick={onNavigate}
          className="inline-flex items-center gap-2 rounded-xl border border-black/5 bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-50"
        >
          <Star size={15} />
          关注工作台
        </Link>
        <Link
          href="/radar"
          onClick={onNavigate}
          className="inline-flex items-center gap-2 rounded-xl border border-black/5 bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-50"
        >
          <Radar size={15} />
          雷达测算
        </Link>
        <Link
          href="/search"
          onClick={onNavigate}
          className="inline-flex items-center gap-2 rounded-xl border border-black/5 bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-50"
        >
          <Search size={15} />
          公告检索
        </Link>
      </div>

      <button
        type="button"
        onClick={onLogout}
        className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm font-semibold text-rose-600 transition-colors hover:bg-rose-100"
      >
        <LogOut size={15} />
        退出登录
      </button>
    </div>
  );
}
