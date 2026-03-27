"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useRef, useState } from "react";
import { AnimatePresence } from "framer-motion";
import { Bell, Compass, Search, Star } from "lucide-react";
import { ApiError, logoutUser } from "@/lib/api";
import { useMonitorTargetsQuery } from "@/hooks/useMonitoringTargets";
import { useWatchlistNoticesQuery } from "@/hooks/useNotifications";
import { useSubscriptionsQuery } from "@/hooks/useSubscriptions";
import {
  readSearchKeywordsFromParams,
  resolveSearchQueryTypeFromParams,
  type SearchRouteQueryType,
  updateSearchRouteParams,
} from "@/lib/search-route-state";
import { useAppStore } from "@/lib/store";
import BiliHeaderUserCard from "./BiliHeaderUserCard";
import { type BiliHeaderCounterState, buildBiliHeaderSummary } from "./bili-header-data";
import {
  BiliHeaderAvatarTrigger,
  BiliHeaderCta,
  BiliHeaderIconActionBar,
  type BiliHeaderIconAction,
  BiliHeaderNavLink,
} from "./bili-header-ui";

type HeaderNavItem = {
  key: "home" | "announcements" | "adjustments" | "radar" | "watchlist" | "admin";
  href: string;
  label: string;
};

export default function Header() {
  return (
    <Suspense fallback={<HeaderFrame currentSearchTab={null} searchParamValue="" searchParamKey="" />}>
      <HeaderSearchAware />
    </Suspense>
  );
}

function HeaderSearchAware() {
  const searchParams = useSearchParams();
  const { portalAuth } = useAppStore();
  return (
    <HeaderFrame
      currentSearchTab={resolveSearchQueryTypeFromParams(searchParams, portalAuth ? "adjustments" : "announcements")}
      searchParamValue={readSearchKeywordsFromParams(searchParams)}
      searchParamKey={searchParams.toString()}
    />
  );
}

