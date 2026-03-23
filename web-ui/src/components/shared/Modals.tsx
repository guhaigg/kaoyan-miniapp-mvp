"use client";

import Link from "next/link";
import { useDeferredValue, useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { BellRing, Star, X } from "lucide-react";
import {
  ApiError,
  MonitorScopeDepartmentItem,
  MonitorScopeSectionItem,
  MonitorTargetItem,
  NotificationEventItem,
  SchoolSuggestItem,
  SubscriptionItem,
  logoutUser,
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

export default function Modals() {
  const {
    isAuthOpen,
    setAuthOpen,
    isWatchlistOpen,
    setWatchlistOpen,
    portalAuth,
    clearPortalAuth,
  } = useAppStore();
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState("");
  const [watchType, setWatchType] = useState<"school" | "department" | "section" | "major" | "keyword" | "region">("school");
  const [watchValue, setWatchValue] = useState("");
  const [scopeSchoolName, setScopeSchoolName] = useState("");
  const [scopeDepartmentName, setScopeDepartmentName] = useState("");
  const [scopeSectionName, setScopeSectionName] = useState("");
  const [selectedSchoolId, setSelectedSchoolId] = useState<string | null>(null);
  const [selectedDepartmentId, setSelectedDepartmentId] = useState<string | null>(null);
  const [selectedSectionId, setSelectedSectionId] = useState<string | null>(null);
  const [selectedSectionLabel, setSelectedSectionLabel] = useState("");
  const canManageScopeTargets = Boolean(portalAuth?.isPremium || portalAuth?.isAdmin);
  const showUpgradePanel = Boolean(portalAuth && !portalAuth.isAdmin && !portalAuth.isPremium);
  const deferredSchoolName = useDeferredValue(scopeSchoolName.trim());
  const deferredDepartmentName = useDeferredValue(scopeDepartmentName.trim());
  const deferredSectionName = useDeferredValue(scopeSectionName.trim());
  const isScopeWatchTypeValue = isScopeWatchType(watchType);

  useEffect(() => {
    if (!canManageScopeTargets && (watchType === "school" || watchType === "department" || watchType === "section")) {
      setWatchType("major");
    }
  }, [canManageScopeTargets, watchType]);

  const subscriptionsQuery = useSubscriptionsQuery(isWatchlistOpen);
  const monitorTargetsQuery = useMonitorTargetsQuery(isWatchlistOpen && canManageScopeTargets);
  const realtimeNoticesQuery = useWatchlistNoticesQuery(isWatchlistOpen);
  const schoolSuggestionsQuery = useSchoolSuggestionsQuery(
    {
      q: deferredSchoolName || undefined,
      limit: 8,
    },
    isWatchlistOpen && canManageScopeTargets && isScopeWatchTypeValue && Boolean(deferredSchoolName),
  );
  const departmentSuggestionsQuery = useMonitorScopeDepartmentsQuery(
    {
      school_name: deferredSchoolName || undefined,
      department_name: deferredDepartmentName || undefined,
      limit: 8,
    },
    isWatchlistOpen &&
      canManageScopeTargets &&
      (watchType === "department" || watchType === "section") &&
      Boolean(deferredSchoolName || deferredDepartmentName),
  );
  const sectionLookupQuery = useMonitorScopeSectionsQuery(
    {
      school_name: deferredSchoolName || undefined,
      department_name: deferredDepartmentName || undefined,
      section_name: deferredSectionName || undefined,
      limit: 10,
    },
    isWatchlistOpen &&
      canManageScopeTargets &&
      watchType === "section" &&
      Boolean(deferredSchoolName || deferredDepartmentName || deferredSectionName),
  );

  const createSubscriptionMutation = useAddSubscriptionMutation();
  const deleteSubscriptionMutation = useDeleteSubscriptionMutation();
  const createMonitorTargetMutation = useAddMonitorTargetMutation();
  const deleteMonitorTargetMutation = useDeleteMonitorTargetMutation();

  const watchEntries = buildWatchEntries(subscriptionsQuery.data?.items || [], monitorTargetsQuery.data?.items || []);

  function resetScopeDraft() {
    setScopeSchoolName("");
    setScopeDepartmentName("");
    setScopeSectionName("");
    setSelectedSchoolId(null);
    setSelectedDepartmentId(null);
    setSelectedSectionId(null);
    setSelectedSectionLabel("");
  }

  function handleScopeSchoolInputChange(nextValue: string) {
    setScopeSchoolName(nextValue);
    setSelectedSchoolId(null);
    setSelectedDepartmentId(null);
    setSelectedSectionId(null);
    setSelectedSectionLabel("");
  }

  function handleScopeDepartmentInputChange(nextValue: string) {
    setScopeDepartmentName(nextValue);
    setSelectedDepartmentId(null);
    setSelectedSectionId(null);
    setSelectedSectionLabel("");
  }

  function handleScopeSectionInputChange(nextValue: string) {
    setScopeSectionName(nextValue);
    setSelectedSectionId(null);
    setSelectedSectionLabel("");
  }

  function selectSchoolSuggestion(item: SchoolSuggestItem) {
    setSelectedSchoolId(item.id);
    setScopeSchoolName(item.name);
    setSelectedDepartmentId(null);
    setSelectedSectionId(null);
    setSelectedSectionLabel("");
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
    setSelectedSectionLabel("");
  }

  function selectSectionSuggestion(item: MonitorScopeSectionItem) {
    setSelectedSectionId(item.id);
    setSelectedSectionLabel(buildSectionLabel(item));
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

  async function handleLogout() {
    setSubmitting(true);
    setMessage("");
    try {
      await logoutUser();
      clearPortalAuth();
      setMessage("已退出登录");
    } catch (error) {
      if (error instanceof ApiError) {
        setMessage(`退出失败：${error.message}`);
      } else {
        setMessage("退出失败，请稍后重试");
      }
    } finally {
      setSubmitting(false);
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

      if (watchType === "school") {
        if (!schoolName) {
          setMessage("请输入学校名称");
          return;
        }
      }

      if (watchType === "department") {
        if (!schoolName || !departmentName) {
          setMessage("学院级关注需要同时填写学校和学院");
          return;
        }
      }

      if (watchType === "section" && !selectedSectionId && !sectionName) {
        setMessage("请输入栏目名称，或从下方候选栏目里选择一个");
        return;
      }

      try {
        setMessage("");
        await createMonitorTargetMutation.mutateAsync({
          scope_type: watchType,
          school_id: selectedSchoolId || undefined,
          school_name: selectedSchoolId ? undefined : schoolName || undefined,
          department_id: selectedDepartmentId || undefined,
          department_name: selectedDepartmentId ? undefined : departmentName || undefined,
          site_section_id: selectedSectionId || undefined,
          site_section_name: selectedSectionId ? undefined : sectionName || undefined,
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

  return (
    <>
      <AnimatePresence>
        {isAuthOpen ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] flex items-center justify-center p-4"
          >
            <div
              className="absolute inset-0 bg-black/60 backdrop-blur-md"
              onClick={() => setAuthOpen(false)}
            />
            <motion.div
              initial={{ scale: 0.95, y: 20 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.95, y: 20 }}
              transition={{ type: "spring", bounce: 0.3 }}
              className="relative z-10 w-full max-w-md rounded-3xl border border-white/10 bg-slate-900/80 p-10 shadow-2xl backdrop-blur-2xl"
            >
              <button
                onClick={() => setAuthOpen(false)}
                className="absolute right-6 top-6 text-slate-400 transition-colors hover:text-white"
              >
                <X size={20} />
              </button>
              <div className="mb-8 flex justify-center">
                <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-white drop-shadow-[0_0_20px_rgba(255,255,255,0.2)]">
                  <span className="text-4xl font-black tracking-tighter text-[#2c3e50]">GW</span>
                </div>
              </div>
              <h3 className="mb-4 text-center text-2xl font-bold text-white">账号入口</h3>
              <p className="mb-6 text-center text-sm leading-7 text-slate-300">
                弹窗现在只保留轻入口。完整的登录、注册和退出流程都走稳定页面，不再把表单塞回这里。
              </p>

              {portalAuth ? (
                <div className="space-y-4">
                  <div className="rounded-xl border border-white/10 bg-black/30 p-4 text-sm text-slate-200">
                    当前账号：{portalAuth.nickname || portalAuth.username}
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="rounded-xl border border-white/10 bg-black/30 p-4">
                      <div className="text-xs uppercase tracking-[0.22em] text-slate-400">角色</div>
                      <div className="mt-2 text-lg font-semibold text-white">{portalAuth.role}</div>
                    </div>
                    <div className="rounded-xl border border-white/10 bg-black/30 p-4">
                      <div className="text-xs uppercase tracking-[0.22em] text-slate-400">状态</div>
                      <div className="mt-2 text-lg font-semibold text-white">{portalAuth.status}</div>
                    </div>
                  </div>
                  {showUpgradePanel ? (
                    <div className="rounded-2xl border border-amber-400/20 bg-[linear-gradient(135deg,rgba(120,53,15,0.35),rgba(20,24,36,0.92))] p-4">
                      <div className="text-xs uppercase tracking-[0.28em] text-amber-300">Membership</div>
                      <div className="mt-2 text-base font-bold text-white">会员开通已迁到账号中心。</div>
                      <div className="mt-2 text-xs leading-6 text-amber-50/85">
                        弹窗只保留快速入口，不再塞订单、绑定、通知和改密。
                      </div>
                      <Link
                        href="/account/billing"
                        onClick={() => setAuthOpen(false)}
                        className="mt-4 inline-flex rounded-xl bg-amber-500 px-4 py-3 text-sm font-semibold text-slate-950 transition-colors hover:bg-amber-400"
                      >
                        去账号中心开通会员
                      </Link>
                    </div>
                  ) : null}
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Link
                      href="/account"
                      onClick={() => setAuthOpen(false)}
                      className="rounded-xl border border-white/20 bg-white/10 px-4 py-3 text-center text-sm font-semibold text-white transition-colors hover:bg-white/20"
                    >
                      进入账号中心
                    </Link>
                    <Link
                      href="/search"
                      onClick={() => setAuthOpen(false)}
                      className="rounded-xl border border-cyan-400/30 bg-cyan-500/10 px-4 py-3 text-center text-sm font-semibold text-cyan-100 transition-colors hover:bg-cyan-500/20"
                    >
                      去检索页
                    </Link>
                  </div>
                  <button
                    type="button"
                    onClick={handleLogout}
                    disabled={submitting}
                    className="w-full rounded-xl border border-white/20 bg-white/10 py-3 font-semibold text-white transition-all hover:bg-white/20 disabled:cursor-not-allowed disabled:opacity-70"
                  >
                    {submitting ? "处理中..." : "退出登录"}
                  </button>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="rounded-2xl border border-white/10 bg-black/30 p-4 text-sm text-slate-300">
                    登录页和注册页现在是独立的应用入口，支持完整认证壳和后续跳转，不再依赖弹窗上下文。
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Link
                      href="/login"
                      onClick={() => setAuthOpen(false)}
                      className="rounded-xl bg-cyan-500 px-4 py-3 text-center text-sm font-semibold text-white transition-colors hover:bg-cyan-400"
                    >
                      去登录
                    </Link>
                    <Link
                      href="/register"
                      onClick={() => setAuthOpen(false)}
                      className="rounded-xl border border-white/20 bg-white/10 px-4 py-3 text-center text-sm font-semibold text-white transition-colors hover:bg-white/20"
                    >
                      去注册
                    </Link>
                  </div>
                </div>
              )}
              {message ? (
                <p className="mt-4 rounded-lg border border-white/10 bg-black/30 px-4 py-2 text-xs text-slate-300">
                  {message}
                </p>
              ) : null}
            </motion.div>
          </motion.div>
        ) : null}
      </AnimatePresence>

      <AnimatePresence>
        {isWatchlistOpen ? (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-[90] bg-black/40 backdrop-blur-sm"
              onClick={() => setWatchlistOpen(false)}
            />
            <motion.div
              initial={{ x: "100%" }}
              animate={{ x: 0 }}
              exit={{ x: "100%" }}
              transition={{ type: "spring", damping: 25, stiffness: 200 }}
              className="fixed right-0 top-0 z-[100] flex h-full w-80 flex-col border-l border-white/10 bg-[#0a0f1a]/95 shadow-[-20px_0_50px_rgba(0,0,0,0.5)] backdrop-blur-3xl md:w-96"
            >
              <div className="flex items-center justify-between border-b border-white/10 p-6 text-white">
                <h3 className="flex items-center gap-2 text-lg font-bold">
                  <Star className="text-yellow-400" size={20} /> 我的关注库
                </h3>
                <button
                  onClick={() => setWatchlistOpen(false)}
                  className="rounded-full bg-white/5 p-1.5 text-slate-400 transition-colors hover:text-white"
                >
                  <X size={16} />
                </button>
              </div>
              <div className="flex-1 space-y-4 overflow-y-auto p-4">
                {portalAuth ? (
                  <>
                    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                      <div className="mb-3 flex items-center gap-2 text-xs text-slate-400">
                        <BellRing size={14} />
                        添加新关注
                      </div>
                      <div className="mb-2 grid grid-cols-3 gap-2">
                        {[
                          { key: "school", label: "学校" },
                          { key: "department", label: "学院" },
                          { key: "section", label: "栏目" },
                          { key: "major", label: "专业" },
                          { key: "keyword", label: "关键词" },
                          { key: "region", label: "地区" },
                        ].map((x) => (
                          <button
                            key={x.key}
                            type="button"
                            disabled={
                              (x.key === "school" || x.key === "department" || x.key === "section") && !canManageScopeTargets
                            }
                            onClick={() =>
                              setWatchType(x.key as "school" | "department" | "section" | "major" | "keyword" | "region")
                            }
                            className={`rounded-lg px-2 py-1.5 text-xs transition-colors ${
                              watchType === x.key
                                ? "bg-cyan-500 text-white"
                                : "bg-white/5 text-slate-300 hover:bg-white/10"
                            } ${
                              (x.key === "school" || x.key === "department" || x.key === "section") && !canManageScopeTargets
                                ? "cursor-not-allowed opacity-50 hover:bg-white/5"
                                : ""
                            }`}
                          >
                            {x.label}
                          </button>
                        ))}
                      </div>
                      {!canManageScopeTargets ? (
                        <div className="mt-2 rounded-xl border border-amber-500/20 bg-amber-500/10 p-3">
                          <div className="text-[11px] text-amber-200">
                            学校、学院、栏目级关注仅高级用户或管理员可用。普通用户不该只看到一行限制提示，所以这里直接给开通入口。
                          </div>
                          <Link
                            href="/account/billing"
                            onClick={() => setWatchlistOpen(false)}
                            className="mt-2 inline-flex rounded-lg border border-amber-300/30 bg-black/20 px-3 py-2 text-xs font-semibold text-amber-100 transition-colors hover:bg-black/30"
                          >
                            立即开通高级会员
                          </Link>
                        </div>
                      ) : null}
                      {watchType === "school" || watchType === "department" || watchType === "section" ? (
                        <div className="space-y-2">
                          <input
                            value={scopeSchoolName}
                            onChange={(event) => handleScopeSchoolInputChange(event.target.value)}
                            placeholder="学校名称，例如：电子科技大学"
                            className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-white outline-none focus:border-cyan-400"
                          />
                          {selectedSchoolId ? (
                            <div className="rounded-lg border border-cyan-400/30 bg-cyan-500/10 px-3 py-2 text-xs text-cyan-100">
                              已锁定学校：{scopeSchoolName}
                            </div>
                          ) : null}
                          {schoolSuggestionsQuery.isLoading ? (
                            <div className="rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-xs text-slate-300">
                              正在匹配学校候选...
                            </div>
                          ) : null}
                          {schoolSuggestionsQuery.data?.items.length ? (
                            <div className="max-h-36 space-y-2 overflow-y-auto rounded-xl border border-white/10 bg-black/20 p-2">
                              {schoolSuggestionsQuery.data.items.map((item) => {
                                const active = selectedSchoolId === item.id;
                                return (
                                  <button
                                    key={item.id}
                                    type="button"
                                    onClick={() => selectSchoolSuggestion(item)}
                                    className={`block w-full rounded-lg border px-3 py-2 text-left transition-colors ${
                                      active
                                        ? "border-cyan-400/40 bg-cyan-500/10"
                                        : "border-white/10 bg-white/5 hover:bg-white/10"
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
                                className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-white outline-none focus:border-cyan-400"
                              />
                              {selectedDepartmentId ? (
                                <div className="rounded-lg border border-cyan-400/30 bg-cyan-500/10 px-3 py-2 text-xs text-cyan-100">
                                  已锁定学院：{scopeDepartmentName}
                                </div>
                              ) : null}
                              {departmentSuggestionsQuery.isLoading ? (
                                <div className="rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-xs text-slate-300">
                                  正在匹配学院候选...
                                </div>
                              ) : null}
                              {departmentSuggestionsQuery.data?.items.length ? (
                                <div className="max-h-36 space-y-2 overflow-y-auto rounded-xl border border-white/10 bg-black/20 p-2">
                                  {departmentSuggestionsQuery.data.items.map((item) => {
                                    const active = selectedDepartmentId === item.id;
                                    return (
                                      <button
                                        key={item.id}
                                        type="button"
                                        onClick={() => selectDepartmentSuggestion(item)}
                                        className={`block w-full rounded-lg border px-3 py-2 text-left transition-colors ${
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
                                className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-white outline-none focus:border-cyan-400"
                              />
                              {selectedSectionLabel ? (
                                <div className="rounded-lg border border-cyan-400/30 bg-cyan-500/10 px-3 py-2 text-xs text-cyan-100">
                                  已选择栏目：{selectedSectionLabel}
                                </div>
                              ) : null}
                              {sectionLookupQuery.isLoading ? (
                                <div className="rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-xs text-slate-300">
                                  正在匹配栏目候选...
                                </div>
                              ) : null}
                              {sectionLookupQuery.data?.items.length ? (
                                <div className="max-h-40 space-y-2 overflow-y-auto rounded-xl border border-white/10 bg-black/20 p-2">
                                  {sectionLookupQuery.data.items.map((item) => {
                                    const active = selectedSectionId === item.id;
                                    return (
                                      <button
                                        key={item.id}
                                        type="button"
                                        onClick={() => selectSectionSuggestion(item)}
                                        className={`block w-full rounded-lg border px-3 py-2 text-left transition-colors ${
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
                            className="w-full rounded-lg bg-cyan-500 px-3 py-2 text-sm font-semibold text-white transition-colors hover:bg-cyan-400 disabled:opacity-70"
                          >
                            添加
                          </button>
                        </div>
                      ) : (
                        <div className="flex gap-2">
                          <input
                            value={watchValue}
                            onChange={(event) => setWatchValue(event.target.value)}
                            placeholder="例如：0854 / 复试线 / 华中地区"
                            className="flex-1 rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-white outline-none focus:border-cyan-400"
                          />
                          <button
                            type="button"
                            disabled={createSubscriptionMutation.isPending}
                            onClick={handleCreateSubscription}
                            className="rounded-lg bg-cyan-500 px-3 py-2 text-sm font-semibold text-white transition-colors hover:bg-cyan-400 disabled:opacity-70"
                          >
                            添加
                          </button>
                        </div>
                      )}
                    </div>

                    {subscriptionsQuery.isLoading || (canManageScopeTargets && monitorTargetsQuery.isLoading) ? (
                      <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-xs text-slate-300">
                        探针巡航中，拉取最新节点...
                      </div>
                    ) : null}

                    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                      <div className="mb-2 text-xs text-slate-400">
                        实时情报流（SSE）
                      </div>
                      {realtimeNoticesQuery.isLoading ? (
                        <div className="text-xs text-slate-300">探针巡航中，拉取最新节点...</div>
                      ) : realtimeNoticesQuery.data?.length ? (
                        <div className="space-y-2">
                          <AnimatePresence initial={false}>
                            {realtimeNoticesQuery.data.map((item) => {
                              const urgent = isUrgentNotice(item);
                              return (
                                <motion.div
                                  key={item.id}
                                  layout
                                  initial={{ opacity: 0, y: -30, scale: 0.9 }}
                                  animate={{ opacity: 1, y: 0, scale: 1 }}
                                  exit={{ opacity: 0, scale: 0.9, transition: { duration: 0.2 } }}
                                  transition={{
                                    layout: { type: "spring", bounce: 0.4, duration: 0.6 },
                                    opacity: { duration: 0.3 },
                                    y: { type: "spring", bounce: 0.5, duration: 0.6 },
                                  }}
                                  className={`cursor-pointer rounded-xl border p-3 transition-colors ${
                                    urgent
                                      ? "border-orange-500/30 bg-orange-950/20 shadow-[0_4px_20px_rgba(249,115,22,0.05)] hover:border-orange-500/50"
                                      : "border-white/10 bg-white/5 shadow-[0_4px_20px_rgba(0,0,0,0.2)] hover:bg-white/10"
                                  }`}
                                >
                                  <div
                                    className={`mb-2 flex items-center gap-1 text-xs font-mono ${
                                      urgent ? "animate-pulse text-orange-400" : "text-cyan-400"
                                    }`}
                                  >
                                    <BellRing size={12} /> {urgent ? "紧急异动！" : "常规监控"}
                                  </div>
                                  <div className="text-sm font-medium leading-snug text-white">
                                    {formatNoticeTitle(item)}
                                  </div>
                                  <div className="mt-1 text-xs text-slate-400">
                                    {formatNoticeSubline(item)}
                                  </div>
                                </motion.div>
                              );
                            })}
                          </AnimatePresence>
                        </div>
                      ) : (
                        <div className="text-xs text-slate-300">暂无最新公告。底层探针正在持续观测。</div>
                      )}
                    </div>

                    {watchEntries.length ? (
                      watchEntries.map((item) => (
                        <div
                          key={`${item.kind}:${item.id}`}
                          className="rounded-2xl border border-white/10 bg-white/5 p-4 transition-colors hover:bg-white/10"
                        >
                          <div className="mb-2 flex items-center justify-between">
                            <div className="flex items-center gap-2 font-mono text-xs text-cyan-400">
                              <BellRing size={12} />
                              正在监控 · {item.kind === "monitor" ? monitorScopeLabel(item.scope_type) : watchTypeLabel(item.subscription_type)}
                            </div>
                            <button
                              type="button"
                              disabled={item.kind === "monitor" ? deleteMonitorTargetMutation.isPending : deleteSubscriptionMutation.isPending}
                              onClick={() =>
                                item.kind === "monitor"
                                  ? handleDeleteMonitorTarget(item.id)
                                  : handleDeleteSubscription(item.id)
                              }
                              className="rounded-md border border-white/20 px-2 py-1 text-[11px] text-slate-300 transition-colors hover:bg-white/10"
                            >
                              移除
                            </button>
                          </div>
                          <div className="mb-2 text-sm font-medium text-white">
                            {item.kind === "monitor" ? item.display_label : item.display_label || item.value}
                          </div>
                          <div className="text-xs text-slate-400">
                            {item.kind === "monitor" ? "范围：站内公告" : `类别：${item.category}`} · 创建于{" "}
                            {new Date(item.created_at).toLocaleString("zh-CN", { hour12: false })}
                          </div>
                        </div>
                      ))
                    ) : subscriptionsQuery.isSuccess && (!canManageScopeTargets || monitorTargetsQuery.isSuccess) ? (
                      <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-xs text-slate-300">
                        暂无归档。将有价值的卡片留存于此。
                      </div>
                    ) : null}
                  </>
                ) : (
                  <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-xs text-slate-300">
                    执行归档（收藏）或个性化订阅，需要建立身份映射。请先登录后再管理关注库。
                  </div>
                )}

                <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-xs text-slate-300">
                  {portalAuth ? (
                    <div className="space-y-3">
                      <div>{`当前登录：${portalAuth.nickname || portalAuth.username}`}</div>
                      <div className="grid grid-cols-2 gap-2">
                        <Link
                          href="/account"
                          onClick={() => setWatchlistOpen(false)}
                          className="rounded-lg border border-white/15 bg-white/5 px-3 py-2 text-center text-xs font-semibold text-white transition-colors hover:bg-white/10"
                        >
                          账号中心
                        </Link>
                        <Link
                          href="/search"
                          onClick={() => setWatchlistOpen(false)}
                          className="rounded-lg border border-cyan-400/20 bg-cyan-500/10 px-3 py-2 text-center text-xs font-semibold text-cyan-100 transition-colors hover:bg-cyan-500/20"
                        >
                          去检索页
                        </Link>
                      </div>
                    </div>
                  ) : (
                    "登录后可同步你的关注列表与检索偏好。"
                  )}
                </div>
              </div>
            </motion.div>
          </>
        ) : null}
      </AnimatePresence>
    </>
  );
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

function buildSectionLabel(item: {
  name: string;
  school_name?: string | null;
  department_name?: string | null;
}) {
  return [item.school_name, item.department_name, item.name].filter(Boolean).join(" · ");
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
