"use client";

import BiliCategoryStrip from "@/components/home/BiliCategoryStrip";
import BiliHeroBanner from "@/components/home/BiliHeroBanner";
import BiliRecommendationGrid from "@/components/home/BiliRecommendationGrid";
import { useHomeAnnouncementsQuery } from "@/hooks/useSearch";

export default function HomePage() {
  const { data, isLoading } = useHomeAnnouncementsQuery({
    page: 1,
    page_size: 9,
  });

  return (
    <div className="pb-20">
      <BiliHeroBanner indexedCount={data?.total || 0} />
      <BiliCategoryStrip />
      <BiliRecommendationGrid items={data?.items || []} loading={isLoading} />
    </div>
  );
}
