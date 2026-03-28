"use client";

import { useMemo, useRef, useState, type MouseEvent as ReactMouseEvent } from "react";
import { motion } from "framer-motion";
import { BookOpen } from "lucide-react";
import type { SearchItem } from "@/lib/api";
import { useMonitorTargetsQuery } from "@/hooks/useMonitoringTargets";
import { useWatchlistNoticesQuery } from "@/hooks/useNotifications";
import { useHomeAdjustmentsQuery, useHomeAnnouncementsQuery } from "@/hooks/useSearch";
import { useSubscriptionsQuery } from "@/hooks/useSubscriptions";
import { useAppStore } from "@/lib/store";

type DistributionBar = {
  label: string;
  value: number;
  color: string;
};

const FALLBACK_DISTRIBUTION: DistributionBar[] = [
  { label: "公告", value: 420, color: "bg-cyan-500" },
  { label: "调剂", value: 280, color: "bg-blue-500" },
  { label: "PDF", value: 160, color: "bg-slate-400" },
  { label: "其他", value: 92, color: "bg-slate-200" },
];

const ANONYMOUS_ADJUSTMENT_FALLBACK = [
  {
    title: "登录后解锁调剂雷达",
    summary: "调剂卡片会切到真实缺额、历史样本和近期活跃学校，不再只是静态演示文本。",
    accent: "Private Feed",
  },
  {
    title: "学校 / 专业 / 关键词联动追踪",
    summary: "把你的关注范围挂到同一套雷达里，命中时自动进入个人空间和通知队列。",
    accent: "Signal Scope",
  },
  {
    title: "首页只放高优先级信号",
    summary: "真正的细筛仍在检索页，首页只保留最值得你进一步点开的调剂入口。",
    accent: "Priority",
  },
] as const;

