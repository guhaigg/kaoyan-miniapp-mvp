"use client";

import { usePathname } from "next/navigation";

export default function Background() {
  const pathname = usePathname();
  const hueRotate =
    pathname === "/admin"
      ? "hue-rotate-90"
      : pathname === "/search"
        ? "-hue-rotate-45"
        : "hue-rotate-0";

  return (
    <>
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
    </>
  );
}
