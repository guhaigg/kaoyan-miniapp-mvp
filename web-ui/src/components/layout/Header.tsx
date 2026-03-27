"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { FormEvent, useEffect, useRef, useState } from "react";
import { Bell, Compass, LogIn, Menu, Search, Sparkles, Star } from "lucide-react";
import { ApiError, logoutUser } from "@/lib/api";
import { useMonitorTargetsQuery } from "@/hooks/useMonitoringTargets";
import { useWatchlistNoticesQuery } from "@/hooks/useNotifications";
import { useSubscriptionsQuery } from "@/hooks/useSubscriptions";
import { useAppStore } from "@/lib/store";
import BiliHeaderUserCard from "./BiliHeaderUserCard";
import { buildHeaderSummary } from "./bili-header-data";

const NAV_ITEMS = [
  { href: "/", label: "首页" },
  { href: "/search", label: "公告" },
  { href: "/radar", label: "雷达" },
  { href: "/watchlist", label: "关注" },
];

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
    if (!keyword) {
      router.push("/search");
      return;
    }
    router.push(`/search?keywords=${encodeURIComponent(keyword)}`);
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
        <div className="mx-auto max-w-[1440px] px-3 py-2 md:px-6">
          <div className="bili-surface flex h-12 items-center gap-2 rounded-full px-3 text-[#18191c] md:h-14 md:gap-3 md:px-5">
            <Link href="/" className="shrink-0 text-xl font-black tracking-tight text-[#00aeec] md:text-2xl">
              GEWU
            </Link>

            <nav className="hidden items-center gap-1 lg:flex">
              {NAV_ITEMS.map((item) => {
                const active = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`rounded-full px-3 py-2 text-sm font-semibold transition-colors ${
                      active ? "bg-[#00aeec]/12 text-[#00a0df]" : "text-slate-600 hover:bg-slate-100"
                    }`}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </nav>

            <form onSubmit={handleSearchSubmit} className="mx-auto hidden min-w-0 flex-1 lg:block">
              <div className="flex h-10 items-center rounded-full border border-black/5 bg-white px-3">
                <Search size={16} className="text-slate-400" />
                <input
                  value={searchInput}
                  onChange={(event) => setSearchInput(event.target.value)}
                  placeholder="搜索公告 / 学校 / 关键词"
                  className="ml-2 w-full bg-transparent text-sm text-slate-700 outline-none placeholder:text-slate-400"
                />
              </div>
            </form>

            <div className="ml-auto flex items-center gap-1 md:gap-2">
              {showUpgradeCta ? (
                <Link
                  href="/account?tab=account&panel=billing"
                  className="hidden rounded-full bg-[linear-gradient(90deg,#fb7299,#00aeec)] px-3 py-2 text-xs font-semibold text-white md:inline-flex"
                >
                  开通高级会员
                </Link>
              ) : null}

              <button
                type="button"
                onClick={handleOpenWatchlist}
                className="inline-flex h-9 w-9 items-center justify-center rounded-full text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900"
                title="关注"
              >
                <Star size={18} />
              </button>
              <Link
                href="/radar"
                className="inline-flex h-9 w-9 items-center justify-center rounded-full text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900"
                title="雷达"
              >
                <Compass size={18} />
              </Link>
              <Link
                href="/account?tab=activity"
                className="hidden h-9 w-9 items-center justify-center rounded-full text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900 md:inline-flex"
                title="动态"
              >
                <Bell size={18} />
              </Link>

              {portalAuth && summary ? (
                <div className="relative" ref={cardAnchorRef}>
                  <button
                    type="button"
                    onClick={() => setUserCardOpen((prev) => !prev)}
                    className="inline-flex items-center gap-2 rounded-full border border-black/5 bg-white px-2.5 py-1.5 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-50"
                  >
                    <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-[linear-gradient(135deg,#ffd7e5,#d7f2ff)] text-sm font-black text-slate-700">
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
                    className="inline-flex items-center gap-1 rounded-full border border-black/5 bg-white px-3 py-2 text-xs font-semibold text-slate-700 transition-colors hover:bg-slate-50"
                  >
                    <LogIn size={14} />
                    登录
                  </button>
                  <button
                    type="button"
                    onClick={() => openAuth("register")}
                    className="inline-flex items-center gap-1 rounded-full bg-[linear-gradient(90deg,#fb7299,#00aeec)] px-3 py-2 text-xs font-semibold text-white"
                  >
                    <Sparkles size={14} />
                    注册
                  </button>
                </div>
              )}

              <button
                type="button"
                onClick={handleOpenWatchlist}
                className="inline-flex h-9 w-9 items-center justify-center rounded-full text-slate-600 transition-colors hover:bg-slate-100 lg:hidden"
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
        className="group fixed bottom-8 right-6 z-[80] flex h-12 w-12 items-center justify-center rounded-full bg-[linear-gradient(135deg,#fb7299,#00aeec)] shadow-[0_16px_36px_rgba(14,116,144,0.28)] transition-transform hover:scale-105 md:hidden"
      >
        <Bell className="text-white" size={18} />
      </button>
    </>
  );
}
