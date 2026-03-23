"use client";

import Link from "next/link";
import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Star, X } from "lucide-react";
import { ApiError, logoutUser } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import WatchlistWorkspace from "@/components/watchlist/WatchlistWorkspace";

export default function Modals() {
  const {
    isAuthOpen,
    setAuthOpen,
    isWatchlistOpen,
    setWatchlistOpen,
    portalAuth,
    clearPortalAuth,
  } = useAppStore();
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState("");
  const showUpgradePanel = Boolean(portalAuth && !portalAuth.isAdmin && !portalAuth.isPremium);

  async function handleLogout() {
    setSubmitting(true);
    setMessage("");
    try {
      await logoutUser();
      clearPortalAuth();
      setMessage("已退出登录");
    } catch (error) {
      if (error instanceof ApiError) {
        setMessage(`退出失败：${error.message}`);
      } else {
        setMessage("退出失败，请稍后重试");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <AnimatePresence>
        {isAuthOpen ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] flex items-center justify-center p-4"
          >
            <div
              className="absolute inset-0 bg-black/60 backdrop-blur-md"
              onClick={() => setAuthOpen(false)}
            />
            <motion.div
              initial={{ scale: 0.95, y: 20 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.95, y: 20 }}
              transition={{ type: "spring", bounce: 0.3 }}
              className="relative z-10 w-full max-w-md rounded-3xl border border-white/10 bg-slate-900/80 p-10 shadow-2xl backdrop-blur-2xl"
            >
              <button
                onClick={() => setAuthOpen(false)}
                className="absolute right-6 top-6 text-slate-400 transition-colors hover:text-white"
              >
                <X size={20} />
              </button>
              <div className="mb-8 flex justify-center">
                <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-white drop-shadow-[0_0_20px_rgba(255,255,255,0.2)]">
                  <span className="text-4xl font-black tracking-tighter text-[#2c3e50]">GW</span>
                </div>
              </div>
              <h3 className="mb-4 text-center text-2xl font-bold text-white">账号入口</h3>
              <p className="mb-6 text-center text-sm leading-7 text-slate-300">
                弹窗现在只保留轻入口。完整的登录、注册和退出流程都走稳定页面，不再把表单塞回这里。
              </p>

              {portalAuth ? (
                <div className="space-y-4">
                  <div className="rounded-xl border border-white/10 bg-black/30 p-4 text-sm text-slate-200">
                    当前账号：{portalAuth.nickname || portalAuth.username}
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="rounded-xl border border-white/10 bg-black/30 p-4">
                      <div className="text-xs uppercase tracking-[0.22em] text-slate-400">角色</div>
                      <div className="mt-2 text-lg font-semibold text-white">{portalAuth.role}</div>
                    </div>
                    <div className="rounded-xl border border-white/10 bg-black/30 p-4">
                      <div className="text-xs uppercase tracking-[0.22em] text-slate-400">状态</div>
                      <div className="mt-2 text-lg font-semibold text-white">{portalAuth.status}</div>
                    </div>
                  </div>
                  {showUpgradePanel ? (
                    <div className="rounded-2xl border border-amber-400/20 bg-[linear-gradient(135deg,rgba(120,53,15,0.35),rgba(20,24,36,0.92))] p-4">
                      <div className="text-xs uppercase tracking-[0.28em] text-amber-300">Membership</div>
                      <div className="mt-2 text-base font-bold text-white">会员开通已迁到账号中心。</div>
                      <div className="mt-2 text-xs leading-6 text-amber-50/85">
                        弹窗只保留快速入口，不再塞订单、绑定、通知和改密。
                      </div>
                      <Link
                        href="/account/billing"
                        onClick={() => setAuthOpen(false)}
                        className="mt-4 inline-flex rounded-xl bg-amber-500 px-4 py-3 text-sm font-semibold text-slate-950 transition-colors hover:bg-amber-400"
                      >
                        去账号中心开通会员
                      </Link>
                    </div>
                  ) : null}
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Link
                      href="/account"
                      onClick={() => setAuthOpen(false)}
                      className="rounded-xl border border-white/20 bg-white/10 px-4 py-3 text-center text-sm font-semibold text-white transition-colors hover:bg-white/20"
                    >
                      进入账号中心
                    </Link>
                    <Link
                      href="/search"
                      onClick={() => setAuthOpen(false)}
                      className="rounded-xl border border-cyan-400/30 bg-cyan-500/10 px-4 py-3 text-center text-sm font-semibold text-cyan-100 transition-colors hover:bg-cyan-500/20"
                    >
                      去检索页
                    </Link>
                  </div>
                  <button
                    type="button"
                    onClick={handleLogout}
                    disabled={submitting}
                    className="w-full rounded-xl border border-white/20 bg-white/10 py-3 font-semibold text-white transition-all hover:bg-white/20 disabled:cursor-not-allowed disabled:opacity-70"
                  >
                    {submitting ? "处理中..." : "退出登录"}
                  </button>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="rounded-2xl border border-white/10 bg-black/30 p-4 text-sm text-slate-300">
                    登录页和注册页现在是独立的应用入口，支持完整认证壳和后续跳转，不再依赖弹窗上下文。
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Link
                      href="/login"
                      onClick={() => setAuthOpen(false)}
                      className="rounded-xl bg-cyan-500 px-4 py-3 text-center text-sm font-semibold text-white transition-colors hover:bg-cyan-400"
                    >
                      去登录
                    </Link>
                    <Link
                      href="/register"
                      onClick={() => setAuthOpen(false)}
                      className="rounded-xl border border-white/20 bg-white/10 px-4 py-3 text-center text-sm font-semibold text-white transition-colors hover:bg-white/20"
                    >
                      去注册
                    </Link>
                  </div>
                </div>
              )}
              {message ? (
                <p className="mt-4 rounded-lg border border-white/10 bg-black/30 px-4 py-2 text-xs text-slate-300">
                  {message}
                </p>
              ) : null}
            </motion.div>
          </motion.div>
        ) : null}
      </AnimatePresence>

      <AnimatePresence>
        {isWatchlistOpen ? (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-[90] bg-black/40 backdrop-blur-sm"
              onClick={() => setWatchlistOpen(false)}
            />
            <motion.div
              initial={{ x: "100%" }}
              animate={{ x: 0 }}
              exit={{ x: "100%" }}
              transition={{ type: "spring", damping: 25, stiffness: 200 }}
              className="fixed right-0 top-0 z-[100] flex h-full w-80 flex-col border-l border-white/10 bg-[#0a0f1a]/95 shadow-[-20px_0_50px_rgba(0,0,0,0.5)] backdrop-blur-3xl md:w-96"
            >
              <div className="flex items-center justify-between gap-3 border-b border-white/10 p-6 text-white">
                <h3 className="min-w-0 flex items-center gap-2 text-lg font-bold">
                  <Star className="text-yellow-400" size={20} /> 我的关注库
                </h3>
                <div className="flex items-center gap-2">
                  <Link
                    href="/watchlist"
                    onClick={() => setWatchlistOpen(false)}
                    className="rounded-full border border-cyan-400/20 bg-cyan-500/10 px-3 py-1.5 text-[11px] font-semibold text-cyan-100 transition-colors hover:bg-cyan-500/20"
                  >
                    打开工作台
                  </Link>
                  <button
                    onClick={() => setWatchlistOpen(false)}
                    className="rounded-full bg-white/5 p-1.5 text-slate-400 transition-colors hover:text-white"
                  >
                    <X size={16} />
                  </button>
                </div>
              </div>
              <WatchlistWorkspace mode="drawer" onNavigate={() => setWatchlistOpen(false)} />
            </motion.div>
          </>
        ) : null}
      </AnimatePresence>
    </>
  );
}
