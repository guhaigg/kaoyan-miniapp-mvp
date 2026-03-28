"use client";

export type PrimaryRouteKey =
  | "home"
  | "announcements"
  | "adjustments"
  | "radar"
  | "watchlist"
  | "account"
  | "admin";

export type SearchMode = "announcements" | "adjustments";

export type PrimaryNavItem = {
  key: PrimaryRouteKey;
  href: string;
  label: string;
  badge?: string;
};

const BASE_PRIMARY_NAV_ITEMS: PrimaryNavItem[] = [
  { key: "home", href: "/", label: "首页" },
  { key: "announcements", href: "/announcements", label: "公告汇总" },
  { key: "adjustments", href: "/adjustments", label: "调剂汇总" },
  { key: "radar", href: "/radar", label: "雷达测算", badge: "BETA" },
  { key: "watchlist", href: "/watchlist", label: "关注库" },
  { key: "account", href: "/account", label: "我的空间" },
];

const ADMIN_NAV_ITEM: PrimaryNavItem = {
  key: "admin",
  href: "/admin",
  label: "管理后台",
};

const GLOBAL_SEARCH_HIDDEN_PREFIXES = ["/announcements", "/adjustments"];

export function getPrimaryNavItems(includeAdmin: boolean) {
  return includeAdmin ? [...BASE_PRIMARY_NAV_ITEMS, ADMIN_NAV_ITEM] : BASE_PRIMARY_NAV_ITEMS;
}

export function resolvePrimaryRouteKey(pathname: string): PrimaryRouteKey {
  if (pathname === "/") return "home";
  if (pathname.startsWith("/announcements")) return "announcements";
  if (pathname.startsWith("/adjustments")) return "adjustments";
  if (pathname.startsWith("/radar")) return "radar";
  if (pathname.startsWith("/watchlist")) return "watchlist";
  if (pathname.startsWith("/account")) return "account";
  if (pathname.startsWith("/admin")) return "admin";
  return "home";
}

export function shouldShowGlobalSearch(pathname: string) {
  return !GLOBAL_SEARCH_HIDDEN_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}

export function buildSearchDestination(mode: SearchMode, keyword: string) {
  const href = mode === "announcements" ? "/announcements" : "/adjustments";
  const params = new URLSearchParams();
  if (keyword.trim()) {
    params.set("keywords", keyword.trim());
  }
  const query = params.toString();
  return query ? `${href}?${query}` : href;
}

export function buildAnnouncementDetailHref(contentId: string) {
  const params = new URLSearchParams({ id: contentId });
  return `/announcements/detail?${params.toString()}`;
}

export function buildAdjustmentDetailHref(itemId: string, itemKind: "content" | "opportunity") {
  const params = new URLSearchParams({ id: itemId, kind: itemKind });
  return `/adjustments/detail?${params.toString()}`;
}
