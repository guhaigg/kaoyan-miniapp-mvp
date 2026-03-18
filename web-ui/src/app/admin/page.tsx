"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Activity, CreditCard, ExternalLink, FileSearch, LayoutDashboard, RotateCcw, ScrollText, Settings2, TestTube2, TriangleAlert, UserCog, WandSparkles } from "lucide-react";
import ActivityChart from "@/components/admin/ActivityChart";
import { useDocumentVisibility } from "@/hooks/useDocumentVisibility";
import {
  ApiError,
  getCurrentUser,
  type ContentFileItem,
  type SiteSectionItem,
  type SiteSectionSelectorPreviewResponse,
} from "@/lib/api";
import { useAppStore } from "@/lib/store";
import {
  useAdminAuditsQuery,
  useAdminCreatePaymentOrderMutation,
  useAdminContentFingerprintStatsQuery,
  useAdminContentFileRetryMutation,
  useAdminContentFilesQuery,
  useAdminDemoteMutation,
  useAdminHealthQuery,
  useAdminMarkPaymentOrderPaidMutation,
  useAdminMeQuery,
  useAdminPaymentOrdersQuery,
  useAdminPromoteMutation,
  useAdminResetPasswordMutation,
  useAdminSiteSectionBackfillMutation,
  useAdminSiteSectionPreviewMutation,
  useAdminSiteSectionUpdateMutation,
  useAdminSiteSectionsQuery,
  useAdminUsersQuery,
} from "@/hooks/useAdmin";

type SelectorDraft = {
  listCssSelector: string;
  listXPathSelector: string;
  detailCssSelector: string;
  detailXPathSelector: string;
};

type SelectorPreviewMap = Record<string, SiteSectionSelectorPreviewResponse>;

const ADMIN_NAV_ITEMS = [
  { id: "overview", label: "总览", description: "健康、吞吐和覆盖率", icon: LayoutDashboard },
  { id: "users", label: "用户管理", description: "角色、密码和权益", icon: UserCog },
  { id: "audits", label: "审计事件", description: "管理员动作轨迹", icon: ScrollText },
  { id: "payments", label: "会员订单", description: "订单到账本和放权", icon: CreditCard },
  { id: "selectors", label: "栏目选择器", description: "Discovery 抽取规则", icon: Settings2 },
  { id: "content-files", label: "PDF 队列", description: "解析状态和重试", icon: FileSearch },
  { id: "runtime", label: "运行面板", description: "服务状态和控制台", icon: Activity },
] as const;

