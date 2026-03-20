"use client";

import { startTransition, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Info, Loader2, Target, TrendingUp } from "lucide-react";
import { predictRadar } from "@/api/radar";
import { ApiError, type RadarPredictResponse } from "@/lib/api";

const CATEGORY_OPTIONS = [
  { value: "工学(不含照顾专业)", label: "工学(不含照顾专业)" },
  { value: "理学", label: "理学" },
  { value: "教育学", label: "教育学 / 教育专硕" },
  { value: "管理学", label: "管理学" },
  { value: "公共管理", label: "公共管理(MPA)" },
  { value: "会计", label: "会计 / 审计 / 图情" },
] as const;

const colorMap = {
  danger: {
    text: "text-red-300",
    track: "bg-red-500",
    glow: "shadow-[0_0_18px_rgba(248,113,113,0.35)]",
    panel: "border-red-500/15 bg-red-500/10",
  },
  warning: {
    text: "text-orange-300",
    track: "bg-orange-500",
    glow: "shadow-[0_0_18px_rgba(249,115,22,0.35)]",
    panel: "border-orange-500/15 bg-orange-500/10",
  },
  info: {
    text: "text-cyan-300",
    track: "bg-cyan-500",
    glow: "shadow-[0_0_18px_rgba(34,211,238,0.35)]",
    panel: "border-cyan-500/15 bg-cyan-500/10",
  },
  success: {
    text: "text-emerald-300",
    track: "bg-emerald-500",
    glow: "shadow-[0_0_18px_rgba(16,185,129,0.35)]",
    panel: "border-emerald-500/15 bg-emerald-500/10",
  },
} as const;

