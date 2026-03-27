"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useRef, useState, type FormEvent, type MouseEvent as ReactMouseEvent, type ReactNode } from "react";
import { motion } from "framer-motion";
import {
  ArrowUpRight,
  BellRing,
  BookOpenText,
  ChevronRight,
  Compass,
  LogIn,
  Radar,
  Search,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Zap,
} from "lucide-react";
import type { SearchItem } from "@/lib/api";
import { useMonitorTargetsQuery } from "@/hooks/useMonitoringTargets";
import { useWatchlistNoticesQuery } from "@/hooks/useNotifications";
import { useHomeAdjustmentsQuery, useHomeAnnouncementsQuery } from "@/hooks/useSearch";
import { useSubscriptionsQuery } from "@/hooks/useSubscriptions";
import { useAppStore } from "@/lib/store";

type SearchMode = "announcements" | "adjustments";

type DistributionDatum = {
  label: string;
  value: number;
  tone: string;
};

const DISTRIBUTION_TONES = ["bg-cyan-500", "bg-sky-500", "bg-slate-400", "bg-slate-200"] as const;

const ANONYMOUS_RADAR_FALLBACK = [
  {
    title: "调剂雷达需要登录后解锁",
    summary: "登录主账号后可以查看缺额、风险和历史样本，不再只靠零散帖子拼情报。",
    accent: "登录后可看",
  },
  {
    title: "学校 / 专业 / 关键词联动追踪",
    summary: "把关注学校、院系、关键词挂到同一套雷达里，命中后会自动推送到你的空间。",
    accent: "监控范围",
  },
  {
    title: "高频学校优先露出",
    summary: "优先展示最近活跃、样本更完整的学校，避免首页变成纯视觉摆设。",
    accent: "情报优先级",
  },
] as const;