export default function AdminPage() {
  const [message, setMessage] = useState("");
  const [promotingAction, setPromotingAction] = useState<string | null>(null);
  const [siteSectionEdits, setSiteSectionEdits] = useState<Record<string, SelectorDraft>>({});
  const [siteSectionPreviews, setSiteSectionPreviews] = useState<SelectorPreviewMap>({});
  const [siteSectionSavingId, setSiteSectionSavingId] = useState<string | null>(null);
  const [siteSectionPreviewingId, setSiteSectionPreviewingId] = useState<string | null>(null);
  const [retryingContentFileId, setRetryingContentFileId] = useState<string | null>(null);
  const [resettingPasswordUserId, setResettingPasswordUserId] = useState<string | null>(null);
  const [creatingPaymentOrderUserId, setCreatingPaymentOrderUserId] = useState<string | null>(null);
  const [markingPaymentOrderId, setMarkingPaymentOrderId] = useState<string | null>(null);
  const [resolvingAdminRole, setResolvingAdminRole] = useState(false);
  const [selectorView, setSelectorView] = useState<"all" | "attention" | "preview-warning">("all");
  const roleRefreshAttemptedTokenRef = useRef<string | null>(null);
  const isDocumentVisible = useDocumentVisibility();
  const portalAuth = useAppStore((state) => state.portalAuth);
  const authBootstrapped = useAppStore((state) => state.authBootstrapped);
  const hasServerSessionHint = useAppStore((state) => state.hasServerSessionHint);
  const setPortalProfile = useAppStore((state) => state.setPortalProfile);
  const isPortalAdmin = Boolean(portalAuth?.isAdmin);

  const meQuery = useAdminMeQuery(authBootstrapped && Boolean(portalAuth || hasServerSessionHint));
  const hasAdminSession = meQuery.isSuccess && meQuery.data.authenticated;
  const canAccessAdminShell = Boolean(isPortalAdmin || hasAdminSession);
  const isAuthenticated = canAccessAdminShell;

  const healthQuery = useAdminHealthQuery(isDocumentVisible);

  const usersQuery = useAdminUsersQuery(isAuthenticated);

  const auditsQuery = useAdminAuditsQuery(isAuthenticated);
  const fingerprintStatsQuery = useAdminContentFingerprintStatsQuery(isAuthenticated, isDocumentVisible);
  const paymentOrdersQuery = useAdminPaymentOrdersQuery(isAuthenticated, isDocumentVisible);
  const siteSectionsQuery = useAdminSiteSectionsQuery(isAuthenticated);
  const contentFilesQuery = useAdminContentFilesQuery(isAuthenticated, isDocumentVisible);

  const promoteMutation = useAdminPromoteMutation();
  const demoteMutation = useAdminDemoteMutation();
  const resetPasswordMutation = useAdminResetPasswordMutation();
  const createPaymentOrderMutation = useAdminCreatePaymentOrderMutation();
  const markPaymentOrderPaidMutation = useAdminMarkPaymentOrderPaidMutation();
  const updateSiteSectionMutation = useAdminSiteSectionUpdateMutation();
  const backfillSiteSectionMutation = useAdminSiteSectionBackfillMutation();
  const previewSiteSectionMutation = useAdminSiteSectionPreviewMutation();
  const retryContentFileMutation = useAdminContentFileRetryMutation();

  const dashboard = useMemo(() => {
    const audits = auditsQuery.data?.items || [];
    const urgentCount = audits.filter((item) => item.event_type.includes("offline")).length;
    const activeServices = (healthQuery.data?.db === "up" ? 1 : 0) + (healthQuery.data?.redis === "up" ? 1 : 0);
    const chartPoints = buildChartPoints(audits);
    const firstHalf = average(chartPoints.slice(0, 6));
    const secondHalf = average(chartPoints.slice(6));
    const trend = firstHalf === 0 ? 100 : ((secondHalf - firstHalf) / firstHalf) * 100;
    return {
      requests: auditsQuery.data?.total ?? 0,
      urgentCount,
      activeServices,
      dbState: healthQuery.data?.db || "--",
      redisState: healthQuery.data?.redis || "--",
      audits,
      chartPoints,
      trend,
    };
  }, [auditsQuery.data, healthQuery.data]);

  const selectorSummary = useMemo(() => {
    const items = siteSectionsQuery.data?.items || [];
    let attention = 0;
    let previewWarning = 0;
    for (const item of items) {
      const preview = siteSectionPreviews[item.id];
      if (hasSelectorAttention(item, preview)) {
        attention += 1;
      }
      if ((preview?.warnings.length || 0) > 0) {
        previewWarning += 1;
      }
    }
    return {
      total: items.length,
      attention,
      previewWarning,
    };
  }, [siteSectionPreviews, siteSectionsQuery.data?.items]);

  const visibleSiteSections = useMemo(() => {
    const items = siteSectionsQuery.data?.items || [];
    return items.filter((item) => {
      const preview = siteSectionPreviews[item.id];
      if (selectorView === "attention") {
        return hasSelectorAttention(item, preview);
      }
      if (selectorView === "preview-warning") {
        return (preview?.warnings.length || 0) > 0;
      }
      return true;
    });
  }, [selectorView, siteSectionPreviews, siteSectionsQuery.data?.items]);

  useEffect(() => {
    const items = siteSectionsQuery.data?.items || [];
    if (items.length === 0) {
      return;
    }
    setSiteSectionEdits((current) => {
      const next = { ...current };
      items.forEach((item) => {
        if (!next[item.id]) {
          next[item.id] = buildSelectorDraft(item);
        }
      });
      return next;
    });
  }, [siteSectionsQuery.data]);

  useEffect(() => {
    const accessToken = portalAuth?.accessToken || null;
    if (!authBootstrapped || !accessToken || portalAuth?.isAdmin) {
      return;
    }
    if (roleRefreshAttemptedTokenRef.current === accessToken) {
      return;
    }
    let alive = true;
    roleRefreshAttemptedTokenRef.current = accessToken;
    setResolvingAdminRole(true);
    getCurrentUser(accessToken)
      .then((profile) => {
        if (!alive) return;
        setPortalProfile({
          nickname: profile.nickname,
          status: profile.status,
          isAdmin: profile.is_admin,
          isPremium: profile.is_premium,
          role: profile.role,
          premiumExpiresAt: profile.premium_expires_at,
        });
      })
      .catch(() => {
        // Keep current local state; admin shell may still be available via admin session.
      })
      .finally(() => {
        if (alive) {
          setResolvingAdminRole(false);
        }
      });
    return () => {
      alive = false;
    };
  }, [authBootstrapped, portalAuth?.accessToken, portalAuth?.isAdmin, setPortalProfile]);

  async function handlePromoteUser(userId: string, targetRole: "premium" | "admin") {
    setPromotingAction(`${userId}:${targetRole}`);
    setMessage("");
    try {
      await promoteMutation.mutateAsync({ userId, targetRole });
      setMessage(targetRole === "admin" ? "用户已提升为管理员" : "用户已提升为高级用户");
    } catch (error) {
      if (error instanceof ApiError) {
        setMessage(`提升失败：${error.message}`);
      } else {
        setMessage("提升失败，请稍后重试");
      }
    } finally {
      setPromotingAction(null);
    }
  }

  async function handleDemoteUser(userId: string, targetRole: "user" | "premium") {
    setPromotingAction(`${userId}:demote:${targetRole}`);
    setMessage("");
    try {
      await demoteMutation.mutateAsync({ userId, targetRole, premiumDays: 30 });
      setMessage(targetRole === "premium" ? "用户已降为高级用户（30天）" : "用户已降级为普通用户");
    } catch (error) {
      if (error instanceof ApiError) {
        setMessage(`降级失败：${error.message}`);
      } else {
        setMessage("降级失败，请稍后重试");
      }
    } finally {
      setPromotingAction(null);
    }
  }

  async function handleResetUserPassword(userId: string, username: string) {
    const nextPassword = window.prompt(`为用户 ${username} 设置新密码（至少 8 位）`);
    if (!nextPassword) {
      return;
    }
    if (nextPassword.trim().length < 8) {
      setMessage("新密码至少 8 位");
      return;
    }
    setResettingPasswordUserId(userId);
    setMessage("");
    try {
      await resetPasswordMutation.mutateAsync({ userId, newPassword: nextPassword.trim() });
      setMessage(`用户 ${username} 的密码已重置`);
    } catch (error) {
      if (error instanceof ApiError) {
        setMessage(`重置密码失败：${error.message}`);
      } else {
        setMessage("重置密码失败，请稍后重试");
      }
    } finally {
      setResettingPasswordUserId(null);
    }
  }

  async function handleCreatePaymentOrder(userId: string, username: string) {
    const durationInput = window.prompt(`为用户 ${username} 创建会员订单，输入时长（30/90/365 天）`, "30");
    if (!durationInput) {
      return;
    }
    const durationDays = Number(durationInput);
    if (![30, 90, 365].includes(durationDays)) {
      setMessage("会员订单时长仅支持 30 / 90 / 365 天");
      return;
    }
    setCreatingPaymentOrderUserId(userId);
    setMessage("");
    try {
      const response = await createPaymentOrderMutation.mutateAsync({ userId, durationDays, amountCents: 0 });
      setMessage(`已为 ${username} 创建 ${durationDays} 天会员订单：${response.order_ref}`);
    } catch (error) {
      if (error instanceof ApiError) {
        setMessage(`创建会员订单失败：${error.message}`);
      } else {
        setMessage("创建会员订单失败，请稍后重试");
      }
    } finally {
      setCreatingPaymentOrderUserId(null);
    }
  }

  async function handleMarkPaymentOrderPaid(orderId: string, username: string) {
    const providerPaymentRef = window.prompt(`确认订单支付，给 ${username} 填写支付流水号（可留空）`, "") || undefined;
    setMarkingPaymentOrderId(orderId);
    setMessage("");
    try {
      const response = await markPaymentOrderPaidMutation.mutateAsync({ orderId, providerPaymentRef });
      setMessage(`订单 ${response.order_ref} 已确认支付，权益已发放`);
    } catch (error) {
      if (error instanceof ApiError) {
        setMessage(`确认支付失败：${error.message}`);
      } else {
        setMessage("确认支付失败，请稍后重试");
      }
    } finally {
      setMarkingPaymentOrderId(null);
    }
  }

  function handleSiteSectionDraftChange(siteSectionId: string, field: keyof SelectorDraft, value: string) {
    setSiteSectionEdits((current) => ({
      ...current,
      [siteSectionId]: {
        ...(current[siteSectionId] || emptySelectorDraft()),
        [field]: value,
      },
    }));
    setSiteSectionPreviews((current) => {
      if (!current[siteSectionId]) {
        return current;
      }
      const next = { ...current };
      delete next[siteSectionId];
      return next;
    });
  }

  async function handleSaveSiteSection(item: SiteSectionItem) {
    const draft = siteSectionEdits[item.id] || buildSelectorDraft(item);
    setSiteSectionSavingId(item.id);
    setMessage("");
    try {
      await updateSiteSectionMutation.mutateAsync({
        siteSectionId: item.id,
        listSelectorConfig: buildListSelectorConfig(item, draft),
        detailSelectorConfig: buildDetailSelectorConfig(item, draft),
      });
      setMessage(`栏目「${item.name}」选择器已保存`);
    } catch (error) {
      if (error instanceof ApiError) {
        setMessage(`保存栏目失败：${error.message}`);
      } else {
        setMessage("保存栏目失败，请稍后重试");
      }
    } finally {
      setSiteSectionSavingId(null);
    }
  }

  function handleResetSiteSectionToSuggested(item: SiteSectionItem) {
    setSiteSectionEdits((current) => ({
      ...current,
      [item.id]: buildSuggestedSelectorDraft(item),
    }));
    setMessage(`栏目「${item.name}」已恢复到推荐规则，确认预览后再保存。`);
  }

  async function handlePreviewSiteSection(item: SiteSectionItem, sampleLinkUrl?: string | null) {
    const draft = siteSectionEdits[item.id] || buildSelectorDraft(item);
    setSiteSectionPreviewingId(item.id);
    setMessage("");
    try {
      const response = await previewSiteSectionMutation.mutateAsync({
        siteSectionId: item.id,
        listSelectorConfig: buildListSelectorConfig(item, draft),
        detailSelectorConfig: buildDetailSelectorConfig(item, draft),
        sampleLinkUrl: sampleLinkUrl ?? null,
      });
      setSiteSectionPreviews((current) => ({ ...current, [item.id]: response }));
      setMessage(
        sampleLinkUrl
          ? `栏目「${item.name}」已切换详情样本，可直接检查该链接的正文抽取效果。`
          : `栏目「${item.name}」预览已刷新，可直接检查列表命中和正文抽取效果。`,
      );
    } catch (error) {
      if (error instanceof ApiError) {
        setMessage(`预览失败：${error.message}`);
      } else {
        setMessage("预览失败，请稍后重试");
      }
    } finally {
      setSiteSectionPreviewingId(null);
    }
  }

  async function handleBackfillSiteSections() {
    setMessage("");
    try {
      const response = await backfillSiteSectionMutation.mutateAsync(false);
      setMessage(`默认选择器回填完成，更新 ${response.updated_sections}/${response.total_sections} 个栏目`);
    } catch (error) {
      if (error instanceof ApiError) {
        setMessage(`回填失败：${error.message}`);
      } else {
        setMessage("回填失败，请稍后重试");
      }
    }
  }

  async function handleRetryContentFile(item: ContentFileItem) {
    setRetryingContentFileId(item.id);
    setMessage("");
    try {
      const response = await retryContentFileMutation.mutateAsync(item.id);
      setMessage(
        response.status === "existing"
          ? `文件「${item.link_title || item.file_url}」已有解析任务在队列中`
          : `文件「${item.link_title || item.file_url}」已重新排队解析`,
      );
    } catch (error) {
      if (error instanceof ApiError) {
        setMessage(`重试解析失败：${error.message}`);
      } else {
        setMessage("重试解析失败，请稍后重试");
      }
    } finally {
      setRetryingContentFileId(null);
    }
  }

  if (!authBootstrapped && (portalAuth || hasServerSessionHint)) {
    return (
      <div className="mx-auto max-w-3xl px-4 pb-20 pt-16">
        <div className="rounded-3xl border border-white/10 bg-black/35 p-8 text-center text-slate-200">
          <h2 className="mb-3 text-2xl font-bold text-white">正在校验管理员身份</h2>
          <p className="text-sm text-slate-300">等待会话与角色信息同步。</p>
        </div>
      </div>
    );
  }

  if (!portalAuth) {
    return (
      <div className="mx-auto max-w-3xl px-4 pb-20 pt-16">
        <div className="rounded-3xl border border-white/10 bg-black/35 p-8 text-center text-slate-200">
          <h2 className="mb-3 text-2xl font-bold text-white">监控台仅管理员可见</h2>
          <p className="mb-6 text-sm text-slate-300">请先登录管理员账号对应的用户账户。</p>
          <div className="flex justify-center gap-3">
            <Link href="/login" className="rounded-xl bg-cyan-500 px-5 py-2.5 text-sm font-semibold text-white">
              去登录
            </Link>
            <Link href="/search" className="rounded-xl border border-white/20 bg-white/5 px-5 py-2.5 text-sm text-slate-200">
              返回检索
            </Link>
          </div>
        </div>
      </div>
    );
  }

  if (resolvingAdminRole && !canAccessAdminShell) {
    return (
      <div className="mx-auto max-w-3xl px-4 pb-20 pt-16">
        <div className="rounded-3xl border border-white/10 bg-black/35 p-8 text-center text-slate-200">
          <h2 className="mb-3 text-2xl font-bold text-white">正在刷新管理员权限</h2>
          <p className="text-sm text-slate-300">正在从服务器确认当前账户的管理员状态。</p>
        </div>
      </div>
    );
  }

  if (!canAccessAdminShell) {
    return (
      <div className="mx-auto max-w-3xl px-4 pb-20 pt-16">
        <div className="rounded-3xl border border-red-500/20 bg-red-950/20 p-8 text-center text-slate-200">
          <h2 className="mb-3 text-2xl font-bold text-white">无权限访问监控台</h2>
          <p className="mb-6 text-sm text-slate-300">当前账户不是管理员，普通用户和高级用户不可见该页面。</p>
          <Link href="/search" className="rounded-xl border border-white/20 bg-white/5 px-5 py-2.5 text-sm text-slate-200">
            返回检索
          </Link>
        </div>
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.98 }}
      transition={{ duration: 0.4 }}
      className="mx-auto max-w-6xl px-4 pb-20 pt-10"
    >
      <section className="relative overflow-hidden rounded-[2rem] border border-cyan-400/15 bg-[radial-gradient(circle_at_top_left,rgba(34,211,238,0.16),transparent_32%),linear-gradient(180deg,rgba(8,12,22,0.92),rgba(4,8,18,0.98))] p-8 shadow-[0_30px_80px_rgba(0,0,0,0.35)]">
        <div className="absolute inset-y-0 right-0 hidden w-80 bg-[radial-gradient(circle_at_top,rgba(245,158,11,0.16),transparent_62%)] lg:block" />
        <div className="relative flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl text-white">
            <div className="text-xs uppercase tracking-[0.28em] text-cyan-300">Admin Settings Shell</div>
            <h1 className="mt-3 text-3xl font-black sm:text-5xl">爬虫阵列中控</h1>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-300">
              监控台现在按稳定应用壳组织。左侧是长期导航，右侧保留现有业务模块，不再是单页堆叠。
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-sm text-slate-200">
            <div className="rounded-xl border border-white/10 bg-white/5 px-4 py-2.5">
              当前管理员：{portalAuth?.nickname || portalAuth?.username || meQuery.data?.username || "--"}
            </div>
            <Link
              href="/account"
              className="rounded-xl border border-white/15 bg-white/5 px-4 py-2.5 font-medium text-white transition-colors hover:bg-white/10"
            >
              返回账号中心
            </Link>
          </div>
        </div>
      </section>

      <div className="mt-8 grid gap-6 xl:grid-cols-[280px_minmax(0,1fr)]">
        <aside className="rounded-[2rem] border border-white/10 bg-black/30 p-4 shadow-2xl backdrop-blur-xl xl:sticky xl:top-28 xl:self-start">
          <div className="mb-4 px-3 text-xs uppercase tracking-[0.24em] text-slate-500">Admin Sections</div>
          <nav className="space-y-2">
            {ADMIN_NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              return (
                <a
                  key={item.id}
                  href={`#${item.id}`}
                  className="block rounded-[1.4rem] border border-white/5 bg-white/[0.03] px-4 py-4 transition-all hover:border-white/10 hover:bg-white/[0.06]"
                >
                  <div className="flex items-start gap-3">
                    <div className="rounded-2xl bg-white/5 p-2 text-slate-300">
                      <Icon size={18} />
                    </div>
                    <div>
                      <div className="text-sm font-semibold text-white">{item.label}</div>
                      <div className="mt-1 text-xs leading-6 text-slate-400">{item.description}</div>
                    </div>
                  </div>
                </a>
              );
            })}
          </nav>
          <div className="mt-4 rounded-[1.4rem] border border-amber-400/15 bg-amber-500/10 p-4">
            <div className="text-xs uppercase tracking-[0.24em] text-amber-300">Ops Frame</div>
            <div className="mt-2 text-sm font-semibold text-white">数据和动作都保留。</div>
            <div className="mt-2 text-xs leading-6 text-amber-50/80">
              这一层只调整信息架构，不改变用户提权、订单确认、选择器维护和 PDF 解析的业务逻辑。
            </div>
          </div>
        </aside>

        <main className="grid grid-cols-1 gap-6 md:grid-cols-4">
        <section id="overview" className="contents">
        <div className="overflow-hidden rounded-3xl border border-white/10 bg-white/5 p-6 shadow-xl backdrop-blur-xl md:col-span-2">
          <div className="flex items-start justify-between">
            <div>
              <div className="mb-1 font-mono text-xs uppercase tracking-wider text-slate-400">
                24H 爬虫全网吞吐量 (Requests)
              </div>
              <div className="text-4xl font-bold text-white">{dashboard.requests}</div>
            </div>
            <span className="rounded-md border border-cyan-500/30 bg-cyan-500/20 px-2 py-1 text-xs text-cyan-400">
              {dashboard.trend >= 0 ? "+" : ""}
              {dashboard.trend.toFixed(1)}%
            </span>
          </div>
          <ActivityChart dataPoints={dashboard.chartPoints} />
        </div>

        <div className="flex flex-col justify-between rounded-3xl border border-orange-500/30 bg-orange-950/20 p-6 shadow-xl backdrop-blur-xl">
          <div className="mb-2 font-mono text-xs uppercase tracking-wider text-slate-400">
            Urgent Alerts
          </div>
          <div className="font-mono text-4xl font-bold text-orange-400">{dashboard.urgentCount}</div>
          <div className="mt-4 text-xs text-slate-400">离线事件和异常告警会在这里累计。</div>
        </div>

        <div className="flex flex-col justify-between rounded-3xl border border-white/10 bg-white/5 p-6 shadow-xl backdrop-blur-xl">
          <div className="mb-2 font-mono text-xs uppercase tracking-wider text-slate-400">
            Service Status
          </div>
          <div className={`font-mono text-4xl font-bold ${dashboard.activeServices === 2 ? "text-cyan-400" : "text-yellow-400"}`}>
            {dashboard.activeServices}/2
          </div>
          <div className="mt-4 text-xs text-slate-400">
            DB {dashboard.dbState.toUpperCase()} · Redis {dashboard.redisState.toUpperCase()}
          </div>
        </div>

        <div className="flex flex-col justify-between rounded-3xl border border-cyan-500/20 bg-cyan-950/10 p-6 shadow-xl backdrop-blur-xl">
          <div className="mb-2 font-mono text-xs uppercase tracking-wider text-slate-400">
            Content Fingerprint
          </div>
          <div className="font-mono text-4xl font-bold text-cyan-300">
            {((fingerprintStatsQuery.data?.coverage_ratio || 0) * 100).toFixed(1)}%
          </div>
          <div className="mt-3 space-y-1 text-xs text-slate-400">
            <div>
              已覆盖 {fingerprintStatsQuery.data?.fingerprinted_contents ?? "--"} / {fingerprintStatsQuery.data?.total_contents ?? "--"}
            </div>
            <div>待处理 {fingerprintStatsQuery.data?.pending_contents ?? "--"}</div>
            <div>碰撞 {fingerprintStatsQuery.data?.collision_contents ?? "--"}</div>
          </div>
        </div>
        </section>

        <section id="users" className="rounded-3xl border border-white/10 bg-black/40 p-6 shadow-2xl md:col-span-2">
          <h3 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
            <UserCog size={18} className="text-cyan-400" />
            用户管理（最近 10 条）
          </h3>
          <div className="space-y-3">
            {(usersQuery.data?.items || []).map((item) => (
              <div
                key={item.id}
                className="flex items-center justify-between rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3"
              >
                <div>
                  <div className="text-sm font-semibold text-white">{item.nickname || item.username}</div>
                  <div className="text-xs text-slate-400">
                    {item.username} · {item.status}
                  </div>
                  {item.identities.length > 0 ? (
                    <div className="mt-1 text-[11px] text-slate-500">
                      身份：
                      {item.identities
                        .map((identity) =>
                          identity.identity_type === "password"
                            ? `${identity.identity_type}:${identity.login_name || "未命名"}(${identity.status})`
                            : `${identity.identity_type}(${identity.status})`,
                        )
                        .join(" · ")}
                    </div>
                  ) : null}
                  {item.roles.length > 0 ? (
                    <div className="mt-1 text-[11px] text-cyan-300">
                      角色：{item.roles.map((role) => `${role.role_code}(${role.status})`).join(" · ")}
                    </div>
                  ) : null}
                  {item.entitlements.length > 0 ? (
                    <div className="mt-1 text-[11px] text-emerald-300">
                      权益：
                      {item.entitlements
                        .map((entitlement) =>
                          `${entitlement.entitlement_code}(${entitlement.status}${
                            entitlement.expires_at
                              ? `, 到期 ${new Date(entitlement.expires_at).toLocaleDateString("zh-CN")}`
                              : ""
                          })`,
                        )
                        .join(" · ")}
                    </div>
                  ) : null}
                  {item.is_premium && item.premium_expires_at ? (
                    <div className="text-[11px] text-amber-300">
                      高级到期：{new Date(item.premium_expires_at).toLocaleString("zh-CN", { hour12: false })}
                    </div>
                  ) : null}
                </div>
                <div className="flex items-center gap-2">
                  {item.is_admin ? (
                    <>
                      <span className="rounded-md border border-cyan-500/30 bg-cyan-500/10 px-2 py-1 text-xs text-cyan-300">
                        管理员
                      </span>
                      <button
                        type="button"
                        disabled={resettingPasswordUserId === item.id || item.status !== "active"}
                        onClick={() => handleResetUserPassword(item.id, item.username)}
                        className="rounded-md border border-violet-500/30 bg-violet-500/10 px-2 py-1 text-xs text-violet-100 transition-colors hover:bg-violet-500/20 disabled:cursor-not-allowed disabled:opacity-70"
                      >
                        {resettingPasswordUserId === item.id ? "处理中..." : "重置密码"}
                      </button>
                      <button
                        type="button"
                        disabled={creatingPaymentOrderUserId === item.id || item.status !== "active"}
                        onClick={() => handleCreatePaymentOrder(item.id, item.username)}
                        className="rounded-md border border-fuchsia-500/30 bg-fuchsia-500/10 px-2 py-1 text-xs text-fuchsia-100 transition-colors hover:bg-fuchsia-500/20 disabled:cursor-not-allowed disabled:opacity-70"
                      >
                        {creatingPaymentOrderUserId === item.id ? "处理中..." : "建会员单"}
                      </button>
                      <button
                        type="button"
                        disabled={promotingAction === `${item.id}:demote:premium`}
                        onClick={() => handleDemoteUser(item.id, "premium")}
                        className="rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-1 text-xs text-amber-200 transition-colors hover:bg-amber-500/20 disabled:cursor-not-allowed disabled:opacity-70"
                      >
                        {promotingAction === `${item.id}:demote:premium` ? "处理中..." : "降为高级"}
                      </button>
                      <button
                        type="button"
                        disabled={promotingAction === `${item.id}:demote:user`}
                        onClick={() => handleDemoteUser(item.id, "user")}
                        className="rounded-md border border-red-500/30 bg-red-500/10 px-2 py-1 text-xs text-red-200 transition-colors hover:bg-red-500/20 disabled:cursor-not-allowed disabled:opacity-70"
                      >
                        {promotingAction === `${item.id}:demote:user` ? "处理中..." : "降级普通"}
                      </button>
                    </>
                  ) : (
                    <>
                      {item.is_premium ? (
                        <>
                          <span className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-1 text-xs text-emerald-300">
                            高级用户
                          </span>
                          <button
                            type="button"
                            disabled={resettingPasswordUserId === item.id || item.status !== "active"}
                            onClick={() => handleResetUserPassword(item.id, item.username)}
                            className="rounded-md border border-violet-500/30 bg-violet-500/10 px-2 py-1 text-xs text-violet-100 transition-colors hover:bg-violet-500/20 disabled:cursor-not-allowed disabled:opacity-70"
                          >
                            {resettingPasswordUserId === item.id ? "处理中..." : "重置密码"}
                          </button>
                          <button
                            type="button"
                            disabled={creatingPaymentOrderUserId === item.id || item.status !== "active"}
                            onClick={() => handleCreatePaymentOrder(item.id, item.username)}
                            className="rounded-md border border-fuchsia-500/30 bg-fuchsia-500/10 px-2 py-1 text-xs text-fuchsia-100 transition-colors hover:bg-fuchsia-500/20 disabled:cursor-not-allowed disabled:opacity-70"
                          >
                            {creatingPaymentOrderUserId === item.id ? "处理中..." : "建会员单"}
                          </button>
                          <button
                            type="button"
                            disabled={promotingAction === `${item.id}:demote:user`}
                            onClick={() => handleDemoteUser(item.id, "user")}
                            className="rounded-md border border-red-500/30 bg-red-500/10 px-2 py-1 text-xs text-red-200 transition-colors hover:bg-red-500/20 disabled:cursor-not-allowed disabled:opacity-70"
                          >
                            {promotingAction === `${item.id}:demote:user` ? "处理中..." : "降级普通"}
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            type="button"
                            disabled={resettingPasswordUserId === item.id || item.status !== "active"}
                            onClick={() => handleResetUserPassword(item.id, item.username)}
                            className="rounded-md border border-violet-500/30 bg-violet-500/10 px-2 py-1 text-xs text-violet-100 transition-colors hover:bg-violet-500/20 disabled:cursor-not-allowed disabled:opacity-70"
                          >
                            {resettingPasswordUserId === item.id ? "处理中..." : "重置密码"}
                          </button>
                          <button
                            type="button"
                            disabled={creatingPaymentOrderUserId === item.id || item.status !== "active"}
                            onClick={() => handleCreatePaymentOrder(item.id, item.username)}
                            className="rounded-md border border-fuchsia-500/30 bg-fuchsia-500/10 px-2 py-1 text-xs text-fuchsia-100 transition-colors hover:bg-fuchsia-500/20 disabled:cursor-not-allowed disabled:opacity-70"
                          >
                            {creatingPaymentOrderUserId === item.id ? "处理中..." : "建会员单"}
                          </button>
                          <button
                            type="button"
                            disabled={promotingAction === `${item.id}:premium`}
                            onClick={() => handlePromoteUser(item.id, "premium")}
                            className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-1 text-xs text-emerald-200 transition-colors hover:bg-emerald-500/20 disabled:cursor-not-allowed disabled:opacity-70"
                          >
                            {promotingAction === `${item.id}:premium` ? "处理中..." : "提升高级"}
                          </button>
                        </>
                      )}
                      <button
                        type="button"
                        disabled={promotingAction === `${item.id}:admin`}
                        onClick={() => handlePromoteUser(item.id, "admin")}
                        className="rounded-md border border-white/20 bg-white/10 px-2 py-1 text-xs text-white transition-colors hover:bg-white/20 disabled:cursor-not-allowed disabled:opacity-70"
                      >
                        {promotingAction === `${item.id}:admin` ? "处理中..." : "提升管理员"}
                      </button>
                    </>
                  )}
                </div>
              </div>
            ))}
            {isAuthenticated && usersQuery.isLoading ? (
              <div className="text-sm text-slate-400">正在加载用户列表...</div>
            ) : null}
          </div>
        </section>

        <section id="audits" className="rounded-3xl border border-white/10 bg-black/40 p-6 shadow-2xl md:col-span-2">
          <h3 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
            <Activity size={18} className="text-cyan-400" />
            审计事件（admin.*）
          </h3>
          <div className="space-y-2">
            {dashboard.audits.map((item) => (
              <div key={item.id} className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3">
                <div className="mb-1 text-sm font-medium text-cyan-300">{item.event_type}</div>
                <div className="text-xs text-slate-400">
                  {new Date(item.created_at).toLocaleString("zh-CN", { hour12: false })}
                </div>
              </div>
            ))}
            {isAuthenticated && auditsQuery.isLoading ? (
              <div className="text-sm text-slate-400">正在拉取审计日志...</div>
            ) : null}
          </div>
        </section>

        <section id="payments" className="rounded-3xl border border-white/10 bg-black/40 p-6 shadow-2xl md:col-span-4">
          <div className="mb-4 flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <div>
              <h3 className="text-lg font-semibold text-white">会员订单账本</h3>
              <p className="mt-1 text-sm text-slate-400">
                网站侧会员按“订单到账本，再确认支付发放权益”运行。微信支付只保留接口位置，不影响当前账号体系闭环。
              </p>
            </div>
            <div className="text-xs text-slate-400">
              最近 {paymentOrdersQuery.data?.items.length || 0} 条 / 总计 {paymentOrdersQuery.data?.total || 0} 条
            </div>
          </div>

          <div className="overflow-hidden rounded-2xl border border-white/10">
            <div className="grid grid-cols-[1.2fr_0.8fr_0.8fr_0.7fr_0.8fr_0.9fr] gap-3 bg-white/[0.04] px-4 py-3 text-xs font-medium uppercase tracking-wide text-slate-400">
              <div>用户 / 订单</div>
              <div>来源</div>
              <div>状态</div>
              <div>时长</div>
              <div>金额</div>
              <div>操作</div>
            </div>
            <div className="divide-y divide-white/10">
              {(paymentOrdersQuery.data?.items || []).map((order) => (
                <div
                  key={order.id}
                  className="grid grid-cols-[1.2fr_0.8fr_0.8fr_0.7fr_0.8fr_0.9fr] gap-3 px-4 py-3 text-sm text-slate-200"
                >
                  <div>
                    <div className="font-medium text-white">{order.username}</div>
                    <div className="text-[11px] text-slate-500">{order.order_ref}</div>
                  </div>
                  <div>{order.source}</div>
                  <div>
                    <span
                      className={`rounded-md px-2 py-1 text-xs ${
                        order.status === "paid"
                          ? "border border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                          : "border border-amber-500/30 bg-amber-500/10 text-amber-200"
                      }`}
                    >
                      {order.status}
                    </span>
                  </div>
                  <div>{order.duration_days} 天</div>
                  <div>
                    {(order.amount_cents / 100).toFixed(2)} {order.currency}
                  </div>
                  <div>
                    {order.status === "pending" ? (
                      <button
                        type="button"
                        disabled={markingPaymentOrderId === order.id}
                        onClick={() => handleMarkPaymentOrderPaid(order.id, order.username)}
                        className="rounded-md border border-cyan-500/30 bg-cyan-500/10 px-2 py-1 text-xs text-cyan-100 transition-colors hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:opacity-70"
                      >
                        {markingPaymentOrderId === order.id ? "处理中..." : "确认支付"}
                      </button>
                    ) : (
                      <span className="text-xs text-slate-500">
                        {order.paid_at ? new Date(order.paid_at).toLocaleString("zh-CN", { hour12: false }) : "已完成"}
                      </span>
                    )}
                  </div>
                </div>
              ))}
              {isAuthenticated && paymentOrdersQuery.isLoading ? (
                <div className="px-4 py-3 text-sm text-slate-400">正在加载会员订单...</div>
              ) : null}
              {isAuthenticated && !paymentOrdersQuery.isLoading && (paymentOrdersQuery.data?.items.length || 0) === 0 ? (
                <div className="px-4 py-3 text-sm text-slate-400">暂无会员订单记录。</div>
              ) : null}
            </div>
          </div>
        </section>

        <section id="selectors" className="rounded-3xl border border-white/10 bg-black/40 p-6 shadow-2xl md:col-span-4">
          <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <h3 className="flex items-center gap-2 text-lg font-semibold text-white">
                <Settings2 size={18} className="text-cyan-400" />
                栏目选择器编辑
              </h3>
              <p className="mt-1 text-sm text-slate-400">
                管理 Discovery 的列表页提取范围，以及详情页正文抽取区域。默认支持 CSS Selector 和 XPath。
              </p>
            </div>
            <button
              type="button"
              onClick={handleBackfillSiteSections}
              disabled={backfillSiteSectionMutation.isPending}
              className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-4 py-2 text-sm font-medium text-cyan-100 transition-colors hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:opacity-70"
            >
              {backfillSiteSectionMutation.isPending ? "回填中..." : "一键回填空栏目规则"}
            </button>
          </div>

          <div className="mb-6 grid gap-3 md:grid-cols-3">
            <div className="rounded-2xl border border-cyan-500/20 bg-cyan-500/10 p-4">
              <div className="text-sm font-semibold text-cyan-100">List 规则管列表入口</div>
              <p className="mt-2 text-xs leading-6 text-cyan-50/80">
                只框住通知列表，别把页脚、导航、友情链接抓进来。常见写法：`.news-list a` 或 `//ul[@class=&apos;news-list&apos;]//a`
              </p>
            </div>
            <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/10 p-4">
              <div className="text-sm font-semibold text-emerald-100">Detail 规则管正文区域</div>
              <p className="mt-2 text-xs leading-6 text-emerald-50/80">
                只抽公告正文，不要把菜单、上一篇下一篇、版权说明混进去。常见写法：`.article-content` 或 `//article`
              </p>
            </div>
            <div className="rounded-2xl border border-amber-500/20 bg-amber-500/10 p-4">
              <div className="text-sm font-semibold text-amber-100">正确流程</div>
              <p className="mt-2 text-xs leading-6 text-amber-50/80">
                先点“恢复推荐规则”，再点“测试提取”，确认命中后再保存。只有预览结果干净，Discovery 和 NLP 才会稳定。
              </p>
            </div>
          </div>

          <div className="mb-6 flex flex-wrap items-center gap-2 rounded-2xl border border-white/10 bg-white/[0.03] p-3">
            <span className="text-xs uppercase tracking-[0.22em] text-slate-500">栏目视图</span>
            <button
              type="button"
              onClick={() => setSelectorView("all")}
              className={`rounded-lg px-3 py-2 text-sm transition-colors ${
                selectorView === "all"
                  ? "bg-cyan-500 text-white"
                  : "border border-white/10 bg-black/20 text-slate-300 hover:bg-white/10"
              }`}
            >
              全部栏目 {selectorSummary.total}
            </button>
            <button
              type="button"
              onClick={() => setSelectorView("attention")}
              className={`rounded-lg px-3 py-2 text-sm transition-colors ${
                selectorView === "attention"
                  ? "bg-amber-500 text-slate-950"
                  : "border border-white/10 bg-black/20 text-slate-300 hover:bg-white/10"
              }`}
            >
              异常栏目 {selectorSummary.attention}
            </button>
            <button
              type="button"
              onClick={() => setSelectorView("preview-warning")}
              className={`rounded-lg px-3 py-2 text-sm transition-colors ${
                selectorView === "preview-warning"
                  ? "bg-fuchsia-500 text-white"
                  : "border border-white/10 bg-black/20 text-slate-300 hover:bg-white/10"
              }`}
            >
              预览有警告 {selectorSummary.previewWarning}
            </button>
            <span className="ml-auto text-xs text-slate-500">
              “异常栏目”包含发现失败、最近有错或预览出现 warning 的栏目。
            </span>
          </div>

          <div className="space-y-4">
            {visibleSiteSections.map((item) => {
              const draft = siteSectionEdits[item.id] || buildSelectorDraft(item);
              const preview = siteSectionPreviews[item.id];
              const hasAttention = hasSelectorAttention(item, preview);
              return (
                <div
                  key={item.id}
                  className={`rounded-2xl border p-4 ${
                    hasAttention
                      ? "border-amber-500/25 bg-amber-500/[0.06]"
                      : "border-white/10 bg-white/[0.03]"
                  }`}
                >
                  <div className="mb-4 flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <div className="text-base font-semibold text-white">{item.name}</div>
                        {hasAttention ? (
                          <span className="rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-1 text-[11px] uppercase tracking-wide text-amber-200">
                            需要处理
                          </span>
                        ) : null}
                        {(preview?.warnings.length || 0) > 0 ? (
                          <span className="rounded-md border border-fuchsia-500/30 bg-fuchsia-500/10 px-2 py-1 text-[11px] uppercase tracking-wide text-fuchsia-200">
                            预览警告 {preview?.warnings.length}
                          </span>
                        ) : null}
                      </div>
                      <div className="text-xs text-slate-400">
                        {item.school_name || "未绑定学校"} · {item.department_name || "未绑定院系"} · {item.section_type}
                      </div>
                      <div className="mt-1 break-all text-xs text-slate-500">{item.section_url}</div>
                    </div>
                    <div className="text-right text-xs text-slate-400">
                      <div>发现状态：{item.last_discovery_status || "未执行"}</div>
                      <div>
                        更新时间：
                        {new Date(item.updated_at).toLocaleString("zh-CN", { hour12: false })}
                      </div>
                      {item.last_error ? <div className="mt-1 text-red-300">最近错误：{item.last_error}</div> : null}
                    </div>
                  </div>

                  <div className="grid gap-3 md:grid-cols-2">
                    <label className="space-y-2">
                      <span className="text-xs font-medium uppercase tracking-wide text-slate-400">List CSS</span>
                      <input
                        value={draft.listCssSelector}
                        onChange={(event) => handleSiteSectionDraftChange(item.id, "listCssSelector", event.target.value)}
                        placeholder=".article-list a"
                        className="w-full rounded-xl border border-white/10 bg-black/30 px-4 py-3 text-sm text-white outline-none transition-colors focus:border-cyan-400"
                      />
                      <div className="text-xs text-slate-500">推荐：{selectorString(item.suggested_list_selector_config, "css_selector") || "自动默认规则"}</div>
                    </label>
                    <label className="space-y-2">
                      <span className="text-xs font-medium uppercase tracking-wide text-slate-400">List XPath</span>
                      <input
                        value={draft.listXPathSelector}
                        onChange={(event) => handleSiteSectionDraftChange(item.id, "listXPathSelector", event.target.value)}
                        placeholder="//ul[@class='news-list']//a"
                        className="w-full rounded-xl border border-white/10 bg-black/30 px-4 py-3 text-sm text-white outline-none transition-colors focus:border-cyan-400"
                      />
                      <div className="text-xs text-slate-500">示例：`//div[contains(@class,&apos;article-list&apos;)]//a[@href]`</div>
                    </label>
                    <label className="space-y-2">
                      <span className="text-xs font-medium uppercase tracking-wide text-slate-400">Detail CSS</span>
                      <input
                        value={draft.detailCssSelector}
                        onChange={(event) =>
                          handleSiteSectionDraftChange(item.id, "detailCssSelector", event.target.value)
                        }
                        placeholder=".article-body"
                        className="w-full rounded-xl border border-white/10 bg-black/30 px-4 py-3 text-sm text-white outline-none transition-colors focus:border-cyan-400"
                      />
                      <div className="text-xs text-slate-500">推荐：{selectorString(item.suggested_detail_selector_config, "css_selector") || "自动默认规则"}</div>
                    </label>
                    <label className="space-y-2">
                      <span className="text-xs font-medium uppercase tracking-wide text-slate-400">Detail XPath</span>
                      <input
                        value={draft.detailXPathSelector}
                        onChange={(event) =>
                          handleSiteSectionDraftChange(item.id, "detailXPathSelector", event.target.value)
                        }
                        placeholder="//div[@class='article-body']"
                        className="w-full rounded-xl border border-white/10 bg-black/30 px-4 py-3 text-sm text-white outline-none transition-colors focus:border-cyan-400"
                      />
                      <div className="text-xs text-slate-500">示例：`//article | //div[contains(@class,&apos;content&apos;)]`</div>
                    </label>
                  </div>

                  <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-white/10 bg-black/20 p-3">
                    <div className="text-xs text-slate-500">
                      当前栏目 URL：{item.section_url}
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        onClick={() => handleResetSiteSectionToSuggested(item)}
                        className="inline-flex items-center gap-2 rounded-xl border border-white/15 bg-white/5 px-3 py-2 text-sm text-slate-200 transition-colors hover:bg-white/10"
                      >
                        <RotateCcw size={14} />
                        恢复推荐规则
                      </button>
                      <button
                        type="button"
                        onClick={() => handlePreviewSiteSection(item)}
                        disabled={siteSectionPreviewingId === item.id}
                        className="inline-flex items-center gap-2 rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-3 py-2 text-sm font-semibold text-cyan-100 transition-colors hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:opacity-70"
                      >
                        <TestTube2 size={14} />
                        {siteSectionPreviewingId === item.id ? "测试中..." : "测试提取"}
                      </button>
                      <button
                        type="button"
                        onClick={() => handleSaveSiteSection(item)}
                        disabled={siteSectionSavingId === item.id}
                        className="rounded-xl bg-cyan-500 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-70"
                      >
                        {siteSectionSavingId === item.id ? "保存中..." : "保存选择器"}
                      </button>
                    </div>
                  </div>

                  {preview ? (
                    <div className="mt-4 grid gap-4 rounded-2xl border border-white/10 bg-black/25 p-4 md:grid-cols-[1.05fr_1fr]">
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <div className="text-sm font-semibold text-white">列表页命中预览</div>
                          <span className="rounded-md border border-cyan-500/30 bg-cyan-500/10 px-2 py-1 text-xs text-cyan-200">
                            命中 {preview.list_match_count} 条
                          </span>
                        </div>
                        <div className="space-y-2">
                          {preview.list_preview_items.length > 0 ? (
                            preview.list_preview_items.map((link, index) => (
                              <div key={`${link.url}:${index}`} className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
                                <div className="flex items-center gap-2">
                                  <span className="rounded-md border border-white/15 bg-white/5 px-2 py-1 text-[11px] uppercase tracking-wide text-slate-300">
                                    {link.link_type}
                                  </span>
                                  <div className="line-clamp-1 text-sm font-medium text-white">{link.text || "未命名链接"}</div>
                                </div>
                                <a
                                  href={link.url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="mt-2 flex items-center gap-1 break-all text-xs text-cyan-300 hover:text-cyan-200"
                                >
                                  <ExternalLink size={12} />
                                  {link.url}
                                </a>
                                {link.link_type === "html" ? (
                                  <div className="mt-3 flex items-center justify-end">
                                    <button
                                      type="button"
                                      onClick={() => handlePreviewSiteSection(item, link.url)}
                                      disabled={siteSectionPreviewingId === item.id}
                                      className={`rounded-lg px-3 py-2 text-xs font-medium transition-colors ${
                                        preview.detail_preview_url === link.url
                                          ? "border border-emerald-500/30 bg-emerald-500/10 text-emerald-100"
                                          : "border border-white/10 bg-black/20 text-slate-200 hover:bg-white/10"
                                      } disabled:cursor-not-allowed disabled:opacity-70`}
                                    >
                                      {preview.detail_preview_url === link.url ? "当前详情样本" : "用这条重测正文"}
                                    </button>
                                  </div>
                                ) : null}
                              </div>
                            ))
                          ) : (
                            <div className="rounded-xl border border-dashed border-white/10 px-4 py-6 text-sm text-slate-400">
                              当前规则没有命中任何可用链接。
                            </div>
                          )}
                        </div>
                      </div>

                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <div className="text-sm font-semibold text-white">详情页正文预览</div>
                          <span className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-1 text-xs text-emerald-200">
                            {preview.detail_extraction_method ? `来源：${preview.detail_extraction_method}` : "未生成正文"}
                          </span>
                        </div>
                        {preview.detail_title ? <div className="text-sm font-medium text-white">{preview.detail_title}</div> : null}
                        {preview.detail_preview_url ? (
                          <a
                            href={preview.detail_preview_url}
                            target="_blank"
                            rel="noreferrer"
                            className="flex items-center gap-1 break-all text-xs text-cyan-300 hover:text-cyan-200"
                          >
                            <ExternalLink size={12} />
                            {preview.detail_preview_url}
                          </a>
                        ) : null}
                        <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3 text-sm leading-7 text-slate-200">
                          {preview.detail_excerpt || "当前没有拿到正文，请先检查详情页规则是否指向真正的公告内容区域。"}
                        </div>
                        {preview.warnings.length > 0 ? (
                          <div className="space-y-2 rounded-xl border border-amber-500/20 bg-amber-500/10 p-3">
                            <div className="flex items-center gap-2 text-sm font-medium text-amber-100">
                              <TriangleAlert size={14} />
                              预览提示
                            </div>
                            <ul className="space-y-1 text-xs leading-6 text-amber-50/85">
                              {preview.warnings.map((warning, index) => (
                                <li key={`${warning}:${index}`}>- {warning}</li>
                              ))}
                            </ul>
                          </div>
                        ) : null}
                        {preview.suggestions.length > 0 ? (
                          <div className="space-y-2 rounded-xl border border-cyan-500/20 bg-cyan-500/10 p-3">
                            <div className="flex items-center gap-2 text-sm font-medium text-cyan-100">
                              <WandSparkles size={14} />
                              建议修复
                            </div>
                            <ul className="space-y-1 text-xs leading-6 text-cyan-50/90">
                              {preview.suggestions.map((suggestion, index) => (
                                <li key={`${suggestion}:${index}`}>- {suggestion}</li>
                              ))}
                            </ul>
                          </div>
                        ) : null}
                      </div>
                    </div>
                  ) : null}
                </div>
              );
            })}
            {isAuthenticated && !siteSectionsQuery.isLoading && visibleSiteSections.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-white/10 px-4 py-8 text-sm text-slate-400">
                当前筛选条件下没有栏目。先运行一次“测试提取”，再切到“预览有警告”会更有意义。
              </div>
            ) : null}
            {isAuthenticated && siteSectionsQuery.isLoading ? (
              <div className="text-sm text-slate-400">正在加载栏目列表...</div>
            ) : null}
          </div>
        </section>

        <section id="content-files" className="rounded-3xl border border-white/10 bg-black/40 p-6 shadow-2xl md:col-span-4">
          <div className="mb-4 flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <div>
              <h3 className="flex items-center gap-2 text-lg font-semibold text-white">
                <FileSearch size={18} className="text-cyan-400" />
                PDF 解析队列
              </h3>
              <p className="mt-1 text-sm text-slate-400">
                查看 `content_files` 的解析状态，支持对 `pending / needs_ocr / failed / done` 文件手动重试解析。
              </p>
            </div>
            <div className="text-xs text-slate-400">
              最近 {contentFilesQuery.data?.items.length || 0} 条 / 总计 {contentFilesQuery.data?.total || 0} 条
            </div>
          </div>

          <div className="overflow-hidden rounded-2xl border border-white/10">
            <div className="grid grid-cols-[1.4fr_1fr_0.9fr_0.9fr_1.2fr] gap-3 bg-white/[0.04] px-4 py-3 text-xs font-medium uppercase tracking-wide text-slate-400">
              <div>文件</div>
              <div>学校 / 栏目</div>
              <div>解析状态</div>
              <div>OCR 状态</div>
              <div className="text-right">操作</div>
            </div>
            <div className="divide-y divide-white/10">
              {(contentFilesQuery.data?.items || []).map((item) => (
                <div key={item.id} className="grid grid-cols-[1.4fr_1fr_0.9fr_0.9fr_1.2fr] gap-3 px-4 py-4 text-sm">
                  <div className="min-w-0">
                    <div className="truncate font-semibold text-white">{item.content_title || item.link_title || item.file_url}</div>
                    <a
                      href={item.file_url}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-1 block truncate text-xs text-cyan-300 hover:text-cyan-200"
                    >
                      {item.file_url}
                    </a>
                    {item.text_excerpt ? <div className="mt-2 line-clamp-2 text-xs text-slate-400">{item.text_excerpt}</div> : null}
                  </div>
                  <div className="text-xs text-slate-300">
                    <div>{item.school_name || "未绑定学校"}</div>
                    <div className="mt-1 text-slate-500">{item.site_section_name || "未绑定栏目"}</div>
                  </div>
                  <div>
                    <span className={statusBadgeClass(item.parse_status)}>{item.parse_status}</span>
                  </div>
                  <div>
                    <span className={ocrBadgeClass(item.ocr_status)}>{item.ocr_status}</span>
                  </div>
                  <div className="flex items-center justify-end gap-2">
                    <button
                      type="button"
                      onClick={() => handleRetryContentFile(item)}
                      disabled={retryingContentFileId === item.id}
                      className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-3 py-2 text-xs font-semibold text-cyan-100 transition-colors hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:opacity-70"
                    >
                      {retryingContentFileId === item.id ? "处理中..." : "重试解析"}
                    </button>
                  </div>
                </div>
              ))}
              {isAuthenticated && contentFilesQuery.isLoading ? (
                <div className="px-4 py-5 text-sm text-slate-400">正在加载 PDF 解析队列...</div>
              ) : null}
              {isAuthenticated && !contentFilesQuery.isLoading && (contentFilesQuery.data?.items.length || 0) === 0 ? (
                <div className="px-4 py-5 text-sm text-slate-400">当前还没有 PDF 文件记录。</div>
              ) : null}
            </div>
          </div>
        </section>

        <section id="runtime" className="mt-2 overflow-hidden rounded-3xl border border-white/10 bg-black/40 shadow-2xl md:col-span-4">
          <div className="flex items-center gap-2 border-b border-white/10 bg-black/60 px-6 py-4">
            <div className="flex gap-2">
              <div className="h-3 w-3 rounded-full bg-red-500/80" />
              <div className="h-3 w-3 rounded-full bg-yellow-500/80" />
              <div className="h-3 w-3 rounded-full bg-green-500/80" />
            </div>
            <span className="ml-4 font-mono text-xs text-slate-500">
              health status · app={healthQuery.data?.app_env || "--"} · db={dashboard.dbState} · redis={dashboard.redisState}
            </span>
          </div>
          <div className="h-60 overflow-y-auto p-6 font-mono text-sm leading-relaxed text-slate-300">
            {dashboard.audits.length === 0 ? (
              <div className="text-slate-400">暂无审计日志，登录并执行管理员动作后会出现。</div>
            ) : (
              dashboard.audits.map((item) => (
                <div key={item.id} className="mb-2">
                  <span className="text-slate-500">
                    [{new Date(item.created_at).toLocaleTimeString("zh-CN", { hour12: false })}]
                  </span>{" "}
                  <span className="text-cyan-300">{item.event_type}</span> · {item.endpoint}
                </div>
              ))
            )}
          </div>
        </section>
        </main>
      </div>

      {message ? (
        <div className="mt-6 rounded-2xl border border-white/10 bg-black/30 p-4 text-sm text-slate-300">
          {message}
        </div>
      ) : null}
    </motion.div>
  );
}

