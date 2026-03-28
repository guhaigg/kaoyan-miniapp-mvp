"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { FormEvent, useEffect, useRef, useState } from "react";
import { Search } from "lucide-react";
import { ApiError, logoutUser } from "@/lib/api";
import { useMonitorTargetsQuery } from "@/hooks/useMonitoringTargets";
import { useWatchlistNoticesQuery } from "@/hooks/useNotifications";
import { useSubscriptionsQuery } from "@/hooks/useSubscriptions";
import { useAppStore } from "@/lib/store";
import BiliHeaderUserCard from "./BiliHeaderUserCard";
import { buildHeaderSummary } from "./bili-header-data";
import {
  buildSearchDestination,
  getPrimaryNavItems,
  resolvePrimaryRouteKey,
  shouldShowGlobalSearch,
  type SearchMode,
} from "./site-navigation";

export default function Header() {
  const router = useRouter();
  const pathname = usePathname();
  const { portalAuth, clearPortalAuth, showToast, setAuthOpen } = useAppStore();

  const canManageScopeTargets = Boolean(portalAuth?.isPremium || portalAuth?.isAdmin);
  const subscriptionsQuery = useSubscriptionsQuery(Boolean(portalAuth));
  const monitorTargetsQuery = useMonitorTargetsQuery(Boolean(portalAuth && canManageScopeTargets));
  const noticesQuery = useWatchlistNoticesQuery(Boolean(portalAuth));

  const [searchInput, setSearchInput] = useState("");
  const [searchMode, setSearchMode] = useState<SearchMode>("announcements");
  const [userCardOpen, setUserCardOpen] = useState(false);
  const cardAnchorRef = useRef<HTMLDivElement>(null);

  const showGlobalSearch = shouldShowGlobalSearch(pathname);
  const activeRoute = resolvePrimaryRouteKey(pathname);
  const navItems = getPrimaryNavItems(Boolean(portalAuth?.isAdmin));

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (!cardAnchorRef.current?.contains(event.target as Node)) {
        setUserCardOpen(false);
      }
    }

    function handleEsc(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setUserCardOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleEsc);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEsc);
    };
  }, []);

  useEffect(() => {
    setUserCardOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (pathname.startsWith("/adjustments") || pathname.startsWith("/radar")) {
      setSearchMode("adjustments");
      return;
    }
    setSearchMode("announcements");
  }, [pathname]);

  async function handleLogout() {
    try {
      await logoutUser();
      clearPortalAuth();
      setUserCardOpen(false);
      showToast("已退出登录", "当前会话已结束", "info");
      setAuthOpen(false);
      router.push("/");
    } catch (error) {
      showToast("退出失败", error instanceof ApiError ? error.message : "请稍后重试", "urgent");
    }
  }

  function openAuth(mode: "login" | "register") {
    setAuthOpen(true, mode);
  }

  function handleOpenWatchlist() {
    if (!portalAuth) {
      showToast("请先登录", "登录后查看收藏院校的最新公告提醒。", "info");
      openAuth("login");
      return;
    }
    router.push("/watchlist");
  }

  function handleSearchSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const keyword = searchInput.trim();

    if (searchMode === "adjustments" && !portalAuth) {
      showToast("请先登录", "调剂检索需要登录后使用。", "info");
      openAuth("login");
      return;
    }

    router.push(buildSearchDestination(searchMode, keyword));
  }

  const summary = portalAuth
    ? buildHeaderSummary({
        username: portalAuth.username,
        nickname: portalAuth.nickname,
        isPremium: portalAuth.isPremium,
        followingCount: subscriptionsQuery.data?.items.length || 0,
        radarCount: canManageScopeTargets ? monitorTargetsQuery.data?.items.length || 0 : 0,
        activityCount: noticesQuery.data?.length || 0,
      })
    : null;

  const membershipLabel = portalAuth?.isAdmin ? "管理员" : portalAuth?.isPremium ? "高级会员" : "普通用户";

  return (
    <header className="fixed inset-x-0 top-0 z-50">
      <div className="border-b border-slate-200/50 bg-white/80 px-6 py-3 backdrop-blur-2xl">
        <div className="relative mx-auto grid max-w-[1680px] grid-cols-[auto_1fr_auto] items-center gap-6 xl:grid-cols-[minmax(max-content,520px)_minmax(0,1fr)_minmax(max-content,420px)]">
          <div className="flex min-w-0 shrink-0 items-center gap-6">
            <Link href="/" className="group flex items-center gap-2">
              <span className="inline-flex h-7 w-7 items-center justify-center rounded bg-slate-900 text-[11px] font-black text-white transition-transform group-hover:scale-105">
                GW
              </span>
              <span className="text-[15px] font-black tracking-[-0.02em] text-slate-900">GewuJL.</span>
            </Link>

            <nav className="hidden items-center gap-6 text-[14px] font-semibold tracking-[0.02em] text-slate-500 xl:flex">
              {navItems.map((item) => {
                const active = activeRoute === item.key;
                return (
                  <Link
                    key={item.key}
                    href={item.href}
                    className={`inline-flex items-center gap-1.5 transition-colors ${
                      active ? "text-slate-900" : "hover:text-slate-900"
                    }`}
                  >
                    {item.label}
                    {item.badge ? (
                      <span className="rounded-md bg-orange-100 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-[0.14em] text-orange-600">
                        {item.badge}
                      </span>
                    ) : null}
                  </Link>
                );
              })}
            </nav>
          </div>

          {showGlobalSearch ? (
            <form
              onSubmit={handleSearchSubmit}
              className="hidden w-full items-center justify-self-center md:flex md:max-w-[440px]"
            >
              <div className="group flex w-full items-center rounded-xl border border-slate-200/60 bg-slate-100/50 p-1 transition-all hover:bg-slate-100 focus-within:border-cyan-300 focus-within:bg-white focus-within:shadow-[0_0_0_2px_rgba(6,182,212,0.1)]">
                <div className="flex shrink-0 items-center rounded-lg border border-slate-200/50 bg-white/80 p-0.5 shadow-sm">
                  {(
                    [
                      { value: "announcements", label: "公告" },
                      { value: "adjustments", label: "调剂" },
                    ] as const
                  ).map((item) => (
                    <button
                      key={item.value}
                      type="button"
                      onClick={() => setSearchMode(item.value)}
                      className={`rounded-md px-3 py-1 text-xs font-bold transition-all ${
                        searchMode === item.value
                          ? "bg-slate-900 text-white shadow-sm"
                          : "text-slate-500 hover:text-slate-800"
                      }`}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
                <div className="flex min-w-0 flex-1 items-center pl-3 pr-2">
                  <Search
                    size={14}
                    className="mr-2 shrink-0 text-slate-400 transition-colors group-focus-within:text-cyan-500"
                  />
                  <input
                    value={searchInput}
                    onChange={(event) => setSearchInput(event.target.value)}
                    placeholder={
                      searchMode === "announcements"
                        ? "输入院校或专业，在公告库检索..."
                        : "输入院校或专业，在调剂库检索..."
                    }
                    className="w-full bg-transparent text-sm font-medium text-slate-800 outline-none placeholder:text-slate-400"
                  />
                </div>
              </div>
            </form>
          ) : (
            <div className="hidden md:block" />
          )}

          <div className="ml-auto flex min-w-0 shrink-0 items-center justify-self-end gap-4">
            <button
              type="button"
              onClick={handleOpenWatchlist}
              className="hidden items-center gap-1.5 rounded-md border border-green-100 bg-green-50 px-2.5 py-1 sm:inline-flex"
              title="See Live"
            >
              <span className="h-1.5 w-1.5 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.55)]" />
              <span className="text-[10px] font-mono uppercase text-green-700">SEE LIVE</span>
            </button>
            <div className="mx-1 hidden h-4 w-px bg-slate-200 sm:block" />

            {portalAuth && summary ? (
              <div className="relative" ref={cardAnchorRef}>
                <button
                  type="button"
                  onClick={() => setUserCardOpen((prev) => !prev)}
                  className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-2.5 py-1.5 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-50"
                >
                  <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-[linear-gradient(135deg,#dbeafe,#d1fae5)] text-sm font-black text-slate-800">
                    {summary.displayName.slice(0, 1).toUpperCase()}
                  </span>
                  <span className="hidden max-w-[108px] truncate md:inline">{summary.displayName}</span>
                </button>

                {userCardOpen ? (
                  <BiliHeaderUserCard
                    summary={summary}
                    membershipLabel={membershipLabel}
                    isAdmin={portalAuth.isAdmin}
                    onLogout={handleLogout}
                    onNavigate={() => setUserCardOpen(false)}
                  />
                ) : null}
              </div>
            ) : (
              <div className="hidden items-center gap-3 md:flex">
                <button
                  type="button"
                  onClick={() => openAuth("login")}
                  className="text-sm font-bold tracking-[0.01em] text-slate-700 transition-colors hover:text-slate-900"
                >
                  登录
                </button>
                <button
                  type="button"
                  onClick={() => openAuth("register")}
                  className="rounded-xl bg-slate-900 px-4 py-2 text-sm font-bold tracking-[0.01em] text-white shadow-sm transition-all hover:bg-slate-800 active:scale-95"
                >
                  免费接入
                </button>
              </div>
            )}

            <button
              type="button"
              onClick={handleOpenWatchlist}
              className="inline-flex h-9 w-9 items-center justify-center rounded-full text-slate-600 transition-colors hover:bg-slate-100 md:hidden"
              title="See Live"
            >
              <span className="h-2.5 w-2.5 rounded-full bg-green-500" />
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}
