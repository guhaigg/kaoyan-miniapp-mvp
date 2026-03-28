"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { FormEvent, useEffect, useRef, useState } from "react";
import { Bell, Search, Star } from "lucide-react";
import { ApiError, logoutUser } from "@/lib/api";
import { useMonitorTargetsQuery } from "@/hooks/useMonitoringTargets";
import { useWatchlistNoticesQuery } from "@/hooks/useNotifications";
import { useSubscriptionsQuery } from "@/hooks/useSubscriptions";
import { useAppStore } from "@/lib/store";
import BiliHeaderUserCard from "./BiliHeaderUserCard";
import { buildHeaderSummary } from "./bili-header-data";

const NAV_ITEMS = [
  { href: "/", label: "情报流" },
  { href: "/search", label: "检索" },
  { href: "/radar", label: "监控台" },
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
  const [searchMode, setSearchMode] = useState<SearchMode>("announcements");
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
  return (
    <>
      <header className="fixed inset-x-0 top-0 z-50">
        <div className="border-b border-slate-200/50 bg-white/80 px-6 py-3 backdrop-blur-2xl">
          <div className="relative mx-auto flex max-w-[1400px] items-center justify-between gap-6">
            <div className="flex shrink-0 items-center gap-6">
              <Link href="/" className="group flex items-center gap-2">
                <span className="inline-flex h-7 w-7 items-center justify-center rounded bg-slate-900 text-[11px] font-black text-white transition-transform group-hover:scale-105">
                  GW
                </span>
                <span className="text-[15px] font-black tracking-[-0.02em] text-slate-900">GewuJL.</span>
              </Link>

              <nav className="hidden items-center gap-7 text-[14px] font-semibold tracking-[0.02em] text-slate-500 lg:flex">
                {NAV_ITEMS.map((item) => {
                  const active = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={`transition-colors ${active ? "text-slate-900" : "hover:text-slate-900"}`}
                    >
                      {item.label}
                    </Link>
                  );
                })}
              </nav>
            </div>

            <form
              onSubmit={handleSearchSubmit}
              className="hidden w-full max-w-[420px] items-center md:flex lg:absolute lg:left-1/2 lg:max-w-[480px] lg:-translate-x-1/2"
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
                        searchMode === item.value ? "bg-slate-900 text-white shadow-sm" : "text-slate-500 hover:text-slate-800"
                      }`}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
                <div className="flex min-w-0 flex-1 items-center pl-3 pr-2">
                  <Search size={14} className="mr-2 shrink-0 text-slate-400 transition-colors group-focus-within:text-cyan-500" />
                  <input
                    value={searchInput}
                    onChange={(event) => setSearchInput(event.target.value)}
                    placeholder="输入目标院校或专业..."
                    className="w-full bg-transparent text-sm font-medium text-slate-800 outline-none placeholder:text-slate-400"
                  />
                </div>
              </div>
            </form>

            <div className="ml-auto flex shrink-0 items-center gap-4">
              <button
                type="button"
                onClick={handleOpenWatchlist}
                className="hidden rounded-full p-1 text-slate-400 transition-colors hover:text-slate-900 sm:block"
                title="关注"
              >
                <Star size={18} />
              </button>
              <button
                type="button"
                className="relative hidden rounded-full p-1 text-slate-400 transition-colors hover:text-slate-900 sm:block"
                title="通知"
              >
                <Bell size={18} />
                <span className="absolute right-0 top-0 h-2 w-2 rounded-full border-2 border-white bg-red-500" />
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
                title="关注"
              >
                <Bell size={18} />
              </button>
            </div>
          </div>
        </div>
      </header>

      <button
        type="button"
        onClick={handleOpenWatchlist}
        data-watchlist-fab="true"
        className="group fixed bottom-8 right-6 z-[80] flex h-12 w-12 items-center justify-center rounded-full bg-slate-900 shadow-[0_16px_36px_rgba(15,23,42,0.28)] transition-transform hover:scale-105 md:hidden"
      >
        <Bell className="text-white" size={18} />
      </button>
    </>
  );
}
