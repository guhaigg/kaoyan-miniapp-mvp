"use client";

import Link from "next/link";
import { Compass, Search, Sparkles } from "lucide-react";

export default function BiliHeroBanner({ indexedCount }: { indexedCount: number }) {
  return (
    <section className="relative overflow-hidden border-b border-black/5">
      <div className="absolute inset-0 bg-[linear-gradient(130deg,rgba(0,174,236,0.12)_0%,rgba(251,114,153,0.14)_52%,rgba(255,255,255,0.5)_100%)]" />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_8%_12%,rgba(255,255,255,0.7),transparent_30%),radial-gradient(circle_at_86%_26%,rgba(255,255,255,0.62),transparent_28%)]" />

      <div className="relative mx-auto max-w-[1440px] px-4 pb-10 pt-14 md:px-6 md:pb-16 md:pt-16">
        <div className="max-w-3xl">
          <span className="bili-chip">
            <Sparkles size={13} className="text-[#fb7299]" />
            GEWU 研招情报壳
          </span>
          <h1 className="mt-4 text-3xl font-black leading-tight text-[#18191c] md:text-5xl">
            公告、调剂、订阅提醒
            <br />
            集中在一个更清晰的入口里
          </h1>
          <p className="mt-4 max-w-2xl text-sm leading-7 text-[#61666d] md:text-base">
            用统一主账号把公告检索、关注范围和雷达信号串起来。现在已索引 {indexedCount} 条公告数据，可直接进入检索与空间页。
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link
              href="/search"
              className="inline-flex items-center gap-2 rounded-full bg-[linear-gradient(90deg,#fb7299,#00aeec)] px-5 py-2.5 text-sm font-semibold text-white"
            >
              <Search size={15} />
              立即检索公告
            </Link>
            <Link
              href="/account"
              className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/90 px-5 py-2.5 text-sm font-semibold text-slate-700"
            >
              <Compass size={15} />
              打开个人空间
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
