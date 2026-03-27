"use client";

import { usePathname } from "next/navigation";

export default function Background() {
  const pathname = usePathname();
  const bannerRoutes = new Set(["/", "/login", "/register", "/account"]);
  const showBannerGlow = bannerRoutes.has(pathname);

  return (
    <>
      <div
        className="pointer-events-none fixed inset-0 z-0 bg-[linear-gradient(180deg,#fbfcff_0%,#f6f7fb_55%,#eef2f8_100%)]"
      />
      {showBannerGlow ? (
        <div className="pointer-events-none fixed inset-x-0 top-0 z-0 h-[420px] bg-[radial-gradient(circle_at_top,rgba(251,114,153,0.18),transparent_48%),radial-gradient(circle_at_35%_18%,rgba(0,174,236,0.16),transparent_34%)]" />
      ) : null}
    </>
  );
}
