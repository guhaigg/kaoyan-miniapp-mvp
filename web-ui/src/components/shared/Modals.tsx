"use client";

import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { Star, X } from "lucide-react";
import { useAppStore } from "@/lib/store";
import WatchlistWorkspace from "@/components/watchlist/WatchlistWorkspace";
import AuthEntryPage from "@/components/shared/AuthEntryPage";

export default function Modals() {
  const { isAuthOpen, authMode, setAuthOpen, isWatchlistOpen, setWatchlistOpen } = useAppStore();

  return (
    <>
      <AnimatePresence>
        {isAuthOpen ? (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <AuthEntryPage initialMode={authMode} routeMode={false} onRequestClose={() => setAuthOpen(false)} />
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