export default function SignalDashboardHome() {
  const dashboardRef = useRef<HTMLDivElement | null>(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

  const { portalAuth } = useAppStore();
  const canManageScopeTargets = Boolean(portalAuth?.isPremium || portalAuth?.isAdmin);

  const announcementsQuery = useHomeAnnouncementsQuery({
    page: 1,
    page_size: 3,
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

  const latestAnnouncements = announcementsQuery.data?.items ?? [];
  const adjustmentSignals = adjustmentsQuery.data?.items ?? [];

  const trendData = useMemo(() => {
    const base = Math.max(indexedCount, 40);
    return [0.08, 0.12, 0.09, 0.16, 0.22, 0.18, 0.34, 0.29, 0.42, 0.56, 0.52, 0.64, 0.6, 0.76, 0.72, 0.88].map(
      (ratio, index) => Math.round(base * ratio + index * 4),
    );
  }, [indexedCount]);

  const distributionData = useMemo<DistributionBar[]>(() => {
    const breakdown = Object.entries(announcementsQuery.data?.source_breakdown ?? {})
      .sort((left, right) => right[1] - left[1])
      .slice(0, 4);

    if (!breakdown.length) {
      return FALLBACK_DISTRIBUTION;
    }

    return breakdown.map(([label, value], index) => ({
      label: label.slice(0, 8),
      value,
      color: FALLBACK_DISTRIBUTION[index]?.color ?? "bg-slate-300",
    }));
  }, [announcementsQuery.data?.source_breakdown]);

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

  const sourceCount = Object.keys(announcementsQuery.data?.source_breakdown ?? {}).length;
  const syncLabel = portalAuth ? `${portalAuth.role.toUpperCase()} ONLINE` : "GUEST MODE";

  return (
    <div className="w-full pb-32 text-slate-900">
      <section
        ref={dashboardRef}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        className="relative flex h-[220px] items-center overflow-hidden border-b border-slate-200/60 bg-[#f8fafc]"
      >
        <motion.div
          animate={{ x: mousePos.x * -10, y: mousePos.y * -5 }}
          className="pointer-events-none absolute left-[-10%] top-[-20%] h-[500px] w-[500px] rounded-full bg-cyan-500/5 blur-[100px]"
        />
        <motion.div
          animate={{ x: mousePos.x * -25, y: mousePos.y * -10 }}
          className="pointer-events-none absolute inset-[-10%] opacity-[0.03]"
          style={{
            backgroundImage:
              "linear-gradient(rgba(6,182,212,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(6,182,212,0.5) 1px, transparent 1px)",
            backgroundSize: "40px 40px",
          }}
        />
        <motion.div animate={{ x: mousePos.x * -45, y: mousePos.y * -15 }} className="pointer-events-none absolute inset-0">
          <div className="absolute right-1/3 top-1/4 h-1.5 w-1.5 rounded-full bg-cyan-200" />
          <div className="absolute bottom-1/3 left-1/4 h-1 w-1 rounded-full bg-slate-200" />
          <div className="absolute right-[10%] top-1/2 h-px w-10 bg-cyan-100" />
        </motion.div>

        <div className="relative z-10 mx-auto flex w-full max-w-7xl flex-col items-center gap-12 px-6 md:flex-row">
          <motion.div animate={{ rotateY: mousePos.x * 5, rotateX: mousePos.y * -5 }} className="group flex flex-1 items-center gap-8">
            <div className="shrink-0">
              <div className="mb-1 flex items-center gap-1.5 text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-cyan-500" />
                Live Intercept
              </div>
              <div className="flex items-baseline gap-2">
                <span className="font-mono text-3xl font-black tracking-tighter text-slate-900">{formatCompactNumber(indexedCount)}</span>
                <span className="text-[10px] font-bold text-slate-400">INDEXED</span>
              </div>
            </div>
            <div className="max-w-[320px] flex-1 rounded-xl border border-white bg-white/40 p-3 shadow-sm backdrop-blur-sm transition-colors group-hover:border-cyan-200">
              <MicroTrendChart data={trendData} />
            </div>
          </motion.div>

          <div className="hidden h-10 w-px bg-slate-200/60 md:block" />

          <motion.div animate={{ rotateY: mousePos.x * 3, rotateX: mousePos.y * -3 }} className="group flex flex-1 items-center gap-8">
            <div className="shrink-0">
              <div className="mb-1 text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">Topology</div>
              <div className="text-sm font-bold text-slate-700">
                {sourceCount || distributionData.length} Sources
                <span className="ml-1 font-mono text-xs text-slate-400">
                  · {portalAuth ? `${followingCount + radarCount + activityCount} linked` : "guest"}
                </span>
              </div>
            </div>
            <div className="max-w-[220px] flex-1 rounded-xl border border-white bg-white/40 p-3 shadow-sm backdrop-blur-sm transition-colors group-hover:border-cyan-200">
              <MicroDistributionChart data={distributionData} />
              <div className="mt-1.5 flex justify-between text-[8px] font-mono tracking-tighter text-slate-400">
                {distributionData.map((item) => (
                  <span key={item.label}>{item.label}</span>
                ))}
              </div>
            </div>
          </motion.div>

          <div className="hidden items-center gap-2 rounded-full border border-white bg-white/80 px-3 py-1.5 shadow-sm backdrop-blur-md xl:flex">
            <div className="h-1.5 w-1.5 animate-pulse rounded-full bg-green-500" />
            <span className="font-mono text-[9px] font-black uppercase tracking-widest text-slate-500">{syncLabel}</span>
          </div>
        </div>
      </section>

      <main className="mx-auto max-w-7xl px-6 py-12">
        <div className="grid grid-cols-1 gap-12 lg:grid-cols-2">
          <div className="space-y-5">
            <div className="mb-8 flex items-center gap-3 border-b border-slate-100 pb-4">
              <div className="h-5 w-1.5 rounded-full bg-cyan-600 shadow-[0_0_8px_rgba(8,145,178,0.3)]" />
              <h2 className="text-sm font-black uppercase tracking-[0.3em] text-slate-900">Latest Notices</h2>
            </div>

            {latestAnnouncements.length ? (
              latestAnnouncements.map((item) => <AnnouncementCard key={item.id} item={item} />)
            ) : (
              <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-500">
                {announcementsQuery.isLoading ? "正在同步公告数据…" : "当前没有可展示的公告数据。"}
              </div>
            )}
          </div>

          <div className="space-y-5">
            <div className="mb-8 flex items-center gap-3 border-b border-slate-100 pb-4">
              <div className="h-5 w-1.5 rounded-full bg-orange-500 shadow-[0_0_8px_rgba(249,115,22,0.3)]" />
              <h2 className="text-sm font-black uppercase tracking-[0.3em] text-slate-900">Adjustment Radar</h2>
            </div>

            {portalAuth ? (
              adjustmentSignals.length ? (
                adjustmentSignals.map((item) => <AdjustmentCard key={item.id} item={item} />)
              ) : (
                <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-500">
                  {adjustmentsQuery.isLoading ? "正在同步调剂信号…" : "当前没有新的调剂信号。"}
                </div>
              )
            ) : (
              ANONYMOUS_ADJUSTMENT_FALLBACK.map((item) => (
                <div
                  key={item.title}
                  className="rounded-xl border border-slate-200 bg-white p-6 transition-all hover:border-orange-500/40 hover:shadow-[0_8px_30px_rgba(0,0,0,0.03)]"
                >
                  <div className="inline-flex rounded-full bg-orange-50 px-2.5 py-1 text-[10px] font-black uppercase tracking-widest text-orange-500">
                    {item.accent}
                  </div>
                  <h3 className="mt-3 text-base font-bold text-slate-900">{item.title}</h3>
                  <p className="mt-2 text-[11px] font-medium leading-6 text-slate-500">{item.summary}</p>
                </div>
              ))
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

function AnnouncementCard({ item }: { item: SearchItem }) {
  return (
    <a
      href={item.source_url || "/search?tab=announcements"}
      target={item.source_url ? "_blank" : undefined}
      rel={item.source_url ? "noopener noreferrer" : undefined}
      className="group relative flex cursor-pointer items-start gap-5 overflow-hidden rounded-xl border border-slate-200 bg-white p-6 transition-all hover:border-cyan-500/50 hover:shadow-[0_8px_30px_rgba(0,0,0,0.03)]"
    >
      <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border border-slate-100 bg-slate-50 transition-colors group-hover:bg-cyan-50">
        <BookOpen size={18} className="text-slate-400 transition-colors group-hover:text-cyan-600" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="mb-1.5 flex items-center gap-3">
          <span className="rounded bg-slate-50 px-1.5 py-0.5 text-[10px] font-black uppercase tracking-widest text-slate-400">
            {item.source_type || "Admission"}
          </span>
          <span className="font-mono text-[10px] italic text-slate-300">{formatRelativeTime(item.published_at || item.updated_at)}</span>
        </div>
        <h3 className="line-clamp-2 text-base font-bold text-slate-800 transition-colors group-hover:text-cyan-700">{item.title}</h3>
        <p className="mt-2 line-clamp-2 text-[11px] leading-6 text-slate-500">
          {item.summary || item.school_name || "点击查看完整公告。"}
        </p>
        <div className="mt-3 text-[11px] font-medium text-slate-500">{item.school_name || "院校待补充"}</div>
      </div>
    </a>
  );
}

function AdjustmentCard({ item }: { item: SearchItem }) {
  return (
    <a
      href={item.source_url || "/search?tab=adjustments"}
      target={item.source_url ? "_blank" : undefined}
      rel={item.source_url ? "noopener noreferrer" : undefined}
      className="group flex cursor-pointer items-center justify-between rounded-xl border border-slate-200 bg-white p-6 transition-all hover:border-orange-500/40 hover:shadow-[0_8px_30px_rgba(0,0,0,0.03)]"
    >
      <div className="min-w-0">
        <h3 className="truncate text-base font-bold text-slate-900 transition-colors group-hover:text-orange-600">
          {item.school_name || item.title}
        </h3>
        <p className="mt-0.5 text-[11px] font-medium text-slate-500">
          {[item.major, item.department_name, item.school_tier].filter(Boolean).join(" · ") || item.title}
        </p>
      </div>
      <div className="ml-6 shrink-0 border-l border-slate-100 pl-6 text-right">
        <div className="font-mono text-2xl font-black leading-none text-slate-900 transition-colors group-hover:text-orange-600">
          {item.adjustment_vacancy_count ?? item.historical_adjustment?.sample_count ?? "--"}
        </div>
        <div className="mt-1 text-[9px] font-black uppercase tracking-widest text-orange-500">
          {item.historical_adjustment?.outlook_label || "Urgent Alert"}
        </div>
      </div>
    </a>
  );
}

function MicroTrendChart({ data }: { data: number[] }) {
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  const max = Math.max(...data);
  const width = 200;
  const height = 40;
  const points = data.map((value, index) => `${(index / (data.length - 1)) * width},${height - (value / max) * height}`).join(" L ");

  return (
    <div className="group relative h-[40px] w-full" onMouseLeave={() => setHoverIdx(null)}>
      <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" className="h-full w-full overflow-visible">
        <motion.path
          d={`M ${points}`}
          fill="none"
          stroke="#0891b2"
          strokeWidth="1.5"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 1.5 }}
        />
        <motion.path
          d={`M 0,${height} L ${points} L ${width},${height} Z`}
          fill="url(#sparkLightGradient)"
          opacity="0.05"
          initial={{ opacity: 0 }}
          animate={{ opacity: 0.05 }}
          transition={{ duration: 1.5 }}
        />
        <defs>
          <linearGradient id="sparkLightGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#0891b2" />
            <stop offset="100%" stopColor="transparent" />
          </linearGradient>
        </defs>
        {hoverIdx !== null ? (
          <g>
            <line
              x1={(hoverIdx / (data.length - 1)) * width}
              y1="0"
              x2={(hoverIdx / (data.length - 1)) * width}
              y2={height}
              stroke="#e2e8f0"
              strokeWidth="1"
            />
            <circle
              cx={(hoverIdx / (data.length - 1)) * width}
              cy={height - (data[hoverIdx] / max) * height}
              r="2.5"
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
            onMouseEnter={() => setHoverIdx(index)}
            className="cursor-crosshair"
          />
        ))}
      </svg>
    </div>
  );
}

function MicroDistributionChart({ data }: { data: DistributionBar[] }) {
  const max = Math.max(...data.map((item) => item.value));

  return (
    <div className="flex h-[30px] w-full items-end gap-1">
      {data.map((item, index) => (
        <motion.div
          key={`${item.label}-${index}`}
          initial={{ height: 0 }}
          animate={{ height: `${(item.value / max) * 100}%` }}
          transition={{ duration: 1, delay: index * 0.1 }}
          className={`flex-1 rounded-t-sm opacity-80 ${item.color}`}
        />
      ))}
    </div>
  );
}

function formatRelativeTime(input: string | null): string {
  if (!input) return "JUST NOW";
  const date = new Date(input);
  if (Number.isNaN(date.getTime())) return "JUST NOW";
  const diffMs = Date.now() - date.getTime();
  if (diffMs < 60 * 1000) return "JUST NOW";
  if (diffMs < 60 * 60 * 1000) return `${Math.floor(diffMs / (60 * 1000))} MIN AGO`;
  if (diffMs < 24 * 60 * 60 * 1000) return `${Math.floor(diffMs / (60 * 60 * 1000))} H AGO`;
  return `${Math.floor(diffMs / (24 * 60 * 60 * 1000))} D AGO`;
}

function formatCompactNumber(value: number): string {
  if (!value) return "0";
  if (value >= 10_000) return `${(value / 10_000).toFixed(1)}w`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}k`;
  return String(value);
}
