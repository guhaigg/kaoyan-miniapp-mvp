import { Suspense } from "react";
import AccountSpacePage from "@/components/account/AccountSpacePage";

export default function AccountPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-slate-50" />}>
      <AccountSpacePage />
    </Suspense>
  );
}
