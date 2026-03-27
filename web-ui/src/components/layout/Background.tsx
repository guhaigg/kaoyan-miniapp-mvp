"use client";

import { usePathname } from "next/navigation";

const BRIGHT_SHELL_ROUTES = new Set(["/login", "/register"]);
const BRIGHT_SHELL_PREFIXES = ["/account"];

type BackgroundMode = "legacy" | "bright" | "hybrid";

function matchesSegment(pathname: string, segment: string) {
  return pathname === segment || pathname.startsWith(`${segment}/`);
}

function getBackgroundMode(pathname: string): BackgroundMode {
  if (pathname === "/") {
    return "hybrid";
  }

  if (
    BRIGHT_SHELL_ROUTES.has(pathname) ||
    BRIGHT_SHELL_PREFIXES.some((prefix) => matchesSegment(pathname, prefix))
  ) {
    return "bright";
  }

  return "legacy";
}

export default function Background() {
  const pathname = usePathname();
  const backgroundMode = getBackgroundMode(pathname);
  const hueRotate =
    pathname === "/admin"
      ? "hue-rotate-90"
      : pathname === "/search"
        ? "-hue-rotate-45"
        : "hue-rotate-0";
  const showLegacyFoundation = backgroundMode !== "bright";
  const showBrightFoundation = backgroundMode === "bright";
  const showHybridBanner = backgroundMode === "hybrid";

  return (
    <>
      {showBrightFoundation ? (
        <>
          <div className="pointer-events-none fixed inset-0 z-0 bg-[linear-gradient(180deg,#fbfcff_0%,#f6f7fb_55%,#eef2f8_100%)]" />
          <div
            className="pointer-events-none fixed inset-x-0 top-0 z-0 bg-[radial-gradient(circle_at_top,rgba(251,114,153,0.18),transparent_48%),radial-gradient(circle_at_35%_18%,rgba(0,174,236,0.16),transparent_34%)]"
            style={{ height: "var(--shell-banner-glow-height)" }}
          />
        </>
      ) : null}
      {showLegacyFoundation ? (
        <>
          <div className="pointer-events-none fixed inset-0 z-0 bg-[#050b14]" />
          <div
            className="pointer-events-none fixed inset-0 z-0"
            style={{
              backgroundImage:
                "linear-gradient(to right, rgba(255,255,255,0.02) 1px, transparent 1px), linear-gradient(to bottom, rgba(255,255,255,0.02) 1px, transparent 1px)",
              backgroundSize: "60px 60px",
              maskImage: "radial-gradient(circle at center, black 30%, transparent 90%)",
              WebkitMaskImage:
                "radial-gradient(circle at center, black 30%, transparent 90%)",
            }}
          />
          <div
            className={`pointer-events-none fixed left-1/2 top-1/2 z-0 h-[100vw] w-[100vw] -translate-x-1/2 -translate-y-1/2 opacity-40 transition-all duration-1000 ${hueRotate}`}
          >
            <div
              className="absolute inset-0 origin-top-left animate-[spin_8s_linear_infinite] rounded-full"
              style={{
                background:
                  "conic-gradient(from 0deg, transparent 70%, rgba(6, 182, 212, 0.15) 100%)",
                transformOrigin: "50% 50%",
              }}
            />
          </div>
          {showHybridBanner ? (
            <div
              className="pointer-events-none fixed inset-x-0 top-0 z-0 bg-[linear-gradient(180deg,rgba(32,45,78,0.72)_0%,rgba(5,11,20,0.15)_68%,rgba(5,11,20,0)_100%),radial-gradient(circle_at_top,rgba(251,114,153,0.16),transparent_46%),radial-gradient(circle_at_34%_18%,rgba(0,174,236,0.14),transparent_30%)]"
              style={{ height: "var(--shell-banner-glow-height)" }}
            />
          ) : null}
        </>
      ) : null}
    </>
  );
}
