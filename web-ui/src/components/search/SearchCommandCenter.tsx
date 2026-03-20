"use client";

import { type Dispatch, type SetStateAction, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Check, ChevronDown, Search, X } from "lucide-react";

export type SearchTab = "announcements" | "adjustments";
export type SchoolTier = "985/211" | "双一流" | "科研院所" | "普通本科";
export type LevelFilter = "不限" | SchoolTier;
export type StudyMode = "all" | "fulltime" | "parttime";

export type SearchCommandCenterFilters = {
  schoolName: string;
  major: string;
  region: string;
  city: string;
  year: string;
  level: LevelFilter;
  type: StudyMode;
  score: string;
  historyBackedOnly: boolean;
  longTrackOnly: boolean;
  referenceLinksOnly: boolean;
  hideMentorWarnings: boolean;
};

interface SearchCommandCenterProps {
  tab: SearchTab;
  setTab: (value: SearchTab) => void;
  keyword: string;
  setKeyword: (value: string) => void;
  filters: SearchCommandCenterFilters;
  setFilters: Dispatch<SetStateAction<SearchCommandCenterFilters>>;
  onSearch: (filterPatch?: Partial<SearchCommandCenterFilters>) => void;
}

type PopoverId = "region" | "year" | "level" | "type";

const filterOptions: Record<PopoverId, string[]> = {
  region: ["不限", "北京", "上海", "湖北", "广东", "江苏", "浙江", "四川", "陕西"],
  year: ["不限", "2026", "2025", "2024", "2023"],
  level: ["不限", "985/211", "双一流", "科研院所", "普通本科"],
  type: ["不限", "全日制", "非全日制"],
};

const quickFilters = [
  { key: "historyBackedOnly", label: "有历史样本" },
  { key: "longTrackOnly", label: "连续活跃" },
  { key: "referenceLinksOnly", label: "带历史链接" },
  { key: "hideMentorWarnings", label: "排除导师预警" },
] as const;

function mapStudyModeLabel(value: StudyMode) {
  if (value === "fulltime") return "全日制";
  if (value === "parttime") return "非全日制";
  return "不限";
}

function mapStudyModeValue(value: string): StudyMode {
  if (value === "全日制") return "fulltime";
  if (value === "非全日制") return "parttime";
  return "all";
}

function InlineInput({
  value,
  onChange,
  onSearch,
  placeholder,
  widthClass,
  inputMode,
  searchOnBlur = false,
}: {
  value: string;
  onChange: (value: string) => void;
  onSearch: () => void;
  placeholder: string;
  widthClass?: string;
  inputMode?: "text" | "numeric";
  searchOnBlur?: boolean;
}) {
  return (
    <input
      value={value}
      onChange={(event) => onChange(event.target.value)}
      onKeyDown={(event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          onSearch();
        }
      }}
      onBlur={() => {
        if (searchOnBlur && value.trim()) {
          onSearch();
        }
      }}
      inputMode={inputMode}
      placeholder={placeholder}
      className={`rounded-xl border border-white/5 bg-white/[0.05] px-3 py-2 text-xs text-white placeholder:text-slate-500 outline-none transition-all focus:border-cyan-400/20 focus:ring-1 focus:ring-cyan-500/40 ${widthClass ?? "w-28"}`}
    />
  );
}

