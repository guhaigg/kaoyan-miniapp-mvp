"use client";

import { type ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Check, Filter, RotateCcw, X } from "lucide-react";

export type SchoolTier = "985/211" | "双一流" | "科研院所" | "普通本科";
export type StudyMode = "all" | "fulltime" | "parttime";

interface FilterDrawerProps {
  isOpen: boolean;
  queryType: "announcements" | "adjustments";
  onClose: () => void;
  onApply: () => void;
  onReset: () => void;
  resultCount: number;
  tiers: SchoolTier[];
  studyMode: StudyMode;
  onToggleTier: (value: SchoolTier) => void;
  onStudyModeChange: (value: StudyMode) => void;
  schoolName: string;
  majorFilter: string;
  regionFilter: string;
  cityFilter: string;
  yearFilter: string;
  schoolTierFilter: string;
  candidateScoreFilter: string;
  onSchoolNameChange: (value: string) => void;
  onMajorFilterChange: (value: string) => void;
  onRegionFilterChange: (value: string) => void;
  onCityFilterChange: (value: string) => void;
  onYearFilterChange: (value: string) => void;
  onSchoolTierFilterChange: (value: string) => void;
  onCandidateScoreFilterChange: (value: string) => void;
  onlyHistoryBacked: boolean;
  onlyLongTrack: boolean;
  onlyWithReferenceLinks: boolean;
  hideMentorWarnings: boolean;
  onOnlyHistoryBackedChange: (value: boolean) => void;
  onOnlyLongTrackChange: (value: boolean) => void;
  onOnlyWithReferenceLinksChange: (value: boolean) => void;
  onHideMentorWarningsChange: (value: boolean) => void;
}

const tierOptions: SchoolTier[] = ["985/211", "双一流", "科研院所", "普通本科"];
const studyModes: Array<{ value: StudyMode; label: string }> = [
  { value: "all", label: "不限" },
  { value: "fulltime", label: "全日制" },
  { value: "parttime", label: "非全日制" },
];

function DrawerInput({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
}) {
  return (
    <input
      value={value}
      onChange={(event) => onChange(event.target.value)}
      placeholder={placeholder}
      className="rounded-2xl border border-white/5 bg-white/[0.05] px-4 py-3 text-sm text-white placeholder:text-slate-500 outline-none transition-all focus:border-cyan-400/15 focus:ring-1 focus:ring-cyan-500/45"
    />
  );
}

function DrawerSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <h4 className="text-[11px] font-bold uppercase tracking-[0.24em] text-slate-400">{title}</h4>
      {children}
    </section>
  );
}

