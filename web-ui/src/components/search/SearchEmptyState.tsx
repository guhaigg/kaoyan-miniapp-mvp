"use client";

import { motion } from "framer-motion";
import { Radar, Sparkles } from "lucide-react";

export default function SearchEmptyState({ setKeyword }: { setKeyword: (value: string) => void }) {
  const suggestions = ["085400", "计算机科学", "211院校", "接受跨考"];

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.8 }}
      className="flex w-full flex-col items-center justify-center py-20 md:py-32"
    >
      <div className="relative mb-6 flex items-center justify-center">
        <motion.div
          animate={{ scale: [1, 1.5, 1], opacity: [0.1, 0.3, 0.1] }}
          transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
          className="absolute h-24 w-24 rounded-full bg-cyan-500/20 blur-xl"
        />
        <Radar size={48} strokeWidth={1} className="relative z-10 text-cyan-500/50" />
      </div>

      <h3 className="mb-2 text-lg font-bold tracking-[0.34em] text-slate-300">
        AWAITING DIRECTIVES
      </h3>
      <p className="mb-8 text-center text-sm text-slate-500">
        输入院校名称、专业代码或地区，雷达将即刻扫描全网情报。
      </p>

      <div className="flex flex-col items-center gap-3">
        <div className="flex items-center gap-1 text-[10px] font-mono uppercase text-slate-600">
          <Sparkles size={12} />
          快捷指令
        </div>
        <div className="flex flex-wrap justify-center gap-2">
          {suggestions.map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => setKeyword(item)}
              className="rounded-full border border-white/5 bg-white/[0.03] px-4 py-1.5 text-xs text-slate-400 transition-all hover:border-cyan-500/30 hover:bg-cyan-500/10 hover:text-cyan-400 active:scale-95"
            >
              {item}
            </button>
          ))}
        </div>
      </div>
    </motion.div>
  );
}
