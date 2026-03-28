import { Suspense } from "react";
import AnnouncementHubPage from "@/components/announcements/AnnouncementHubPage";

export default function AnnouncementsPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-slate-50" />}>
      <AnnouncementHubPage />
    </Suspense>
  );
}
