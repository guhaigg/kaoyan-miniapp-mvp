"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { FormEvent, useEffect, useRef, useState } from "react";
import { Bell, LogIn, Menu, Search, Sparkles, Star } from "lucide-react";
import { ApiError, logoutUser } from "@/lib/api";
import { useMonitorTargetsQuery } from "@/hooks/useMonitoringTargets";
import { useWatchlistNoticesQuery } from "@/hooks/useNotifications";
import { useSubscriptionsQuery } from "@/hooks/useSubscriptions";
import { useAppStore } from "@/lib/store";
import BiliHeaderUserCard from "./BiliHeaderUserCard";
import { buildHeaderSummary } from "./bili-header-data";

const NAV_ITEMS = [
  { href: "/", label: "情报总览" },
  { href: "/search", label: "公告检索" },
  { href: "/radar", label: "雷达监控" },
];

type SearchMode = "announcements" | "adjustments";

export default function Header() {
  const router = useRouter();
  const pathname = usePathname();
  const {
    setWatchlistOpen,
    portalAuth,
    clearPortalAuth,
    showToast,
    setAuthOpen,
  } = useAppStore();

  const canManageScopeTargets = Boolean(portalAuth?.isPremium || portalAuth?.isAdmin);
  const subscriptionsQuery = useSubscriptionsQuery(Boolean(portalAuth));
  const monitorTargetsQuery = useMonitorTargetsQuery(Boolean(portalAuth && canManageScopeTargets));
  const noticesQuery = useWatchlistNoticesQuery(Boolean(portalAuth));

  const [searchInput, setSearchInput] = useState("");
  const [searchMode, setSearchMode] = useState<SearchMode>(portalAuth ? "adjustments" : "announcements");
  const [userCardOpen, setUserCardOpen] = useState(false);
  const cardAnchorRef = useRef<HTMLDivElement>(null);

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
      showToast("请先登录", "收藏、关注和调剂等深度功能需要登录后使用", "info");
      openAuth("login");
      return;
    }
    setWatchlistOpen(true);
  }

  function handleSearchSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const keyword = searchInput.trim();

    if (searchMode === "adjustments" && !portalAuth) {
      showToast("请先登录", "调剂检索需要登录后使用", "info");
      openAuth("login");
      return;
    }

    const params = new URLSearchParams();
    params.set("tab", searchMode);
    if (keyword) {
      params.set("keywords", keyword);
    }
    router.push(`/search?${params.toString()}`);
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
  const showUpgradeCta = Boolean(portalAuth && !portalAuth.isAdmin && !portalAuth.isPremium);

  return (
    <>
      <header className="fixed inset-x-0 top-0 z-50">
        <div className="mx-auto max-w-[1880px] px-3 py-2 md:px-6">
          <div className="relative flex h-16 items-center justify-between rounded-[28px] border border-black/5 bg-white/92 px-4 shadow-[0_18px_46px_rgba(15,23,42,0.08)] backdrop-blur-xl md:px-5">
            <div className="flex min-w-0 items-center gap-3">
              <Link href="/" className="flex shrink-0 items-center gap-3">
                <span className="inline-flex h-10 w-10 items-center justify-center rounded-2xl bg-[#111827] text-white shadow-[0_12px_28px_rgba(15,23,42,0.18)]">
                  <span className="text-sm font-black tracking-[0.14em]">GW</span>
                </span>
                <span className="text-[1.9rem] font-black tracking-[-0.06em] text-slate-900">GewuJL.</span>
              </Link>

              <nav className="hidden items-center gap-1 xl:flex">
                {NAV_ITEMS.map((item) => {
                  const active = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={`rounded-full px-4 py-2.5 text-[12px] font-semibold uppercase tracking-[0.22em] transition-all ${
                        active
                          ? "bg-slate-950 text-white shadow-[0_10px_22px_rgba(15,23,42,0.18)]"
                          : "text-slate-500 hover:bg-slate-100 hover:text-slate-900"
                      }`}
                    >
                      {item.label}
                    </Link>
                  );
                })}
              </nav>
            </div>

            <form
              onSubmit={handleSearchSubmit}
              className="absolute left-1/2 top-1/2 hidden w-full max-w-[460px] -translate-x-1/2 -translate-y-1/2 xl:block"
            >
              <div className="flex h-11 items-center rounded-full border border-black/5 bg-slate-100/88 p-1 pl-1.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.75)]">
                <div className="flex shrink-0 items-center gap-1">
                  {(
                    [
                      { value: "adjustments", label: "调剂" },
                      { value: "announcements", label: "公告" },
                    ] as const
                  ).map((item) => (
                    <button
                      key={item.value}
                      type="button"
                      onClick={() => setSearchMode(item.value)}
                      className={`rounded-full px-3 py-1.5 text-[11px] font-semibold tracking-[0.08em] transition-all ${
                        searchMode === item.value ? "bg-white text-slate-950 shadow-sm" : "text-slate-400"
                      }`}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
                <div className="ml-2 flex min-w-0 flex-1 items-center">
                  <Search size={15} className="shrink-0 text-slate-400" />
                  <input
                    value={searchInput}
                    onChange={(event) => setSearchInput(event.target.value)}
                    placeholder={searchMode === "adjustments" ? "快速过滤调剂情报…" : "快速搜索公告 / 学校 / 关键词"}
                    className="ml-2 w-full bg-transparent text-[13px] font-medium text-slate-700 outline-none placeholder:text-slate-400"
                  />
                </div>
              </div>
            </form>

            <div className="ml-auto flex items-center gap-2">
              {showUpgradeCta ? (
                <Link
                  href="/account?tab=account&panel=billing"
                  className="hidden rounded-full bg-[linear-gradient(90deg,#111827,#0f766e)] px-4 py-2.5 text-[11px] font-semibold uppercase tracking-[0.16em] text-white lg:inline-flex"
                >
                  开通高级会员
                </Link>
              ) : null}

              <button
                type="button"
                onClick={handleOpenWatchlist}
                className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-black/5 bg-white text-slate-600 transition-colors hover:bg-slate-50 hover:text-slate-900"
                title="关注"
              >
                <Star size={17} />
              </button>
              <Link
                href="/account?tab=activity"
                className="hidden h-10 w-10 items-center justify-center rounded-full border border-black/5 bg-white text-slate-600 transition-colors hover:bg-slate-50 hover:text-slate-900 md:inline-flex"
                title="动态"
              >
                <Bell size={17} />
              </Link>

              {portalAuth && summary ? (
                <div className="relative" ref={cardAnchorRef}>
                  <button
                    type="button"
                    onClick={() => setUserCardOpen((prev) => !prev)}
                    className="inline-flex items-center gap-2 rounded-full border border-black/5 bg-white px-2.5 py-1.5 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-50"
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
                      onLogout={handleLogout}
                      onNavigate={() => setUserCardOpen(false)}
                    />
                  ) : null}
                </div>
              ) : (
                <div className="hidden items-center gap-2 md:flex">
                  <button
                    type="button"
                    onClick={() => openAuth("login")}
                    className="inline-flex items-center gap-1 rounded-full border border-black/5 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-700 transition-colors hover:bg-slate-50"
                  >
                    <LogIn size={14} />
                    登录
                  </button>
                  <button
                    type="button"
                    onClick={() => openAuth("register")}
                    className="inline-flex items-center gap-1 rounded-full bg-slate-950 px-3.5 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-white"
                  >
                    <Sparkles size={14} />
                    注册
                  </button>
                </div>
              )}

              <button
                type="button"
                onClick={handleOpenWatchlist}
                className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-black/5 bg-white text-slate-600 transition-colors hover:bg-slate-50 lg:hidden"
                title="菜单"
              >
                <Menu size={18} />
              </button>
            </div>
          </div>
        </div>
      </header>

      <button
        type="button"
        onClick={handleOpenWatchlist}
        data-watchlist-fab="true"
        className="group fixed bottom-8 right-6 z-[80] flex h-12 w-12 items-center justify-center rounded-full bg-[linear-gradient(135deg,#111827,#0f766e)] shadow-[0_16px_36px_rgba(15,23,42,0.28)] transition-transform hover:scale-105 md:hidden"
      >
        <Bell className="text-white" size={18} />
      </button>
    </>
  );
}
