"use client";

import Link from "next/link";
import { BellRing, Compass, Layers3, Radar, Sparkles, University } from "lucide-react";

const categories = [
  {
    label: "公告流",
    description: "最新招生通知先看核心频道",
    href: "/search?tab=announcements",
    icon: BellRing,
    accent: "from-rose-300/65 to-white",
  },
  {
    label: "调剂情报",
    description: "直接跳到调剂检索和机会位",
    href: "/search?tab=adjustments",
    icon: Radar,
    accent: "from-sky-300/65 to-white",
  },
  {
    label: "学校入口",
    description: "把学校、专业、栏目入口排成一层",
    href: "/query",
    icon: University,
    accent: "from-amber-200/80 to-white",
  },
  {
    label: "关注提醒",
    description: "关注变化和待处理提醒合并看",
    href: "/account?tab=activity",
    icon: Sparkles,
    accent: "from-fuchsia-200/80 to-white",
  },
  {
    label: "功能导航",
    description: "快速找到站内所有可用能力",
    href: "/query",
    icon: Compass,
    accent: "from-cyan-200/80 to-white",
  },
  {
    label: "数据视角",
    description: "把同一份公告数据排成推荐页",
    href: "/search?tab=announcements",
    icon: Layers3,
    accent: "from-indigo-200/80 to-white",
  },
] as const;

export default function BiliCategoryStrip() {
  return (
    <section className="mx-auto max-w-[1440px] px-4 pb-4 md:px-6">
      <div className="overflow-x-auto pb-1">
        <div className="grid min-w-[980px] gap-3 md:grid-cols-3 xl:grid-cols-6">
          {categories.map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.label}
                href={item.href}
                className={`group rounded-[26px] border border-white/80 bg-[linear-gradient(135deg,var(--tw-gradient-stops))] ${item.accent} p-4 shadow-[0_16px_34px_rgba(148,163,184,0.12)] transition-transform hover:-translate-y-1`}
              >
                <div className="flex items-center gap-3">
                  <span className="flex h-12 w-12 items-center justify-center rounded-[18px] bg-white/95 text-slate-800 shadow-[0_12px_26px_rgba(148,163,184,0.16)] transition-colors group-hover:text-sky-500">
                    <Icon size={18} />
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate text-base font-black text-slate-900">{item.label}</span>
                    <span className="mt-1 block text-xs leading-6 text-slate-500">{item.description}</span>
                  </span>
                </div>
              </Link>
            );
          })}
        </div>
      </div>
    </section>
  );
}
