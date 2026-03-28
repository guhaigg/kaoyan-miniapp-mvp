import { Suspense } from "react";
import AdjustmentDetailPage from "@/components/adjustments/AdjustmentDetailPage";

export default function AdjustmentDetailRoute() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-slate-50" />}>
      <AdjustmentDetailPage />
    </Suspense>
  );
}
