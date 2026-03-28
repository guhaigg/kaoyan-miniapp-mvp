"use client";

import Link from "next/link";
import { startTransition, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, Info, Loader2, Orbit, Radar, Sparkles, Target } from "lucide-react";
import { predictRadar } from "@/api/radar";
import { ApiError, type RadarPredictResponse } from "@/lib/api";

const CATEGORY_OPTIONS = [
  { value: "工学(不含照顾专业)", label: "工学(不含照顾专业) - 历年A线约 264-273", range: "A线约 264-273" },
  { value: "理学", label: "理学 - 历年A线约 274-288", range: "A线约 274-288" },
  { value: "教育学", label: "教育学 / 教育专硕 - 历年A线约 341-350", range: "A线约 341-350" },
  { value: "管理学", label: "管理学 - 历年A线约 332-347", range: "A线约 332-347" },
  { value: "公共管理", label: "公共管理(MPA) - 历年A线约 164-175", range: "A线约 164-175" },
  { value: "会计", label: "会计 / 审计 / 图情 - 历年A线约 191-201", range: "A线约 191-201" },
] as const;

const LEVEL_THEME = {
  danger: {
    accentText: "text-red-600",
    accentBg: "bg-red-500",
    accentSoft: "bg-red-50",
    accentBorder: "border-red-200/80",
    accentTint: "bg-[radial-gradient(circle_at_top_right,rgba(239,68,68,0.14),transparent_55%)]",
    badge: "高压区",
    summary: "优先看保守样本",
  },
  warning: {
    accentText: "text-orange-600",
    accentBg: "bg-orange-500",
    accentSoft: "bg-orange-50",
    accentBorder: "border-orange-200/80",
    accentTint: "bg-[radial-gradient(circle_at_top_right,rgba(249,115,22,0.14),transparent_55%)]",
    badge: "观察区",
    summary: "先收窄活跃样本",
  },
  info: {
    accentText: "text-cyan-600",
    accentBg: "bg-cyan-500",
    accentSoft: "bg-cyan-50",
    accentBorder: "border-cyan-200/80",
    accentTint: "bg-[radial-gradient(circle_at_top_right,rgba(6,182,212,0.14),transparent_55%)]",
    badge: "机会区",
    summary: "适合看高匹配样本",
  },
  success: {
    accentText: "text-emerald-600",
    accentBg: "bg-emerald-500",
    accentSoft: "bg-emerald-50",
    accentBorder: "border-emerald-200/80",
    accentTint: "bg-[radial-gradient(circle_at_top_right,rgba(16,185,129,0.14),transparent_55%)]",
    badge: "进攻区",
    summary: "可以试探优质院校",
  },
} as const;

const quickScores = [
  { label: "边线试探", score: 275, category: "工学(不含照顾专业)" },
  { label: "理学参考", score: 300, category: "理学" },
  { label: "管理学参考", score: 355, category: "管理学" },
] as const;

const idlePreviewCards = [
  { title: "当前线差", detail: "输出你与对照线的绝对分差，先判断是否值得投入筛选。", icon: Target },
  { title: "历史折算", detail: "结合中位值和分位带，看你的分数落在样本带的哪一层。", icon: Orbit },
  { title: "样本规模", detail: "展示历史样本量与样本组数，避免被少量偶然值带偏。", icon: Sparkles },
  { title: "动作建议", detail: "直接生成下一步检索动作，不让结果停在一句空话上。", icon: Info },
] as const;

