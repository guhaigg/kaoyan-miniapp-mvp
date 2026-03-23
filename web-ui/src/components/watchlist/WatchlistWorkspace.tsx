"use client";

import Link from "next/link";
import { useDeferredValue, useEffect, useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { BellRing, ChevronRight, Compass, FolderKanban, Layers3, Radar, Search, Star } from "lucide-react";
import {
  ApiError,
  MonitorScopeDepartmentItem,
  MonitorScopeSectionItem,
  MonitorTargetItem,
  NotificationEventItem,
  SchoolSuggestItem,
  SubscriptionItem,
} from "@/lib/api";
import { useAppStore } from "@/lib/store";
import {
  useAddSubscriptionMutation,
  useDeleteSubscriptionMutation,
  useSubscriptionsQuery,
} from "@/hooks/useSubscriptions";
import {
  useAddMonitorTargetMutation,
  useMonitorScopeDepartmentsQuery,
  useDeleteMonitorTargetMutation,
  useMonitorScopeSectionsQuery,
  useSchoolSuggestionsQuery,
  useMonitorTargetsQuery,
} from "@/hooks/useMonitoringTargets";
import { useWatchlistNoticesQuery } from "@/hooks/useNotifications";

type WorkspaceMode = "drawer" | "page";
type WatchType = "school" | "department" | "section" | "major" | "keyword" | "region";
type EntryFilterKey = "all" | "school" | "department" | "section" | "major" | "keyword" | "region" | "radar";
type WatchEntry =
  | ({ kind: "subscription" } & SubscriptionItem)
  | ({ kind: "monitor" } & MonitorTargetItem);

type WatchlistWorkspaceProps = {
  mode: WorkspaceMode;
  onNavigate?: () => void;
};

const DRAWER_PREVIEW_LIMIT = 6;

export default function WatchlistWorkspace({ mode, onNavigate }: WatchlistWorkspaceProps) {
  const { portalAuth } = useAppStore();
  const [message, setMessage] = useState("");
  const [watchType, setWatchType] = useState<WatchType>("school");
  const [watchValue, setWatchValue] = useState("");
  const [scopeSchoolName, setScopeSchoolName] = useState("");
  const [scopeDepartmentName, setScopeDepartmentName] = useState("");
  const [scopeSectionName, setScopeSectionName] = useState("");
  const [selectedSchoolId, setSelectedSchoolId] = useState<string | null>(null);
  const [selectedDepartmentId, setSelectedDepartmentId] = useState<string | null>(null);
  const [selectedSectionId, setSelectedSectionId] = useState<string | null>(null);
  const [entryFilter, setEntryFilter] = useState<EntryFilterKey>("all");
  const [entryQuery, setEntryQuery] = useState("");
  const canManageScopeTargets = Boolean(portalAuth?.isPremium || portalAuth?.isAdmin);
  const deferredSchoolName = useDeferredValue(scopeSchoolName.trim());
  const deferredDepartmentName = useDeferredValue(scopeDepartmentName.trim());
  const deferredSectionName = useDeferredValue(scopeSectionName.trim());
  const deferredEntryQuery = useDeferredValue(entryQuery.trim().toLowerCase());
  const isScopeWatchTypeValue = isScopeWatchType(watchType);

  useEffect(() => {
    if (!canManageScopeTargets && isScopeWatchTypeValue) {
      setWatchType("major");
    }
  }, [canManageScopeTargets, isScopeWatchTypeValue]);

  const subscriptionsQuery = useSubscriptionsQuery(Boolean(portalAuth));
  const monitorTargetsQuery = useMonitorTargetsQuery(Boolean(portalAuth && canManageScopeTargets));
  const realtimeNoticesQuery = useWatchlistNoticesQuery(Boolean(portalAuth));
  const schoolSuggestionsQuery = useSchoolSuggestionsQuery(
    {
      q: deferredSchoolName || undefined,
      limit: 8,
    },
    Boolean(portalAuth && canManageScopeTargets && isScopeWatchTypeValue && deferredSchoolName),
  );
  const departmentSuggestionsQuery = useMonitorScopeDepartmentsQuery(
    {
      school_name: deferredSchoolName || undefined,
      department_name: deferredDepartmentName || undefined,
      limit: 8,
    },
    Boolean(
      portalAuth &&
        canManageScopeTargets &&
        (watchType === "department" || watchType === "section") &&
        (deferredSchoolName || deferredDepartmentName),
    ),
  );
  const sectionLookupQuery = useMonitorScopeSectionsQuery(
    {
      school_name: deferredSchoolName || undefined,
      department_name: deferredDepartmentName || undefined,
      section_name: deferredSectionName || undefined,
      limit: 10,
    },
    Boolean(
      portalAuth &&
        canManageScopeTargets &&
        watchType === "section" &&
        (deferredSchoolName || deferredDepartmentName || deferredSectionName),
    ),
  );

  const createSubscriptionMutation = useAddSubscriptionMutation();
  const deleteSubscriptionMutation = useDeleteSubscriptionMutation();
  const createMonitorTargetMutation = useAddMonitorTargetMutation();
  const deleteMonitorTargetMutation = useDeleteMonitorTargetMutation();

  const watchEntries = buildWatchEntries(subscriptionsQuery.data?.items || [], monitorTargetsQuery.data?.items || []);
  const recentSignalOverview = monitorTargetsQuery.data?.recent_signal_overview || null;
  const schoolSuggestions = schoolSuggestionsQuery.data?.items || [];
  const departmentSuggestions = departmentSuggestionsQuery.data?.items || [];
  const sectionSuggestions = sectionLookupQuery.data?.items || [];
  const filteredEntries = watchEntries.filter((item) => {
    if (entryFilter !== "all" && getEntryFilterKey(item) !== entryFilter) {
      return false;
    }
    if (!deferredEntryQuery) {
      return true;
    }
    const haystack = [
      item.kind === "monitor" ? item.display_label : item.display_label || item.value,
      item.kind === "monitor" ? item.school_name : item.target_university,
      item.kind === "monitor" ? item.department_name : item.target_department_name,
      item.kind === "monitor" ? item.site_section_name : null,
      item.kind === "subscription" ? item.value : null,
      item.kind === "subscription" ? item.source_title : null,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.includes(deferredEntryQuery);
  });
  const visibleEntries = mode === "drawer" ? filteredEntries.slice(0, DRAWER_PREVIEW_LIMIT) : filteredEntries;
  const hiddenEntryCount = Math.max(0, filteredEntries.length - visibleEntries.length);
  const monitorCount = watchEntries.filter((item) => item.kind === "monitor").length;
  const subscriptionCount = watchEntries.filter((item) => item.kind === "subscription").length;
  const latestNoticeCount = realtimeNoticesQuery.data?.length || 0;

  function resetScopeDraft() {
    setScopeSchoolName("");
    setScopeDepartmentName("");
    setScopeSectionName("");
    setSelectedSchoolId(null);
    setSelectedDepartmentId(null);
    setSelectedSectionId(null);
  }

  function handleScopeSchoolInputChange(nextValue: string) {
    setScopeSchoolName(nextValue);
    setSelectedSchoolId(null);
    setSelectedDepartmentId(null);
    setSelectedSectionId(null);
  }

  function handleScopeDepartmentInputChange(nextValue: string) {
    setScopeDepartmentName(nextValue);
    setSelectedDepartmentId(null);
    setSelectedSectionId(null);
  }

  function handleScopeSectionInputChange(nextValue: string) {
    setScopeSectionName(nextValue);
    setSelectedSectionId(null);
  }

  function selectSchoolSuggestion(item: SchoolSuggestItem) {
    setSelectedSchoolId(item.id);
    setScopeSchoolName(item.name);
    setSelectedDepartmentId(null);
    setSelectedSectionId(null);
  }

  function selectDepartmentSuggestion(item: MonitorScopeDepartmentItem) {
    setSelectedDepartmentId(item.id);
    setScopeDepartmentName(item.name);
    if (item.school_id) {
      setSelectedSchoolId(item.school_id);
    }
    if (item.school_name) {
      setScopeSchoolName(item.school_name);
    }
    setSelectedSectionId(null);
  }

  function selectSectionSuggestion(item: MonitorScopeSectionItem) {
    setSelectedSectionId(item.id);
    setScopeSectionName(item.name);
    if (item.school_id) {
      setSelectedSchoolId(item.school_id);
    }
    if (item.school_name) {
      setScopeSchoolName(item.school_name);
    }
    if (item.department_id) {
      setSelectedDepartmentId(item.department_id);
    }
    if (item.department_name) {
      setScopeDepartmentName(item.department_name);
    }
  }

  async function handleCreateSubscription() {
    if (watchType === "school" || watchType === "department" || watchType === "section") {
      if (!canManageScopeTargets) {
        setMessage("学校、学院、栏目级关注仅高级用户或管理员可用。");
        return;
      }

      const schoolName = scopeSchoolName.trim();
      const departmentName = scopeDepartmentName.trim();
      const sectionName = scopeSectionName.trim();
      const matchedSchool = selectedSchoolId
        ? null
        : findExactNameMatch(schoolName, schoolSuggestions, (item) => item.name);
      const matchedDepartment = selectedDepartmentId
        ? null
        : findExactNameMatch(departmentName, departmentSuggestions, (item) => item.name);
      const matchedSection = selectedSectionId
        ? null
        : findExactNameMatch(sectionName, sectionSuggestions, (item) => item.name);

      const resolvedSchoolId =
        selectedSchoolId || matchedSection?.school_id || matchedDepartment?.school_id || matchedSchool?.id || undefined;
      const resolvedDepartmentId =
        selectedDepartmentId || matchedSection?.department_id || matchedDepartment?.id || undefined;
      const resolvedSectionId = selectedSectionId || matchedSection?.id || undefined;

      if (watchType === "school" && !schoolName) {
        setMessage("请输入学校名称");
        return;
      }
      if (watchType === "department" && (!schoolName || !departmentName)) {
        setMessage("学院级关注需要同时填写学校和学院");
        return;
      }
      if (watchType === "section" && !selectedSectionId && !sectionName) {
        setMessage("请输入栏目名称，或从下方候选栏目里选择一个");
        return;
      }

      try {
        setMessage("");
        await createMonitorTargetMutation.mutateAsync({
          scope_type: watchType,
          school_id: resolvedSchoolId,
          school_name: resolvedSchoolId ? undefined : schoolName || undefined,
          department_id: resolvedDepartmentId,
          department_name: resolvedDepartmentId ? undefined : departmentName || undefined,
          site_section_id: resolvedSectionId,
          site_section_name: resolvedSectionId ? undefined : sectionName || undefined,
          check_interval_minutes: 60,
        });
        resetScopeDraft();
        setMessage("关注已加入雷达。");
      } catch (error) {
        if (error instanceof ApiError) {
          setMessage(`操作失败：${error.message}`);
        } else {
          setMessage("操作失败，请稍后重试");
        }
      }
      return;
    }

    const value = watchValue.trim();
    if (!value) {
      setMessage("请输入你要关注的关键词或院校");
      return;
    }
    try {
      setMessage("");
      await createSubscriptionMutation.mutateAsync({
        subscription_type: watchType,
        value,
        category: "all",
      });
      setWatchValue("");
      setMessage("卡片已归档。");
    } catch (error) {
      if (error instanceof ApiError) {
        setMessage(`操作失败：${error.message}`);
      } else {
        setMessage("操作失败，请稍后重试");
      }
    }
  }

  async function handleDeleteSubscription(subscriptionId: string) {
    try {
      setMessage("");
      await deleteSubscriptionMutation.mutateAsync(subscriptionId);
      setMessage("已移出归档。");
    } catch (error) {
      if (error instanceof ApiError) {
        setMessage(`操作失败：${error.message}`);
      } else {
        setMessage("操作失败，请稍后重试");
      }
    }
  }

  async function handleDeleteMonitorTarget(targetId: string) {
    try {
      setMessage("");
      await deleteMonitorTargetMutation.mutateAsync(targetId);
      setMessage("已移出归档。");
    } catch (error) {
      if (error instanceof ApiError) {
        setMessage(`操作失败：${error.message}`);
      } else {
        setMessage("操作失败，请稍后重试");
      }
    }
  }

  const composerCard = (
    <section
      className={`overflow-hidden rounded-[28px] border border-white/10 bg-[linear-gradient(180deg,rgba(13,20,34,0.96),rgba(7,11,19,0.96))] shadow-[0_24px_80px_rgba(0,0,0,0.35)] ${
        mode === "page" ? "p-5" : "p-4"
      }`}
    >
      <div className="mb-4 flex items-center justify-between">
        <div>
          <div className="text-[10px] uppercase tracking-[0.32em] text-cyan-300/80">Watch Composer</div>
          <div className="mt-1 text-lg font-semibold text-white">添加新关注</div>
        </div>
        <div className="rounded-full border border-cyan-400/20 bg-cyan-500/10 px-3 py-1 text-[11px] font-medium text-cyan-100">
          {watchEntries.length} 项已入库
        </div>
      </div>

      <div className="mb-3 grid grid-cols-3 gap-2">
        {[
          { key: "school", label: "学校" },
          { key: "department", label: "学院" },
          { key: "section", label: "栏目" },
          { key: "major", label: "专业" },
          { key: "keyword", label: "关键词" },
          { key: "region", label: "地区" },
        ].map((item) => (
          <button
            key={item.key}
            type="button"
            disabled={
              (item.key === "school" || item.key === "department" || item.key === "section") && !canManageScopeTargets
            }
            onClick={() => setWatchType(item.key as WatchType)}
            className={`rounded-2xl px-3 py-2 text-xs transition-colors ${
              watchType === item.key
                ? "bg-cyan-500 text-white shadow-[0_0_24px_rgba(6,182,212,0.3)]"
                : "bg-white/5 text-slate-300 hover:bg-white/10"
            } ${
              (item.key === "school" || item.key === "department" || item.key === "section") && !canManageScopeTargets
                ? "cursor-not-allowed opacity-50 hover:bg-white/5"
                : ""
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      {!canManageScopeTargets ? (
        <div className="mb-3 rounded-2xl border border-amber-500/20 bg-amber-500/10 p-3">
          <div className="text-[11px] leading-6 text-amber-100">
            学校、学院、栏目级关注只对高级用户开放。普通用户仍可追踪专业、关键词和地区。
          </div>
          <Link
            href="/account/billing"
            onClick={onNavigate}
            className="mt-3 inline-flex rounded-xl border border-amber-300/25 bg-black/25 px-3 py-2 text-xs font-semibold text-amber-100 transition-colors hover:bg-black/35"
          >
            开通高级会员
          </Link>
        </div>
      ) : null}

      {watchType === "school" || watchType === "department" || watchType === "section" ? (
        <div className="space-y-2.5">
          <input
            value={scopeSchoolName}
            onChange={(event) => handleScopeSchoolInputChange(event.target.value)}
            placeholder="学校名称，例如：电子科技大学"
            className="w-full rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-sm text-white outline-none transition-colors focus:border-cyan-400"
          />
          <div className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-xs leading-6 text-slate-400">
            候选列表只是提速和纠偏，不需要先点选；直接输入后添加，后端也会自动尝试解析学校、学院和栏目。
          </div>
          {schoolSuggestionsQuery.isLoading ? (
            <div className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-xs text-slate-300">
              正在匹配学校候选...
            </div>
          ) : null}
          {schoolSuggestions.length ? (
            <div className="max-h-40 space-y-2 overflow-y-auto rounded-2xl border border-white/10 bg-black/25 p-2">
              {schoolSuggestions.map((item) => {
                const active = selectedSchoolId === item.id;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => selectSchoolSuggestion(item)}
                    className={`block w-full rounded-xl border px-3 py-3 text-left transition-colors ${
                      active ? "border-cyan-400/40 bg-cyan-500/10" : "border-white/10 bg-white/5 hover:bg-white/10"
                    }`}
                  >
                    <div className="text-sm font-medium text-white">{item.name}</div>
                    <div className="mt-1 text-[11px] text-slate-400">{item.province || "学校候选"}</div>
                  </button>
                );
              })}
            </div>
          ) : null}
          {watchType === "department" || watchType === "section" ? (
            <>
              <input
                value={scopeDepartmentName}
                onChange={(event) => handleScopeDepartmentInputChange(event.target.value)}
                placeholder={watchType === "department" ? "学院名称，例如：计算机学院" : "学院名称，可选"}
                className="w-full rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-sm text-white outline-none transition-colors focus:border-cyan-400"
              />
              {departmentSuggestionsQuery.isLoading ? (
                <div className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-xs text-slate-300">
                  正在匹配学院候选...
                </div>
              ) : null}
              {departmentSuggestions.length ? (
                <div className="max-h-40 space-y-2 overflow-y-auto rounded-2xl border border-white/10 bg-black/25 p-2">
                  {departmentSuggestions.map((item) => {
                    const active = selectedDepartmentId === item.id;
                    return (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => selectDepartmentSuggestion(item)}
                        className={`block w-full rounded-xl border px-3 py-3 text-left transition-colors ${
                          active
                            ? "border-cyan-400/40 bg-cyan-500/10"
                            : "border-white/10 bg-white/5 hover:bg-white/10"
                        }`}
                      >
                        <div className="text-sm font-medium text-white">{item.name}</div>
                        <div className="mt-1 text-[11px] text-slate-400">
                          {[item.school_name, item.department_type].filter(Boolean).join(" · ")}
                        </div>
                      </button>
                    );
                  })}
                </div>
              ) : null}
            </>
          ) : null}
          {watchType === "section" ? (
            <>
              <input
                value={scopeSectionName}
                onChange={(event) => handleScopeSectionInputChange(event.target.value)}
                placeholder="栏目名称或关键词，例如：通知公告 / 招生动态"
                className="w-full rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-sm text-white outline-none transition-colors focus:border-cyan-400"
              />
              {sectionLookupQuery.isLoading ? (
                <div className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-xs text-slate-300">
                  正在匹配栏目候选...
                </div>
              ) : null}
              {sectionSuggestions.length ? (
                <div className="max-h-44 space-y-2 overflow-y-auto rounded-2xl border border-white/10 bg-black/25 p-2">
                  {sectionSuggestions.map((item) => {
                    const active = selectedSectionId === item.id;
                    return (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => selectSectionSuggestion(item)}
                        className={`block w-full rounded-xl border px-3 py-3 text-left transition-colors ${
                          active
                            ? "border-cyan-400/40 bg-cyan-500/10"
                            : "border-white/10 bg-white/5 hover:bg-white/10"
                        }`}
                      >
                        <div className="text-sm font-medium text-white">{item.name}</div>
                        <div className="mt-1 text-[11px] text-slate-400">
                          {[item.school_name, item.department_name, item.discovery_category].filter(Boolean).join(" · ")}
                        </div>
                      </button>
                    );
                  })}
                </div>
              ) : null}
            </>
          ) : null}
          <button
            type="button"
            disabled={createMonitorTargetMutation.isPending}
            onClick={handleCreateSubscription}
            className="w-full rounded-2xl bg-cyan-500 px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-cyan-400 disabled:opacity-70"
          >
            {createMonitorTargetMutation.isPending ? "正在加入..." : "直接添加关注"}
          </button>
        </div>
      ) : (
        <div className="flex gap-2">
          <input
            value={watchValue}
            onChange={(event) => setWatchValue(event.target.value)}
            placeholder="例如：0854 / 复试线 / 华中地区"
            className="flex-1 rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-sm text-white outline-none transition-colors focus:border-cyan-400"
          />
          <button
            type="button"
            disabled={createSubscriptionMutation.isPending}
            onClick={handleCreateSubscription}
            className="rounded-2xl bg-cyan-500 px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-cyan-400 disabled:opacity-70"
          >
            {createSubscriptionMutation.isPending ? "加入中..." : "添加"}
          </button>
        </div>
      )}
      {message ? (
        <div className="mt-3 rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-xs text-slate-300">
          {message}
        </div>
      ) : null}
    </section>
  );

  const realtimeCard = (
    <section
      className={`rounded-[28px] border border-white/10 bg-white/[0.04] shadow-[0_18px_60px_rgba(0,0,0,0.28)] ${
        mode === "page" ? "p-5" : "p-4"
      }`}
    >
      <div className="mb-3 flex items-center justify-between">
        <div>
          <div className="text-[10px] uppercase tracking-[0.32em] text-cyan-300/80">Live Radar</div>
          <div className="mt-1 text-lg font-semibold text-white">实时情报流</div>
        </div>
        <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] text-slate-300">
          {latestNoticeCount} 条
        </div>
      </div>
      {realtimeNoticesQuery.isLoading ? (
        <div className="text-xs text-slate-300">探针巡航中，拉取最新节点...</div>
      ) : realtimeNoticesQuery.data?.length ? (
        <div className="space-y-2">
          <AnimatePresence initial={false}>
            {realtimeNoticesQuery.data.slice(0, mode === "page" ? 8 : 4).map((item) => {
              const urgent = isUrgentNotice(item);
              return (
                <motion.div
                  key={item.id}
                  layout
                  initial={{ opacity: 0, y: -18, scale: 0.96 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  transition={{
                    layout: { type: "spring", bounce: 0.35, duration: 0.5 },
                    opacity: { duration: 0.25 },
                    y: { type: "spring", bounce: 0.45, duration: 0.5 },
                  }}
                  className={`rounded-2xl border p-3 ${
                    urgent ? "border-orange-500/35 bg-orange-950/25" : "border-white/10 bg-white/5"
                  }`}
                >
                  <div className={`mb-2 flex items-center gap-2 text-[11px] font-medium ${urgent ? "text-orange-300" : "text-cyan-300"}`}>
                    <BellRing size={12} />
                    {urgent ? "紧急异动" : "常规监控"}
                  </div>
                  <div className="text-sm font-medium leading-6 text-white">{formatNoticeTitle(item)}</div>
                  <div className="mt-1 text-xs leading-5 text-slate-400">{formatNoticeSubline(item)}</div>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>
      ) : (
        <div className="text-xs text-slate-300">暂无最新公告。底层探针正在持续观测。</div>
      )}
    </section>
  );

  const recentSignalCard = (
    <section
      className={`rounded-[28px] border border-cyan-400/14 bg-[linear-gradient(180deg,rgba(8,16,27,0.96),rgba(5,10,18,0.98))] shadow-[0_18px_60px_rgba(0,0,0,0.28)] ${
        mode === "page" ? "p-5" : "p-4"
      }`}
    >
      <div className="mb-3 flex items-center justify-between">
        <div>
          <div className="text-[10px] uppercase tracking-[0.32em] text-cyan-300/80">3 Day Signal</div>
          <div className="mt-1 text-lg font-semibold text-white">近三日公告雷达</div>
        </div>
        <div className="rounded-full border border-cyan-400/20 bg-cyan-500/10 px-3 py-1 text-[11px] font-medium text-cyan-100">
          {recentSignalOverview?.window_days || 3} 天窗
        </div>
      </div>

      {monitorCount ? (
        <>
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-[22px] border border-white/10 bg-white/[0.04] p-4">
              <div className="text-[10px] uppercase tracking-[0.28em] text-slate-500">有更新</div>
              <div className="mt-2 text-3xl font-semibold text-white">{recentSignalOverview?.active_target_count || 0}</div>
              <div className="mt-1 text-xs text-slate-400">共 {recentSignalOverview?.tracked_target_count || monitorCount} 个范围关注</div>
            </div>
            <div className="rounded-[22px] border border-orange-400/15 bg-orange-500/10 p-4">
              <div className="text-[10px] uppercase tracking-[0.28em] text-orange-200/75">研招相关</div>
              <div className="mt-2 text-3xl font-semibold text-orange-50">
                {recentSignalOverview?.recruitment_target_count || 0}
              </div>
              <div className="mt-1 text-xs text-orange-100/70">
                公告 {recentSignalOverview?.total_recruitment_announcements || 0} 条
              </div>
            </div>
          </div>

          <div className="mt-3 rounded-[22px] border border-white/10 bg-black/25 p-4">
            <div className="flex flex-wrap gap-2 text-[11px]">
              <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-slate-300">
                近 3 日总公告 {recentSignalOverview?.total_recent_announcements || 0} 条
              </span>
              <span className="rounded-full border border-cyan-400/18 bg-cyan-500/10 px-3 py-1 text-cyan-100">
                重点看学校级、学院级、栏目级关注
              </span>
            </div>
            {recentSignalOverview?.latest_announcement ? (
              <div className="mt-3 space-y-1">
                <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Latest Hit</div>
                {recentSignalOverview.latest_announcement.source_url ? (
                  <a
                    href={recentSignalOverview.latest_announcement.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="block text-sm font-medium leading-6 text-white transition-colors hover:text-cyan-200"
                  >
                    {recentSignalOverview.latest_announcement.title}
                  </a>
                ) : (
                  <div className="text-sm font-medium leading-6 text-white">
                    {recentSignalOverview.latest_announcement.title}
                  </div>
                )}
                <div className="text-xs leading-6 text-slate-400">
                  {[
                    recentSignalOverview.latest_announcement.school_name,
                    recentSignalOverview.latest_announcement.department_name,
                    recentSignalOverview.latest_announcement.site_section_name,
                    formatSignalTimestamp(recentSignalOverview.latest_announcement.published_at),
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </div>
              </div>
            ) : (
              <div className="mt-3 text-xs leading-6 text-slate-400">
                近 3 日还没有命中新公告，底层扫描会继续刷新这块情报板。
              </div>
            )}
          </div>
        </>
      ) : (
        <div className="rounded-[22px] border border-dashed border-white/10 bg-white/[0.03] p-4 text-xs leading-6 text-slate-300">
          先添加学校、学院或栏目级关注，这里才会开始汇总近 3 日最新公告和研招相关动态。
        </div>
      )}
    </section>
  );

  const accountCard = portalAuth ? (
    <section className="rounded-[28px] border border-white/10 bg-white/[0.04] p-5 shadow-[0_18px_60px_rgba(0,0,0,0.28)]">
      <div className="text-[10px] uppercase tracking-[0.32em] text-cyan-300/80">Control Deck</div>
      <div className="mt-1 text-lg font-semibold text-white">{portalAuth.nickname || portalAuth.username}</div>
      <div className="mt-2 text-xs text-slate-400">角色：{portalAuth.role} · 状态：{portalAuth.status}</div>
      <div className="mt-4 grid grid-cols-2 gap-2">
        <Link
          href="/account"
          onClick={onNavigate}
          className="rounded-2xl border border-white/15 bg-white/5 px-4 py-3 text-center text-xs font-semibold text-white transition-colors hover:bg-white/10"
        >
          账号中心
        </Link>
        <Link
          href="/search"
          onClick={onNavigate}
          className="rounded-2xl border border-cyan-400/20 bg-cyan-500/10 px-4 py-3 text-center text-xs font-semibold text-cyan-100 transition-colors hover:bg-cyan-500/20"
        >
          去检索页
        </Link>
      </div>
    </section>
  ) : null;

  if (mode === "page") {
    if (!portalAuth) {
      return (
        <div className="min-h-screen bg-[radial-gradient(circle_at_top,rgba(6,182,212,0.14),transparent_34%),linear-gradient(180deg,#040810_0%,#08111d_100%)] px-6 pb-20 pt-28 text-white">
          <div className="mx-auto max-w-5xl">
            <div className="overflow-hidden rounded-[36px] border border-white/10 bg-[linear-gradient(135deg,rgba(10,16,28,0.96),rgba(5,9,16,0.98))] p-10 shadow-[0_40px_120px_rgba(0,0,0,0.45)]">
              <div className="text-[11px] uppercase tracking-[0.38em] text-cyan-300/80">Watchlist Workspace</div>
              <h1 className="mt-4 max-w-2xl text-4xl font-semibold leading-tight text-white md:text-5xl">
                关注项不该被挤在一条侧边缝里。
              </h1>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-300">
                登录后，这里会展开成完整的关注管理工作台。你可以集中查看学校、学院、栏目、关键词和实时雷达，不再被抽屉高度限制。
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <Link
                  href="/login"
                  className="rounded-full bg-cyan-500 px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-cyan-400"
                >
                  去登录
                </Link>
                <Link
                  href="/register"
                  className="rounded-full border border-white/20 bg-white/5 px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-white/10"
                >
                  去注册
                </Link>
              </div>
            </div>
          </div>
        </div>
      );
    }

    return (
      <div className="min-h-screen bg-[radial-gradient(circle_at_top,rgba(6,182,212,0.16),transparent_30%),radial-gradient(circle_at_85%_20%,rgba(245,158,11,0.09),transparent_24%),linear-gradient(180deg,#040810_0%,#08111d_100%)] px-6 pb-20 pt-28 text-white">
        <div className="mx-auto max-w-7xl">
          <section className="relative overflow-hidden rounded-[36px] border border-white/10 bg-[linear-gradient(135deg,rgba(11,18,31,0.96),rgba(7,12,21,0.98))] p-8 shadow-[0_40px_120px_rgba(0,0,0,0.42)] md:p-10">
            <div className="absolute inset-y-0 right-0 hidden w-72 bg-[radial-gradient(circle_at_center,rgba(34,211,238,0.12),transparent_62%)] md:block" />
            <div className="relative">
              <div className="text-[11px] uppercase tracking-[0.38em] text-cyan-300/80">Watchlist Operations Board</div>
              <div className="mt-5 flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
                <div className="max-w-3xl">
                  <h1 className="text-4xl font-semibold leading-tight text-white md:text-5xl">我的关注库</h1>
                  <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-300">
                    抽屉现在退回“快看和快加”，完整管理搬到这里。关注项再多，也可以按类型筛、按关键词搜、按实时信号整理。
                  </p>
                </div>
                <div className="flex flex-wrap gap-3">
                  <Link
                    href="/search"
                    className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-white/10"
                  >
                    <Search size={16} />
                    去检索页补充关注
                  </Link>
                  <div className="inline-flex items-center gap-2 rounded-full border border-cyan-400/25 bg-cyan-500/10 px-5 py-3 text-sm font-semibold text-cyan-100">
                    <FolderKanban size={16} />
                    当前是完整工作台
                  </div>
                </div>
              </div>

              <div className="mt-8 grid gap-3 md:grid-cols-4">
                <StatCard label="总关注数" value={String(watchEntries.length)} accent="cyan" icon={<Star size={16} />} />
                <StatCard label="范围关注" value={String(monitorCount)} accent="amber" icon={<Layers3 size={16} />} />
                <StatCard label="快捷订阅" value={String(subscriptionCount)} accent="cyan" icon={<Compass size={16} />} />
                <StatCard label="实时节点" value={String(latestNoticeCount)} accent="orange" icon={<Radar size={16} />} />
              </div>
            </div>
          </section>

          <div className="mt-8 grid gap-6 xl:grid-cols-[minmax(0,1.7fr)_minmax(340px,0.95fr)]">
            <section className="overflow-hidden rounded-[32px] border border-white/10 bg-[linear-gradient(180deg,rgba(10,16,28,0.96),rgba(5,9,16,0.98))] shadow-[0_32px_100px_rgba(0,0,0,0.38)]">
              <div className="border-b border-white/10 px-5 py-5 md:px-6">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                  <div>
                    <div className="text-[10px] uppercase tracking-[0.32em] text-cyan-300/80">Library Surface</div>
                    <div className="mt-1 text-xl font-semibold text-white">关注项总览</div>
                  </div>
                  <div className="w-full max-w-sm">
                    <div className="flex items-center gap-2 rounded-full border border-white/10 bg-black/30 px-4 py-3">
                      <Search size={15} className="text-slate-500" />
                      <input
                        value={entryQuery}
                        onChange={(event) => setEntryQuery(event.target.value)}
                        placeholder="搜索学校、学院、栏目或关键词"
                        className="w-full bg-transparent text-sm text-white outline-none placeholder:text-slate-500"
                      />
                    </div>
                  </div>
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  {[
                    { key: "all", label: "全部" },
                    { key: "school", label: "学校" },
                    { key: "department", label: "学院" },
                    { key: "section", label: "栏目" },
                    { key: "major", label: "专业" },
                    { key: "keyword", label: "关键词" },
                    { key: "region", label: "地区" },
                    { key: "radar", label: "雷达" },
                  ].map((item) => (
                    <button
                      key={item.key}
                      type="button"
                      onClick={() => setEntryFilter(item.key as EntryFilterKey)}
                      className={`rounded-full px-4 py-2 text-xs font-medium transition-colors ${
                        entryFilter === item.key
                          ? "bg-cyan-500 text-white shadow-[0_0_22px_rgba(6,182,212,0.25)]"
                          : "border border-white/10 bg-white/5 text-slate-300 hover:bg-white/10"
                      }`}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-4 p-5 md:p-6">
                {filteredEntries.length ? (
                  filteredEntries.map((item) => (
                    <WatchEntryCard
                      key={`${item.kind}:${item.id}`}
                      item={item}
                      mode={mode}
                      deleting={item.kind === "monitor" ? deleteMonitorTargetMutation.isPending : deleteSubscriptionMutation.isPending}
                      onDelete={() =>
                        item.kind === "monitor"
                          ? handleDeleteMonitorTarget(item.id)
                          : handleDeleteSubscription(item.id)
                      }
                    />
                  ))
                ) : (
                  <div className="rounded-[28px] border border-dashed border-white/10 bg-white/[0.03] p-8 text-center">
                    <div className="text-lg font-semibold text-white">当前筛选下没有匹配项</div>
                    <div className="mt-2 text-sm leading-7 text-slate-400">
                      换个关键词，或者去右侧继续添加新的学校、学院、栏目级关注。
                    </div>
                  </div>
                )}
              </div>
            </section>

            <div className="space-y-6 xl:sticky xl:top-28 xl:self-start">
              {composerCard}
              {recentSignalCard}
              {realtimeCard}
              {accountCard}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 space-y-4 overflow-y-auto p-4">
      <div className="rounded-[28px] border border-cyan-400/14 bg-[linear-gradient(135deg,rgba(5,11,19,0.96),rgba(10,18,30,0.96))] p-4 shadow-[0_22px_70px_rgba(0,0,0,0.32)]">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-[10px] uppercase tracking-[0.32em] text-cyan-300/80">Expanded Mode</div>
            <div className="mt-1 text-base font-semibold text-white">抽屉只保留快看，完整管理移到专页。</div>
          </div>
          <Link
            href="/watchlist"
            onClick={onNavigate}
            className="inline-flex shrink-0 items-center gap-2 rounded-full border border-cyan-400/25 bg-cyan-500/10 px-4 py-2 text-xs font-semibold text-cyan-100 transition-colors hover:bg-cyan-500/20"
          >
            打开工作台
            <ChevronRight size={14} />
          </Link>
        </div>
        <div className="mt-4 grid grid-cols-3 gap-2">
          <DrawerMetric label="总量" value={watchEntries.length} />
          <DrawerMetric label="范围" value={monitorCount} />
          <DrawerMetric label="信号" value={latestNoticeCount} />
        </div>
      </div>
      {composerCard}
      {recentSignalCard}
      {realtimeCard}

      <section className="rounded-[28px] border border-white/10 bg-white/[0.04] p-4 shadow-[0_18px_60px_rgba(0,0,0,0.28)]">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <div className="text-[10px] uppercase tracking-[0.32em] text-cyan-300/80">Watchlist Preview</div>
            <div className="mt-1 text-lg font-semibold text-white">当前关注</div>
          </div>
          <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] text-slate-300">
            {filteredEntries.length} 项
          </div>
        </div>
        {watchEntries.length ? (
          <div className="space-y-3">
            {visibleEntries.map((item) => (
              <WatchEntryCard
                key={`${item.kind}:${item.id}`}
                item={item}
                mode={mode}
                deleting={item.kind === "monitor" ? deleteMonitorTargetMutation.isPending : deleteSubscriptionMutation.isPending}
                onDelete={() =>
                  item.kind === "monitor"
                    ? handleDeleteMonitorTarget(item.id)
                    : handleDeleteSubscription(item.id)
                }
              />
            ))}
            {hiddenEntryCount > 0 ? (
              <Link
                href="/watchlist"
                onClick={onNavigate}
                className="flex items-center justify-between rounded-2xl border border-dashed border-cyan-400/20 bg-cyan-500/10 px-4 py-3 text-sm text-cyan-100 transition-colors hover:bg-cyan-500/15"
              >
                <span>还有 {hiddenEntryCount} 项未展开</span>
                <span className="inline-flex items-center gap-1">
                  查看全部
                  <ChevronRight size={14} />
                </span>
              </Link>
            ) : null}
          </div>
        ) : subscriptionsQuery.isSuccess && (!canManageScopeTargets || monitorTargetsQuery.isSuccess) ? (
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-xs text-slate-300">
            暂无归档。将有价值的卡片留存于此。
          </div>
        ) : null}
      </section>

      {accountCard}
    </div>
  );
}

function WatchEntryCard({
  item,
  mode,
  deleting,
  onDelete,
}: {
  item: WatchEntry;
  mode: WorkspaceMode;
  deleting: boolean;
  onDelete: () => void;
}) {
  const icon = item.kind === "monitor" ? <Radar size={14} /> : <Star size={14} />;
  const title = buildWatchEntryTitle(item);
  const detail = buildWatchEntryDetail(item);
  const recentSignal = item.kind === "monitor" ? item.recent_signal : null;
  const timestampLabel =
    item.kind === "monitor"
      ? item.last_hit_at || item.last_checked_at || item.created_at
      : item.updated_at || item.created_at;

  return (
    <article
      className={`rounded-[24px] border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.05),rgba(255,255,255,0.02))] ${
        mode === "page" ? "p-5" : "p-4"
      } transition-colors hover:bg-white/[0.07]`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2 text-[11px] font-medium text-cyan-300">
            <span className="inline-flex items-center gap-1">{icon}{item.kind === "monitor" ? monitorScopeLabel(item.scope_type) : watchTypeLabel(item.subscription_type)}</span>
            <span className="text-slate-500">•</span>
            <span className="text-slate-400">{new Date(timestampLabel).toLocaleString("zh-CN", { hour12: false })}</span>
          </div>
          <div className="mt-2 break-words text-base font-semibold leading-6 text-white">{title}</div>
          {detail ? <div className="mt-2 text-xs leading-6 text-slate-400">{detail}</div> : null}
          {item.kind === "monitor" ? <RecentSignalPanel signal={recentSignal} /> : null}
        </div>
        <button
          type="button"
          disabled={deleting}
          onClick={onDelete}
          className="shrink-0 rounded-full border border-white/15 bg-white/5 px-3 py-1.5 text-[11px] text-slate-300 transition-colors hover:bg-white/10 disabled:opacity-60"
        >
          移除
        </button>
      </div>
    </article>
  );
}

function RecentSignalPanel({
  signal,
}: {
  signal?: MonitorTargetItem["recent_signal"];
}) {
  if (!signal) {
    return null;
  }

  if (!signal.has_recent_announcements) {
    return (
      <div className="mt-3 rounded-[20px] border border-white/10 bg-black/20 px-4 py-3 text-xs leading-6 text-slate-400">
        近 {signal.window_days} 日暂无新公告，当前仍会持续盯住下一条更新。
      </div>
    );
  }

  const latest = signal.latest_announcement;

  return (
    <div className="mt-3 rounded-[20px] border border-cyan-400/12 bg-cyan-500/[0.07] p-4">
      <div className="flex flex-wrap gap-2">
        <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] font-medium text-slate-200">
          近 {signal.window_days} 日 {signal.recent_announcement_count} 条公告
        </span>
        <span
          className={`rounded-full border px-3 py-1 text-[11px] font-medium ${
            signal.has_recruitment_announcements
              ? "border-orange-400/20 bg-orange-500/10 text-orange-100"
              : "border-white/10 bg-white/5 text-slate-300"
          }`}
        >
          研招相关 {signal.recruitment_announcement_count} 条
        </span>
      </div>

      {latest ? (
        <div className="mt-3 space-y-1.5">
          <div className="text-[11px] uppercase tracking-[0.24em] text-cyan-200/80">Latest Notice</div>
          {latest.source_url ? (
            <a
              href={latest.source_url}
              target="_blank"
              rel="noreferrer"
              className="block text-sm font-medium leading-6 text-white transition-colors hover:text-cyan-200"
            >
              {latest.title}
            </a>
          ) : (
            <div className="text-sm font-medium leading-6 text-white">{latest.title}</div>
          )}
          <div className="text-xs leading-6 text-slate-300">
            {[latest.department_name, latest.site_section_name, formatSignalTimestamp(latest.published_at)]
              .filter(Boolean)
              .join(" · ")}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function StatCard({
  label,
  value,
  accent,
  icon,
}: {
  label: string;
  value: string;
  accent: "cyan" | "amber" | "orange";
  icon: ReactNode;
}) {
  const accentStyles =
    accent === "amber"
      ? "border-amber-400/20 bg-amber-500/10 text-amber-100"
      : accent === "orange"
        ? "border-orange-400/20 bg-orange-500/10 text-orange-100"
        : "border-cyan-400/20 bg-cyan-500/10 text-cyan-100";
  return (
    <div className="rounded-[26px] border border-white/10 bg-white/[0.04] p-4">
      <div className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-[11px] ${accentStyles}`}>
        {icon}
        {label}
      </div>
      <div className="mt-4 text-3xl font-semibold tracking-tight text-white">{value}</div>
    </div>
  );
}

function DrawerMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.04] px-3 py-3">
      <div className="text-[10px] uppercase tracking-[0.28em] text-slate-500">{label}</div>
      <div className="mt-2 text-lg font-semibold text-white">{value}</div>
    </div>
  );
}