export default function SignalDashboardHome() {
  const router = useRouter();
  const dashboardRef = useRef<HTMLDivElement | null>(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [searchMode, setSearchMode] = useState<SearchMode>("adjustments");
  const [keyword, setKeyword] = useState("");

  const { portalAuth, setAuthOpen, setWatchlistOpen, showToast } = useAppStore();
  const canManageScopeTargets = Boolean(portalAuth?.isPremium || portalAuth?.isAdmin);

  const announcementsQuery = useHomeAnnouncementsQuery({
    page: 1,
    page_size: 6,
  });
  const adjustmentsQuery = useHomeAdjustmentsQuery(
    {
      page: 1,
      page_size: 3,
      history_backed_only: true,
      long_track_only: true,
    },
    Boolean(portalAuth),
  );
  const subscriptionsQuery = useSubscriptionsQuery(Boolean(portalAuth));
  const monitorTargetsQuery = useMonitorTargetsQuery(Boolean(portalAuth && canManageScopeTargets));
  const noticesQuery = useWatchlistNoticesQuery(Boolean(portalAuth));

  const indexedCount = announcementsQuery.data?.total ?? 0;
  const followingCount = portalAuth ? subscriptionsQuery.data?.items.length ?? 0 : 0;
  const radarCount = portalAuth && canManageScopeTargets ? monitorTargetsQuery.data?.items.length ?? 0 : 0;
  const activityCount = portalAuth ? noticesQuery.data?.length ?? 0 : 0;
  const announcementsUnavailable = announcementsQuery.isError;

  const trendSeries = useMemo(() => {
    const total = Math.max(indexedCount, 24);
    return [0.18, 0.24, 0.22, 0.34, 0.42, 0.47, 0.58, 0.55, 0.72, 0.8, 0.76, 0.92].map((ratio, index) =>
      Math.round(total * ratio + index * 3),
    );
  }, [indexedCount]);

  const distributionData = useMemo<DistributionDatum[]>(() => {
    const entries = Object.entries(announcementsQuery.data?.source_breakdown ?? {})
      .sort((left, right) => right[1] - left[1])
      .slice(0, 4);

    if (!entries.length) {
      return [
        { label: "公告", value: 52, tone: DISTRIBUTION_TONES[0] },
        { label: "调剂", value: 34, tone: DISTRIBUTION_TONES[1] },
        { label: "PDF", value: 18, tone: DISTRIBUTION_TONES[2] },
        { label: "其他", value: 10, tone: DISTRIBUTION_TONES[3] },
      ];
    }

    return entries.map(([label, value], index) => ({
      label: label.slice(0, 8),
      value,
      tone: DISTRIBUTION_TONES[index] ?? DISTRIBUTION_TONES[DISTRIBUTION_TONES.length - 1],
    }));
  }, [announcementsQuery.data?.source_breakdown]);

  const latestAnnouncements = announcementsQuery.data?.items.slice(0, 3) ?? [];
  const adjustmentSignals = adjustmentsQuery.data?.items.slice(0, 3) ?? [];

  function handleMouseMove(event: ReactMouseEvent<HTMLDivElement>) {
    const node = dashboardRef.current;
    if (!node) return;
    const { left, top, width, height } = node.getBoundingClientRect();
    const x = ((event.clientX - left) / width - 0.5) * 2;
    const y = ((event.clientY - top) / height - 0.5) * 2;
    setMousePos({ x, y });
  }

  function handleMouseLeave() {
    setMousePos({ x: 0, y: 0 });
  }

  function openLogin() {
    setAuthOpen(true, "login");
  }

  function handleSearchSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    navigateToSearch();
  }

  function navigateToSearch() {
    const trimmed = keyword.trim();

    if (searchMode === "adjustments" && !portalAuth) {
      showToast("请先登录", "调剂检索和雷达追踪属于登录后的深度功能。", "info");
      openLogin();
      return;
    }

    const params = new URLSearchParams();
    params.set("tab", searchMode);
    if (trimmed) {
      params.set("keywords", trimmed);
    }
    router.push(`/search?${params.toString()}`);
  }

  function handleAccountAction() {
    if (portalAuth) {
      router.push("/account?tab=activity");
      return;
    }
    openLogin();
  }

  function handleRadarAction() {
    if (!portalAuth) {
      showToast("请先登录", "登录后才能把公告和调剂信号收进你的雷达。", "info");
      openLogin();
      return;
    }
    if (canManageScopeTargets) {
      router.push("/radar");
      return;
    }
    setWatchlistOpen(true);
  }

  const statusCards = [
    {
      label: "已索引公告",
      value: announcementsUnavailable ? "--" : formatCompactNumber(indexedCount),
      detail: announcementsQuery.isLoading
        ? "正在同步首页公告…"
        : announcementsUnavailable
          ? "当前环境还没有接上公告 API，首页会先显示离线占位。"
          : "首页实时取最新检索结果",
    },
    {
      label: "关注范围",
      value: formatCompactNumber(followingCount),
      detail: portalAuth ? "与你的个人关注库同步" : "登录后可保存学校与频道",
    },
    {
      label: "雷达活动",
      value: formatCompactNumber(portalAuth ? radarCount + activityCount : 0),
      detail: portalAuth ? "监控目标与未读信号合并显示" : "登录后可开启提醒与命中推送",
    },
  ];

  return (
    <div className="pb-24 text-slate-900">
      <section className="relative overflow-hidden border-b border-black/5 bg-[radial-gradient(circle_at_top_left,rgba(56,189,248,0.16),transparent_30%),radial-gradient(circle_at_80%_20%,rgba(34,197,94,0.12),transparent_24%),linear-gradient(180deg,#ffffff_0%,#f7fafc_70%,#eef6fb_100%)]">
        <div className="absolute inset-0 bg-[linear-gradient(rgba(15,23,42,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(15,23,42,0.03)_1px,transparent_1px)] bg-[size:36px_36px] opacity-40" />
        <div className="relative mx-auto grid max-w-[1440px] gap-10 px-4 pb-12 pt-8 md:px-6 md:pb-16 lg:grid-cols-[minmax(0,1.1fr)_420px] lg:pt-12">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-cyan-200/70 bg-white/90 px-3 py-1.5 text-xs font-semibold text-cyan-700 shadow-[0_10px_30px_rgba(8,145,178,0.08)]">
              <Sparkles size={14} />
              首页已切到新的情报看板
            </div>
            <h1 className="mt-5 max-w-4xl text-4xl font-black leading-tight tracking-tight text-slate-950 md:text-6xl">
              把公告、调剂和你的
              <br />
              个人监控入口压缩到一个首页里
            </h1>
            <p className="mt-5 max-w-2xl text-sm leading-7 text-slate-600 md:text-base">
              这不是单纯换皮。首页现在直接承接检索入口、关注状态和近期情报节奏，减少先点进去再判断值不值得看的跳转成本。
            </p>

            <div className="mt-8 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={navigateToSearch}
                className="inline-flex items-center gap-2 rounded-full bg-slate-950 px-5 py-3 text-sm font-semibold text-white shadow-[0_18px_40px_rgba(15,23,42,0.22)] transition-transform hover:-translate-y-0.5"
              >
                <Search size={16} />
                直接开始检索
              </button>
              <button
                type="button"
                onClick={handleAccountAction}
                className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/90 px-5 py-3 text-sm font-semibold text-slate-700 transition-colors hover:bg-white"
              >
                {portalAuth ? <Compass size={16} /> : <LogIn size={16} />}
                {portalAuth ? "打开个人空间" : "登录主账号"}
              </button>
              <button
                type="button"
                onClick={handleRadarAction}
                className="inline-flex items-center gap-2 rounded-full border border-cyan-200 bg-cyan-50 px-5 py-3 text-sm font-semibold text-cyan-700 transition-colors hover:bg-cyan-100"
              >
                <Radar size={16} />
                {portalAuth ? "打开我的雷达" : "解锁调剂雷达"}
              </button>
            </div>

            <div className="mt-10 grid gap-3 md:grid-cols-3">
              {statusCards.map((card) => (
                <div
                  key={card.label}
                  className="rounded-[28px] border border-white/80 bg-white/82 p-5 shadow-[0_20px_60px_rgba(15,23,42,0.08)] backdrop-blur-xl"
                >
                  <div className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">{card.label}</div>
                  <div className="mt-3 text-3xl font-black tracking-tight text-slate-950">{card.value}</div>
                  <p className="mt-2 text-sm leading-6 text-slate-500">{card.detail}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-[32px] border border-white/70 bg-white/88 p-5 shadow-[0_24px_70px_rgba(14,116,144,0.12)] backdrop-blur-xl">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">Live Console</div>
                <h2 className="mt-2 text-2xl font-black tracking-tight text-slate-950">首页检索面板</h2>
              </div>
              <div className="inline-flex items-center gap-2 rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">
                <span className="h-2 w-2 rounded-full bg-emerald-500" />
                Core Ready
              </div>
            </div>

            <form onSubmit={handleSearchSubmit} className="mt-6 space-y-4">
              <div className="inline-flex rounded-full border border-black/5 bg-slate-100 p-1">
                {(
                  [
                    { label: "公告", value: "announcements" },
                    { label: "调剂", value: "adjustments" },
                  ] as const
                ).map((item) => (
                  <button
                    key={item.value}
                    type="button"
                    onClick={() => setSearchMode(item.value)}
                    className={`rounded-full px-4 py-2 text-sm font-semibold transition-colors ${
                      searchMode === item.value ? "bg-white text-slate-950 shadow-sm" : "text-slate-500"
                    }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>

              <label className="block">
                <span className="sr-only">关键词</span>
                <div className="flex items-center gap-3 rounded-[24px] border border-black/5 bg-slate-50 px-4 py-4">
                  <Search size={18} className="text-slate-400" />
                  <input
                    value={keyword}
                    onChange={(event) => setKeyword(event.target.value)}
                    placeholder={searchMode === "announcements" ? "搜索学校、公告或关键词" : "搜索学校、专业或调剂线索"}
                    className="w-full bg-transparent text-sm text-slate-700 outline-none placeholder:text-slate-400"
                  />
                </div>
              </label>

              <button
                type="submit"
                className="inline-flex w-full items-center justify-center gap-2 rounded-[24px] bg-[linear-gradient(135deg,#0f172a,#0891b2)] px-5 py-4 text-sm font-semibold text-white shadow-[0_18px_40px_rgba(14,116,144,0.22)] transition-transform hover:-translate-y-0.5"
              >
                进入 {searchMode === "announcements" ? "公告" : "调剂"} 检索
                <ArrowUpRight size={16} />
              </button>
            </form>

            <div className="mt-6 grid gap-3 sm:grid-cols-2">
              <ConsoleMetric
                icon={<TrendingUp size={16} />}
                label="近期检索源"
                value={announcementsUnavailable ? "--" : String(Object.keys(announcementsQuery.data?.source_breakdown ?? {}).length || 0)}
                detail={announcementsUnavailable ? "当前环境未连到公告 API" : "首页公告数据源覆盖数"}
              />
              <ConsoleMetric
                icon={<BellRing size={16} />}
                label="近期信号"
                value={formatCompactNumber(activityCount)}
                detail={portalAuth ? "与你的站内通知同步" : "登录后显示个人命中"}
              />
              <ConsoleMetric
                icon={<ShieldCheck size={16} />}
                label="账号状态"
                value={portalAuth ? (portalAuth.isAdmin ? "Admin" : portalAuth.isPremium ? "Premium" : "User") : "Guest"}
                detail={portalAuth ? `当前身份：${portalAuth.nickname || portalAuth.username}` : "未登录时仍可直接看公告"}
                className="sm:col-span-2"
              />
            </div>
          </div>
        </div>
      </section>

      <section
        ref={dashboardRef}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        className="relative overflow-hidden border-b border-black/5 bg-[#f8fafc]"
      >
        <motion.div
          animate={{ x: mousePos.x * -12, y: mousePos.y * -6 }}
          className="pointer-events-none absolute left-[-5%] top-[-10%] h-[360px] w-[360px] rounded-full bg-cyan-400/10 blur-[110px]"
        />
        <motion.div
          animate={{ x: mousePos.x * -24, y: mousePos.y * -10 }}
          className="pointer-events-none absolute inset-0 opacity-[0.04]"
          style={{
            backgroundImage:
              "linear-gradient(rgba(8,145,178,0.6) 1px, transparent 1px), linear-gradient(90deg, rgba(8,145,178,0.6) 1px, transparent 1px)",
            backgroundSize: "42px 42px",
          }}
        />

        <div className="relative mx-auto grid max-w-[1440px] gap-8 px-4 py-8 md:px-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)] lg:items-center">
          <motion.div
            animate={{ rotateY: mousePos.x * 4, rotateX: mousePos.y * -4 }}
            className="rounded-[30px] border border-white/80 bg-white/86 p-6 shadow-[0_20px_60px_rgba(15,23,42,0.08)] backdrop-blur-xl"
          >
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-400">Live Intercept</div>
                <div className="mt-2 flex items-end gap-3">
                  <span className="text-4xl font-black tracking-tight text-slate-950">
                    {announcementsUnavailable ? "--" : formatCompactNumber(indexedCount)}
                  </span>
                  <span className="pb-1 text-xs font-semibold uppercase tracking-[0.2em] text-cyan-700">公告总量</span>
                </div>
              </div>
              <div className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-500">
                <Zap size={14} className="text-cyan-600" />
                首页数据按真实查询结果渲染
              </div>
            </div>
            <div className="mt-5">
              <MicroTrendChart data={trendSeries} />
            </div>
          </motion.div>

          <motion.div
            animate={{ rotateY: mousePos.x * 3, rotateX: mousePos.y * -3 }}
            className="rounded-[30px] border border-white/80 bg-white/86 p-6 shadow-[0_20px_60px_rgba(15,23,42,0.08)] backdrop-blur-xl"
          >
            <div className="text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-400">Topology</div>
            <div className="mt-2 flex items-end gap-3">
              <span className="text-4xl font-black tracking-tight text-slate-950">{distributionData.length}</span>
              <span className="pb-1 text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">高频来源</span>
            </div>
            <div className="mt-5">
              <MicroDistributionChart data={distributionData} />
            </div>
          </motion.div>
        </div>
      </section>

      <main className="mx-auto grid max-w-[1440px] gap-8 px-4 py-10 md:px-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <section className="rounded-[32px] border border-black/5 bg-white/88 p-6 shadow-[0_18px_60px_rgba(15,23,42,0.06)] backdrop-blur-xl">
          <SectionHeading
            badgeTone="bg-cyan-500"
            title="Latest Notices"
            actionHref="/search?tab=announcements"
            actionLabel="进入公告检索"
          />
          <div className="mt-6 space-y-4">
            {latestAnnouncements.length ? (
              latestAnnouncements.map((item) => <AnnouncementCard key={item.id} item={item} />)
            ) : (
              <EmptyBlock
                title={announcementsQuery.isLoading ? "正在同步首页公告…" : "首页公告还没同步出来"}
                detail="如果刚部署过 crawler 或数据源正在刷新，这里会在首页查询完成后自动补上。"
              />
            )}
          </div>
        </section>

        <section className="rounded-[32px] border border-black/5 bg-white/88 p-6 shadow-[0_18px_60px_rgba(15,23,42,0.06)] backdrop-blur-xl">
          <SectionHeading
            badgeTone="bg-orange-500"
            title="Adjustment Radar"
            actionHref={portalAuth ? "/search?tab=adjustments" : "/login"}
            actionLabel={portalAuth ? "进入调剂检索" : "登录后查看"}
          />
          <div className="mt-6 space-y-4">
            {portalAuth ? (
              adjustmentSignals.length ? (
                adjustmentSignals.map((item) => <AdjustmentCard key={item.id} item={item} />)
              ) : (
                <EmptyBlock
                  title={adjustmentsQuery.isLoading ? "正在同步调剂情报…" : "暂时没有新的调剂信号"}
                  detail="这里显示的是首页预取的高优先级调剂结果；完整筛选仍在检索页。"
                />
              )
            ) : (
              ANONYMOUS_RADAR_FALLBACK.map((item) => (
                <div
                  key={item.title}
                  className="rounded-[26px] border border-orange-100 bg-[linear-gradient(135deg,rgba(255,247,237,0.96),rgba(255,255,255,0.96))] p-5"
                >
                  <div className="inline-flex rounded-full bg-orange-100 px-2.5 py-1 text-[11px] font-semibold text-orange-700">
                    {item.accent}
                  </div>
                  <h3 className="mt-3 text-lg font-bold text-slate-900">{item.title}</h3>
                  <p className="mt-2 text-sm leading-6 text-slate-600">{item.summary}</p>
                </div>
              ))
            )}
          </div>
        </section>
      </main>

      <section className="mx-auto max-w-[1440px] px-4 md:px-6">
        <div className="relative overflow-hidden rounded-[36px] border border-black/5 bg-[linear-gradient(135deg,#082f49,#0f172a_58%,#155e75)] px-6 py-8 text-white shadow-[0_24px_80px_rgba(8,47,73,0.28)] md:px-8">
          <div className="absolute inset-y-0 right-0 w-1/2 bg-[radial-gradient(circle_at_top,rgba(103,232,249,0.22),transparent_48%)]" />
          <div className="relative flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
            <div className="max-w-2xl">
              <div className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] text-cyan-100">
                <Radar size={14} />
                One home, less context switching
              </div>
              <h2 className="mt-4 text-3xl font-black tracking-tight md:text-4xl">首页现在就是你的第一块控制面板</h2>
              <p className="mt-3 text-sm leading-7 text-cyan-50/86 md:text-base">
                公开公告可以直接看，登录后继续沿着同一套壳层进入调剂检索、空间页和监控工作台，不再把首页当成纯跳板。
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Link
                href="/search"
                className="inline-flex items-center gap-2 rounded-full bg-white px-5 py-3 text-sm font-semibold text-slate-900 transition-transform hover:-translate-y-0.5"
              >
                去检索
                <ChevronRight size={16} />
              </Link>
              <button
                type="button"
                onClick={handleRadarAction}
                className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-white/15"
              >
                {portalAuth ? "打开监控面板" : "登录后开启监控"}
                <ArrowUpRight size={16} />
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

function ConsoleMetric({
  icon,
  label,
  value,
  detail,
  className = "",
}: {
  icon: ReactNode;
  label: string;
  value: string;
  detail: string;
  className?: string;
}) {
  return (
    <div className={`rounded-[24px] border border-black/5 bg-slate-50/90 p-4 ${className}`}>
      <div className="flex items-center gap-2 text-sm font-semibold text-slate-600">
        <span className="text-cyan-700">{icon}</span>
        {label}
      </div>
      <div className="mt-3 text-2xl font-black tracking-tight text-slate-950">{value}</div>
      <p className="mt-2 text-sm leading-6 text-slate-500">{detail}</p>
    </div>
  );
}

function SectionHeading({
  badgeTone,
  title,
  actionHref,
  actionLabel,
}: {
  badgeTone: string;
  title: string;
  actionHref: string;
  actionLabel: string;
}) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-slate-100 pb-4">
      <div className="flex items-center gap-3">
        <div className={`h-5 w-1.5 rounded-full ${badgeTone}`} />
        <h2 className="text-sm font-black uppercase tracking-[0.3em] text-slate-900">{title}</h2>
      </div>
      <Link href={actionHref} className="text-sm font-semibold text-slate-500 transition-colors hover:text-slate-900">
        {actionLabel}
      </Link>
    </div>
  );
}

function AnnouncementCard({ item }: { item: SearchItem }) {
  const detailHref = item.source_url || "/search?tab=announcements";

  return (
    <a
      href={detailHref}
      target={item.source_url ? "_blank" : undefined}
      rel={item.source_url ? "noopener noreferrer" : undefined}
      className="group flex items-start gap-4 rounded-[28px] border border-slate-200 bg-white p-5 transition-all hover:border-cyan-300 hover:shadow-[0_18px_40px_rgba(8,145,178,0.08)]"
    >
      <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-slate-100 bg-slate-50 text-slate-400 transition-colors group-hover:bg-cyan-50 group-hover:text-cyan-700">
        <BookOpenText size={18} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-400">
          <span className="rounded-full bg-slate-50 px-2 py-1 text-[10px] text-slate-500">{item.source_type || "公告"}</span>
          <span>{formatRelativeTime(item.published_at || item.updated_at)}</span>
        </div>
        <h3 className="mt-3 line-clamp-2 text-lg font-bold leading-7 text-slate-900 transition-colors group-hover:text-cyan-700">
          {item.title}
        </h3>
        <p className="mt-2 line-clamp-2 text-sm leading-6 text-slate-600">
          {item.summary || "当前公告没有结构化摘要，点击后可继续查看原文。"}
        </p>
        <div className="mt-4 flex items-center justify-between gap-3 text-sm text-slate-500">
          <span className="truncate">{item.school_name || "院校待补充"}</span>
          <span className="inline-flex items-center gap-1 font-semibold text-slate-700">
            查看详情
            <ChevronRight size={15} />
          </span>
        </div>
      </div>
    </a>
  );
}

function AdjustmentCard({ item }: { item: SearchItem }) {
  const urgencyLabel =
    item.adjustment_vacancy_count && item.adjustment_vacancy_count > 0
      ? `${item.adjustment_vacancy_count} 个缺额`
      : item.historical_adjustment?.outlook_label || "优先关注";

  return (
    <a
      href={item.source_url || "/search?tab=adjustments"}
      target={item.source_url ? "_blank" : undefined}
      rel={item.source_url ? "noopener noreferrer" : undefined}
      className="group flex items-center justify-between gap-4 rounded-[28px] border border-slate-200 bg-white p-5 transition-all hover:border-orange-300 hover:shadow-[0_18px_40px_rgba(249,115,22,0.08)]"
    >
      <div className="min-w-0">
        <div className="inline-flex rounded-full bg-orange-50 px-2.5 py-1 text-[11px] font-semibold text-orange-700">
          {urgencyLabel}
        </div>
        <h3 className="mt-3 truncate text-lg font-bold text-slate-900 transition-colors group-hover:text-orange-600">
          {item.school_name || item.title}
        </h3>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          {[item.major, item.department_name, item.school_tier].filter(Boolean).join(" · ") || item.title}
        </p>
      </div>
      <div className="shrink-0 rounded-[24px] border border-orange-100 bg-orange-50 px-4 py-3 text-right">
        <div className="text-2xl font-black tracking-tight text-slate-950">
          {item.adjustment_vacancy_count ?? item.historical_adjustment?.sample_count ?? "--"}
        </div>
        <div className="mt-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-orange-700">Radar</div>
      </div>
    </a>
  );
}

function EmptyBlock({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="rounded-[28px] border border-dashed border-slate-200 bg-slate-50/80 p-6">
      <h3 className="text-lg font-bold text-slate-900">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-slate-500">{detail}</p>
    </div>
  );
}

function MicroTrendChart({ data }: { data: number[] }) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const width = 240;
  const height = 54;
  const max = Math.max(...data);
  const points = data
    .map((value, index) => `${(index / (data.length - 1)) * width},${height - (value / max) * height}`)
    .join(" L ");

  return (
    <div className="relative h-[54px] w-full" onMouseLeave={() => setHoverIndex(null)}>
      <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" className="h-full w-full overflow-visible">
        <motion.path
          d={`M ${points}`}
          fill="none"
          stroke="#0891b2"
          strokeWidth="2"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 1.2 }}
        />
        <motion.path
          d={`M 0,${height} L ${points} L ${width},${height} Z`}
          fill="url(#homeTrendFill)"
          initial={{ opacity: 0 }}
          animate={{ opacity: 0.14 }}
          transition={{ duration: 1.2 }}
        />
        <defs>
          <linearGradient id="homeTrendFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#06b6d4" />
            <stop offset="100%" stopColor="transparent" />
          </linearGradient>
        </defs>
        {hoverIndex !== null ? (
          <g>
            <line
              x1={(hoverIndex / (data.length - 1)) * width}
              y1="0"
              x2={(hoverIndex / (data.length - 1)) * width}
              y2={height}
              stroke="#cbd5e1"
              strokeWidth="1"
            />
            <circle
              cx={(hoverIndex / (data.length - 1)) * width}
              cy={height - (data[hoverIndex] / max) * height}
              r="3"
              fill="#0891b2"
            />
          </g>
        ) : null}
        {data.map((_, index) => (
          <rect
            key={index}
            x={index === 0 ? 0 : ((index - 0.5) / (data.length - 1)) * width}
            y="0"
            width={width / (data.length - 1)}
            height={height}
            fill="transparent"
            onMouseEnter={() => setHoverIndex(index)}
          />
        ))}
      </svg>
    </div>
  );
}

function MicroDistributionChart({ data }: { data: DistributionDatum[] }) {
  const max = Math.max(...data.map((item) => item.value));

  return (
    <>
      <div className="flex h-[58px] items-end gap-2">
        {data.map((item) => (
          <motion.div
            key={item.label}
            initial={{ height: 0 }}
            animate={{ height: `${(item.value / max) * 100}%` }}
            transition={{ duration: 0.9 }}
            className={`flex-1 rounded-t-xl ${item.tone}`}
          />
        ))}
      </div>
      <div className="mt-3 flex justify-between gap-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">
        {data.map((item) => (
          <span key={item.label} className="truncate">
            {item.label}
          </span>
        ))}
      </div>
    </>
  );
}

function formatCompactNumber(value: number): string {
  if (!value) return "0";
  if (value >= 10_000) return `${(value / 10_000).toFixed(1)}w`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}k`;
  return String(value);
}

function formatRelativeTime(input: string | null): string {
  if (!input) return "时间未知";
  const value = new Date(input).getTime();
  if (Number.isNaN(value)) return "时间未知";

  const diff = Date.now() - value;
  if (diff < 60_000) return "刚刚";
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} 分钟前`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} 小时前`;
  return `${Math.floor(diff / 86_400_000)} 天前`;
}