function buildSelectorDraft(item: SiteSectionItem): SelectorDraft {
  return {
    listCssSelector: selectorString(item.list_selector_config, "css_selector"),
    listXPathSelector: selectorString(item.list_selector_config, "xpath_selector"),
    detailCssSelector: selectorString(item.detail_selector_config, "css_selector"),
    detailXPathSelector: selectorString(item.detail_selector_config, "xpath_selector"),
  };
}

function buildSuggestedSelectorDraft(item: SiteSectionItem): SelectorDraft {
  return {
    listCssSelector: selectorString(item.suggested_list_selector_config, "css_selector"),
    listXPathSelector: selectorString(item.suggested_list_selector_config, "xpath_selector"),
    detailCssSelector: selectorString(item.suggested_detail_selector_config, "css_selector"),
    detailXPathSelector: selectorString(item.suggested_detail_selector_config, "xpath_selector"),
  };
}

function emptySelectorDraft(): SelectorDraft {
  return {
    listCssSelector: "",
    listXPathSelector: "",
    detailCssSelector: "",
    detailXPathSelector: "",
  };
}

function selectorString(config: Record<string, unknown>, key: string) {
  const value = config?.[key];
  return typeof value === "string" ? value : "";
}

function buildListSelectorConfig(item: SiteSectionItem, draft: SelectorDraft) {
  return {
    ...item.list_selector_config,
    css_selector: draft.listCssSelector.trim(),
    xpath_selector: draft.listXPathSelector.trim(),
    fallback_to_all_links: item.list_selector_config?.fallback_to_all_links ?? true,
  };
}