function getEntryFilterKey(item: WatchEntry): EntryFilterKey {
  if (item.kind === "monitor") {
    return item.scope_type;
  }
  return item.subscription_type;
}

function watchTypeLabel(type: string) {
  if (type === "school") return "院校";
  if (type === "radar") return "雷达";
  if (type === "major") return "专业";
  if (type === "keyword") return "关键词";
  if (type === "region") return "地区";
  return "未知";
}

function monitorScopeLabel(type: string) {
  if (type === "school") return "学校级";
  if (type === "department") return "学院级";
  if (type === "section") return "栏目级";
  return "监控";
}

function formatNoticeTitle(item: NotificationEventItem) {
  const school = item.payload.school_name || "未知院校";
  const department = item.payload.department_name;
  const major = item.payload.major_name || item.payload.major || item.payload.major_code;
  const category = item.payload.category === "adjustment" ? "雷达异动" : "公告更新";
  return [school, department, major, category].filter(Boolean).join(" · ");
}

function formatNoticeSubline(item: NotificationEventItem) {
  const title = item.payload.title || "无标题";
  const department = item.payload.department_name ? ` · ${item.payload.department_name}` : "";
  const sectionName = item.payload.site_section_name ? ` · ${item.payload.site_section_name}` : "";
  const majorValue = item.payload.major_name || item.payload.major || item.payload.major_code;
  const major = majorValue ? ` · ${majorValue}` : "";
  const time = new Date(item.created_at).toLocaleString("zh-CN", { hour12: false });
  return `${title}${department}${sectionName}${major} · ${time}`;
}