export default function SearchCommandCenter({
  tab,
  setTab,
  keyword,
  setKeyword,
  filters,
  setFilters,
  onSearch,
}: SearchCommandCenterProps) {
  const [openPopover, setOpenPopover] = useState<PopoverId | null>(null);

  const activeFilterCount = useMemo(() => {
    let count = 0;
    if (filters.schoolName.trim()) count += 1;
    if (filters.major.trim()) count += 1;
    if (filters.region !== "不限") count += 1;
    if (filters.city.trim()) count += 1;
    if (filters.year.trim()) count += 1;
    if (filters.level !== "不限") count += 1;
    if (filters.type !== "all") count += 1;
    if (filters.score.trim()) count += 1;
    if (filters.historyBackedOnly) count += 1;
    if (filters.longTrackOnly) count += 1;
    if (filters.referenceLinksOnly) count += 1;
    if (filters.hideMentorWarnings) count += 1;
    return count;
  }, [filters]);

  const searchPlaceholder =
    tab === "adjustments"
      ? "输入院校、专业名或专业代码..."
      : "输入院校、学院或招生关键词...";

  function updatePopoverFilter(id: PopoverId, value: string) {
    const filterPatch: Partial<SearchCommandCenterFilters> = {
      region: id === "region" ? value : filters.region,
      year: id === "year" ? (value === "不限" ? "" : value) : filters.year,
      level: id === "level" ? (value as LevelFilter) : filters.level,
      type: id === "type" ? mapStudyModeValue(value) : filters.type,
    };
    setFilters((previous) => ({
      ...previous,
      ...filterPatch,
    }));
    setOpenPopover(null);
    onSearch(filterPatch);
  }

  return (
    <div className="relative z-30 mb-8">
      <div className="mb-5 flex justify-center">
        <div className="flex items-center gap-1 rounded-full border border-white/10 bg-white/[0.04] p-1 shadow-[0_18px_48px_rgba(0,0,0,0.22)] backdrop-blur-2xl">
          {[
            { id: "announcements", label: "公告检索" },
            { id: "adjustments", label: "调剂检索" },
          ].map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setTab(item.id as SearchTab)}
              className={`relative rounded-full px-6 py-2.5 text-sm font-bold transition-colors ${
                tab === item.id ? "text-white" : "text-slate-400 hover:text-white"
              }`}
            >
              {tab === item.id ? (
                <motion.div
                  layoutId="search-command-tab"
                  className="absolute inset-0 rounded-full bg-cyan-500/80 shadow-[0_0_24px_rgba(6,182,212,0.28)]"
                />
              ) : null}
              <span className="relative z-10">{item.label}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="overflow-visible rounded-[2rem] border border-white/10 bg-[linear-gradient(180deg,rgba(10,15,26,0.88),rgba(8,12,20,0.84))] shadow-[0_24px_80px_rgba(0,0,0,0.32)] backdrop-blur-2xl transition-colors hover:border-white/15">
        <div className="flex items-center gap-2 p-2">
          <Search className="ml-3 shrink-0 text-slate-400" size={20} />
          <input
            type="text"
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                onSearch();
              }
            }}
            placeholder={searchPlaceholder}
            className="min-w-0 flex-1 bg-transparent py-3 text-base text-white outline-none placeholder:text-slate-600 md:text-lg"
          />
          {keyword ? (
            <button
              type="button"
              onClick={() => setKeyword("")}
              className="rounded-full p-2 text-slate-500 transition-colors hover:text-white"
            >
              <X size={16} />
            </button>
          ) : null}
          <button
            type="button"
            onClick={() => onSearch()}
            className="rounded-[1.35rem] bg-white px-6 py-3 text-sm font-extrabold text-black transition-all hover:bg-cyan-400 hover:text-white active:scale-[0.98]"
          >
            检索
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-2.5 border-t border-white/5 bg-white/[0.02] px-5 py-3">
          <span className="mr-1 text-[11px] font-bold uppercase tracking-[0.2em] text-slate-500">
            精准过滤
          </span>

          {(
            [
              { id: "region", label: "地区", value: filters.region || "不限" },
              ...(tab === "adjustments"
                ? [
                    { id: "year", label: "年份", value: filters.year || "不限" },
                    { id: "level", label: "院校层次", value: filters.level || "不限" },
                    { id: "type", label: "学习方式", value: mapStudyModeLabel(filters.type) },
                  ]
                : []),
            ] as Array<{ id: PopoverId; label: string; value: string }>
          ).map((item) => (
            <div key={item.id} className="relative">
              <button
                type="button"
                onClick={() => setOpenPopover((current) => (current === item.id ? null : item.id))}
                className={`flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-medium transition-all ${
                  openPopover === item.id || item.value !== "不限"
                    ? "border-cyan-500/30 bg-cyan-500/10 text-cyan-200"
                    : "border-transparent bg-white/[0.05] text-slate-400 hover:bg-white/[0.08] hover:text-white"
                }`}
              >
                {item.label}: {item.value}
                <ChevronDown
                  size={14}
                  className={`transition-transform ${openPopover === item.id ? "rotate-180" : ""}`}
                />
              </button>

              <AnimatePresence>
                {openPopover === item.id ? (
                  <>
                    <div className="fixed inset-0 z-40" onClick={() => setOpenPopover(null)} />
                    <motion.div
                      initial={{ opacity: 0, y: 8, scale: 0.96 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, y: 4, scale: 0.96 }}
                      transition={{ duration: 0.14 }}
                      className="absolute left-0 top-full z-50 mt-2 w-48 rounded-2xl border border-white/10 bg-[#0b1220]/95 p-1.5 shadow-[0_24px_60px_rgba(0,0,0,0.45)] backdrop-blur-3xl"
                    >
                      {filterOptions[item.id].map((option) => {
                        const isActive = item.value === option;
                        return (
                          <button
                            key={option}
                            type="button"
                            onClick={() => updatePopoverFilter(item.id, option)}
                            className={`flex w-full items-center justify-between rounded-xl px-3 py-2 text-left text-sm transition-colors ${
                              isActive
                                ? "bg-cyan-500/16 font-semibold text-cyan-200"
                                : "text-slate-300 hover:bg-white/[0.06]"
                            }`}
                          >
                            {option}
                            {isActive ? <Check size={14} /> : null}
                          </button>
                        );
                      })}
                    </motion.div>
                  </>
                ) : null}
              </AnimatePresence>
            </div>
          ))}

              <InlineInput
                value={filters.schoolName}
                onChange={(value) => setFilters((previous) => ({ ...previous, schoolName: value }))}
                onSearch={() => onSearch({ schoolName: filters.schoolName })}
                placeholder={tab === "adjustments" ? "精确院校" : "院校限定"}
              />

          {tab === "adjustments" ? (
            <>
              <InlineInput
                value={filters.major}
                onChange={(value) => setFilters((previous) => ({ ...previous, major: value }))}
                onSearch={() => onSearch({ major: filters.major })}
                placeholder="精确专业 / 代码"
                widthClass="w-32"
              />
              <InlineInput
                value={filters.city}
                onChange={(value) => setFilters((previous) => ({ ...previous, city: value }))}
                onSearch={() => onSearch({ city: filters.city })}
                placeholder="城市"
                widthClass="w-24"
              />
              <InlineInput
                value={filters.score}
                onChange={(value) => setFilters((previous) => ({ ...previous, score: value }))}
                onSearch={() => onSearch({ score: filters.score })}
                placeholder="你的分数"
                widthClass="w-20"
                inputMode="numeric"
                searchOnBlur
              />
            </>
          ) : null}

          {tab === "adjustments" ? (
            <div className="ml-auto flex flex-wrap items-center gap-2">
              {quickFilters.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => {
                    const filterPatch = {
                      [item.key]: !filters[item.key],
                    } as Partial<SearchCommandCenterFilters>;
                    setFilters((previous) => ({
                      ...previous,
                      ...filterPatch,
                    }));
                    onSearch(filterPatch);
                  }}
                  className={`rounded-full border px-3 py-1.5 text-[11px] font-semibold transition-colors ${
                    filters[item.key]
                      ? "border-emerald-400/30 bg-emerald-500/12 text-emerald-200"
                      : "border-white/8 bg-white/[0.04] text-slate-400 hover:bg-white/[0.08] hover:text-white"
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          ) : null}
        </div>

        <div className="flex items-center justify-between px-5 pb-4 pt-1 text-[11px] text-slate-500">
          <span>
            {tab === "adjustments"
              ? "学校、专业、地区和快筛都在这一条里完成，不再弹出抽屉。"
              : "公告检索保持轻量，只保留院校限定和主关键词。"}
          </span>
          <span>{activeFilterCount > 0 ? `已启用 ${activeFilterCount} 个过滤条件` : "当前未叠加过滤条件"}</span>
        </div>
      </div>
    </div>
  );
}
