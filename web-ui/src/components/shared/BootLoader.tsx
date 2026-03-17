"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

export default function BootLoader() {
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (sessionStorage.getItem("gewu_booted")) {
      setIsLoading(false);
      return;
    }
    const timer = setTimeout(() => {
      setIsLoading(false);
      sessionStorage.setItem("gewu_booted", "true");
    }, 1500);
    return () => clearTimeout(timer);
  }, []);

  return (
    <AnimatePresence>
      {isLoading && (
        <motion.div
          exit={{ opacity: 0, scale: 1.05 }}
          transition={{ duration: 0.5, ease: "easeInOut" }}
          className="fixed inset-0 z-[9999] flex flex-col items-center justify-center bg-[#050b14]"
        >
          <div className="relative mb-6 flex h-24 w-24 items-center justify-center overflow-hidden rounded-2xl bg-white drop-shadow-[0_0_20px_rgba(255,255,255,0.2)]">
            <span className="text-5xl font-black tracking-tighter text-[#2c3e50]">GW</span>
            <motion.div
              initial={{ top: "-10%", opacity: 0 }}
              animate={{ top: "110%", opacity: [0, 1, 1, 0] }}
              transition={{ repeat: Infinity, duration: 1.2, ease: "easeInOut" }}
              className="absolute left-0 h-[3px] w-full bg-cyan-400 shadow-[0_0_15px_#06b6d4]"
            />
          </div>
          <div className="font-mono text-xs tracking-widest text-cyan-400">
            MOUNTING GW CORE...
          </div>
          <div className="mt-6 h-1 w-48 overflow-hidden rounded-full bg-white/10">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: "100%" }}
              transition={{ duration: 1.2, ease: "easeInOut" }}
              className="h-full bg-cyan-400 shadow-[0_0_10px_#06b6d4]"
            />
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
