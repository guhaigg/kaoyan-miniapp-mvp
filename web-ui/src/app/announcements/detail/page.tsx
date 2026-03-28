import { Suspense } from "react";
import AnnouncementDetailPage from "@/components/announcements/AnnouncementDetailPage";

export default function AnnouncementDetailRoute() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-slate-50" />}>
      <AnnouncementDetailPage />
    </Suspense>
  );
}
