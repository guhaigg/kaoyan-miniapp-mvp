"use client";

import Link from "next/link";
import { LogIn, Sparkles, type LucideIcon } from "lucide-react";
import type { BiliHeaderTier } from "./bili-header-data";

export type BiliHeaderIconAction = {
  href?: string;
  label: string;
  icon: LucideIcon;
  onClick?: () => void;
  badgeCount?: number;
  badgeTone?: "accent" | "danger";
};

export function BiliHeaderNavLink({
  href,
  label,
  active,
  compact = false,
}: {
  href: string;
  label: string;
  active: boolean;
  compact?: boolean;
}) {
  return (
    <Link
      href={href}
      className={`inline-flex items-center justify-center rounded-full px-4 py-2 text-sm font-semibold transition-colors ${
        active
          ? "bg-slate-900 text-white"
          : compact
            ? "bg-white text-slate-700"
            : "text-slate-600 hover:bg-white/80 hover:text-slate-900"
      }`}
    >
      {label}
    </Link>
  );
}

export function BiliHeaderIconActionBar({ actions }: { actions: BiliHeaderIconAction[] }) {
  return (
    <div className="flex items-center gap-2">
      {actions.map((action) => {
        const content = (
          <>
            <action.icon size={17} />
            {action.badgeCount && action.badgeCount > 0 ? (
              <span
                className={`absolute -right-1 -top-1 flex h-5 min-w-[20px] items-center justify-center rounded-full border-2 border-white px-1 text-[10px] font-bold text-white ${
                  action.badgeTone === "danger" ? "bg-rose-500" : "bg-sky-500"
                }`}
              >
                {Math.min(action.badgeCount, 99)}
              </span>
            ) : null}
          </>
        );

        const className =
          "relative inline-flex h-10 w-10 items-center justify-center rounded-full border border-white/80 bg-white/90 text-slate-700 transition-colors hover:border-sky-200 hover:bg-sky-50 hover:text-slate-900";

        if (action.href) {
          return (
            <Link key={action.label} href={action.href} aria-label={action.label} className={className}>
              {content}
            </Link>
          );
        }

        return (
          <button
            key={action.label}
            type="button"
            onClick={action.onClick}
            aria-label={action.label}
            className={className}
          >
            {content}
          </button>
        );
      })}
    </div>
  );
}

export function BiliHeaderCta({
  href,
  children,
  primary = false,
}: {
  href: string;
  children: string;
  primary?: boolean;
}) {
  return (
    <Link
      href={href}
      className={`inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold transition-colors ${
        primary
          ? "bg-[linear-gradient(90deg,#60a5fa,#f472b6)] text-white shadow-[0_14px_26px_rgba(96,165,250,0.24)]"
          : "border border-white/80 bg-white/90 text-slate-700 hover:border-sky-200 hover:bg-sky-50"
      }`}
    >
      {primary ? <LogIn size={15} /> : <Sparkles size={15} />}
      {children}
    </Link>
  );
}

export function BiliHeaderAvatarTrigger({
  displayName,
  tier,
  onClick,
}: {
  displayName: string;
  tier: BiliHeaderTier;
  onClick?: () => void;
}) {
  const initials = Array.from(displayName.trim() || "GW")
    .slice(0, displayName.trim().length > 2 ? 1 : 2)
    .join("")
    .toUpperCase();
  const accentClass =
    tier === "admin"
      ? "bg-[linear-gradient(135deg,#0f172a,#6366f1)]"
      : tier === "premium"
        ? "bg-[linear-gradient(135deg,#fb7185,#f59e0b)]"
        : "bg-[linear-gradient(135deg,#fb7185,#60a5fa)]";
  const statusClass =
    tier === "admin" ? "bg-indigo-500" : tier === "premium" ? "bg-amber-400" : "bg-emerald-400";
  const className = `relative inline-flex h-11 w-11 items-center justify-center rounded-full ${accentClass} text-sm font-black text-white shadow-[0_12px_26px_rgba(96,165,250,0.28)] ${
    onClick ? "transition-transform hover:scale-[1.03]" : ""
  }`;

  if (!onClick) {
    return (
      <span className={className}>
        {initials}
        <span className={`absolute -bottom-0.5 -right-0.5 h-4 w-4 rounded-full border-2 border-white ${statusClass}`} />
      </span>
    );
  }

  return (
    <button type="button" onClick={onClick} className={className}>
      {initials}
      <span className={`absolute -bottom-0.5 -right-0.5 h-4 w-4 rounded-full border-2 border-white ${statusClass}`} />
    </button>
  );
}
