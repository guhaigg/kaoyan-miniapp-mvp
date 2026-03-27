"use client";

import { motion } from "framer-motion";
import { useHomeAnnouncementsQuery } from "@/hooks/useSearch";
import BiliCategoryStrip from "@/components/home/BiliCategoryStrip";
import BiliHeroBanner from "@/components/home/BiliHeroBanner";
import BiliRecommendationGrid from "@/components/home/BiliRecommendationGrid";

export default function HomePage() {
  const { data, isLoading } = useHomeAnnouncementsQuery({
    page: 1,
    page_size: 9,
  });

  const items = data?.items || [];
  const featuredItem = items[0] || null;
  const sourceSummary = Object.entries(data?.source_breakdown || {})
    .sort((left, right) => right[1] - left[1])
    .slice(0, 3);

  return (
    <motion.div
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.98 }}
      transition={{ duration: 0.35 }}
      className="pb-20"
    >
      <BiliHeroBanner
        indexedCount={data?.total || 0}
        featuredItem={featuredItem}
        lastUpdatedAt={data?.last_updated_at || featuredItem?.updated_at || null}
      />
      <BiliCategoryStrip />

      <section className="mx-auto max-w-[1440px] px-4 pb-5 pt-3 md:px-6">
        <div className="flex flex-col gap-4 rounded-[34px] border border-white/80 bg-white/85 px-6 py-5 shadow-[0_18px_42px_rgba(148,163,184,0.12)] md:flex-row md:items-end md:justify-between">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-400">
              Recommended Feed
            </div>
            <h2 className="mt-2 text-3xl font-black tracking-tight text-slate-950">
              最近值得先点开的站内公告
            </h2>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-500">
              首页卡片继续用真实公告数据，但排布改成更像内容站首页的推荐流。置顶位更重，次级卡片更轻，进站第一屏不再像后台。
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            {sourceSummary.length > 0 ? (
              sourceSummary.map(([label, count]) => (
                <span
                  key={label}
                  className="rounded-full border border-slate-200 bg-slate-50 px-4 py-2 text-sm font-semibold text-slate-600"
                >
                  {label} · {count}
                </span>
              ))
            ) : (
              <span className="rounded-full border border-slate-200 bg-slate-50 px-4 py-2 text-sm font-semibold text-slate-500">
                正在等待推荐数据
              </span>
            )}
          </div>
        </div>
      </section>

      <BiliRecommendationGrid items={items} isLoading={isLoading} />
    </motion.div>
  );
}
