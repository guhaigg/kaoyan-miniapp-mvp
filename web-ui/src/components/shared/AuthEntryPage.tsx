"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import type { AuthPane } from "./bili-auth-copy";
import BiliAuthModal from "./BiliAuthModal";

type AuthMode = "login" | "register";

export default function AuthEntryPage({
  initialMode,
}: {
  initialMode: AuthMode;
}) {
  return (
    <Suspense fallback={<AuthEntryPageFrame initialMode={initialMode} initialPane={initialMode === "register" ? "register" : "password"} />}>
      <AuthEntryPageSearchAware initialMode={initialMode} />
    </Suspense>
  );
}

function AuthEntryPageSearchAware({ initialMode }: { initialMode: AuthMode }) {
  const searchParams = useSearchParams();
  const initialPane: AuthPane =
    searchParams.get("tab") === "sms" ? "sms" : initialMode === "register" ? "register" : "password";

  return <AuthEntryPageFrame initialMode={initialMode} initialPane={initialPane} />;
}

function AuthEntryPageFrame({
  initialMode,
  initialPane,
}: {
  initialMode: AuthMode;
  initialPane: AuthPane;
}) {
  return (
    <div className="relative overflow-hidden">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[420px] bg-[linear-gradient(180deg,rgba(255,255,255,0.86),rgba(255,255,255,0))]" />
      <div className="pointer-events-none absolute inset-x-0 top-16 h-[520px] bg-[radial-gradient(circle_at_top_left,rgba(251,207,232,0.38),transparent_36%),radial-gradient(circle_at_top_right,rgba(191,219,254,0.34),transparent_34%),linear-gradient(180deg,rgba(248,250,255,0.92),rgba(246,248,255,0.42))]" />
      <BiliAuthModal initialMode={initialMode} initialPane={initialPane} presentation="page" />
    </div>
  );
}