export default function RadarCalculator() {
  const [score, setScore] = useState("");
  const [category, setCategory] = useState("");
  const [isCalculating, setIsCalculating] = useState(false);
  const [result, setResult] = useState<RadarPredictResponse | null>(null);
  const [error, setError] = useState("");
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) {
        window.clearTimeout(timerRef.current);
      }
    };
  }, []);

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
      }, 550);
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

  function applyCategoryReference(nextCategory: string) {
    setCategory(nextCategory);
  }

  const parsedScore = Number.parseInt(score, 10);
  const canCalculate = !Number.isNaN(parsedScore) && Boolean(category) && !isCalculating;
  const theme = result ? LEVEL_THEME[result.level] : LEVEL_THEME.info;
  const searchPlan = result ? buildRadarSearchPlan(result, score) : null;

  return (
    <div className="grid grid-cols-1 items-start gap-8 xl:grid-cols-[minmax(0,430px)_minmax(0,1fr)]">
      <motion.section
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.45, ease: "easeOut" }}
        className="relative overflow-hidden rounded-[2rem] border border-slate-200/70 bg-white/92 p-8 shadow-[0_26px_70px_rgba(15,23,42,0.08)] backdrop-blur-xl"
      >
        <div className="pointer-events-none absolute -right-10 top-0 h-40 w-40 rounded-full bg-cyan-100/60 blur-3xl" />
        <div className="relative z-10">
          <div className="mb-5 flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-2 rounded-full border border-cyan-200 bg-cyan-50 px-3 py-1 text-[11px] font-bold uppercase tracking-[0.18em] text-cyan-700">
              <Sparkles size={12} />
              AI Predictive Engine
            </span>
            <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-[11px] font-medium text-slate-500">A 区基线</span>
          </div>

          <h3 className="mb-2 flex items-center gap-3 text-[28px] font-black tracking-tight text-slate-900">
            <span className="inline-flex h-12 w-12 items-center justify-center rounded-2xl border border-cyan-100 bg-cyan-50 text-cyan-600">
              <Target size={22} />
            </span>
            参数录入
          </h3>
          <p className="mb-8 text-sm leading-7 text-slate-500">
            输入总分与报考门类，系统会综合国家线位置、历史样本折算和分段带宽，给出一版适合调剂决策的初筛判断。
          </p>

          <div className="space-y-6">
            <div>
              <label htmlFor="radar-score" className="mb-2 block text-[11px] font-bold uppercase tracking-[0.2em] text-slate-500">
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
                className="w-full rounded-[1.4rem] border border-slate-200 bg-white px-5 py-4 text-lg font-semibold text-slate-900 outline-none transition-all placeholder:text-slate-400 focus:border-cyan-300 focus:shadow-[0_0_0_4px_rgba(34,211,238,0.12)]"
              />
            </div>

            <div>
              <label htmlFor="radar-category" className="mb-2 block text-[11px] font-bold uppercase tracking-[0.2em] text-slate-500">
                报考门类
              </label>
              <div className="relative">
                <select
                  id="radar-category"
                  value={category}
                  onChange={(event) => setCategory(event.target.value)}
                  className="w-full appearance-none rounded-[1.4rem] border border-slate-200 bg-white px-5 py-4 text-base font-medium text-slate-900 outline-none transition-all focus:border-cyan-300 focus:shadow-[0_0_0_4px_rgba(34,211,238,0.12)]"
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
                <div className="pointer-events-none absolute right-5 top-1/2 -translate-y-1/2 text-xs text-slate-400">▼</div>
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              {quickScores.map((preset) => (
                <button
                  key={preset.label}
                  type="button"
                  onClick={() => applyPreset(preset.score, preset.category)}
                  className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-[11px] font-medium text-slate-500 transition-all hover:border-cyan-200 hover:bg-cyan-50 hover:text-cyan-700"
                >
                  {preset.label}
                </button>
              ))}
            </div>

            <button
              type="button"
              onClick={() => void handleCalculate()}
              disabled={!canCalculate}
              className="inline-flex w-full items-center justify-center gap-2 rounded-[1.4rem] bg-slate-900 px-8 py-4 text-base font-bold text-white shadow-[0_18px_40px_rgba(15,23,42,0.16)] transition-all hover:bg-slate-800 active:scale-[0.99] disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400"
            >
              {isCalculating ? (
                <>
                  <Loader2 size={18} className="animate-spin" />
                  深度推演中...
                </>
              ) : (
                <>
                  启动诊断
                  <ArrowRight size={16} />
                </>
              )}
            </button>

            {error ? (
              <div className="rounded-[1.2rem] border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
                {error}
              </div>
            ) : null}

            <div className="grid gap-3 sm:grid-cols-2">
              <GuideChip label="参考范围" value="最近三年 A 区国家线" />
              <GuideChip label="输出结果" value="胜率 / 线差 / 检索建议" />
            </div>
          </div>
        </div>
      </motion.section>

      <motion.section
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.45, delay: 0.08, ease: "easeOut" }}
        className="relative overflow-hidden rounded-[2rem] border border-slate-200/70 bg-[linear-gradient(180deg,rgba(255,255,255,0.92),rgba(248,250,252,0.88))] p-8 shadow-[0_22px_70px_rgba(15,23,42,0.06)]"
      >
        <div className="pointer-events-none absolute right-0 top-0 h-56 w-56 rounded-full bg-cyan-100/50 blur-3xl" />
        <div className="pointer-events-none absolute bottom-0 left-0 h-40 w-40 rounded-full bg-orange-100/40 blur-3xl" />

        <AnimatePresence mode="wait">
          {!result || isCalculating ? (
            <motion.div
              key={isCalculating ? "loading" : "idle"}
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.98 }}
              className="relative z-10 grid h-full min-h-[520px] items-center gap-8 xl:grid-cols-[0.92fr_1.08fr]"
            >
              <div className="flex flex-col items-center justify-center text-center xl:items-start xl:text-left">
                <div className="relative mb-8 flex h-32 w-32 items-center justify-center">
                  <motion.div
                    animate={
                      isCalculating
                        ? { scale: [1, 1.65, 1], opacity: [0.12, 0.32, 0.12] }
                        : { scale: [1, 1.18, 1], opacity: [0.08, 0.18, 0.08] }
                    }
                    transition={{ duration: isCalculating ? 1.1 : 3.2, repeat: Infinity, ease: "easeInOut" }}
                    className="absolute h-32 w-32 rounded-full bg-cyan-200 blur-2xl"
                  />
                  <motion.div
                    animate={isCalculating ? { rotate: 360 } : undefined}
                    transition={isCalculating ? { duration: 5, repeat: Infinity, ease: "linear" } : undefined}
                    className="relative z-10 inline-flex h-24 w-24 items-center justify-center rounded-full border border-cyan-100 bg-white/80"
                  >
                    <Radar size={54} strokeWidth={1.2} className={isCalculating ? "text-cyan-500" : "text-cyan-400"} />
                  </motion.div>
                </div>

                <div className="mb-2 text-[11px] font-bold uppercase tracking-[0.22em] text-slate-400">
                  {isCalculating ? "System Calculating" : "Waiting For Input"}
                </div>
                <h4 className="mb-3 text-3xl font-black tracking-tight text-slate-900">
                  {isCalculating ? "正在生成你的调剂诊断" : "先录分数，再看诊断画布"}
                </h4>
                <p className="max-w-md text-sm leading-7 text-slate-500">
                  {isCalculating
                    ? "系统正在比对国家线、历史样本折算和分位带宽，结果页会返回胜率、线差和下一步检索动作。"
                    : "这不是聊天式建议页，而是一块面向调剂决策的工作台。它会把分数先折算到可执行的样本区间。"}
                </p>
              </div>

              <div className="space-y-4">
                <div className="grid gap-3 sm:grid-cols-2">
                  {idlePreviewCards.map((card) => (
                    <div key={card.title} className="rounded-[1.4rem] border border-slate-200 bg-white/80 p-4">
                      <div className="mb-3 inline-flex h-10 w-10 items-center justify-center rounded-2xl border border-slate-100 bg-slate-50 text-slate-700">
                        <card.icon size={18} />
                      </div>
                      <div className="text-sm font-bold text-slate-900">{card.title}</div>
                      <p className="mt-2 text-[13px] leading-6 text-slate-500">{card.detail}</p>
                    </div>
                  ))}
                </div>

                <div className="rounded-[1.5rem] border border-slate-200 bg-white/80 p-5">
                  <div className="mb-3 text-[11px] font-bold uppercase tracking-[0.2em] text-slate-400">热门门类参考</div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {CATEGORY_OPTIONS.slice(0, 4).map((option) => (
                      <button
                        key={option.value}
                        type="button"
                        onClick={() => applyCategoryReference(option.value)}
                        className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-left transition-all hover:border-cyan-200 hover:bg-cyan-50"
                      >
                        <div className="text-sm font-bold text-slate-900">{option.value}</div>
                        <div className="mt-1 text-[12px] text-slate-500">{option.range}</div>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="result"
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.98 }}
              className="relative z-10"
            >
              <div className={`relative overflow-hidden rounded-[1.9rem] border ${theme.accentBorder} ${theme.accentSoft} p-8`}>
                <div className={`pointer-events-none absolute inset-0 opacity-100 ${theme.accentTint}`} />

                <div className="relative z-10 mb-8 flex flex-col gap-8 xl:grid xl:grid-cols-[260px_minmax(0,1fr)]">
                  <div>
                    <div className="mb-3 flex flex-wrap items-center gap-2">
                      <span className={`rounded-full px-3 py-1 text-[11px] font-bold uppercase tracking-[0.16em] ${theme.accentText} ${theme.accentSoft}`}>
                        {theme.badge}
                      </span>
                      <span className="text-[11px] font-medium uppercase tracking-[0.14em] text-slate-400">{theme.summary}</span>
                    </div>

                    <div className="text-[11px] font-bold uppercase tracking-[0.22em] text-slate-400">AI 综合预估胜率</div>
                    <div className="mt-3 flex items-end gap-1">
                      <span className={`font-mono text-7xl font-black tracking-[-0.08em] ${theme.accentText}`}>{result.win_rate}</span>
                      <span className="pb-2 text-2xl text-slate-400">%</span>
                    </div>
                    <div className="mt-4 space-y-2 text-sm text-slate-500">
                      <div>门类：{result.category_label}</div>
                      <div>
                        较 A 区线 {result.delta_to_comparison_line >= 0 ? "+" : ""}
                        {result.delta_to_comparison_line}
                      </div>
                    </div>
                  </div>

                  <div>
                    <div className="mb-2 flex items-center justify-between text-[11px] font-bold uppercase tracking-[0.14em] text-slate-400">
                      <span>0% 极度危险</span>
                      <span>100% 稳操胜券</span>
                    </div>
                    <div className="h-4 overflow-hidden rounded-full border border-white/70 bg-white/70 p-0.5">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${result.win_rate}%` }}
                        transition={{ duration: 1.2, type: "spring", bounce: 0.16 }}
                        className={`h-full rounded-full ${theme.accentBg}`}
                      />
                    </div>

                    <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                      <MetricCard label="当前 A 区线" value={String(result.comparison_line)} />
                      <MetricCard
                        label="历史折算中位"
                        value={result.historical_benchmark_score !== null ? String(result.historical_benchmark_score) : "暂无"}
                      />
                      <MetricCard label="分位带" value={buildPercentileBand(result)} />
                      <MetricCard label="历史样本量" value={`${result.historical_sample_count} / ${result.historical_group_count}组`} />
                    </div>
                  </div>
                </div>

                <div className="relative z-10 rounded-[1.5rem] border border-white/70 bg-white/80 p-5">
                  <div className="mb-3 flex items-center gap-3 text-slate-900">
                    <Info size={18} className={theme.accentText} />
                    <h4 className="text-base font-bold">行动指令建议</h4>
                  </div>
                  <p className="text-sm leading-8 text-slate-600">{result.advice}</p>
                  <div className="mt-4 flex flex-wrap items-center gap-3 text-[11px] font-medium uppercase tracking-[0.14em] text-slate-400">
                    <span>参考年份 {result.national_line_reference_years.join(" / ")}</span>
                    <span className="h-3 w-px bg-slate-200" />
                    <span>门类 {result.category_label}</span>
                    <span className="h-3 w-px bg-slate-200" />
                    <span>国家线均值 {result.national_line_reference_avg}</span>
                  </div>
                </div>
              </div>

              <div className="mt-5 flex flex-wrap items-center justify-between gap-3 px-1">
                <div className="text-sm text-slate-500">
                  这是一版门类级诊断。下一步请把分数和院校条件叠加到检索页的真实调剂样本上看。
                </div>
                {searchPlan ? (
                  <div className="flex flex-wrap items-center gap-2">
                    <Link
                      href={searchPlan.primaryHref}
                      className="rounded-full bg-slate-900 px-4 py-2 text-xs font-bold text-white transition-colors hover:bg-slate-800"
                    >
                      {searchPlan.primaryLabel}
                    </Link>
                    <Link
                      href={searchPlan.secondaryHref}
                      className="rounded-full border border-slate-200 bg-white px-4 py-2 text-xs font-bold text-slate-700 transition-colors hover:border-cyan-200 hover:text-cyan-700"
                    >
                      {searchPlan.secondaryLabel}
                    </Link>
                  </div>
                ) : null}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.section>
    </div>
  );
}

function GuideChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
      <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">{label}</div>
      <div className="mt-1 text-sm font-semibold text-slate-700">{value}</div>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/80 bg-white/80 px-4 py-3">
      <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">{label}</div>
      <div className="mt-1 text-base font-bold text-slate-900">{value}</div>
    </div>
  );
}

function buildPercentileBand(result: RadarPredictResponse) {
  if (result.historical_p25_score === null || result.historical_p75_score === null) {
    return "暂无";
  }
  return `${result.historical_p25_score}-${result.historical_p75_score}`;
}

function buildRadarSearchPlan(result: RadarPredictResponse, score: string) {
  const majorToken = resolveRadarSearchMajorToken(result);
  const baseParams = new URLSearchParams({
    tab: "adjustments",
    score,
    history: "1",
  });

  if (majorToken) {
    baseParams.set("major", majorToken);
  }

  const primaryParams = new URLSearchParams(baseParams);
  const secondaryParams = new URLSearchParams(baseParams);

  let primaryLabel = "带着结果去搜";
  let secondaryLabel = "查看全部历史样本";

  if (result.level === "danger") {
    primaryParams.set("level", "普通本科");
    primaryParams.set("long", "1");
    primaryLabel = "先看稳妥样本";
    secondaryLabel = "放宽到全部历史样本";
  } else if (result.level === "warning") {
    primaryParams.set("level", "普通本科");
    primaryParams.set("long", "1");
    primaryLabel = "先看保守样本";
    secondaryLabel = "查看全部活跃样本";
  } else if (result.level === "info") {
    primaryParams.set("long", "1");
    secondaryParams.set("level", "双一流");
    primaryLabel = "查看高匹配样本";
    secondaryLabel = "试探双一流样本";
  } else {
    primaryParams.set("level", "双一流");
    secondaryParams.set("level", "985/211");
    primaryLabel = "先看优质院校";
    secondaryLabel = "冲刺 985/211";
  }

  return {
    primaryHref: `/search?${primaryParams.toString()}`,
    primaryLabel,
    secondaryHref: `/search?${secondaryParams.toString()}`,
    secondaryLabel,
  };
}

function resolveRadarSearchMajorToken(result: RadarPredictResponse) {
  if (result.category_key.length >= 4) {
    return result.category_key;
  }
  const compactLabel = result.category_label.replace(/\s+/g, "");
  if (compactLabel === "公共管理" || compactLabel === "会计") {
    return compactLabel;
  }
  return "";
}