export default function RadarCalculator() {
  const [score, setScore] = useState("");
  const [category, setCategory] = useState("");
  const [isCalculating, setIsCalculating] = useState(false);
  const [result, setResult] = useState<RadarPredictResponse | null>(null);
  const [error, setError] = useState("");

  async function handleCalculate() {
    const parsedScore = Number.parseInt(score, 10);
    if (Number.isNaN(parsedScore) || !category) {
      return;
    }

    setIsCalculating(true);
    setError("");
    setResult(null);

    try {
      const payload = await predictRadar({
        score: parsedScore,
        category,
        area: "A",
      });
      startTransition(() => {
        setResult(payload);
      });
    } catch (requestError) {
      if (requestError instanceof ApiError) {
        setError(requestError.message);
      } else {
        setError("测算失败，请稍后重试。");
      }
    } finally {
      setIsCalculating(false);
    }
  }

  const visual = result ? colorMap[result.level] : colorMap.info;

  return (
    <motion.div
      layout
      className="relative w-full max-w-4xl overflow-hidden rounded-[1.75rem] border border-white/10 bg-[#0a0f1a]/80 p-5 shadow-[0_24px_80px_rgba(0,0,0,0.28)] backdrop-blur-2xl md:p-6"
    >
      <div className="pointer-events-none absolute right-0 top-0 h-64 w-64 -translate-y-1/2 translate-x-1/2 rounded-full bg-cyan-500/7 blur-3xl" />

      <div className="relative z-10 flex flex-col gap-5 md:flex-row md:items-center">
        <div className="md:w-[30%]">
          <div className="mb-3 inline-flex h-11 w-11 items-center justify-center rounded-2xl border border-cyan-400/20 bg-cyan-500/12 text-cyan-300">
            <Target size={22} />
          </div>
          <h3 className="text-lg font-bold text-white">调剂雷达测算</h3>
          <p className="mt-1 text-sm leading-6 text-slate-400">
            用国家线位置和近三年历史样本折算值，快速判断你当前分数所处的调剂区间。
          </p>
        </div>

        <div className="flex w-full flex-col gap-3 md:w-[70%] md:flex-row">
          <label className="sr-only" htmlFor="radar-score">
            初试总分
          </label>
          <input
            id="radar-score"
            type="number"
            placeholder="初试总分"
            inputMode="numeric"
            value={score}
            onChange={(event) => setScore(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                void handleCalculate();
              }
            }}
            className="w-full rounded-2xl border border-white/8 bg-white/[0.05] px-4 py-3.5 text-sm text-white outline-none transition-colors placeholder:text-slate-600 focus:border-cyan-500/45 focus:bg-white/[0.07] sm:w-36"
          />

          <label className="sr-only" htmlFor="radar-category">
            报考门类
          </label>
          <div className="relative flex-1">
            <select
              id="radar-category"
              value={category}
              onChange={(event) => setCategory(event.target.value)}
              className="h-full w-full appearance-none rounded-2xl border border-white/8 bg-white/[0.05] px-4 py-3.5 text-sm text-slate-200 outline-none transition-colors focus:border-cyan-500/45 focus:bg-white/[0.07]"
            >
              <option value="" disabled>
                选择报考门类
              </option>
              {CATEGORY_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <span className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-xs text-slate-500">
              ▼
            </span>
          </div>

          <button
            type="button"
            onClick={() => void handleCalculate()}
            disabled={isCalculating || !score || !category}
            className="inline-flex min-w-[132px] items-center justify-center rounded-2xl bg-white px-6 py-3.5 text-sm font-extrabold text-black transition-all hover:bg-cyan-400 hover:text-white active:scale-[0.98] disabled:cursor-not-allowed disabled:bg-slate-800 disabled:text-slate-500"
          >
            {isCalculating ? <Loader2 size={18} className="animate-spin" /> : "测算胜率"}
          </button>
        </div>
      </div>

      {error ? (
        <div className="relative z-10 mt-4 rounded-2xl border border-red-500/15 bg-red-500/8 px-4 py-3 text-sm text-red-200">
          {error}
        </div>
      ) : null}

      <AnimatePresence initial={false}>
        {result ? (
          <motion.div
            key={`${result.category_key}-${result.win_rate}-${result.historical_sample_count}`}
            initial={{ height: 0, opacity: 0, marginTop: 0 }}
            animate={{ height: "auto", opacity: 1, marginTop: 24 }}
            exit={{ height: 0, opacity: 0, marginTop: 0 }}
            className="relative z-10 overflow-hidden border-t border-white/8 pt-6"
          >
            <div className="flex flex-col gap-5 md:flex-row md:items-stretch">
              <div className={`flex flex-col items-center justify-center rounded-[1.4rem] border p-5 md:w-[30%] ${visual.panel}`}>
                <span className="text-xs uppercase tracking-[0.26em] text-slate-500">AI 胜率</span>
                <div className="mt-3 flex items-end gap-1">
                  <motion.span
                    initial={{ opacity: 0, y: 14 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={`font-mono text-5xl font-black tracking-[-0.06em] ${visual.text}`}
                  >
                    {result.win_rate}
                  </motion.span>
                  <span className="pb-1 text-lg text-slate-500">%</span>
                </div>
                <div className="mt-3 text-center text-xs text-slate-400">
                  {result.national_line_year} {result.area}区线 {result.comparison_line} 分
                </div>
              </div>

              <div className="flex-1">
                <div className="mb-5 rounded-full border border-white/6 bg-white/[0.05] p-1">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${result.win_rate}%` }}
                    transition={{ duration: 1.1, ease: "easeOut" }}
                    className={`h-2.5 rounded-full ${visual.track} ${visual.glow}`}
                  />
                </div>

                <div className="grid gap-3 sm:grid-cols-3">
                  <MetricPill label="近三年A线均值" value={String(result.national_line_reference_avg)} />
                  <MetricPill
                    label="历史折算中位"
                    value={result.historical_benchmark_score !== null ? String(result.historical_benchmark_score) : "暂无"}
                  />
                  <MetricPill label="样本量" value={`${result.historical_sample_count}`} />
                </div>

                <div className="mt-4 flex gap-3 rounded-[1.2rem] border border-white/6 bg-white/[0.05] p-4">
                  <Info size={18} className={`mt-0.5 shrink-0 ${visual.text}`} />
                  <div>
                    <p className="text-sm leading-7 text-slate-200">{result.advice}</p>
                    <div className="mt-3 flex flex-wrap items-center gap-3 text-[11px] text-slate-500">
                      <span>参考年份 {result.national_line_reference_years.join(" / ")}</span>
                      <span className="h-3 w-px bg-white/10" />
                      <span>门类 {result.category_label}</span>
                      <span className="h-3 w-px bg-white/10" />
                      <span>较 {result.area}区线 {result.delta_to_comparison_line >= 0 ? "+" : ""}{result.delta_to_comparison_line}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </motion.div>
  );
}

function MetricPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/6 bg-black/20 px-4 py-3">
      <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">{label}</div>
      <div className="mt-1 flex items-center gap-1 text-sm font-semibold text-white">
        <TrendingUp size={13} className="text-slate-500" />
        <span className="font-mono">{value}</span>
      </div>
    </div>
  );
}
