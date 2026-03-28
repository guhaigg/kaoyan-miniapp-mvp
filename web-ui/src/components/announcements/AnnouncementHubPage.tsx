"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { CalendarRange, ChevronRight, FileText, Search } from "lucide-react";
import { fetchAnnouncementResults } from "@/api/search";
import { buildAnnouncementDetailHref } from "@/components/layout/site-navigation";
import {
  buildAnnouncementMeta,
  buildAnnouncementSearchPayload,
  parseAnnouncementPageState,
  type AnnouncementPageState,
} from "./announcement-page-data";

const emptyStateCopy = {
  title: "当前筛选没有命中公告",
  detail: "可以放宽学校、时间或标签条件，或者回到首页先看最新情报流。",
};

export default function AnnouncementHubPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const pageState = useMemo(
    () => parseAnnouncementPageState(new URLSearchParams(searchParams.toString())),
    [searchParams],
  );
  const [draft, setDraft] = useState<AnnouncementPageState>(pageState);

  useEffect(() => {
    setDraft(pageState);
  }, [pageState]);

  const payload = useMemo(() => buildAnnouncementSearchPayload(pageState), [pageState]);
  const announcementQuery = useQuery({
    queryKey: ["announcements", payload],
    queryFn: () => fetchAnnouncementResults(payload),
  });

  function pushState(next: AnnouncementPageState) {
    const params = new URLSearchParams();
    if (next.keywords.trim()) params.set("keywords", next.keywords.trim());
    if (next.schoolName.trim()) params.set("school_name", next.schoolName.trim());
    next.systemTags.forEach((tag) => params.append("system_tags", tag));
    if (next.startDate) params.set("start_date", next.startDate);
    if (next.endDate) params.set("end_date", next.endDate);
    if (next.page > 1) params.set("page", String(next.page));
    const query = params.toString();
    router.push(query ? `/announcements?${query}` : "/announcements");
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    pushState({ ...draft, page: 1 });
  }

  function handleQuickTag(tag: string) {
    const exists = draft.systemTags.includes(tag);
    const nextTags = exists ? draft.systemTags.filter((item) => item !== tag) : [...draft.systemTags, tag];
    setDraft((current) => ({ ...current, systemTags: nextTags }));
  }

  const availableTags = announcementQuery.data?.available_system_tags || [];

  return (
    <div className="mx-auto w-full max-w-[1680px] px-6 pb-16 pt-8">
      <section className="rounded-[2rem] border border-slate-200/70 bg-white/90 p-6 shadow-[0_24px_80px_rgba(15,23,42,0.08)] backdrop-blur-xl">
        <div className="flex flex-col gap-6 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <div className="text-[11px] font-bold uppercase tracking-[0.22em] text-cyan-600">Announcement Index</div>
            <h1 className="mt-2 text-3xl font-black tracking-tight text-slate-900">公告汇总</h1>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-500">
              首页风格下的正式高级检索页。这里负责收敛公告筛选条件、承接首页情报流入口，并把结果送入独立详情页。
            </p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-right">
            <div className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Results</div>
            <div className="mt-1 text-2xl font-black text-slate-900">{announcementQuery.data?.total ?? 0}</div>
            <div className="mt-1 text-xs text-slate-500">当前页 {announcementQuery.data?.page ?? pageState.page}</div>
          </div>
        </div>

        <div className="mt-6 grid gap-6 xl:grid-cols-[340px_minmax(0,1fr)]">
          <aside className="space-y-4 rounded-[1.5rem] border border-slate-200 bg-slate-50/80 p-4">
            <form onSubmit={handleSubmit} className="space-y-4">
              <label className="block">
                <div className="mb-2 text-[11px] font-bold uppercase tracking-[0.2em] text-slate-400">关键词</div>
                <div className="flex items-center rounded-2xl border border-slate-200 bg-white px-4 py-3">
                  <Search size={16} className="mr-2 text-slate-400" />
                  <input
                    value={draft.keywords}
                    onChange={(event) => setDraft((current) => ({ ...current, keywords: event.target.value }))}
                    placeholder="输入公告关键词"
                    className="w-full bg-transparent text-sm text-slate-800 outline-none placeholder:text-slate-400"
                  />
                </div>
              </label>

              <label className="block">
                <div className="mb-2 text-[11px] font-bold uppercase tracking-[0.2em] text-slate-400">院校</div>
                <input
                  value={draft.schoolName}
                  onChange={(event) => setDraft((current) => ({ ...current, schoolName: event.target.value }))}
                  placeholder="例如 浙江大学"
                  className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800 outline-none placeholder:text-slate-400"
                />
              </label>

              <div className="space-y-3">
                <div className="text-[11px] font-bold uppercase tracking-[0.2em] text-slate-400">系统标签</div>
                <div className="flex flex-wrap gap-2">
                  {availableTags.slice(0, 8).map((tag) => (
                    <button
                      key={tag}
                      type="button"
                      onClick={() => handleQuickTag(tag)}
                      className={`rounded-full px-3 py-1.5 text-xs font-semibold transition-colors ${
                        draft.systemTags.includes(tag)
                          ? "bg-slate-900 text-white"
                          : "border border-slate-200 bg-white text-slate-600 hover:border-cyan-200 hover:text-cyan-700"
                      }`}
                    >
                      {tag}
                    </button>
                  ))}
                  {!availableTags.length ? <span className="text-xs text-slate-400">当前结果暂无可用系统标签</span> : null}
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
                <label className="block">
                  <div className="mb-2 text-[11px] font-bold uppercase tracking-[0.2em] text-slate-400">开始日期</div>
                  <input
                    type="date"
                    value={draft.startDate}
                    onChange={(event) => setDraft((current) => ({ ...current, startDate: event.target.value }))}
                    className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800 outline-none"
                  />
                </label>
                <label className="block">
                  <div className="mb-2 text-[11px] font-bold uppercase tracking-[0.2em] text-slate-400">结束日期</div>
                  <input
                    type="date"
                    value={draft.endDate}
                    onChange={(event) => setDraft((current) => ({ ...current, endDate: event.target.value }))}
                    className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800 outline-none"
                  />
                </label>
              </div>

              <button
                type="submit"
                className="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-slate-900 px-4 py-3 text-sm font-bold text-white transition-colors hover:bg-slate-800"
              >
                执行检索
                <ChevronRight size={15} />
              </button>
            </form>
          </aside>

          <div className="space-y-4 rounded-[1.5rem] border border-slate-200 bg-white/80 p-4">
            <div className="flex items-center justify-between gap-3 rounded-2xl border border-slate-200/80 bg-slate-50 px-4 py-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-700">
                <CalendarRange size={15} className="text-cyan-600" />
                {pageState.startDate || pageState.endDate
                  ? `时间范围 ${pageState.startDate || "不限"} - ${pageState.endDate || "不限"}`
                  : "当前未设置时间范围"}
              </div>
              <div className="text-xs text-slate-500">每页 12 条</div>
            </div>

            {announcementQuery.isLoading ? (
              Array.from({ length: 6 }, (_, index) => (
                <div key={index} className="h-[154px] animate-pulse rounded-[1.6rem] border border-slate-100 bg-slate-50/70" />
              ))
            ) : announcementQuery.data?.items.length ? (
              announcementQuery.data.items.map((item) => {
                const meta = buildAnnouncementMeta(item);
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => router.push(buildAnnouncementDetailHref(item.id))}
                    className="group block w-full rounded-[1.6rem] border border-slate-200/80 bg-white p-5 text-left transition-all hover:border-cyan-300 hover:shadow-[0_14px_40px_rgba(6,182,212,0.08)]"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <div className="mb-2 flex flex-wrap items-center gap-2 text-[11px] text-slate-400">
                          <span className="inline-flex items-center gap-1 rounded-full bg-cyan-50 px-2.5 py-1 font-semibold text-cyan-700">
                            <FileText size={12} />
                            {item.notice_kind || item.channel_label || "公告"}
                          </span>
                          <span>{meta.school}</span>
                          {meta.department ? <span>· {meta.department}</span> : null}
                        </div>
                        <h2 className="text-lg font-black text-slate-900 transition-colors group-hover:text-cyan-700">
                          {meta.title}
                        </h2>
                        <p className="mt-3 line-clamp-3 text-sm leading-7 text-slate-500">{meta.summary}</p>
                      </div>
                      <div className="shrink-0 text-right">
                        <div className="text-xs font-semibold text-slate-400">{meta.time ? new Date(meta.time).toLocaleDateString("zh-CN") : "未知时间"}</div>
                        <div className="mt-6 inline-flex h-10 w-10 items-center justify-center rounded-full border border-slate-200 bg-slate-50 text-slate-500 transition-colors group-hover:border-cyan-200 group-hover:text-cyan-700">
                          <ChevronRight size={16} />
                        </div>
                      </div>
                    </div>
                    <div className="mt-4 flex flex-wrap gap-2">
                      {meta.tags.length ? meta.tags.map((tag) => (
                        <span key={`${item.id}-${tag}`} className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] text-slate-500">
                          {tag}
                        </span>
                      )) : <span className="text-xs text-slate-400">暂无标签</span>}
                    </div>
                  </button>
                );
              })
            ) : (
              <div className="rounded-[1.6rem] border border-dashed border-slate-200 bg-slate-50/60 px-6 py-12 text-center">
                <div className="text-base font-bold text-slate-700">{emptyStateCopy.title}</div>
                <p className="mt-3 text-sm leading-7 text-slate-500">{emptyStateCopy.detail}</p>
              </div>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