function HeaderFrame({
  currentSearchTab,
  searchParamValue,
  searchParamKey,
}: {
  currentSearchTab: SearchRouteQueryType | null;
  searchParamValue: string;
  searchParamKey: string;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const mobileUserCardRef = useRef<HTMLDivElement | null>(null);
  const desktopUserCardRef = useRef<HTMLDivElement | null>(null);
  const [searchValue, setSearchValue] = useState("");
  const [isUserCardOpen, setIsUserCardOpen] = useState(false);
  const { setWatchlistOpen, portalAuth, clearPortalAuth, showToast } = useAppStore();
  const canManageScopeTargets = Boolean(portalAuth?.isPremium || portalAuth?.isAdmin);
  const subscriptionsQuery = useSubscriptionsQuery(Boolean(portalAuth));
  const monitorTargetsQuery = useMonitorTargetsQuery(Boolean(portalAuth && canManageScopeTargets));
  const noticesQuery = useWatchlistNoticesQuery(Boolean(portalAuth));

  const subscriptions = subscriptionsQuery.data?.items || [];
  const monitorTargets = monitorTargetsQuery.data?.items || [];
  const pendingNotices = noticesQuery.data || [];
  const subscriptionsState = resolveCounterState({
    enabled: Boolean(portalAuth),
    isError: subscriptionsQuery.isError,
    isLoading: subscriptionsQuery.isLoading || subscriptionsQuery.isPending,
    hasData: Boolean(subscriptionsQuery.data),
  });
  const monitorTargetsState = resolveCounterState({
    enabled: canManageScopeTargets,
    disabledState: "locked",
    isError: monitorTargetsQuery.isError,
    isLoading: monitorTargetsQuery.isLoading || monitorTargetsQuery.isPending,
    hasData: Boolean(monitorTargetsQuery.data),
  });
  const noticesState = resolveCounterState({
    enabled: Boolean(portalAuth),
    isError: noticesQuery.isError,
    isLoading: noticesQuery.isLoading || noticesQuery.isPending,
    hasData: Boolean(noticesQuery.data),
  });
  const userSummary = portalAuth
    ? buildBiliHeaderSummary({
        portalAuth,
        subscriptions: {
          items: subscriptions,
          state: subscriptionsState,
        },
        monitorTargets: {
          items: monitorTargets,
          state: monitorTargetsState,
        },
        pendingNotices: {
          items: pendingNotices,
          state: noticesState,
        },
      })
    : null;
  const watchlistBadgeCount =
    subscriptionsState === "ready" && (!canManageScopeTargets || monitorTargetsState === "ready")
      ? subscriptions.length + (canManageScopeTargets ? monitorTargets.length : 0)
      : undefined;
  const noticeBadgeCount = noticesState === "ready" ? pendingNotices.length : undefined;

  useEffect(() => {
    setSearchValue(searchParamValue);
  }, [searchParamValue]);

  useEffect(() => {
    setIsUserCardOpen(false);
  }, [pathname, searchParamKey]);

  useEffect(() => {
    if (!isUserCardOpen) {
      return;
    }

    function handlePointerDown(event: MouseEvent) {
      const target = event.target as Node;
      const clickedInsideMobile = mobileUserCardRef.current?.contains(target);
      const clickedInsideDesktop = desktopUserCardRef.current?.contains(target);
      if (!clickedInsideMobile && !clickedInsideDesktop) {
        setIsUserCardOpen(false);
      }
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsUserCardOpen(false);
      }
    }

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [isUserCardOpen]);

  async function handleLogout() {
    try {
      await logoutUser();
      clearPortalAuth();
      setIsUserCardOpen(false);
      showToast("已退出登录", "当前账号会话已经结束。", "info");
      router.push("/login");
    } catch (error) {
      showToast("退出失败", error instanceof ApiError ? error.message : "请稍后重试", "urgent");
    }
  }

  function handleThemeClick() {
    showToast("主题切换准备中", "下一轮会把亮色与夜间主题切换接到这里。", "info");
  }

  function handleOpenWatchlist() {
    if (!portalAuth) {
      showToast("请先登录", "关注、雷达和提醒都需要登录后再管理。", "info");
      router.push("/login");
      return;
    }
    setWatchlistOpen(true);
  }

  function handleSearchSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const params =
      pathname === "/search"
        ? updateSearchRouteParams(searchParamKey, {
            queryType: currentSearchTab || "announcements",
            keywords: searchValue,
          })
        : updateSearchRouteParams("", {
            queryType: "announcements",
            keywords: searchValue,
          });
    router.push(`/search?${params.toString()}`);
  }

  const navItems: HeaderNavItem[] = [
    { key: "home", href: "/", label: "首页" },
    { key: "announcements", href: "/search?tab=announcements", label: "公告" },
    { key: "adjustments", href: "/search?tab=adjustments", label: "调剂" },
    { key: "radar", href: "/radar", label: "胜率" },
    ...(portalAuth ? [{ key: "watchlist", href: "/watchlist", label: "关注" } satisfies HeaderNavItem] : []),
    ...(portalAuth?.isAdmin ? [{ key: "admin", href: "/admin", label: "管理台" } satisfies HeaderNavItem] : []),
  ];

  const iconActions: BiliHeaderIconAction[] = [
    {
      href: "/query",
      label: "功能导航",
      icon: Compass,
    },
    {
      label: "关注抽屉",
      icon: Star,
      onClick: handleOpenWatchlist,
      badgeCount: portalAuth ? watchlistBadgeCount : undefined,
    },
    {
      href: "/account?tab=activity",
      label: "提醒中心",
      icon: Bell,
      badgeCount: noticeBadgeCount,
      badgeTone: "danger",
    },
  ];

  return (
    <>
      <header className="fixed inset-x-0 top-0 z-50 px-3 pt-3 md:px-5">
        <div className="mx-auto max-w-[1380px] rounded-[30px] border border-white/80 bg-[linear-gradient(135deg,rgba(255,255,255,0.82),rgba(248,250,252,0.74))] shadow-[0_22px_70px_rgba(15,23,42,0.14)] backdrop-blur-2xl">
          <div className="flex flex-col gap-3 px-3 py-3 md:px-4 lg:flex-row lg:items-center lg:gap-5">
            <div className="flex items-center justify-between gap-3 lg:min-w-[220px]">
              <Link href="/" className="group flex min-w-0 items-center gap-3">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[16px] bg-[linear-gradient(135deg,#fb7185,#60a5fa)] text-lg font-black tracking-tight text-white shadow-[0_14px_30px_rgba(96,165,250,0.28)] transition-transform group-hover:scale-[1.04]">
                  GW
                </div>
                <div className="min-w-0">
                  <div className="truncate text-[15px] font-black tracking-[0.24em] text-slate-900">格物简录</div>
                  <div className="truncate text-[11px] font-medium tracking-[0.22em] text-slate-500">
                    GEWU PORTAL
                  </div>
                </div>
              </Link>

              <div className="flex items-center gap-2 lg:hidden">
                <BiliHeaderIconActionBar actions={iconActions} />
                {portalAuth ? (
                  <div ref={mobileUserCardRef} className="relative">
                    <BiliHeaderAvatarTrigger
                      displayName={userSummary?.displayName || portalAuth.username}
                      tier={userSummary?.tier || "basic"}
                      onClick={() => setIsUserCardOpen((current) => !current)}
                    />
                    <AnimatePresence>
                      {isUserCardOpen && userSummary ? (
                        <div className="absolute right-0 top-[calc(100%+0.8rem)] z-20">
                          <BiliHeaderUserCard
                            summary={userSummary}
                            username={portalAuth.username}
                            onClose={() => setIsUserCardOpen(false)}
                            onLogout={handleLogout}
                            onThemeClick={handleThemeClick}
                          />
                        </div>
                      ) : null}
                    </AnimatePresence>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <BiliHeaderCta href="/login" primary>
                      接入账号
                    </BiliHeaderCta>
                    <BiliHeaderCta href="/register">新建账户</BiliHeaderCta>
                  </div>
                )}
              </div>
            </div>

            <nav className="hidden items-center gap-1 lg:flex">
              {navItems.map((item) => (
                <BiliHeaderNavLink
                  key={item.key}
                  href={item.href}
                  label={item.label}
                  active={isNavItemActive(item.key, pathname, currentSearchTab)}
                />
              ))}
            </nav>

            <form
              onSubmit={handleSearchSubmit}
              className="flex min-w-0 flex-1 items-center gap-3 rounded-[22px] border border-slate-200 bg-white/90 px-4 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.8)]"
            >
              <Search size={18} className="shrink-0 text-slate-400" />
              <input
                value={searchValue}
                onChange={(event) => setSearchValue(event.target.value)}
                placeholder="搜学校、专业或公告关键词"
                className="min-w-0 flex-1 bg-transparent text-sm text-slate-900 outline-none placeholder:text-slate-400"
              />
              <button
                type="submit"
                className="inline-flex shrink-0 items-center gap-2 rounded-full bg-[linear-gradient(90deg,#60a5fa,#f472b6)] px-4 py-2 text-sm font-semibold text-white shadow-[0_14px_26px_rgba(96,165,250,0.26)] transition-transform hover:scale-[1.02]"
              >
                <Search size={15} />
                搜索
              </button>
            </form>

            <div className="hidden items-center gap-3 lg:flex">
              <BiliHeaderIconActionBar actions={iconActions} />

              {portalAuth ? (
                <div ref={desktopUserCardRef} className="relative">
                  <button
                    type="button"
                    onClick={() => setIsUserCardOpen((current) => !current)}
                    className={`flex items-center gap-3 rounded-full border px-2.5 py-2 pr-4 transition-colors ${
                      isUserCardOpen
                        ? "border-sky-200 bg-sky-50 text-slate-900"
                        : "border-white/80 bg-white/90 text-slate-900 hover:border-sky-200 hover:bg-sky-50"
                    }`}
                  >
                    <BiliHeaderAvatarTrigger
                      displayName={userSummary?.displayName || portalAuth.username}
                      tier={userSummary?.tier || "basic"}
                    />
                    <span className="min-w-0 text-left">
                      <span className="block max-w-[120px] truncate text-sm font-semibold text-slate-900">
                        {userSummary?.displayName || portalAuth.username}
                      </span>
                      <span className="block text-xs text-slate-500">
                        {userSummary?.levelLabel || "普通账户"}
                      </span>
                    </span>
                  </button>

                  <AnimatePresence>
                    {isUserCardOpen && userSummary ? (
                      <div className="absolute right-0 top-[calc(100%+0.85rem)] z-20">
                        <BiliHeaderUserCard
                          summary={userSummary}
                          username={portalAuth.username}
                          onClose={() => setIsUserCardOpen(false)}
                          onLogout={handleLogout}
                          onThemeClick={handleThemeClick}
                        />
                      </div>
                    ) : null}
                  </AnimatePresence>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <BiliHeaderCta href="/login" primary>
                    登录主账号
                  </BiliHeaderCta>
                  <BiliHeaderCta href="/register">创建新账户</BiliHeaderCta>
                </div>
              )}
            </div>
          </div>

          <div className="border-t border-white/70 px-3 pb-3 pt-2 lg:hidden">
            <div className="flex gap-2 overflow-x-auto pb-1">
              {navItems.map((item) => (
                <BiliHeaderNavLink
                  key={item.key}
                  href={item.href}
                  label={item.label}
                  active={isNavItemActive(item.key, pathname, currentSearchTab)}
                  compact
                />
              ))}
            </div>
          </div>
        </div>
      </header>

      <button
        type="button"
        onClick={handleOpenWatchlist}
        data-watchlist-fab="true"
        className="group fixed bottom-10 right-6 z-[80] flex h-14 w-14 items-center justify-center rounded-full bg-[linear-gradient(135deg,#60a5fa,#f472b6)] shadow-[0_18px_36px_rgba(96,165,250,0.34)] transition-transform hover:scale-110"
      >
        <Bell className="text-white group-hover:animate-pulse" size={24} />
        {pendingNotices.length > 0 ? (
          <span className="absolute right-0 top-0 flex h-5 min-w-[20px] items-center justify-center rounded-full border-2 border-white bg-rose-500 px-1 text-[10px] font-bold text-white">
            {Math.min(pendingNotices.length, 99)}
          </span>
        ) : (
          <span className="absolute right-1 top-1 h-3 w-3 rounded-full border-2 border-white bg-sky-400" />
        )}
      </button>
    </>
  );
}

function isNavItemActive(
  key: HeaderNavItem["key"],
  pathname: string,
  currentSearchTab: string | null,
) {
  if (key === "home") {
    return pathname === "/";
  }
  if (key === "announcements") {
    return pathname === "/search" && (currentSearchTab === "announcements" || !currentSearchTab);
  }
  if (key === "adjustments") {
    return pathname === "/search" && currentSearchTab === "adjustments";
  }
  if (key === "radar") {
    return pathname === "/radar";
  }
  if (key === "watchlist") {
    return pathname === "/watchlist";
  }
  return pathname === "/admin";
}

function resolveCounterState(args: {
  enabled: boolean;
  disabledState?: BiliHeaderCounterState;
  isError: boolean;
  isLoading: boolean;
  hasData: boolean;
}): BiliHeaderCounterState {
  if (!args.enabled) {
    return args.disabledState ?? "unavailable";
  }
  if (args.isError) {
    return "unavailable";
  }
  if (args.hasData) {
    return "ready";
  }
  if (args.isLoading) {
    return "loading";
  }
  return "loading";
}
