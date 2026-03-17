"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Check, Filter, RotateCcw, X } from "lucide-react";

export type SchoolTier = "985/211" | "双一流" | "科研院所" | "普通本科";
export type StudyMode = "all" | "fulltime" | "parttime";

interface FilterDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  tiers: SchoolTier[];
  studyMode: StudyMode;
  onToggleTier: (value: SchoolTier) => void;
  onStudyModeChange: (value: StudyMode) => void;
  onReset: () => void;
  resultCount: number;
}

const tierOptions: SchoolTier[] = ["985/211", "双一流", "科研院所", "普通本科"];
const studyModes: Array<{ value: StudyMode; label: string }> = [
  { value: "all", label: "不限" },
  { value: "fulltime", label: "全日制" },
  { value: "parttime", label: "非全日制" },
];

export default function FilterDrawer({
  isOpen,
  onClose,
  tiers,
  studyMode,
  onToggleTier,
  onStudyModeChange,
  onReset,
  resultCount,
}: FilterDrawerProps) {
  return (
    <AnimatePresence>
      {isOpen ? (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] bg-black/40"
            onClick={onClose}
          />
          <motion.aside
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 25, stiffness: 200 }}
            className="fixed right-0 top-0 z-[101] flex h-full w-full max-w-[400px] flex-col border-l border-white/10 bg-[#0a0f1a]/95 shadow-[-20px_0_50px_rgba(0,0,0,0.5)] backdrop-blur-3xl"
          >
            <div className="flex items-center justify-between border-b border-white/10 p-6 text-white">
              <h3 className="flex items-center gap-2 text-xl font-bold">
                <Filter className="text-cyan-400" size={20} />
                高级筛选
              </h3>
              <button
                type="button"
                onClick={onClose}
                className="rounded-full bg-white/5 p-2 text-slate-400 transition-colors hover:text-white"
              >
                <X size={16} />
              </button>
            </div>

            <div className="flex-1 space-y-8 overflow-y-auto p-8">
              <div>
                <h4 className="mb-4 text-sm font-bold uppercase tracking-wider text-slate-300">
                  院校层次
                </h4>
                <div className="flex flex-wrap gap-3">
                  {tierOptions.map((tier) => {
                    const active = tiers.includes(tier);
                    return (
                      <button
                        key={tier}
                        type="button"
                        onClick={() => onToggleTier(tier)}
                        className={`flex items-center gap-2 rounded-xl border px-4 py-2 text-sm font-medium transition-all ${
                          active
                            ? "border-cyan-400 bg-cyan-500/20 text-cyan-300 shadow-[0_0_15px_rgba(6,182,212,0.2)]"
                            : "border-transparent bg-white/5 text-slate-400 hover:bg-white/10"
                        }`}
                      >
                        {active ? <Check size={14} /> : null}
                        {tier}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div>
                <h4 className="mb-4 text-sm font-bold uppercase tracking-wider text-slate-300">
                  学习方式
                </h4>
                <div className="grid grid-cols-3 gap-3 rounded-2xl border border-white/5 bg-white/5 p-1">
                  {studyModes.map((item) => {
                    const active = item.value === studyMode;
                    return (
                      <button
                        key={item.value}
                        type="button"
                        onClick={() => onStudyModeChange(item.value)}
                        className={`relative rounded-xl py-2.5 text-sm font-medium transition-colors ${
                          active ? "text-white" : "text-slate-400"
                        }`}
                      >
                        {active ? (
                          <motion.div
                            layoutId="studyMode"
                            className="absolute inset-0 rounded-xl bg-white/10"
                          />
                        ) : null}
                        <span className="relative z-10">{item.label}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                <div className="mb-1 text-xs uppercase tracking-[0.24em] text-slate-500">
                  Filter State
                </div>
                <div className="text-sm leading-7 text-slate-300">
                  当前层次:
                  <span className="ml-2 text-cyan-300">
                    {tiers.length ? tiers.join(" / ") : "不限"}
                  </span>
                </div>
                <div className="text-sm leading-7 text-slate-300">
                  学习方式:
                  <span className="ml-2 text-cyan-300">
                    {studyMode === "all"
                      ? "不限"
                      : studyMode === "fulltime"
                        ? "全日制"
                        : "非全日制"}
                  </span>
                </div>
                <p className="mt-3 text-xs leading-6 text-slate-500">
                  当前版本将对检索结果做前端二次筛选，用于快速收窄目标列表。
                </p>
              </div>
            </div>

            <div className="border-t border-white/10 bg-black/20 p-6">
              <div className="mb-3 flex gap-3">
                <button
                  type="button"
                  onClick={onReset}
                  className="flex flex-1 items-center justify-center gap-2 rounded-2xl border border-white/10 bg-white/5 py-3 text-sm font-medium text-slate-200 transition-colors hover:bg-white/10"
                >
                  <RotateCcw size={14} />
                  重置
                </button>
                <button
                  type="button"
                  onClick={onClose}
                  className="flex-[1.5] rounded-2xl bg-cyan-600 py-3 text-sm font-bold text-white shadow-[0_0_20px_rgba(6,182,212,0.3)] transition-all hover:bg-cyan-500 active:scale-[0.98]"
                >
                  应用筛选 ({resultCount} 条结果)
                </button>
              </div>
            </div>
          </motion.aside>
        </>
      ) : null}
    </AnimatePresence>
  );
}