function QuickFilterChip({
  active,
  onClick,
  label,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors ${
        active
          ? "border-cyan-400/35 bg-cyan-500/12 text-cyan-100"
          : "border-white/10 bg-white/[0.04] text-slate-300 hover:bg-white/[0.08]"
      }`}
    >
      {label}
    </button>
  );
}

export default function FilterDrawer({
  isOpen,
  queryType,
  onClose,
  onApply,
  onReset,
  resultCount,
  tiers,
  studyMode,
  onToggleTier,
  onStudyModeChange,
  schoolName,
  majorFilter,
  regionFilter,
  cityFilter,
  yearFilter,
  schoolTierFilter,
  candidateScoreFilter,
  onSchoolNameChange,
  onMajorFilterChange,
  onRegionFilterChange,
  onCityFilterChange,
  onYearFilterChange,
  onSchoolTierFilterChange,
  onCandidateScoreFilterChange,
  onlyHistoryBacked,
  onlyLongTrack,
  onlyWithReferenceLinks,
  hideMentorWarnings,
  onOnlyHistoryBackedChange,
  onOnlyLongTrackChange,
  onOnlyWithReferenceLinksChange,
  onHideMentorWarningsChange,
}: FilterDrawerProps) {
  const isAdjustments = queryType === "adjustments";

  return (
    <AnimatePresence>
      {isOpen ? (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[130] bg-black/45"
            onClick={onClose}
          />
          <motion.aside
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 26, stiffness: 220 }}
            className="fixed right-0 top-0 z-[140] flex h-full w-full max-w-[420px] flex-col border-l border-white/8 bg-[radial-gradient(circle_at_top,rgba(34,211,238,0.08),transparent_28%),linear-gradient(180deg,rgba(5,11,20,0.82),rgba(5,11,20,0.9))] shadow-[-24px_0_64px_rgba(0,0,0,0.48)] backdrop-blur-2xl"
          >
            <div className="flex items-center justify-between border-b border-white/10 p-6 text-white">
              <div>
                <h3 className="flex items-center gap-2 text-lg font-bold">
                  <Filter className="text-cyan-400" size={18} />
                  筛选与限定
                </h3>
                <p className="mt-1 text-sm text-slate-400">能藏进抽屉的条件，不再留在主页面。</p>
              </div>
              <button
                type="button"
                onClick={onClose}
                className="rounded-full bg-white/5 p-2 text-slate-400 transition-colors hover:text-white"
              >
                <X size={16} />
              </button>
            </div>

            <div className="flex-1 space-y-7 overflow-y-auto p-6 pb-28">
              <DrawerSection title="精确限定">
                <div className="grid gap-3">
                  <DrawerInput value={schoolName} onChange={onSchoolNameChange} placeholder="精确院校（可选）" />
                  <DrawerInput value={majorFilter} onChange={onMajorFilterChange} placeholder="精确专业 / 代码（可选）" />
                  {isAdjustments ? (
                    <>
                      <DrawerInput value={regionFilter} onChange={onRegionFilterChange} placeholder="地区（如 湖北、武汉）" />
                      <DrawerInput value={cityFilter} onChange={onCityFilterChange} placeholder="城市（如 武汉、上海）" />
                      <DrawerInput value={yearFilter} onChange={onYearFilterChange} placeholder="年份（如 2026）" />
                      <select
                        value={schoolTierFilter}
                        onChange={(event) => onSchoolTierFilterChange(event.target.value)}
                        className="rounded-2xl border border-white/5 bg-white/[0.05] px-4 py-3 text-sm text-white outline-none transition-all focus:border-cyan-400/15 focus:ring-1 focus:ring-cyan-500/45"
                      >
                        <option value="">院校类别（全部）</option>
                        <option value="985">985</option>
                        <option value="211">211</option>
                        <option value="双一流">双一流</option>
                        <option value="普本">普本</option>
                      </select>
                      <DrawerInput value={candidateScoreFilter} onChange={onCandidateScoreFilterChange} placeholder="你的分数（可选）" />
                    </>
                  ) : null}
                </div>
              </DrawerSection>

              {isAdjustments ? (
                <DrawerSection title="情报快筛">
                  <div className="flex flex-wrap gap-2">
                    <QuickFilterChip active={onlyHistoryBacked} onClick={() => onOnlyHistoryBackedChange(!onlyHistoryBacked)} label="有历史样本" />
                    <QuickFilterChip active={onlyLongTrack} onClick={() => onOnlyLongTrackChange(!onlyLongTrack)} label="连续活跃" />
                    <QuickFilterChip active={onlyWithReferenceLinks} onClick={() => onOnlyWithReferenceLinksChange(!onlyWithReferenceLinks)} label="带历史链接" />
                    <QuickFilterChip active={hideMentorWarnings} onClick={() => onHideMentorWarningsChange(!hideMentorWarnings)} label="排除导师预警" />
                  </div>
                </DrawerSection>
              ) : null}

              <DrawerSection title="结果裁剪">
                <div>
                  <div className="mb-3 text-sm font-semibold text-slate-200">院校层次</div>
                  <div className="flex flex-wrap gap-2">
                    {tierOptions.map((tier) => {
                      const active = tiers.includes(tier);
                      return (
                        <button
                          key={tier}
                          type="button"
                          onClick={() => onToggleTier(tier)}
                          className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-sm font-medium transition-all ${
                            active
                              ? "border-cyan-400 bg-cyan-500/20 text-cyan-300 shadow-[0_0_15px_rgba(6,182,212,0.16)]"
                              : "border-white/10 bg-white/[0.04] text-slate-400 hover:bg-white/[0.08]"
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
                  <div className="mb-3 text-sm font-semibold text-slate-200">学习方式</div>
                  <div className="grid grid-cols-3 gap-3 rounded-2xl border border-white/5 bg-white/[0.04] p-1">
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
                          {active ? <motion.div layoutId="studyMode" className="absolute inset-0 rounded-xl bg-white/10" /> : null}
                          <span className="relative z-10">{item.label}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              </DrawerSection>

              <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-sm text-slate-300">
                <div className="mb-1 text-[11px] uppercase tracking-[0.24em] text-slate-500">当前筛选</div>
                <div>层次：<span className="text-cyan-300">{tiers.length ? tiers.join(" / ") : "不限"}</span></div>
                <div>学习方式：<span className="text-cyan-300">{studyMode === "all" ? "不限" : studyMode === "fulltime" ? "全日制" : "非全日制"}</span></div>
                {isAdjustments ? (
                  <div className="mt-1">服务端快筛：<span className="text-cyan-300">{[
                    onlyHistoryBacked && "有历史样本",
                    onlyLongTrack && "连续活跃",
                    onlyWithReferenceLinks && "带历史链接",
                    hideMentorWarnings && "排除导师预警",
                  ].filter(Boolean).join(" / ") || "未启用"}</span></div>
                ) : null}
              </div>
            </div>

            <div className="sticky bottom-0 border-t border-white/10 bg-[linear-gradient(180deg,rgba(5,11,20,0.5),rgba(5,11,20,0.92))] p-6 pb-8 pt-5 shadow-[0_-24px_50px_rgba(0,0,0,0.24)] backdrop-blur-2xl">
              <div className="mb-2 flex gap-3">
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
                  onClick={onApply}
                  className="flex-[1.6] rounded-2xl bg-cyan-600 py-3 text-sm font-bold text-white shadow-[0_0_20px_rgba(6,182,212,0.25)] transition-all hover:bg-cyan-500 active:scale-[0.98]"
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