function buildDetailSelectorConfig(item: SiteSectionItem, draft: SelectorDraft) {
  return {
    ...item.detail_selector_config,
    css_selector: draft.detailCssSelector.trim(),
    xpath_selector: draft.detailXPathSelector.trim(),
    fallback_to_full_text: item.detail_selector_config?.fallback_to_full_text ?? true,
  };
}

function buildChartPoints(
  audits: Array<{
    created_at: string;
  }>,
) {
  if (audits.length === 0) {
    return new Array(12).fill(0);
  }

  const now = Date.now();
  const buckets = new Array(12).fill(0);

  audits.forEach((item) => {
    const diffHours = (now - new Date(item.created_at).getTime()) / 3_600_000;
    const bucket = 11 - Math.min(11, Math.max(0, Math.floor(diffHours / 2)));
    buckets[bucket] += 1;
  });

  return buckets.map((value, index) => value * 18 + 18 + index * 2);
}

function hasSelectorAttention(item: SiteSectionItem, preview?: SiteSectionSelectorPreviewResponse) {
  return Boolean(
    item.last_error ||
      (item.last_discovery_status && item.last_discovery_status !== "done") ||
      ((preview?.warnings.length || 0) > 0),
  );
}

function average(values: number[]) {
  if (values.length === 0) return 0;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function statusBadgeClass(status: string) {
  if (status === "done") return "rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-1 text-xs text-emerald-300";
  if (status === "pending") return "rounded-md border border-cyan-500/30 bg-cyan-500/10 px-2 py-1 text-xs text-cyan-300";
  if (status === "needs_ocr") return "rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-1 text-xs text-amber-300";
  if (status === "failed") return "rounded-md border border-red-500/30 bg-red-500/10 px-2 py-1 text-xs text-red-300";
  return "rounded-md border border-white/20 bg-white/10 px-2 py-1 text-xs text-slate-200";
}

function ocrBadgeClass(status: string) {
  if (status === "skipped_mvp") return "rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-1 text-xs text-amber-200";
  if (status === "not_started") return "rounded-md border border-white/20 bg-white/10 px-2 py-1 text-xs text-slate-200";
  if (status === "done") return "rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-1 text-xs text-emerald-300";
  return "rounded-md border border-white/20 bg-white/10 px-2 py-1 text-xs text-slate-200";
}
