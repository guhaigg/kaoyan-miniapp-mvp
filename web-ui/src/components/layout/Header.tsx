"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { Activity, BellRing, LogOut, Menu, Search, Target, Terminal, UserCircle } from "lucide-react";
import { ApiError, logoutUser } from "@/lib/api";
import { useAppStore } from "@/lib/store";

export default function Header() {
  const router = useRouter();
  const { setWatchlistOpen, portalAuth, clearPortalAuth, showToast } = useAppStore();
  const pathname = usePathname();
  const showAdminNav = Boolean(portalAuth?.isAdmin);
  const showUpgradeCta = Boolean(portalAuth && !portalAuth.isAdmin && !portalAuth.isPremium);

  async function handleLogout() {
    try {
      await logoutUser();
      clearPortalAuth();
      showToast("已退出登录", "当前会话已结束", "info");
      router.push("/login");
    } catch (error) {
      showToast("退出失败", error instanceof ApiError ? error.message : "请稍后重试", "urgent");
    }
  }

  function handleOpenWatchlist() {
    if (!portalAuth) {
      showToast("请先登录", "收藏、关注和调剂等深度功能需要登录后使用", "info");
      router.push("/login");
      return;
    }
    setWatchlistOpen(true);
  }

  const navItems = [
    { href: "/", label: "全网流", icon: Activity },
    { href: "/search", label: "数据检索", icon: Search },
    { href: "/radar", label: "胜率测算", icon: Target },
    ...(showAdminNav ? [{ href: "/admin", label: "监控台", icon: Terminal }] : []),
  ];

  return (
    <>
      <header className="glass-panel fixed top-0 z-50 w-full border-x-0 border-t-0 px-6 py-4 transition-all duration-300">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <Link href="/" className="group flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white drop-shadow-[0_0_10px_rgba(255,255,255,0.2)] transition-transform group-hover:scale-105">
              <span className="text-2xl font-black tracking-tighter text-[#2c3e50]">GW</span>
            </div>
            <div className="flex flex-col">
              <span className="leading-tight text-lg font-bold tracking-widest text-white">
                格物简录
              </span>
              <span className="font-mono text-[10px] tracking-widest text-cyan-400">
                GEWUJL.CLOUD
              </span>
            </div>
          </Link>

          <nav className="hidden items-center gap-10 text-sm font-medium md:flex">
            {navItems.map((item) => {
              const active = pathname === item.href;
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`relative flex items-center gap-2 transition-colors ${
                    active ? "text-white" : "text-slate-400 hover:text-white"
                  }`}
                >
                  <Icon size={16} /> {item.label}
                  {active ? (
                    <motion.div
                      layoutId="nav-indicator"
                      className="absolute -bottom-[22px] left-0 right-0 h-[2px] bg-cyan-400 shadow-[0_0_8px_#06b6d4]"
                    />
                  ) : null}
                </Link>
              );
            })}
          </nav>

          <div className="flex items-center gap-3">
            {showUpgradeCta ? (
              <Link
                href="/account/billing"
                className="hidden rounded-full border border-amber-400/30 bg-amber-500/10 px-4 py-2 text-xs font-semibold text-amber-100 transition-colors hover:bg-amber-500/20 md:flex"
              >
                开通高级会员
              </Link>
            ) : null}
            {portalAuth ? (
              <div className="hidden items-center gap-3 md:flex">
                <Link
                  href="/account"
                  className="group relative overflow-hidden rounded-full border border-white/20 bg-white/5 px-6 py-2 transition-all hover:border-cyan-400"
                >
                  <div className="absolute inset-0 translate-y-full bg-cyan-500/20 transition-transform duration-300 ease-out group-hover:translate-y-0" />
                  <span className="relative flex items-center gap-2 text-sm font-bold text-white drop-shadow-md">
                    <UserCircle size={18} />
                    {`账户：${portalAuth.nickname || portalAuth.username}`}
                  </span>
                </Link>
                <button
                  type="button"
                  onClick={handleLogout}
                  className="rounded-full border border-red-400/25 bg-red-500/10 px-4 py-2 text-xs font-semibold text-red-50 transition-colors hover:bg-red-500/20"
                >
                  <span className="flex items-center gap-2">
                    <LogOut size={14} />
                    退出
                  </span>
                </button>
              </div>
            ) : (
              <div className="hidden items-center gap-3 md:flex">
                <Link
                  href="/login"
                  className="group relative overflow-hidden rounded-full border border-white/20 bg-white/5 px-6 py-2 transition-all hover:border-cyan-400"
                >
                  <div className="absolute inset-0 translate-y-full bg-cyan-500/20 transition-transform duration-300 ease-out group-hover:translate-y-0" />
                  <span className="relative flex items-center gap-2 text-sm font-bold text-white drop-shadow-md">
                    <UserCircle size={18} />
                    登录
                  </span>
                </Link>
                <Link
                  href="/register"
                  className="rounded-full border border-cyan-400/30 bg-cyan-500/10 px-4 py-2 text-xs font-semibold text-cyan-100 transition-colors hover:bg-cyan-500/20"
                >
                  注册
                </Link>
              </div>
            )}
            <button
              onClick={handleOpenWatchlist}
              className="rounded-lg bg-white/10 p-2 text-white transition-colors hover:bg-white/20 md:hidden"
            >
              <Menu size={20} />
            </button>
          </div>
        </div>
      </header>

      <button
        onClick={handleOpenWatchlist}
        data-watchlist-fab="true"
        className="group fixed bottom-10 right-6 z-[80] flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br from-cyan-600 to-blue-700 shadow-[0_0_20px_rgba(6,182,212,0.4)] transition-transform hover:scale-110"
      >
        <BellRing className="text-white group-hover:animate-pulse" size={24} />
        <span className="absolute right-0 top-0 h-3 w-3 rounded-full border-2 border-[#050b14] bg-red-500"></span>
      </button>
    </>
  );
}
