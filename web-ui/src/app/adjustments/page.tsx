import { Suspense } from "react";
import AdjustmentHubPage from "@/components/adjustments/AdjustmentHubPage";

export default function AdjustmentsPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-slate-50" />}>
      <AdjustmentHubPage />
    </Suspense>
  );
}
