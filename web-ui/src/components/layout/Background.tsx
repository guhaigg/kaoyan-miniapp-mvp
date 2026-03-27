"use client";

import { usePathname } from "next/navigation";

const BANNER_ROUTES = new Set(["/", "/login", "/register", "/account"]);

export default function Background() {
  const pathname = usePathname();
  const showBannerGlow = BANNER_ROUTES.has(pathname);
  const showAdminTone = pathname.startsWith("/admin");

  return (
    <>
      <div className="pointer-events-none fixed inset-0 z-0 bg-[linear-gradient(180deg,#fbfcff_0%,#f6f7fb_55%,#eef2f8_100%)]" />
      <div
        className={`pointer-events-none fixed inset-0 z-0 transition-opacity duration-300 ${
          showAdminTone ? "opacity-100" : "opacity-0"
        }`}
      >
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_90%_8%,rgba(56,189,248,0.12),transparent_28%),radial-gradient(circle_at_12%_16%,rgba(251,113,133,0.08),transparent_34%)]" />
      </div>
      {showBannerGlow ? (
        <div className="pointer-events-none fixed inset-x-0 top-0 z-0 h-[420px] bg-[radial-gradient(circle_at_top,rgba(251,114,153,0.18),transparent_48%),radial-gradient(circle_at_35%_18%,rgba(0,174,236,0.16),transparent_34%)]" />
      ) : null}
      <div className="pointer-events-none fixed inset-0 z-0 opacity-30 [background-image:linear-gradient(to_right,rgba(15,23,42,0.04)_1px,transparent_1px),linear-gradient(to_bottom,rgba(15,23,42,0.04)_1px,transparent_1px)] [background-size:44px_44px]" />
    </>
  );
}
