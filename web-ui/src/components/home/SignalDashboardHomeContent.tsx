'use client';

import { useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { AnimatePresence, motion } from 'framer-motion';
import { Activity, ArrowUpRight, ChevronRight, FileText, Star } from 'lucide-react';
import { fetchAdjustmentResults, fetchAnnouncementResults } from '@/api/search';
import { useMonitorTargetsQuery } from '@/hooks/useMonitoringTargets';
import { useWatchlistNoticesQuery } from '@/hooks/useNotifications';
import { useSubscriptionsQuery } from '@/hooks/useSubscriptions';
import { useAppStore } from '@/lib/store';
import type { SearchItem } from '@/lib/api';
import { buildSearchDestination } from '@/components/layout/site-navigation';
import {
  buildFocusedAdjustmentPayload,
  buildHomeLiveSummary,
  buildTierBreakdown,
  buildTrendSeries,
  buildWatchedAnnouncementFeed,
  mapAnnouncementSearchItem,
  mapAdjustmentSearchItem,
  type AnnouncementFeedItem,
  type AdjustmentFeedItem,
  type HomeSectionView,
  type TierBreakdownItem,
  type TrendPoint,
} from '@/components/home/homepage-live-data';

const QuotaTrendChart = ({ data }: { data: TrendPoint[] }) => {
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  const safeData = data.length ? data : Array.from({ length: 8 }, (_, index) => ({ label: `T${index + 1}`, value: 0 }));
  const max = Math.max(...safeData.map((item) => item.value), 1);
  const width = 220;
  const height = 48;
  const pointsMeta = safeData.map((item, index) => ({
    ...item,
    x: safeData.length === 1 ? width : (index / (safeData.length - 1)) * width,
    y: height - (item.value / max) * height,
  }));
  const points = pointsMeta.map((point) => `${point.x},${point.y}`).join(' L ');
  const fillD = `M 0,${height} L ${points} L ${width},${height} Z`;
  const endPoint = pointsMeta[pointsMeta.length - 1];

  return (
    <div className="relative h-[48px] w-full min-w-[180px] max-w-[420px]" onMouseLeave={() => setHoverIdx(null)}>
      <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" className="h-full w-full overflow-visible">
        <defs>
          <linearGradient id="trendGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgba(6, 182, 212, 0.32)" />
            <stop offset="100%" stopColor="rgba(6, 182, 212, 0)" />
          </linearGradient>
          <linearGradient id="trendSweepGradient" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="rgba(255,255,255,0)" />
            <stop offset="50%" stopColor="rgba(255,255,255,0.6)" />
            <stop offset="100%" stopColor="rgba(255,255,255,0)" />
          </linearGradient>
          <filter id="trendGlow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="2.4" result="glow" />
            <feMerge>
              <feMergeNode in="glow" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <clipPath id="trendClip">
            <path d={fillD} />
          </clipPath>
        </defs>
        <motion.path d={fillD} fill="url(#trendGradient)" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.9 }} />
        <motion.path
          d={`M ${points}`}
          fill="none"
          stroke="rgba(34, 211, 238, 0.45)"
          strokeWidth="4"
          strokeLinecap="round"
          strokeLinejoin="round"
          filter="url(#trendGlow)"
          initial={{ pathLength: 0, opacity: 0.2 }}
          animate={{ pathLength: 1, opacity: 0.5 }}
          transition={{ duration: 1.6, ease: 'easeInOut' }}
        />
        <motion.path
          d={`M ${points}`}
          fill="none"
          stroke="#06b6d4"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          initial={{ pathLength: 0, opacity: 0.35 }}
          animate={{ pathLength: 1, opacity: 1 }}
          transition={{ duration: 1.6, ease: 'easeInOut' }}
        />
        <motion.rect
          x={-72}
          y={0}
          width={72}
          height={height}
          fill="url(#trendSweepGradient)"
          clipPath="url(#trendClip)"
          animate={{ x: [-72, width + 36] }}
          transition={{ duration: 2.8, repeat: Infinity, ease: 'linear' }}
        />
        {pointsMeta.filter((_, index) => index % Math.max(1, Math.floor(pointsMeta.length / 4)) === 0).map((point, index) => (
          <motion.circle
            key={`${point.label}-${index}`}
            cx={point.x}
            cy={point.y}
            r="1.8"
            fill="rgba(103, 232, 249, 0.65)"
            animate={{ opacity: [0.15, 0.45, 0.15], scale: [1, 1.45, 1] }}
            transition={{ duration: 2.2 + index * 0.3, repeat: Infinity, ease: 'easeInOut' }}
          />
        ))}
        <motion.circle
          cx={endPoint.x}
          cy={endPoint.y}
          r="3.5"
          fill="#ffffff"
          stroke="#06b6d4"
          strokeWidth="2"
          animate={{ scale: [1, 1.26, 1], opacity: [0.9, 1, 0.92] }}
          transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
        />
        <motion.circle
          cx={endPoint.x}
          cy={endPoint.y}
          r="6"
          fill="none"
          stroke="rgba(34, 211, 238, 0.55)"
          strokeWidth="1.2"
          animate={{ scale: [1, 1.9, 1], opacity: [0.55, 0, 0.55] }}
          transition={{ duration: 2.1, repeat: Infinity, ease: 'easeOut' }}
        />
        {hoverIdx !== null ? (
          <g>
            <line x1={pointsMeta[hoverIdx].x} y1="0" x2={pointsMeta[hoverIdx].x} y2={height} stroke="#cbd5e1" strokeWidth="1" strokeDasharray="2 2" />
            <circle cx={pointsMeta[hoverIdx].x} cy={pointsMeta[hoverIdx].y} r="3.5" fill="#06b6d4" stroke="#ffffff" strokeWidth="1.5" className="drop-shadow-md" />
          </g>
        ) : null}
        {pointsMeta.map((point, index) => (
          <rect
            key={point.label}
            x={index === 0 ? 0 : Math.max(0, point.x - width / Math.max(8, pointsMeta.length * 2))}
            y="0"
            width={width / Math.max(pointsMeta.length - 1, 1)}
            height={height}
            fill="transparent"
            onMouseEnter={() => setHoverIdx(index)}
            className="cursor-crosshair"
          />
        ))}
      </svg>

      <AnimatePresence>
        {hoverIdx !== null ? (
          <motion.div
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="pointer-events-none absolute -top-10 z-10 flex -translate-x-1/2 flex-col items-center whitespace-nowrap rounded-lg bg-slate-800 px-2.5 py-1.5 text-[10px] font-bold text-white shadow-lg"
            style={{ left: `${(pointsMeta[hoverIdx].x / width) * 100}%` }}
          >
            <span className="font-mono text-cyan-400">+{safeData[hoverIdx].value} 条信号</span>
            <span className="text-[9px] font-normal text-slate-400">{safeData[hoverIdx].label}</span>
            <div className="absolute -bottom-1 left-1/2 h-2 w-2 -translate-x-1/2 rotate-45 bg-slate-800" />
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
};

const TierDistributionChart = ({ tiers }: { tiers: TierBreakdownItem[] }) => {
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  const orderedTiers = (['985', '211', 'doubleFirst', 'other'] as const).map((label) => {
    return tiers.find((item) => item.label === label) || { label, count: 0 };
  });
  const max = Math.max(...orderedTiers.map((item) => item.count), 1);
  const total = orderedTiers.reduce((acc, item) => acc + item.count, 0);
  const tierLabelMap: Record<TierBreakdownItem['label'], string> = {
    '985': '985',
    '211': '211',
    doubleFirst: '双一流',
    other: '其他',
  };
  const styleMap: Record<TierBreakdownItem['label'], { color: string; glow: string }> = {
    '985': { color: '#06b6d4', glow: 'rgba(6,182,212,0.18)' },
    '211': { color: '#3b82f6', glow: 'rgba(59,130,246,0.18)' },
    doubleFirst: { color: '#818cf8', glow: 'rgba(129,140,248,0.18)' },
    other: { color: '#cbd5e1', glow: 'rgba(148,163,184,0.18)' },
  };

  return (
    <div className="flex h-[36px] w-full min-w-[160px] max-w-[320px] items-end gap-1.5" onMouseLeave={() => setHoverIdx(null)}>
      {orderedTiers.map((tier, index) => {
        const isHovered = hoverIdx === index;
        const heightPercent = Math.max(18, (tier.count / max) * 100);
        const percentage = total ? Math.round((tier.count / total) * 100) : 0;
        const style = styleMap[tier.label];

        return (
          <div key={tier.label} className="group relative flex h-full flex-1 cursor-pointer flex-col justify-end" onMouseEnter={() => setHoverIdx(index)}>
            <motion.div
              initial={{ height: 0, opacity: 0.35 }}
              animate={{ height: `${heightPercent}%`, opacity: hoverIdx !== null && !isHovered ? 0.4 : 1 }}
              transition={{ duration: 0.9, delay: index * 0.08, ease: 'easeOut' }}
              className="relative w-full overflow-hidden rounded-t-sm transition-all duration-200"
              style={{ backgroundColor: style.color, boxShadow: `0 0 20px ${style.glow}`, filter: hoverIdx !== null && !isHovered ? 'saturate(0.8)' : 'none' }}
            >
              <motion.div className="absolute inset-y-0 -left-1/2 w-1/2" style={{ background: 'linear-gradient(90deg, rgba(255,255,255,0), rgba(255,255,255,0.45), rgba(255,255,255,0))' }} animate={{ x: ['0%', '260%'] }} transition={{ duration: 2.4 + index * 0.15, repeat: Infinity, ease: 'linear' }} />
              <motion.div className="absolute inset-x-0 top-0 h-2/5" style={{ background: 'linear-gradient(180deg, rgba(255,255,255,0.32), rgba(255,255,255,0))' }} animate={{ opacity: [0.35, 0.7, 0.35] }} transition={{ duration: 1.8 + index * 0.2, repeat: Infinity, ease: 'easeInOut' }} />
            </motion.div>
            <AnimatePresence>
              {isHovered ? (
                <motion.div
                  initial={{ opacity: 0, y: 5 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className="pointer-events-none absolute -top-12 left-1/2 z-10 flex -translate-x-1/2 flex-col items-center whitespace-nowrap rounded-lg bg-slate-800 px-3 py-1.5 text-[10px] font-bold text-white shadow-lg"
                >
                  <span>{tierLabelMap[tier.label]}：<span className="font-mono text-cyan-400">{tier.count}</span> 所</span>
                  <span className="text-[9px] font-normal text-slate-400">占实时样本 {percentage}%</span>
                  <div className="absolute -bottom-1 left-1/2 h-2 w-2 -translate-x-1/2 rotate-45 bg-slate-800" />
                </motion.div>
              ) : null}
            </AnimatePresence>
          </div>
        );
      })}
    </div>
  );
};

const SectionViewSwitch = ({ view, onChange }: { view: HomeSectionView; onChange: (next: HomeSectionView) => void }) => (
  <div className="flex items-center gap-1 rounded-lg border border-slate-200/60 bg-white/70 p-0.5 shadow-sm">
    {(['latest', 'watching'] as const).map((item) => (
      <button key={item} type="button" onClick={() => onChange(item)} className={`rounded-md px-3 py-1 text-[11px] font-bold transition-all ${view === item ? 'bg-slate-900 text-white shadow-sm' : 'text-slate-400 hover:text-slate-700'}`}>
        {item === 'latest' ? '最新' : '我的关注'}
      </button>
    ))}
  </div>
);

const HomepageEmptyState = ({ title, detail, ctaLabel, onClick }: { title: string; detail: string; ctaLabel?: string; onClick?: () => void }) => (
  <div className="flex min-h-[220px] flex-col items-center justify-center rounded-2xl border-2 border-dashed border-slate-100 bg-white/40 px-6 py-10 text-center">
    <p className="text-sm font-semibold text-slate-500">{title}</p>
    <p className="mt-2 max-w-[320px] text-xs leading-6 text-slate-400">{detail}</p>
    {ctaLabel && onClick ? (
      <button type="button" onClick={onClick} className="mt-5 flex items-center gap-1 text-xs font-bold text-cyan-600 transition-colors hover:text-cyan-700">
        {ctaLabel} <ChevronRight size={12} />
      </button>
    ) : null}
  </div>
);

function useLatestAnnouncements() {
  return useQuery({
    queryKey: ['home', 'latest-announcements'],
    queryFn: async () => {
      const response = await fetchAnnouncementResults({ page: 1, page_size: 6 });
      return response.items;
    },
  });
}

function useLatestAdjustments() {
  return useQuery({
    queryKey: ['home', 'latest-adjustments'],
    queryFn: async () => {
      const response = await fetchAdjustmentResults({ page: 1, page_size: 12 });
      return response.items;
    },
  });
}

export default function SignalDashboardHomeContent() {
  const router = useRouter();
  const portalAuth = useAppStore((state) => state.portalAuth);
  const setAuthOpen = useAppStore((state) => state.setAuthOpen);
  const showToast = useAppStore((state) => state.showToast);
  const canManageScopeTargets = Boolean(portalAuth?.isPremium || portalAuth?.isAdmin);
  const [announcementView, setAnnouncementView] = useState<HomeSectionView>('latest');
  const [adjustmentView, setAdjustmentView] = useState<HomeSectionView>('latest');

  const latestAnnouncementsQuery = useLatestAnnouncements();
  const latestAdjustmentsQuery = useLatestAdjustments();
  const pendingNoticesQuery = useWatchlistNoticesQuery(Boolean(portalAuth));
  const monitorTargetsQuery = useMonitorTargetsQuery(Boolean(portalAuth && canManageScopeTargets));
  const subscriptionsQuery = useSubscriptionsQuery(Boolean(portalAuth));

  const latestAnnouncementCards = useMemo(
    () => (latestAnnouncementsQuery.data || []).slice(0, 3).map((item) => mapAnnouncementSearchItem(item)),
    [latestAnnouncementsQuery.data],
  );
  const watchedAnnouncementCards = useMemo(
    () => buildWatchedAnnouncementFeed(pendingNoticesQuery.data || [], monitorTargetsQuery.data?.items || []).slice(0, 3),
    [monitorTargetsQuery.data?.items, pendingNoticesQuery.data],
  );

  const focusedAdjustment = useMemo(
    () => buildFocusedAdjustmentPayload(subscriptionsQuery.data?.items || []),
    [subscriptionsQuery.data?.items],
  );

  const watchedAdjustmentsQuery = useQuery({
    queryKey: ['home', 'watching-adjustments', portalAuth?.userId, focusedAdjustment?.focusLabel],
    queryFn: async () => {
      if (!focusedAdjustment) {
        return [] as SearchItem[];
      }
      const response = await fetchAdjustmentResults(focusedAdjustment.payload);
      return response.items;
    },
    enabled: Boolean(portalAuth && focusedAdjustment),
  });

  const latestAdjustmentSearchItems = useMemo(
    () => latestAdjustmentsQuery.data || [],
    [latestAdjustmentsQuery.data],
  );
  const latestAdjustmentCards = useMemo(
    () => latestAdjustmentSearchItems.slice(0, 3).map((item) => mapAdjustmentSearchItem(item)),
    [latestAdjustmentSearchItems],
  );
  const watchedAdjustmentCards = useMemo(
    () => (watchedAdjustmentsQuery.data || []).slice(0, 3).map((item) => mapAdjustmentSearchItem(item)),
    [watchedAdjustmentsQuery.data],
  );

  const trendSeries = useMemo(() => buildTrendSeries(latestAdjustmentSearchItems), [latestAdjustmentSearchItems]);
  const tierBreakdown = useMemo(() => buildTierBreakdown(latestAdjustmentSearchItems), [latestAdjustmentSearchItems]);
  const highTierCount = tierBreakdown
    .filter((item) => item.label === '985' || item.label === '211' || item.label === 'doubleFirst')
    .reduce((sum, item) => sum + item.count, 0);
  const qualityTierRate = latestAdjustmentSearchItems.length
    ? Math.round((highTierCount / latestAdjustmentSearchItems.length) * 100)
    : 0;
  const releaseVelocity = trendSeries[trendSeries.length - 1]?.value ?? latestAdjustmentSearchItems.length;
  const liveSummary = useMemo(
    () => buildHomeLiveSummary(pendingNoticesQuery.data || [], monitorTargetsQuery.data?.items || []),
    [monitorTargetsQuery.data?.items, pendingNoticesQuery.data],
  );

  const announcementCards = announcementView === 'latest' ? latestAnnouncementCards : watchedAnnouncementCards;
  const adjustmentCards = adjustmentView === 'latest' ? latestAdjustmentCards : watchedAdjustmentCards;
  const loadingNotices =
    announcementView === 'latest'
      ? latestAnnouncementsQuery.isLoading
      : Boolean(portalAuth) && (pendingNoticesQuery.isLoading || monitorTargetsQuery.isLoading);
  const loadingAdjustments =
    adjustmentView === 'latest'
      ? latestAdjustmentsQuery.isLoading
      : Boolean(portalAuth) && (subscriptionsQuery.isLoading || watchedAdjustmentsQuery.isLoading);

  function promptLogin(message: string) {
    setAuthOpen(true, 'login');
    showToast('请先登录', message, 'info');
  }

  function openProtectedPage(href: string) {
    if (!portalAuth) {
      promptLogin('登录后使用收藏、关注和提醒功能。');
      return;
    }
    router.push(href);
  }

  function openAnnouncementCard(item: AnnouncementFeedItem) {
    if (item.href) {
      router.push(item.href);
      return;
    }
    if (item.sourceUrl) {
      window.open(item.sourceUrl, '_blank', 'noopener,noreferrer');
      return;
    }
    router.push(buildSearchDestination('announcements', item.school));
  }

  function openAdjustmentCard(item: AdjustmentFeedItem) {
    if (item.href) {
      router.push(item.href);
      return;
    }
    if (item.sourceUrl) {
      window.open(item.sourceUrl, '_blank', 'noopener,noreferrer');
      return;
    }
    router.push(buildSearchDestination('adjustments', item.school));
  }

  const liveSummaryLabel = portalAuth
    ? liveSummary.latestSchool || `${liveSummary.activeTargetCount} 个收藏范围在线`
    : '登录后查看收藏院校提醒';

  return (
    <div className="relative z-10 w-full px-6 pb-32 pt-8 md:px-8 xl:px-10 2xl:px-12">
      <div className="mb-20 flex w-full flex-col gap-12 lg:flex-row lg:items-end lg:gap-10 xl:gap-12">
        <div className="flex min-w-0 w-full flex-1 items-end gap-6">
          <div>
            <div className="mb-1.5 flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest text-slate-400">
              <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 shadow-[0_0_6px_rgba(6,182,212,0.6)]" />
              RELEASE VELOCITY
            </div>
            <div className="flex items-baseline gap-2">
              <span className="flex items-center text-3xl font-black tracking-tighter text-slate-900">
                <span className="mr-0.5 text-xl font-bold text-cyan-500">+</span>
                {releaseVelocity}
              </span>
              <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400">/ 24H</span>
            </div>
          </div>
          <div className="flex-1 pb-1">
            <QuotaTrendChart data={trendSeries} />
            <div className="mt-2 font-mono text-[8px] uppercase tracking-widest text-slate-400">全网调剂新增趋势</div>
          </div>
        </div>

        <div className="flex min-w-0 w-full flex-1 items-end gap-6">
          <div>
            <div className="mb-1.5 text-[10px] font-bold uppercase tracking-widest text-slate-400">QUALITY TIER</div>
            <div className="flex items-baseline gap-1.5">
              <span className="text-base font-black text-slate-900">{qualityTierRate}%</span>
              <span className="text-[10px] font-bold text-slate-400">来自 985/211/双一流</span>
            </div>
          </div>
          <div className="flex-1 pb-1">
            <TierDistributionChart tiers={tierBreakdown} />
            <div className="mt-2 flex w-full max-w-[320px] justify-between font-mono text-[8px] uppercase text-slate-400">
              <span>985</span>
              <span>211</span>
              <span>D1L</span>
              <span>ORD</span>
            </div>
          </div>
        </div>

        <button
          type="button"
          className="hidden min-w-[220px] flex-none flex-col items-start gap-1.5 rounded-xl border border-orange-200/50 bg-orange-50/60 px-5 py-3 text-left shadow-sm backdrop-blur-sm transition-colors hover:bg-orange-100/60 xl:flex"
          onClick={() => openProtectedPage('/watchlist')}
        >
          <div className="flex items-center gap-2">
            <div className="h-1.5 w-1.5 animate-pulse rounded-full bg-orange-500" />
            <span className="text-[10px] font-bold uppercase tracking-widest text-orange-600">SEE LIVE</span>
          </div>
          <div className="mt-0.5 flex items-end gap-2">
            <span className="font-mono text-xl font-bold leading-none text-orange-500">{portalAuth ? liveSummary.pendingCount : 0}</span>
            <span className="mb-0.5 text-[10px] text-slate-500">{liveSummaryLabel}</span>
          </div>
        </button>
      </div>

      <div className="grid w-full grid-cols-1 gap-12 lg:grid-cols-2 lg:gap-10 xl:gap-12">
        <div className="space-y-4 opacity-100 transition-opacity duration-300">
          <div className="mb-4 flex items-center justify-between gap-4 border-b border-slate-100 pb-2">
            <div className="flex min-w-0 items-center gap-3">
              <h2 className="flex shrink-0 items-center gap-2 text-xs font-black uppercase tracking-widest text-slate-400">
                <FileText size={14} className="text-cyan-500" />
                全网公告流
              </h2>
              <SectionViewSwitch view={announcementView} onChange={setAnnouncementView} />
            </div>
            <button
              type="button"
              onClick={() => router.push('/announcements')}
              className="flex shrink-0 items-center gap-1 text-xs font-bold text-cyan-600 transition-colors hover:text-cyan-700"
            >
              高级检索 <ChevronRight size={12} />
            </button>
          </div>

          <div className="min-h-[300px] space-y-3">
            {loadingNotices ? (
              Array.from({ length: 3 }, (_, index) => (
                <div key={index} className="h-32 animate-pulse rounded-2xl border border-slate-100 bg-white/50 p-5" />
              ))
            ) : announcementCards.length > 0 ? (
              announcementCards.map((item) => (
                <motion.div
                  key={item.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3 }}
                  className="group relative cursor-pointer rounded-2xl border border-slate-200/50 bg-white p-5 transition-all hover:border-cyan-300 hover:shadow-[0_8px_30px_rgba(6,182,212,0.08)]"
                  onClick={() => openAnnouncementCard(item)}
                >
                  <div className="mb-3 flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      {item.isNew ? <span className="h-1.5 w-1.5 rounded-full bg-cyan-500" /> : null}
                      <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-bold text-slate-600">{item.type}</span>
                      <span className="font-mono text-[11px] text-slate-400">{item.time}</span>
                    </div>
                    <span className="text-[11px] font-bold text-slate-400">{item.school}</span>
                  </div>
                  <h3 className="mb-2 pr-6 text-[15px] font-bold leading-snug text-slate-900 transition-colors group-hover:text-cyan-600">
                    {item.title}
                  </h3>
                  <p className="line-clamp-2 text-[13px] leading-relaxed text-slate-500">{item.content}</p>
                  <div className="absolute right-4 top-1/2 -translate-y-1/2 -translate-x-2 opacity-0 transition-all group-hover:translate-x-0 group-hover:opacity-100">
                    <ArrowUpRight className="text-cyan-500" size={20} />
                  </div>
                </motion.div>
              ))
            ) : !portalAuth && announcementView === 'watching' ? (
              <HomepageEmptyState
                title="登录后查看我的关注"
                detail="首页会直接展示你收藏院校和监控范围内的最新公告提醒。"
                ctaLabel="立即登录"
                onClick={() => promptLogin('登录后查看你的关注公告。')}
              />
            ) : portalAuth && announcementView === 'watching' && !watchedAnnouncementCards.length && !(monitorTargetsQuery.data?.items || []).length ? (
              <HomepageEmptyState
                title="还没有关注范围"
                detail="先去关注库收藏院校或设置监控范围，首页才会自动汇总关注公告。"
                ctaLabel="去设置关注"
                onClick={() => router.push('/watchlist')}
              />
            ) : portalAuth && announcementView === 'watching' ? (
              <HomepageEmptyState
                title="关注范围暂时没有新公告"
                detail="收藏院校和监控范围仍在监听中，新的提醒会优先回流到这里。"
                ctaLabel="查看关注库"
                onClick={() => router.push('/watchlist')}
              />
            ) : (
              <HomepageEmptyState
                title="暂时没有新的公告数据"
                detail="可以进入公告汇总页做更细的检索，或稍后刷新首页。"
                ctaLabel="进入公告汇总"
                onClick={() => router.push('/announcements')}
              />
            )}
          </div>
        </div>

        <div className="space-y-4 opacity-100 transition-opacity duration-300">
          <div className="mb-4 flex items-center justify-between gap-4 border-b border-slate-100 pb-2">
            <div className="flex min-w-0 items-center gap-3">
              <h2 className="flex shrink-0 items-center gap-2 text-xs font-black uppercase tracking-widest text-slate-400">
                <Activity size={14} className="text-orange-500" />
                调剂异动雷达
              </h2>
              <SectionViewSwitch view={adjustmentView} onChange={setAdjustmentView} />
            </div>
            <button
              type="button"
              onClick={() => router.push('/adjustments')}
              className="flex shrink-0 items-center gap-1 text-xs font-bold text-orange-500 transition-colors hover:text-orange-600"
            >
              调剂汇总 <ChevronRight size={12} />
            </button>
          </div>

          <div className="min-h-[300px] space-y-3">
            {loadingAdjustments ? (
              Array.from({ length: 3 }, (_, index) => (
                <div key={index} className="h-32 animate-pulse rounded-2xl border border-slate-100 bg-white/50 p-5" />
              ))
            ) : adjustmentCards.length > 0 ? (
              adjustmentCards.map((item) => (
                <motion.div
                  key={item.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3 }}
                  className={`group relative flex cursor-pointer items-center justify-between rounded-2xl border bg-white p-5 transition-all ${
                    item.urgent
                      ? 'border-orange-200/60 hover:border-orange-400 hover:shadow-[0_8px_30px_rgba(249,115,22,0.08)]'
                      : 'border-slate-200/50 hover:border-cyan-300 hover:shadow-[0_8px_30px_rgba(6,182,212,0.08)]'
                  }`}
                  onClick={() => openAdjustmentCard(item)}
                >
                  <div className="min-w-0 flex-1 pr-4">
                    <div className="mb-1.5 flex items-center gap-2">
                      <span className="text-[11px] font-bold text-slate-500">{item.school}</span>
                      <span className="text-[10px] text-slate-300">•</span>
                      <span className="text-[11px] text-slate-400">{item.major}</span>
                    </div>
                    <h3 className={`mb-2 truncate text-[15px] font-bold transition-colors ${item.urgent ? 'text-slate-900 group-hover:text-orange-600' : 'text-slate-900 group-hover:text-cyan-600'}`}>
                      {item.title}
                    </h3>
                    <div className="mt-2 flex items-center gap-1.5">
                      {item.tags.map((tag, index) => (
                        <span key={`${item.id}-${tag}-${index}`} className="rounded border border-slate-100 bg-slate-50 px-1.5 py-0.5 text-[10px] text-slate-500">
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="ml-4 flex shrink-0 flex-col items-end text-right">
                    <div className="mb-1 flex items-baseline gap-1">
                      <span className="text-xs font-bold text-slate-400">缺额</span>
                      <span className={`font-mono text-2xl font-black leading-none ${item.urgent ? 'text-orange-500' : 'text-slate-900 group-hover:text-cyan-600'}`}>
                        {item.count}
                      </span>
                    </div>
                    <div className="mt-1 flex gap-2">
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          openProtectedPage('/watchlist');
                        }}
                        className="p-1 text-slate-300 transition-colors hover:text-yellow-400"
                      >
                        <Star size={14} />
                      </button>
                      {item.urgent ? <span className="rounded-sm bg-orange-50 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-orange-600">Urgent</span> : null}
                    </div>
                  </div>
                </motion.div>
              ))
            ) : !portalAuth && adjustmentView === 'watching' ? (
              <HomepageEmptyState
                title="登录后查看我的调剂关注"
                detail="首页会把你收藏院校、专业或雷达订阅对应的调剂结果自动拉回首页。"
                ctaLabel="立即登录"
                onClick={() => promptLogin('登录后查看你的调剂关注。')}
              />
            ) : portalAuth && adjustmentView === 'watching' && !focusedAdjustment ? (
              <HomepageEmptyState
                title="还没有调剂关注"
                detail="先在调剂汇总页或关注库保存学校、专业或雷达订阅，首页才能展示对应的调剂汇总。"
                ctaLabel="去设置关注"
                onClick={() => router.push('/watchlist')}
              />
            ) : portalAuth && adjustmentView === 'watching' ? (
              <HomepageEmptyState
                title="当前关注暂无调剂新信号"
                detail={focusedAdjustment ? `已按 ${focusedAdjustment.focusLabel} 追踪调剂结果，新的异动会直接回流到首页。` : '收藏院校和专业仍在持续扫描中。'}
                ctaLabel="进入调剂汇总"
                onClick={() => router.push('/adjustments')}
              />
            ) : !portalAuth ? (
              <HomepageEmptyState
                title="登录后查看最新调剂异动"
                detail="调剂数据支持游客预览，登录后可查看更完整的收藏与提醒动作。"
                ctaLabel="立即登录"
                onClick={() => promptLogin('登录后保存调剂机会并接收提醒。')}
              />
            ) : (
              <HomepageEmptyState
                title="暂时没有新的调剂数据"
                detail="可以进入调剂汇总页查看更多实时结果，或稍后刷新首页。"
                ctaLabel="进入调剂汇总"
                onClick={() => router.push('/adjustments')}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
