"use client";

import { motion } from "framer-motion";
import { Activity, ShieldCheck, Sparkles, Waypoints } from "lucide-react";
import RadarCalculator from "@/components/search/RadarCalculator";

const RADAR_HIGHLIGHTS = [
  {
    label: "国家线回溯",
    value: "A / B 区近三年参考",
    icon: Activity,
  },
  {
    label: "历史折算",
    value: "样本中位值 + 分位带",
    icon: Waypoints,
  },
  {
    label: "动作输出",
    value: "直接生成检索动作",
    icon: ShieldCheck,
  },
] as const;

export default function RadarPage() {
  return (
    <div className="mx-auto max-w-[1280px] px-6 pb-24 pt-12 md:pt-16">
      <div className="mb-10 grid gap-6 xl:grid-cols-[1.12fr_0.88fr]">
        <motion.section
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: "easeOut" }}
          className="relative overflow-hidden rounded-[2.25rem] border border-slate-200/70 bg-white/92 p-8 shadow-[0_24px_70px_rgba(15,23,42,0.08)] backdrop-blur-xl"
        >
          <div className="pointer-events-none absolute -right-12 top-0 h-48 w-48 rounded-full bg-cyan-100/70 blur-3xl" />
          <div className="relative z-10">
            <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-cyan-200 bg-cyan-50 px-4 py-1.5 text-xs font-bold uppercase tracking-[0.18em] text-cyan-700">
              <Sparkles size={14} />
              AI Predictive Engine
            </div>
            <h1 className="max-w-3xl text-4xl font-black tracking-tight text-slate-900 md:text-5xl">
              调剂胜率测算中枢
            </h1>
            <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-500">
              这页不是一个聊天问答框，而是一块面向调剂决策的轻量工作台。你先输入分数和门类，
              系统再把国家线位置、历史样本折算与分位带一起压成一版可执行的诊断。
            </p>

            <div className="mt-8 grid gap-3 sm:grid-cols-3">
              {RADAR_HIGHLIGHTS.map((item) => (
                <div key={item.label} className="rounded-[1.5rem] border border-slate-200 bg-slate-50/80 p-4">
                  <div className="mb-3 inline-flex h-10 w-10 items-center justify-center rounded-2xl border border-slate-100 bg-white text-slate-700">
                    <item.icon size={18} />
                  </div>
                  <div className="text-sm font-bold text-slate-900">{item.label}</div>
                  <div className="mt-1 text-[13px] leading-6 text-slate-500">{item.value}</div>
                </div>
              ))}
            </div>
          </div>
        </motion.section>

        <motion.aside
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.06, ease: "easeOut" }}
          className="rounded-[2.25rem] border border-slate-200/70 bg-[linear-gradient(180deg,rgba(255,255,255,0.94),rgba(248,250,252,0.88))] p-8 shadow-[0_22px_60px_rgba(15,23,42,0.06)]"
        >
          <div className="mb-3 text-[11px] font-bold uppercase tracking-[0.22em] text-slate-400">How It Works</div>
          <h2 className="text-2xl font-black tracking-tight text-slate-900">先测胜率，再进检索页做精筛</h2>
          <p className="mt-3 text-sm leading-7 text-slate-500">
            雷达页负责把你的分数先归位，判断它更接近稳妥带、观察带还是进攻带；真正的院校和专业筛选，
            仍然建议带着这版诊断去检索页完成。
          </p>

          <div className="mt-6 space-y-3">
            {[
              "输入总分和报考门类，先拿到一版门类级诊断。",
              "看线差、样本量和折算中位值，不再只盯一个胜率数字。",
              "直接跳到预设好的检索路径，继续看真实调剂样本。",
            ].map((item, index) => (
              <div key={item} className="flex items-start gap-3 rounded-2xl border border-slate-200 bg-white/80 p-4">
                <span className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-900 text-[11px] font-bold text-white">
                  {index + 1}
                </span>
                <p className="text-sm leading-6 text-slate-600">{item}</p>
              </div>
            ))}
          </div>
        </motion.aside>
      </div>

      <RadarCalculator />
    </div>
  );
}