function isUrgentNotice(item: NotificationEventItem) {
  return item.payload.category === "adjustment" || item.payload.status === "urgent";
}

function isScopeWatchType(type: string) {
  return type === "school" || type === "department" || type === "section";
}

function findExactNameMatch<T>(
  rawValue: string,
  items: T[],
  getName: (item: T) => string | null | undefined,
) {
  const normalized = rawValue.trim().toLowerCase();
  if (!normalized) {
    return null;
  }
  return items.find((item) => (getName(item) || "").trim().toLowerCase() === normalized) || null;
}

function buildWatchEntryTitle(item: WatchEntry) {
  if (item.kind === "monitor") {
    return [item.school_name, item.department_name, item.site_section_name].filter(Boolean).join(" · ") || item.display_label || monitorScopeLabel(item.scope_type);
  }

  if (item.subscription_type === "radar") {
    return (
      item.display_label ||
      [item.target_university, item.target_department_name, item.target_major_name || item.target_major_code]
        .filter(Boolean)
        .join(" · ") ||
      item.value
    );
  }

  if (item.subscription_type === "school") {
    return item.target_university || item.display_label || item.value;
  }

  if (item.subscription_type === "major") {
    return item.target_major_name || item.target_major_code || item.display_label || item.value;
  }

  return item.display_label || item.value;
}

