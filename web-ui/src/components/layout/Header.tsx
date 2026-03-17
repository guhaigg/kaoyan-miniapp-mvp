"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { Activity, BellRing, Menu, Search, Terminal, UserCircle } from "lucide-react";
import { useAppStore } from "@/lib/store";

export default function Header() {
  const { setAuthOpen, setWatchlistOpen, portalAuth } = useAppStore();
  const pathname = usePathname();

  const navItems = [
    { href: "/", label: "全网流", icon: Activity },
    { href: "/search", label: "数据检索", icon: Search },
    { href: "/admin", label: "监控台", icon: Terminal },
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
            <button
              onClick={() => setAuthOpen(true)}
              className="group relative hidden overflow-hidden rounded-full border border-white/20 bg-white/5 px-6 py-2 transition-all hover:border-cyan-400 md:flex"
            >
              <div className="absolute inset-0 translate-y-full bg-cyan-500/20 transition-transform duration-300 ease-out group-hover:translate-y-0" />
              <span className="relative flex items-center gap-2 text-sm font-bold text-white drop-shadow-md">
                <UserCircle size={18} />
                {portalAuth ? `账户：${portalAuth.nickname || portalAuth.username}` : "接入系统"}
              </span>
            </button>
            <button
              onClick={() => setWatchlistOpen(true)}
              className="rounded-lg bg-white/10 p-2 text-white transition-colors hover:bg-white/20 md:hidden"
            >
              <Menu size={20} />
            </button>
          </div>
        </div>
      </header>

      <button
        onClick={() => setWatchlistOpen(true)}
        className="group fixed bottom-10 right-6 z-[80] flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br from-cyan-600 to-blue-700 shadow-[0_0_20px_rgba(6,182,212,0.4)] transition-transform hover:scale-110"
      >
        <BellRing className="text-white group-hover:animate-pulse" size={24} />
        <span className="absolute right-0 top-0 h-3 w-3 rounded-full border-2 border-[#050b14] bg-red-500"></span>
      </button>
    </>
  );
}
