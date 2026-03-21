"use client";

import Link from "next/link";
import { startTransition, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Info, Loader2, Radar, Sparkles, Target } from "lucide-react";
import { predictRadar } from "@/api/radar";
import { ApiError, type RadarPredictResponse } from "@/lib/api";

const CATEGORY_OPTIONS = [
  { value: "工学(不含照顾专业)", label: "工学(不含照顾专业) - 历年A线约 264-273" },
  { value: "理学", label: "理学 - 历年A线约 274-288" },
  { value: "教育学", label: "教育学 / 教育专硕 - 历年A线约 341-350" },
  { value: "管理学", label: "管理学 - 历年A线约 332-347" },
  { value: "公共管理", label: "公共管理(MPA) - 历年A线约 164-175" },
  { value: "会计", label: "会计 / 审计 / 图情 - 历年A线约 191-201" },
] as const;

const colorMap = {
  danger: {
    text: "text-red-300",
    bg: "bg-red-500",
    glow: "shadow-[0_0_15px_rgba(239,68,68,0.45)]",
    border: "border-red-500/25",
    panel: "bg-red-500/8",
  },
  warning: {
    text: "text-orange-300",
    bg: "bg-orange-500",
    glow: "shadow-[0_0_15px_rgba(249,115,22,0.45)]",
    border: "border-orange-500/25",
    panel: "bg-orange-500/8",
  },
  info: {
    text: "text-cyan-300",
    bg: "bg-cyan-500",
    glow: "shadow-[0_0_15px_rgba(6,182,212,0.45)]",
    border: "border-cyan-500/25",
    panel: "bg-cyan-500/8",
  },
  success: {
    text: "text-emerald-300",
    bg: "bg-emerald-500",
    glow: "shadow-[0_0_15px_rgba(34,197,94,0.45)]",
    border: "border-emerald-500/25",
    panel: "bg-emerald-500/8",
  },
} as const;

const quickScores = [
  { label: "边线试探", score: 275, category: "工学(不含照顾专业)" },
  { label: "理学参考", score: 300, category: "理学" },
  { label: "管理学参考", score: 355, category: "管理学" },
] as const;

