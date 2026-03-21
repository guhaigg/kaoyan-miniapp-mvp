"use client";

import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";
import RadarCalculator from "@/components/search/RadarCalculator";

export default function RadarPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 pb-20 pt-32">
      <div className="mb-12 text-center">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-4 inline-flex items-center gap-2 rounded-full border border-cyan-500/20 bg-cyan-500/10 px-4 py-1.5 text-xs font-mono uppercase tracking-[0.22em] text-cyan-300"
        >
          <Sparkles size={14} />
          AI Predictive Engine
        </motion.div>
        <h1 className="mb-4 text-4xl font-black tracking-tight text-white md:text-5xl">
          调剂胜率测算中枢
        </h1>
        <p className="mx-auto max-w-3xl text-sm font-mono leading-7 text-slate-400">
          系统会实时调取历年国家线与站内历史调剂画像，生成一版用于初筛判断的门类级诊断。
          它不是拍脑袋提示词，而是一块独立的决策控制台。
        </p>
      </div>

      <RadarCalculator />
    </div>
  );
}