function buildWatchEntryDetail(item: WatchEntry) {
  if (item.kind === "monitor") {
    if (item.scope_type === "school") {
      return "锁定该学校的站内公告";
    }
    if (item.scope_type === "department") {
      return "锁定该学院的站内公告";
    }
    if (item.scope_type === "section") {
      return [selectedSectionSummary(item), "精准盯住栏目更新"].filter(Boolean).join(" · ");
    }
    return "站内公告监控";
  }

  const categoryLabel =
    item.category === "announcement" ? "范围：公告" : item.category === "adjustment" ? "范围：调剂" : "范围：全量";
  const details =
    item.subscription_type === "school"
      ? [categoryLabel]
      : [categoryLabel, item.target_university, item.target_department_name, item.target_major_name || item.target_major_code];
  return details.filter(Boolean).join(" · ");
}

function selectedSectionSummary(item: MonitorTargetItem) {
  return [item.school_name, item.department_name, item.site_section_name].filter(Boolean).join(" · ");
}

function formatSignalTimestamp(value?: string | null) {
  if (!value) {
    return null;
  }
  return new Date(value).toLocaleString("zh-CN", { hour12: false });
}

function buildWatchEntries(subscriptions: SubscriptionItem[], monitorTargets: MonitorTargetItem[]) {
  const items = [
    ...subscriptions.map((item) => ({ kind: "subscription" as const, ...item })),
    ...monitorTargets.map((item) => ({ kind: "monitor" as const, ...item })),
  ];
  return items.sort(
    (left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime(),
  );
}