export default function RadarCalculator() {
  const [score, setScore] = useState("");
  const [category, setCategory] = useState("");
  const [isCalculating, setIsCalculating] = useState(false);
  const [result, setResult] = useState<RadarPredictResponse | null>(null);
  const [error, setError] = useState("");
  const timerRef = useRef<number | null>(null);

  async function handleCalculate() {
    const parsedScore = Number.parseInt(score, 10);
    if (Number.isNaN(parsedScore) || !category) {
      return;
    }

    if (timerRef.current) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }

    setError("");
    setResult(null);
    setIsCalculating(true);

    try {
      const payload = await predictRadar({
        score: parsedScore,
        category,
        area: "A",
      });

      timerRef.current = window.setTimeout(() => {
        startTransition(() => {
          setResult(payload);
          setIsCalculating(false);
        });
      }, 600);
    } catch (requestError) {
      setIsCalculating(false);
      if (requestError instanceof ApiError) {
        setError(requestError.message);
      } else {
        setError("测算失败，请稍后重试。");
      }
    }
  }

  function applyPreset(nextScore: number, nextCategory: string) {
    setScore(String(nextScore));
    setCategory(nextCategory);
  }

  const visual = result ? colorMap[result.level] : colorMap.info;

  return (
    <div className="grid grid-cols-1 items-start gap-8 lg:grid-cols-12">
      <motion.section
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.45, ease: "easeOut" }}
        className="relative overflow-hidden rounded-[2rem] border border-white/10 bg-[#0a0f1a]/82 p-8 shadow-[0_28px_100px_rgba(0,0,0,0.28)] backdrop-blur-2xl lg:col-span-5"
      >
        <div className="pointer-events-none absolute -right-16 top-0 h-48 w-48 rounded-full bg-cyan-500/10 blur-3xl" />
        <div className="relative z-10">
          <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-cyan-500/20 bg-cyan-500/10 px-4 py-1.5 text-xs font-mono uppercase tracking-[0.22em] text-cyan-300">
            <Sparkles size={14} />
            AI Predictive Engine
          </div>

          <h3 className="mb-2 flex items-center gap-3 text-2xl font-black tracking-tight text-white">
            <span className="inline-flex h-11 w-11 items-center justify-center rounded-2xl border border-cyan-400/20 bg-cyan-500/12 text-cyan-300">
              <Target size={22} />
            </span>
            参数录入
          </h3>
          <p className="mb-8 text-sm leading-7 text-slate-400">
            系统会综合国家线位置、近三年历史样本折算中位值和分段分布，给出一版实战调剂诊断。
          </p>

          <div className="space-y-6">
            <div>
              <label htmlFor="radar-score" className="mb-2 block text-[11px] font-bold uppercase tracking-[0.22em] text-slate-500">
                初试总分
              </label>
              <input
                id="radar-score"
                type="number"
                inputMode="numeric"
                placeholder="例如 315"
                value={score}
                onChange={(event) => setScore(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    void handleCalculate();
                  }
                }}
                className="w-full rounded-[1.4rem] border border-white/8 bg-black/35 px-5 py-4 text-lg text-white outline-none transition-colors placeholder:text-slate-600 focus:border-cyan-500/45 focus:bg-black/45"
              />
            </div>

            <div>
              <label htmlFor="radar-category" className="mb-2 block text-[11px] font-bold uppercase tracking-[0.22em] text-slate-500">
                报考门类
              </label>
              <div className="relative">
                <select
                  id="radar-category"
                  value={category}
                  onChange={(event) => setCategory(event.target.value)}
                  className="w-full appearance-none rounded-[1.4rem] border border-white/8 bg-black/35 px-5 py-4 text-base text-slate-100 outline-none transition-colors focus:border-cyan-500/45 focus:bg-black/45"
                >
                  <option value="" disabled>
                    点击选择门类
                  </option>
                  {CATEGORY_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
                <div className="pointer-events-none absolute right-5 top-1/2 -translate-y-1/2 text-xs text-slate-500">▼</div>
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              {quickScores.map((preset) => (
                <button
                  key={preset.label}
                  type="button"
                  onClick={() => applyPreset(preset.score, preset.category)}
                  className="rounded-full border border-white/8 bg-white/[0.04] px-3 py-1.5 text-[11px] font-medium text-slate-400 transition-all hover:border-cyan-500/25 hover:bg-cyan-500/10 hover:text-cyan-300"
                >
                  {preset.label}
                </button>
              ))}
            </div>

            <button
              type="button"
              onClick={() => void handleCalculate()}
              disabled={isCalculating || !score || !category}
              className="inline-flex w-full items-center justify-center gap-2 rounded-[1.4rem] bg-gradient-to-r from-cyan-600 to-blue-600 px-8 py-4 text-lg font-extrabold text-white shadow-[0_0_20px_rgba(6,182,212,0.28)] transition-all hover:from-cyan-500 hover:to-blue-500 active:scale-[0.99] disabled:cursor-not-allowed disabled:from-slate-800 disabled:to-slate-800 disabled:text-slate-500"
            >
              {isCalculating ? (
                <>
                  <Loader2 size={20} className="animate-spin" />
                  深度推演中...
                </>
              ) : (
                "启动诊断"
              )}
            </button>

            {error ? (
              <div className="rounded-[1.2rem] border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-200">
                {error}
              </div>
            ) : null}
          </div>
        </div>
      </motion.section>

      <motion.section
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.45, delay: 0.08, ease: "easeOut" }}
        className="relative flex min-h-[520px] flex-col justify-center overflow-hidden rounded-[2rem] border border-white/8 bg-white/[0.03] p-8 shadow-[0_22px_90px_rgba(0,0,0,0.22)] backdrop-blur-xl lg:col-span-7"
      >
        <div className="pointer-events-none absolute left-1/2 top-1/2 h-[22rem] w-[22rem] -translate-x-1/2 -translate-y-1/2 rounded-full bg-cyan-500/6 blur-3xl" />

        <AnimatePresence mode="wait">
          {!result || isCalculating ? (
            <motion.div
              key={isCalculating ? "loading" : "idle"}
              initial={{ opacity: 0, scale: 0.97 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.96 }}
              className="relative z-10 flex w-full flex-1 flex-col items-center justify-center text-center"
            >
              <div className="relative mb-8 flex items-center justify-center">
                <motion.div
                  animate={
                    isCalculating
                      ? { scale: [1, 1.95, 1], opacity: [0.18, 0.45, 0.18] }
                      : { scale: [1, 1.2, 1], opacity: [0.08, 0.18, 0.08] }
                  }
                  transition={{ duration: isCalculating ? 1 : 3.2, repeat: Infinity, ease: "easeInOut" }}
                  className="absolute h-32 w-32 rounded-full bg-cyan-500/22 blur-2xl"
                />
                <motion.div
                  animate={isCalculating ? { rotate: 360 } : undefined}
                  transition={isCalculating ? { duration: 3, repeat: Infinity, ease: "linear" } : undefined}
                  className="relative z-10"
                >
                  <Radar size={68} strokeWidth={1} className={isCalculating ? "text-cyan-300" : "text-cyan-500/55"} />
                </motion.div>
              </div>

              <h4 className="mb-2 text-xl font-bold tracking-[0.16em] text-slate-200">
                {isCalculating ? "SYSTEM CALCULATING..." : "WAITING FOR INPUT"}
              </h4>
              <p className="max-w-lg text-sm leading-7 text-slate-500">
                {isCalculating
                  ? "正在比对国家线、历史分段与高频上岸样本，诊断台正在生成你当前分数的调剂区间。"
                  : "请在左侧录入你的分数和门类，雷达会生成一版面向调剂决策的综合诊断。"}
              </p>
            </motion.div>
          ) : (
            <motion.div
              key="result"
              initial={{ opacity: 0, scale: 0.97 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.96 }}
              className="relative z-10 flex h-full flex-col justify-center"
            >
              <div className={`relative overflow-hidden rounded-[1.75rem] border p-8 ${visual.border} ${visual.panel}`}>
                <div className={`pointer-events-none absolute right-0 top-0 h-56 w-56 -translate-y-1/2 translate-x-1/2 rounded-full blur-3xl opacity-20 ${visual.bg}`} />

                <div className="relative z-10 mb-8 flex flex-col gap-8 md:flex-row md:items-center">
                  <div className="text-center md:min-w-[12rem] md:text-left">
                    <span className="mb-2 block text-sm font-mono uppercase tracking-[0.22em] text-slate-500">
                      AI 综合预估胜率
                    </span>
                    <div className="flex items-end justify-center gap-1 md:justify-start">
                      <motion.span
                        initial={{ opacity: 0, y: 18 }}
                        animate={{ opacity: 1, y: 0 }}
                        className={`font-mono text-7xl font-black tracking-[-0.08em] ${visual.text}`}
                      >
                        {result.win_rate}
                      </motion.span>
                      <span className="pb-2 text-2xl text-slate-500">%</span>
                    </div>
                  </div>

                  <div className="hidden h-24 w-px bg-white/10 md:block" />

                  <div className="flex-1">
                    <div className="mb-2 flex items-center justify-between text-[11px] font-mono uppercase tracking-[0.14em] text-slate-500">
                      <span>0% 极度危险</span>
                      <span>100% 稳操胜券</span>
                    </div>
                    <div className="h-4 overflow-hidden rounded-full border border-white/6 bg-white/[0.05] p-0.5">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${result.win_rate}%` }}
                        transition={{ duration: 1.4, type: "spring", bounce: 0.18 }}
                        className={`h-full rounded-full ${visual.bg} ${visual.glow}`}
                      />
                    </div>
                    <div className="mt-4 grid gap-3 sm:grid-cols-3">
                      <MetricChip label="当前A区线" value={`${result.comparison_line}`} />
                      <MetricChip
                        label="历史折算中位"
                        value={result.historical_benchmark_score !== null ? `${result.historical_benchmark_score}` : "暂无"}
                      />
                      <MetricChip label="历史样本量" value={`${result.historical_sample_count}`} />
                    </div>
                  </div>
                </div>

                <div className="relative z-10 rounded-[1.4rem] border border-white/6 bg-white/[0.04] p-5">
                  <div className="mb-3 flex items-center gap-3 text-white">
                    <Info size={20} className={visual.text} />
                    <h4 className="text-base font-bold">行动指令建议</h4>
                  </div>
                  <p className="text-sm leading-8 text-slate-200">{result.advice}</p>
                  <div className="mt-4 flex flex-wrap items-center gap-3 text-[11px] font-mono uppercase tracking-[0.12em] text-slate-500">
                    <span>参考年份 {result.national_line_reference_years.join(" / ")}</span>
                    <span className="h-3 w-px bg-white/10" />
                    <span>门类 {result.category_label}</span>
                    <span className="h-3 w-px bg-white/10" />
                    <span>
                      较A区线 {result.delta_to_comparison_line >= 0 ? "+" : ""}
                      {result.delta_to_comparison_line}
                    </span>
                  </div>
                </div>
              </div>

              <div className="mt-5 flex flex-wrap items-center justify-between gap-3 px-1">
                <div className="text-xs text-slate-500">
                  这是一版门类级诊断。下一步请进入检索页，把分数和院校条件叠加到真实调剂样本上看。
                </div>
                <Link
                  href="/search"
                  className="rounded-full border border-white/10 bg-white/[0.04] px-4 py-2 text-xs font-semibold text-slate-200 transition-colors hover:border-cyan-500/25 hover:bg-cyan-500/10 hover:text-cyan-300"
                >
                  前往数据检索
                </Link>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.section>
    </div>
  );
}

function MetricChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/6 bg-black/20 px-4 py-3">
      <div className="text-[10px] font-mono uppercase tracking-[0.18em] text-slate-500">{label}</div>
      <div className="mt-1 text-base font-bold text-white">{value}</div>
    </div>
  );
}
