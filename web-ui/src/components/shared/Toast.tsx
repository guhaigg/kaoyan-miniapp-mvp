"use client";

import { useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, BellRing, X } from "lucide-react";
import { useAppStore } from "@/lib/store";

export default function Toast() {
  const toast = useAppStore((state) => state.toast);
  const hideToast = useAppStore((state) => state.hideToast);
  const setWatchlistOpen = useAppStore((state) => state.setWatchlistOpen);

  useEffect(() => {
    if (!toast.open) return;
    const timer = window.setTimeout(() => {
      hideToast();
    }, 4000);
    return () => {
      window.clearTimeout(timer);
    };
  }, [hideToast, toast.open, toast.message, toast.title, toast.type]);

  return (
    <AnimatePresence>
      {toast.open ? (
        <motion.div
          initial={{ opacity: 0, y: -50, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -20, scale: 0.95 }}
          transition={{ type: "spring", bounce: 0.4, duration: 0.5 }}
          className="fixed left-1/2 top-6 z-[120] w-[90%] max-w-sm -translate-x-1/2 cursor-pointer"
          onClick={() => {
            hideToast();
            setWatchlistOpen(true);
          }}
        >
          <div
            className={`flex items-start gap-3 rounded-2xl border p-4 shadow-2xl backdrop-blur-2xl ${
              toast.type === "urgent"
                ? "border-orange-500/50 bg-orange-950/80 shadow-[0_10px_40px_rgba(249,115,22,0.3)]"
                : "border-cyan-500/30 bg-[#0a0f1a]/90 shadow-[0_10px_40px_rgba(6,182,212,0.2)]"
            }`}
          >
            <div
              className={`mt-0.5 rounded-xl p-2 ${
                toast.type === "urgent" ? "bg-orange-500/20 text-orange-400" : "bg-cyan-500/20 text-cyan-400"
              }`}
            >
              {toast.type === "urgent" ? <AlertTriangle size={18} /> : <BellRing size={18} />}
            </div>
            <div className="flex-1">
              <h4 className="mb-1 text-sm font-bold text-white">{toast.title}</h4>
              <p className="line-clamp-2 text-xs text-slate-300">{toast.message}</p>
            </div>
            <button
              onClick={(event) => {
                event.stopPropagation();
                hideToast();
              }}
              className="text-slate-500 transition-colors hover:text-white"
            >
              <X size={16} />
            </button>
          </div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
