"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { Search, Target } from "lucide-react";
import { ApiError, SearchResponse, searchAdjustments, searchAnnouncements } from "@/lib/api";

export default function SearchPage() {
  const [queryType, setQueryType] = useState<"announcements" | "adjustments">("announcements");
  const [keywords, setKeywords] = useState("");
  const [schoolName, setSchoolName] = useState("");
  const [majorFilter, setMajorFilter] = useState("");
  const [regionFilter, setRegionFilter] = useState("");
  const [message, setMessage] = useState("");
  const [searchResult, setSearchResult] = useState<SearchResponse | null>(null);

  const [score, setScore] = useState("");
  const [major, setMajor] = useState("");
  const [result, setResult] = useState<{ percent: number; text: string } | null>(null);

  const searchMutation = useMutation({
    mutationFn: async (page: number) => {
      if (queryType === "announcements") {
        return searchAnnouncements({
          keywords: keywords.trim() || undefined,
          school_name: schoolName.trim() || undefined,
          page,
          page_size: 12,
        });
      }
      return searchAdjustments({
        keywords: keywords.trim() || undefined,
        school_name: schoolName.trim() || undefined,
        major: majorFilter.trim() || undefined,
        region: regionFilter.trim() || undefined,
        page,
        page_size: 12,
      });
    },
    onSuccess: (payload) => {
      setSearchResult(payload);
      if (payload.total === 0) {
        setMessage("未匹配到确切坐标，请尝试提取核心关键词。");
      } else {
        setMessage("");
      }
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        setMessage(`查询失败：${error.message}`);
      } else {
        setMessage("数据源响应超时，请稍后重连。");
      }
    },
  });

  const calculateMatch = () => {
    if (!score || !major) return;
    const diff =
      parseInt(score, 10) -
      (major === "工科" ? 273 : major === "理学" ? 279 : 346);
    setResult({
      percent: diff < 0 ? 5 : diff < 20 ? 45 : diff < 50 ? 75 : 95,
      text:
        diff < 0
          ? "低于国家A区线，建议重点关注B区偏远院校。"
          : diff < 50
            ? "初筛通过率较高，建议全力准备专业课复试。"
            : "高分段优势极大！可冲击优质调剂名额！",
    });
  };

  function triggerSearch(page = 1) {
    setMessage("");
    searchMutation.mutate(page);
  }

  const currentPage = searchResult?.page || 1;
  const totalPages = searchResult ? Math.max(1, Math.ceil(searchResult.total / searchResult.page_size)) : 1;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.98 }}
      transition={{ duration: 0.4 }}
      className="mx-auto max-w-6xl px-4 pb-20 pt-10"
    >
      <div className="mb-10 text-center">
        <h2 className="mb-4 text-4xl font-bold text-white">数据库全局检索</h2>
        <p className="font-mono text-sm text-slate-400">
          Indexed Records:{" "}
          <span className="text-cyan-400">{searchResult?.total ?? "点击检索后显示"}</span>
        </p>
      </div>

      <div className="mb-6 overflow-hidden rounded-3xl border border-white/10 bg-white/5 p-3 shadow-xl backdrop-blur-xl transition-colors hover:border-cyan-500/50">
        <div className="mb-3 grid grid-cols-2 gap-2 rounded-xl border border-white/10 bg-black/20 p-1 text-sm">
          <button
            type="button"
            className={`rounded-lg px-3 py-2 transition-colors ${
              queryType === "announcements" ? "bg-cyan-500 text-white" : "text-slate-300 hover:bg-white/10"
            }`}
            onClick={() => setQueryType("announcements")}
          >
            公告检索
          </button>
          <button
            type="button"
            className={`rounded-lg px-3 py-2 transition-colors ${
              queryType === "adjustments" ? "bg-cyan-500 text-white" : "text-slate-300 hover:bg-white/10"
            }`}
            onClick={() => setQueryType("adjustments")}
          >
            调剂检索
          </button>
        </div>
        <div className="flex items-center gap-2">
          <Search className="ml-2 text-slate-400" />
          <input
            value={keywords}
            onChange={(event) => setKeywords(event.target.value)}
            type="text"
            placeholder="输入公告关键词，如 调剂、复试、招生简章"
            className="w-full border-none bg-transparent py-4 text-lg text-white placeholder-slate-500 focus:outline-none"
          />
          <button
            onClick={() => triggerSearch(1)}
            disabled={searchMutation.isPending}
            className="rounded-2xl bg-white px-8 py-3 font-bold text-black transition-colors hover:bg-cyan-400 hover:text-white active:scale-95 disabled:cursor-not-allowed disabled:opacity-70"
          >
            {searchMutation.isPending ? "检索中..." : "检索"}
          </button>
        </div>
        <div className="mt-3 grid gap-2 md:grid-cols-4">
          <input
            value={schoolName}
            onChange={(event) => setSchoolName(event.target.value)}
            placeholder="院校名（可选）"
            className="rounded-xl border border-white/10 bg-black/30 px-4 py-2.5 text-sm text-white outline-none transition-colors focus:border-cyan-400"
          />
          <input
            value={majorFilter}
            onChange={(event) => setMajorFilter(event.target.value)}
            placeholder="专业（调剂模式可选）"
            className="rounded-xl border border-white/10 bg-black/30 px-4 py-2.5 text-sm text-white outline-none transition-colors focus:border-cyan-400"
          />
          <input
            value={regionFilter}
            onChange={(event) => setRegionFilter(event.target.value)}
            placeholder="地区（调剂模式可选）"
            className="rounded-xl border border-white/10 bg-black/30 px-4 py-2.5 text-sm text-white outline-none transition-colors focus:border-cyan-400"
          />
          <button
            type="button"
            onClick={() => {
              setKeywords("");
              setSchoolName("");
              setMajorFilter("");
              setRegionFilter("");
              setSearchResult(null);
              setMessage("");
            }}
            className="rounded-xl border border-white/20 bg-white/5 px-4 py-2.5 text-sm text-slate-200 transition-colors hover:bg-white/10"
          >
            清空筛选
          </button>
        </div>
      </div>

      {message ? (
        <div className="mb-8 rounded-2xl border border-white/10 bg-black/30 p-4 text-sm text-slate-300">
          {message}
        </div>
      ) : null}

      {searchResult ? (
        <div className="mb-12 space-y-4">
          {searchResult.items.length === 0 ? null : (
            <div className="grid gap-4 md:grid-cols-2">
              {searchResult.items.map((item) => (
                <a
                  key={item.id}
                  href={item.source_url || "#"}
                  target={item.source_url ? "_blank" : undefined}
                  rel={item.source_url ? "noopener noreferrer" : undefined}
                  className="rounded-2xl border border-white/10 bg-white/[0.04] p-5 shadow-lg backdrop-blur-xl transition-colors hover:border-cyan-400/50"
                >
                  <div className="mb-2 flex items-center justify-between gap-3">
                    <span className="rounded-md border border-white/15 bg-black/30 px-2 py-1 text-xs text-cyan-300">
                      {item.category === "announcement" ? "公告" : "调剂"}
                    </span>
                    <span className="font-mono text-xs text-slate-400">
                      {item.published_at
                        ? new Date(item.published_at).toLocaleString("zh-CN", {
                            hour12: false,
                          })
                        : "时间未知"}
                    </span>
                  </div>
                  <h3 className="mb-2 line-clamp-2 text-lg font-semibold text-white">{item.title}</h3>
                  <p className="line-clamp-2 text-sm text-slate-400">{item.summary || "暂无摘要"}</p>
                  <div className="mt-3 text-xs text-slate-300">
                    {item.school_name || "未知院校"}
                    {item.region ? ` · ${item.region}` : ""}
                    {item.major ? ` · ${item.major}` : ""}
                  </div>
                </a>
              ))}
            </div>
          )}
          <div className="flex items-center justify-between rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-sm">
            <span className="text-slate-300">
              第 {currentPage}/{totalPages} 页 · 共 {searchResult.total} 条
            </span>
            <div className="flex gap-2">
              <button
                disabled={currentPage <= 1 || searchMutation.isPending}
                onClick={() => triggerSearch(currentPage - 1)}
                className="rounded-lg border border-white/20 bg-white/5 px-3 py-1.5 text-slate-200 transition-colors hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-60"
              >
                上一页
              </button>
              <button
                disabled={currentPage >= totalPages || searchMutation.isPending}
                onClick={() => triggerSearch(currentPage + 1)}
                className="rounded-lg border border-white/20 bg-white/5 px-3 py-1.5 text-slate-200 transition-colors hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-60"
              >
                下一页
              </button>
            </div>
          </div>
        </div>
      ) : null}

      <div className="relative overflow-hidden rounded-3xl border border-cyan-500/20 bg-cyan-950/10 p-8 shadow-2xl backdrop-blur-xl">
        <div className="pointer-events-none absolute right-0 top-0 h-64 w-64 -translate-y-1/2 translate-x-1/2 rounded-full bg-cyan-500/10 blur-3xl" />
        <div className="relative z-10 flex flex-col items-center gap-8 md:flex-row">
          <div className="text-white md:w-1/3">
            <h3 className="mb-2 flex items-center gap-2 text-2xl font-bold">
              <Target className="text-cyan-400" /> 调剂雷达测算
            </h3>
            <p className="text-sm leading-relaxed text-slate-400">
              系统将比对往年国家线及院系均分，测算你的初筛通过率。
            </p>
          </div>
          <div className="flex w-full flex-col gap-4 sm:flex-row md:w-2/3">
            <input
              type="number"
              placeholder="初试总分"
              value={score}
              onChange={(event) => setScore(event.target.value)}
              className="w-full rounded-xl border border-white/10 bg-black/40 px-5 py-4 text-white outline-none transition-colors focus:border-cyan-400 sm:w-32"
            />
            <select
              value={major}
              onChange={(event) => setMajor(event.target.value)}
              className="flex-1 appearance-none rounded-xl border border-white/10 bg-black/40 px-5 py-4 text-white outline-none transition-colors focus:border-cyan-400"
            >
              <option value="" disabled>
                选择门类
              </option>
              <option value="工科">工科(不含照顾) - 历年均线约 273</option>
              <option value="理学">理学 - 历年均线约 279</option>
            </select>
            <button
              onClick={calculateMatch}
              className="whitespace-nowrap rounded-xl bg-cyan-500 px-8 py-4 font-bold text-white shadow-[0_0_15px_rgba(6,182,212,0.3)] transition-all hover:bg-cyan-400 active:scale-95"
            >
              测算胜率
            </button>
          </div>
        </div>

        <AnimatePresence>
          {result ? (
            <motion.div
              initial={{ height: 0, opacity: 0, marginTop: 0 }}
              animate={{ height: "auto", opacity: 1, marginTop: 32 }}
              exit={{ height: 0, opacity: 0, marginTop: 0 }}
              className="overflow-hidden rounded-2xl border border-white/5 bg-black/40 p-6"
            >
              <div className="mb-3 flex items-end justify-between">
                <span className="text-sm text-slate-300">历史大数据预估通过率：</span>
                <span className="font-mono text-4xl font-bold text-cyan-400">
                  {result.percent}%
                </span>
              </div>
              <div className="h-4 w-full overflow-hidden rounded-full border border-white/5 bg-white/5 p-0.5">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${result.percent}%` }}
                  transition={{ duration: 1.2, ease: "easeOut" }}
                  className="h-full rounded-full bg-gradient-to-r from-blue-500 to-cyan-400 shadow-[0_0_10px_rgba(6,182,212,0.5)]"
                />
              </div>
              <p className="mt-4 font-mono text-sm text-slate-400">{result.text}</p>
            </motion.div>
          ) : null}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}
