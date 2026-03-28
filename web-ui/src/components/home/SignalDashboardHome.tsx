'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import React, { useEffect, useMemo, useState } from 'react';
import { create } from 'zustand';
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import { fetchEventSource } from '@microsoft/fetch-event-source';
import { 
  Search, X, Star, ArrowUpRight, Activity, 
  Terminal, ShieldCheck, LogOut, ChevronRight, CheckCircle2,
  FileText, User, Info
} from 'lucide-react';
import { fetchAdjustmentResults, fetchAnnouncementResults } from '@/api/search';
import {
  getCurrentUser,
  loginUser,
  logoutUser,
  notificationsStreamUrl,
  registerUser,
  type NotificationEventItem,
  type SearchItem,
} from '@/lib/api';
import { mergeNoticeList, watchlistNoticeQueryKey } from '@/lib/notice-cache';
import { useMonitorTargetsQuery } from '@/hooks/useMonitoringTargets';
import { useWatchlistNoticesQuery } from '@/hooks/useNotifications';
import { useSubscriptionsQuery } from '@/hooks/useSubscriptions';
import { useAppStore as usePortalStore } from '@/lib/store';
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

// ==========================================
// 1. 全局状态、接口与 Toast 系统
// ==========================================
interface User { id: string; name: string; email: string; role: 'user' | 'admin'; }
interface ToastMsg { id: string; msg: string; type: 'success' | 'info' | 'warning'; }

interface AppState {
  isAuthOpen: boolean;
  setAuthOpen: (open: boolean) => void;
  user: User | null;
  setUser: (user: User | null) => void;
  toasts: ToastMsg[];
  addToast: (toast: Omit<ToastMsg, 'id'>) => void;
  removeToast: (id: string) => void;
}

const useAppStore = create<AppState>((set) => ({
  isAuthOpen: false,
  setAuthOpen: (open) => set({ isAuthOpen: open }),
  user: null, 
  setUser: (user) => set({ user }),
  toasts: [],
  addToast: (toast) => set((state) => {
    const id = Math.random().toString(36).substr(2, 9);
    setTimeout(() => { set((s) => ({ toasts: s.toasts.filter(t => t.id !== id) })) }, 4000);
    return { toasts: [...state.toasts, { ...toast, id }] };
  }),
  removeToast: (id) => set((state) => ({ toasts: state.toasts.filter(t => t.id !== id) })),
}));

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 1000 * 60 } } 
});

function mapPortalUser(
  portalAuth: ReturnType<typeof usePortalStore.getState>['portalAuth'],
): User | null {
  if (!portalAuth) {
    return null;
  }
  return {
    id: portalAuth.userId,
    name: portalAuth.nickname || portalAuth.username,
    email: portalAuth.username,
    role: portalAuth.isAdmin ? 'admin' : 'user',
  };
}

function buildRealtimeToast(item: NotificationEventItem) {
  const school = item.payload.school_name || '目标院校';
  const title = item.payload.title || item.payload.summary || '有新的情报变更';
  return `${school}: ${title}`;
}

// ==========================================
// 2. 基础 UI 组件与重构后【有意义】的图表
// ==========================================
const GlobalBackground = () => (
  <div className="fixed inset-0 z-0 pointer-events-none bg-[#fcfcfc]" style={{
    backgroundImage: 'linear-gradient(to right, #f1f5f9 1px, transparent 1px), linear-gradient(to bottom, #f1f5f9 1px, transparent 1px)',
    backgroundSize: '80px 80px',
  }}>
    <div className="absolute top-[10%] right-[20%] w-[400px] h-[400px] bg-cyan-100/30 rounded-full blur-[120px] pointer-events-none" />
  </div>
);

const ToastContainer = () => {
  const { toasts, removeToast } = useAppStore();
  return (
    <div className="fixed bottom-6 right-6 z-[200] flex flex-col gap-3 pointer-events-none">
      <AnimatePresence>
        {toasts.map(t => (
          <motion.div 
            key={t.id} initial={{ opacity: 0, x: 50, scale: 0.9 }} animate={{ opacity: 1, x: 0, scale: 1 }} exit={{ opacity: 0, scale: 0.9, transition: { duration: 0.2 } }}
            className={`pointer-events-auto flex items-center gap-3 px-4 py-3 rounded-2xl shadow-xl border backdrop-blur-xl ${
              t.type === 'success' ? 'bg-cyan-50/90 border-cyan-200 text-cyan-800' :
              t.type === 'warning' ? 'bg-orange-50/90 border-orange-200 text-orange-800' :
              'bg-slate-900/90 border-slate-700 text-white'
            }`}
          >
            {t.type === 'success' ? <CheckCircle2 size={18} className="text-cyan-500" /> : 
             t.type === 'warning' ? <Activity size={18} className="text-orange-500" /> : 
             <Info size={18} className="text-cyan-400" />}
            <span className="text-sm font-bold tracking-wide">{t.msg}</span>
            <button onClick={() => removeToast(t.id)} className="ml-2 opacity-50 hover:opacity-100 transition-opacity"><X size={14}/></button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
};

// ✨ 重构 1：24H 缺额释放流速趋势图 (Release Velocity)
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
    <div className="relative h-[48px] w-full min-w-[180px] max-w-[320px] xl:max-w-[420px]" onMouseLeave={() => setHoverIdx(null)}>
      <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" className="w-full h-full overflow-visible">
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
          transition={{ duration: 1.6, ease: "easeInOut" }}
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
          transition={{ duration: 1.6, ease: "easeInOut" }}
        />
        <motion.rect
          x={-72}
          y={0}
          width={72}
          height={height}
          fill="url(#trendSweepGradient)"
          clipPath="url(#trendClip)"
          animate={{ x: [-72, width + 36] }}
          transition={{ duration: 2.8, repeat: Infinity, ease: "linear" }}
        />

        {pointsMeta.filter((_, index) => index % Math.max(1, Math.floor(pointsMeta.length / 4)) === 0).map((point, index) => (
          <motion.circle
            key={`${point.label}-${index}`}
            cx={point.x}
            cy={point.y}
            r="1.8"
            fill="rgba(103, 232, 249, 0.65)"
            animate={{ opacity: [0.15, 0.45, 0.15], scale: [1, 1.45, 1] }}
            transition={{ duration: 2.2 + index * 0.3, repeat: Infinity, ease: "easeInOut" }}
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
          transition={{ duration: 1.8, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.circle
          cx={endPoint.x}
          cy={endPoint.y}
          r="6"
          fill="none"
          stroke="rgba(34, 211, 238, 0.55)"
          strokeWidth="1.2"
          animate={{ scale: [1, 1.9, 1], opacity: [0.55, 0, 0.55] }}
          transition={{ duration: 2.1, repeat: Infinity, ease: "easeOut" }}
        />

        {hoverIdx !== null && (
          <g>
            <line x1={pointsMeta[hoverIdx].x} y1="0" x2={pointsMeta[hoverIdx].x} y2={height} stroke="#cbd5e1" strokeWidth="1" strokeDasharray="2 2" />
            <circle cx={pointsMeta[hoverIdx].x} cy={pointsMeta[hoverIdx].y} r="3.5" fill="#06b6d4" stroke="#ffffff" strokeWidth="1.5" className="drop-shadow-md" />
          </g>
        )}

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
        {hoverIdx !== null && (
          <motion.div
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="absolute -top-10 px-2.5 py-1.5 bg-slate-800 text-white text-[10px] font-bold rounded-lg shadow-lg pointer-events-none z-10 whitespace-nowrap flex flex-col items-center"
            style={{ left: `${(pointsMeta[hoverIdx].x / width) * 100}%`, transform: 'translateX(-50%)' }}
          >
            <span className="text-cyan-400 font-mono">+{safeData[hoverIdx].value} 条信号</span>
            <span className="text-[9px] text-slate-400 font-normal">{safeData[hoverIdx].label}</span>
            <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-2 h-2 bg-slate-800 rotate-45"></div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

// ✨ 重构 2：今日调剂名额层级画像 (Tier Distribution)
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
    <div className="flex h-[36px] w-full min-w-[160px] max-w-[260px] items-end gap-1.5 xl:max-w-[320px]" onMouseLeave={() => setHoverIdx(null)}>
      {orderedTiers.map((tier, index) => {
        const isHovered = hoverIdx === index;
        const heightPercent = Math.max(18, (tier.count / max) * 100);
        const percentage = total ? Math.round((tier.count / total) * 100) : 0;
        const style = styleMap[tier.label];

        return (
          <div key={tier.label} className="flex-1 flex flex-col justify-end h-full relative cursor-pointer group" onMouseEnter={() => setHoverIdx(index)}>
            <motion.div
              initial={{ height: 0, opacity: 0.35 }}
              animate={{ height: `${heightPercent}%`, opacity: hoverIdx !== null && !isHovered ? 0.4 : 1 }}
              transition={{ duration: 0.9, delay: index * 0.08, ease: 'easeOut' }}
              className="w-full rounded-t-sm transition-all duration-200 relative overflow-hidden"
              style={{
                backgroundColor: style.color,
                boxShadow: `0 0 20px ${style.glow}`,
                filter: hoverIdx !== null && !isHovered ? 'saturate(0.8)' : 'none',
              }}
            >
              <motion.div
                className="absolute inset-y-0 -left-1/2 w-1/2"
                style={{ background: 'linear-gradient(90deg, rgba(255,255,255,0), rgba(255,255,255,0.45), rgba(255,255,255,0))' }}
                animate={{ x: ['0%', '260%'] }}
                transition={{ duration: 2.4 + index * 0.15, repeat: Infinity, ease: 'linear' }}
              />
              <motion.div
                className="absolute inset-x-0 top-0 h-2/5"
                style={{ background: 'linear-gradient(180deg, rgba(255,255,255,0.32), rgba(255,255,255,0))' }}
                animate={{ opacity: [0.35, 0.7, 0.35] }}
                transition={{ duration: 1.8 + index * 0.2, repeat: Infinity, ease: 'easeInOut' }}
              />
            </motion.div>

            <AnimatePresence>
              {isHovered && (
                <motion.div
                  initial={{ opacity: 0, y: 5 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className="absolute -top-12 left-1/2 -translate-x-1/2 px-3 py-1.5 bg-slate-800 text-white text-[10px] font-bold rounded-lg shadow-lg pointer-events-none whitespace-nowrap z-10 flex flex-col items-center"
                >
                  <span>{tierLabelMap[tier.label]}：<span className="text-cyan-400 font-mono">{tier.count}</span> 所</span>
                  <span className="text-[9px] text-slate-400 font-normal">占实时样本 {percentage}%</span>
                  <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-2 h-2 bg-slate-800 rotate-45"></div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        );
      })}
    </div>
  );
};

const SectionViewSwitch = ({
  view,
  onChange,
}: {
  view: HomeSectionView;
  onChange: (next: HomeSectionView) => void;
}) => (
  <div className="flex items-center gap-1 rounded-lg border border-slate-200/60 bg-white/70 p-0.5 shadow-sm">
    {(['latest', 'watching'] as const).map((item) => (
      <button
        key={item}
        type="button"
        onClick={() => onChange(item)}
        className={`px-3 py-1 text-[11px] font-bold rounded-md transition-all ${
          view === item ? 'bg-slate-900 text-white shadow-sm' : 'text-slate-400 hover:text-slate-700'
        }`}
      >
        {item === 'latest' ? '最新' : '我的关注'}
      </button>
    ))}
  </div>
);

const HomepageEmptyState = ({
  title,
  detail,
  ctaLabel,
  onClick,
}: {
  title: string;
  detail: string;
  ctaLabel?: string;
  onClick?: () => void;
}) => (
  <div className="flex min-h-[220px] flex-col items-center justify-center rounded-2xl border-2 border-dashed border-slate-100 bg-white/40 px-6 py-10 text-center">
    <p className="text-sm font-semibold text-slate-500">{title}</p>
    <p className="mt-2 max-w-[320px] text-xs leading-6 text-slate-400">{detail}</p>
    {ctaLabel && onClick ? (
      <button
        type="button"
        onClick={onClick}
        className="mt-5 text-xs font-bold text-cyan-600 hover:text-cyan-700 transition-colors flex items-center gap-1"
      >
        {ctaLabel} <ChevronRight size={12} />
      </button>
    ) : null}
  </div>
);

// ==========================================
// 3. 核心布局与视图
// ==========================================

const Header = () => {
  const router = useRouter();
  const { user, setAuthOpen, setUser, addToast } = useAppStore();
  const portalAuth = usePortalStore((state) => state.portalAuth);
  const clearPortalAuth = usePortalStore((state) => state.clearPortalAuth);
  const [searchMode, setSearchMode] = useState<'公告' | '调剂'>('公告');
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const [localKw, setLocalKw] = useState('');

  const navigateToSearch = (mode: '公告' | '调剂', keyword: string) => {
    const params = new URLSearchParams();
    params.set('tab', mode === '公告' ? 'announcements' : 'adjustments');
    if (keyword.trim()) {
      params.set('q', keyword.trim());
    }
    router.push(`/search?${params.toString()}`);
  };

  const handleLogout = async () => {
    try {
      await logoutUser();
    } catch {
      // local UI logout should still complete when the remote session is already invalidated
    }
    clearPortalAuth();
    setUser(null);
    setShowProfileMenu(false);
    addToast({ msg: '系统已断开连接', type: 'info' });
  };

  const executeSearch = () => {
    navigateToSearch(searchMode, localKw);
  };

  const handleWatchlistShortcut = () => {
    if (!portalAuth) {
      setAuthOpen(true);
      addToast({ msg: '登录后查看收藏院校的最新提醒', type: 'info' });
      return;
    }
    router.push('/watchlist');
  };

  return (
    <header className="fixed top-0 z-50 w-full border-b border-slate-200/50 bg-white/80 px-6 py-3 backdrop-blur-2xl transition-all duration-300 md:px-8 xl:px-10 2xl:px-12">
      <div className="grid w-full grid-cols-[auto_1fr_auto] items-center gap-6 xl:grid-cols-[minmax(max-content,360px)_minmax(0,1fr)_minmax(max-content,360px)]">
        <div className="flex min-w-0 items-center gap-6">
          <button type="button" className="flex items-center gap-2 cursor-pointer group" onClick={() => { setLocalKw(''); router.push('/'); }}>
            <div className="w-7 h-7 bg-slate-900 text-white rounded flex items-center justify-center font-black text-xs transition-transform group-hover:scale-105">GW</div>
            <span className="font-bold text-sm text-slate-900 tracking-tight">GewuJL.</span>
          </button>

          <nav className="hidden lg:flex items-center gap-6 text-sm font-medium text-slate-500">
            <Link href="/search?tab=announcements" className="text-slate-900 transition-colors">公告汇总</Link>
            <Link href="/search?tab=adjustments" className="hover:text-slate-900 transition-colors">调剂汇总</Link>
            <Link href="/radar" className="hover:text-slate-900 transition-colors flex items-center gap-1">
              雷达测算 <span className="bg-orange-100 text-orange-600 text-[9px] px-1.5 py-0.5 rounded uppercase font-bold tracking-wider">Beta</span>
            </Link>
          </nav>
        </div>

        <div className="group hidden w-full items-center justify-self-center rounded-xl border border-slate-200/60 bg-slate-100/50 p-1 transition-all hover:bg-slate-100 focus-within:border-cyan-300 focus-within:bg-white focus-within:shadow-[0_0_0_2px_rgba(6,182,212,0.1)] md:flex md:max-w-[560px] lg:max-w-[720px] xl:max-w-[920px] 2xl:max-w-[1080px]">
          <div className="flex items-center bg-white/80 rounded-lg shadow-sm p-0.5 border border-slate-200/50 shrink-0">
            {(['公告', '调剂'] as const).map((mode) => (
              <button
                key={mode}
                onClick={() => { setSearchMode(mode); navigateToSearch(mode, localKw); }}
                className={`px-3 py-1 text-xs font-bold rounded-md transition-all ${searchMode === mode ? 'bg-slate-900 text-white shadow-sm' : 'text-slate-500 hover:text-slate-800'}`}
              >
                {mode}
              </button>
            ))}
          </div>
          <div className="flex-1 flex items-center pl-3 pr-2">
            <Search size={14} className="text-slate-400 mr-2 shrink-0 group-focus-within:text-cyan-500 transition-colors" />
            <input
              type="text"
              value={localKw}
              onChange={(event) => setLocalKw(event.target.value)}
              onKeyDown={(event) => event.key === 'Enter' && executeSearch()}
              placeholder={`输入院校或专业, 在${searchMode}库检索...`}
              className="w-full bg-transparent border-none outline-none text-sm text-slate-800 placeholder-slate-400 font-medium"
            />
            {localKw && <button onClick={() => setLocalKw('')} className="text-slate-400 hover:text-slate-600 mr-2"><X size={14} /></button>}
          </div>
        </div>

        <div className="flex min-w-0 items-center justify-self-end gap-4">
          <button type="button" className="hidden sm:flex items-center gap-1.5 bg-green-50 px-2.5 py-1 rounded-md border border-green-100 cursor-pointer" onClick={handleWatchlistShortcut}>
            <span className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse shadow-[0_0_8px_#22c55e]"></span>
            <span className="text-[10px] font-mono text-green-700 uppercase">See Live</span>
          </button>

          <div className="w-px h-4 bg-slate-200 mx-1 hidden sm:block"></div>

          {user ? (
            <div className="relative" onMouseEnter={() => setShowProfileMenu(true)} onMouseLeave={() => setShowProfileMenu(false)}>
              <div className="flex items-center gap-2 cursor-pointer py-1">
                <div className="w-7 h-7 bg-cyan-100 text-cyan-700 rounded-md flex items-center justify-center font-bold text-xs uppercase">{user.name.charAt(0)}</div>
                <div className="hidden md:block text-xs font-bold text-slate-700">{user.name}</div>
              </div>

              <AnimatePresence>
                {showProfileMenu && (
                  <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 5 }} transition={{ duration: 0.15 }}
                    className="absolute right-0 top-full mt-1 w-56 bg-white border border-slate-200/60 rounded-xl shadow-xl overflow-hidden"
                  >
                    <div className="px-4 py-3 border-b border-slate-100 bg-slate-50/50">
                      <div className="text-sm font-bold text-slate-900 truncate">{user.email}</div>
                      <div className="text-[10px] text-slate-500 font-mono mt-0.5 flex items-center gap-1">
                        <ShieldCheck size={12} className="text-green-500"/> 已认证干员
                      </div>
                    </div>
                    <div className="p-2 space-y-1">
                      <Link href="/watchlist" className="flex items-center gap-2 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50 hover:text-cyan-600 rounded-lg transition-colors"><Star size={16} /> 雷达工作台</Link>
                      <Link href="/account" className="flex items-center gap-2 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50 hover:text-cyan-600 rounded-lg transition-colors"><User size={16} /> 账号中心</Link>
                      {user.role === 'admin' && (
                        <Link href="/admin" className="flex items-center gap-2 px-3 py-2 text-sm text-purple-600 hover:bg-purple-50 rounded-lg transition-colors"><Terminal size={16} /> 管理后台</Link>
                      )}
                    </div>
                    <div className="p-2 border-t border-slate-100">
                      <button onClick={handleLogout} className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors"><LogOut size={16} /> 断开连接</button>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          ) : (
            <>
              <button onClick={() => setAuthOpen(true)} className="text-sm font-bold text-slate-700 hover:text-slate-900 transition-colors">登录</button>
              <button onClick={() => setAuthOpen(true)} className="bg-slate-900 text-white text-sm font-bold px-4 py-1.5 rounded-lg hover:bg-slate-800 transition-all active:scale-95 shadow-sm">免费接入</button>
            </>
          )}
        </div>
      </div>
    </header>
  );
};

const useLatestAnnouncements = () => {
  return useQuery({
    queryKey: ['home', 'latest-announcements'],
    queryFn: async () => {
      const response = await fetchAnnouncementResults({
        page: 1,
        page_size: 6,
      });
      return response.items;
    }
  });
};

const useLatestAdjustments = () => {
  return useQuery({
    queryKey: ['home', 'latest-adjustments'],
    queryFn: async () => {
      const response = await fetchAdjustmentResults({
        page: 1,
        page_size: 12,
      });
      return response.items;
    }
  });
};

const DashboardHome = () => {
  const router = useRouter();
  const { addToast, setAuthOpen } = useAppStore();
  const portalAuth = usePortalStore((state) => state.portalAuth);
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
  const loadingNotices = announcementView === 'latest'
    ? latestAnnouncementsQuery.isLoading
    : Boolean(portalAuth) && (pendingNoticesQuery.isLoading || monitorTargetsQuery.isLoading);
  const loadingAdjustments = adjustmentView === 'latest'
    ? latestAdjustmentsQuery.isLoading
    : Boolean(portalAuth) && (subscriptionsQuery.isLoading || watchedAdjustmentsQuery.isLoading);

  const openProtectedPage = (href: string) => {
    if (!portalAuth) {
      setAuthOpen(true);
      addToast({ msg: '登录后使用收藏与关注功能', type: 'info' });
      return;
    }
    router.push(href);
  };

  const openAnnouncementCard = (item: AnnouncementFeedItem) => {
    if (item.sourceUrl) {
      window.open(item.sourceUrl, '_blank', 'noopener,noreferrer');
      return;
    }
    router.push(item.href || '/search?tab=announcements');
  };

  const openAdjustmentCard = (item: AdjustmentFeedItem) => {
    if (item.sourceUrl) {
      window.open(item.sourceUrl, '_blank', 'noopener,noreferrer');
      return;
    }
    router.push(item.href || '/search?tab=adjustments');
  };

  const liveSummaryLabel = portalAuth
    ? (liveSummary.latestSchool || `${liveSummary.activeTargetCount} 个收藏范围在线`)
    : '登录后查看收藏院校提醒';

  return (
    <div className="relative z-10 w-full px-6 pb-32 pt-28 md:px-8 xl:px-10 2xl:px-12">
      <div className="mb-20 flex w-full flex-col gap-12 lg:flex-row lg:items-end lg:gap-10 xl:gap-12">
        <div className="flex w-full flex-1 min-w-0 items-end gap-6">
          <div>
            <div className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1.5 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 bg-cyan-400 rounded-full shadow-[0_0_6px_rgba(6,182,212,0.6)]"></span> RELEASE VELOCITY
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-black text-slate-900 tracking-tighter flex items-center"><span className="text-xl text-cyan-500 font-bold mr-0.5">+</span>{releaseVelocity}</span>
              <span className="text-[10px] font-bold text-slate-400 tracking-widest uppercase">/ 24H</span>
            </div>
          </div>
          <div className="flex-1 pb-1">
            <QuotaTrendChart data={trendSeries} />
            <div className="text-[8px] text-slate-400 font-mono tracking-widest uppercase mt-2">全网调剂新增趋势</div>
          </div>
        </div>

        <div className="flex w-full flex-1 min-w-0 items-end gap-6">
          <div>
            <div className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1.5">QUALITY TIER</div>
            <div className="flex items-baseline gap-1.5">
              <span className="text-base font-black text-slate-900">{qualityTierRate}%</span>
              <span className="text-[10px] font-bold text-slate-400">来自 985/211/双一流</span>
            </div>
          </div>
          <div className="flex-1 pb-1">
            <TierDistributionChart tiers={tierBreakdown} />
            <div className="mt-2 flex w-full max-w-[260px] justify-between text-[8px] font-mono uppercase text-slate-400 xl:max-w-[320px]">
              <span>985</span><span>211</span><span>D1L</span><span>ORD</span>
            </div>
          </div>
        </div>

        <div 
          className="hidden flex-col items-start gap-1.5 rounded-xl border border-orange-200/50 bg-orange-50/60 px-5 py-3 shadow-sm backdrop-blur-sm transition-colors group cursor-pointer hover:bg-orange-100/60 xl:flex xl:min-w-[220px] xl:flex-none"
          onClick={() => openProtectedPage('/watchlist')}
        >
           <div className="flex items-center gap-2">
             <div className="w-1.5 h-1.5 bg-orange-500 rounded-full animate-pulse"></div>
             <span className="text-[10px] font-bold text-orange-600 uppercase tracking-widest">SEE LIVE</span>
           </div>
           <div className="flex items-end gap-2 mt-0.5">
              <span className="text-xl font-bold font-mono text-orange-500 leading-none">{portalAuth ? liveSummary.pendingCount : 0}</span>
              <span className="text-[10px] text-slate-500 mb-0.5 group-hover:text-orange-600 transition-colors">{liveSummaryLabel}</span>
           </div>
        </div>
      </div>

      <div className="grid w-full grid-cols-1 gap-12 lg:grid-cols-2 lg:gap-10 xl:gap-12">
        <div className="space-y-4 transition-opacity duration-300 opacity-100">
          <div className="flex items-center justify-between mb-4 pb-2 border-b border-slate-100 gap-4">
            <div className="flex items-center gap-3 min-w-0">
              <h2 className="text-xs font-black text-slate-400 uppercase tracking-widest flex items-center gap-2 shrink-0">
                <FileText size={14} className="text-cyan-500"/> 全网公告流
              </h2>
              <SectionViewSwitch view={announcementView} onChange={setAnnouncementView} />
            </div>
            <button onClick={() => router.push('/search?tab=announcements')} className="text-xs font-bold text-cyan-600 hover:text-cyan-700 transition-colors flex items-center gap-1 shrink-0">
              高级检索 <ChevronRight size={12}/>
            </button>
          </div>
          
          <div className="space-y-3 min-h-[300px]">
            {loadingNotices ? (
              Array(3).fill(0).map((_, index) => <div key={index} className="p-5 rounded-2xl border border-slate-100 bg-white/50 animate-pulse h-32"></div>)
            ) : announcementCards.length > 0 ? announcementCards.map((item) => (
              <motion.div 
                key={item.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
                className="group relative bg-white rounded-2xl p-5 border border-slate-200/50 hover:border-cyan-300 hover:shadow-[0_8px_30px_rgba(6,182,212,0.08)] transition-all cursor-pointer"
                onClick={() => openAnnouncementCard(item)}
              >
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2.5">
                    {item.isNew && <span className="w-1.5 h-1.5 bg-cyan-500 rounded-full"></span>}
                    <span className="text-[11px] font-bold text-slate-600 bg-slate-100 px-2 py-0.5 rounded-md">{item.type}</span>
                    <span className="text-[11px] font-mono text-slate-400">{item.time}</span>
                  </div>
                  <span className="text-[11px] font-bold text-slate-400">{item.school}</span>
                </div>
                <h3 className="text-[15px] font-bold text-slate-900 mb-2 leading-snug group-hover:text-cyan-600 transition-colors pr-6">
                  {item.title}
                </h3>
                <p className="text-[13px] text-slate-500 line-clamp-2 leading-relaxed">{item.content}</p>
                <div className="absolute right-4 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-all -translate-x-2 group-hover:translate-x-0">
                  <ArrowUpRight className="text-cyan-500" size={20} />
                </div>
              </motion.div>
            )) : !portalAuth && announcementView === 'watching' ? (
              <HomepageEmptyState
                title="登录后查看我的关注"
                detail="首页会直接展示你收藏院校和监控范围内的最新公告提醒。"
                ctaLabel="立即登录"
                onClick={() => setAuthOpen(true)}
              />
            ) : portalAuth && announcementView === 'watching' && !watchedAnnouncementCards.length && !(monitorTargetsQuery.data?.items || []).length ? (
              <HomepageEmptyState
                title="还没有关注范围"
                detail="先去工作台收藏院校或设置监控范围，首页才会自动汇总关注公告。"
                ctaLabel="去设置关注"
                onClick={() => router.push('/watchlist')}
              />
            ) : portalAuth && announcementView === 'watching' ? (
              <HomepageEmptyState
                title="关注范围暂时没有新公告"
                detail="收藏院校和监控范围还在监听中，新的提醒会优先回流到这里。"
                ctaLabel="查看工作台"
                onClick={() => router.push('/watchlist')}
              />
            ) : (
              <HomepageEmptyState
                title="暂时没有新的公告数据"
                detail="可以进入公告搜索页做更细的检索，或稍后刷新首页。"
                ctaLabel="进入公告汇总"
                onClick={() => router.push('/search?tab=announcements')}
              />
            )}
          </div>
        </div>

        <div className="space-y-4 transition-opacity duration-300 opacity-100">
          <div className="flex items-center justify-between mb-4 pb-2 border-b border-slate-100 gap-4">
            <div className="flex items-center gap-3 min-w-0">
              <h2 className="text-xs font-black text-slate-400 uppercase tracking-widest flex items-center gap-2 shrink-0">
                <Activity size={14} className="text-orange-500"/> 调剂异动雷达
              </h2>
              <SectionViewSwitch view={adjustmentView} onChange={setAdjustmentView} />
            </div>
            <button onClick={() => router.push('/search?tab=adjustments')} className="text-xs font-bold text-orange-500 hover:text-orange-600 transition-colors flex items-center gap-1 shrink-0">
              调剂汇总 <ChevronRight size={12}/>
            </button>
          </div>

          <div className="space-y-3 min-h-[300px]">
            {loadingAdjustments ? (
              Array(3).fill(0).map((_, index) => <div key={index} className="p-5 rounded-2xl border border-slate-100 bg-white/50 animate-pulse h-32"></div>)
            ) : adjustmentCards.length > 0 ? adjustmentCards.map((item) => (
              <motion.div 
                key={item.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
                className={`group relative bg-white rounded-2xl p-5 border transition-all cursor-pointer flex items-center justify-between 
                  ${item.urgent ? 'border-orange-200/60 hover:border-orange-400 hover:shadow-[0_8px_30px_rgba(249,115,22,0.08)]' : 'border-slate-200/50 hover:border-cyan-300 hover:shadow-[0_8px_30px_rgba(6,182,212,0.08)]'}
                `}
                onClick={() => openAdjustmentCard(item)}
              >
                <div className="min-w-0 pr-4 flex-1">
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className="text-[11px] font-bold text-slate-500">{item.school}</span>
                    <span className="text-slate-300 text-[10px]">•</span>
                    <span className="text-[11px] text-slate-400">{item.major}</span>
                  </div>
                  <h3 className={`text-[15px] font-bold mb-2 truncate transition-colors ${item.urgent ? 'text-slate-900 group-hover:text-orange-600' : 'text-slate-900 group-hover:text-cyan-600'}`}>
                    {item.title}
                  </h3>
                  <div className="flex items-center gap-1.5 mt-2">
                    {item.tags.map((tag, index) => (
                      <span key={`${item.id}-${tag}-${index}`} className="px-1.5 py-0.5 bg-slate-50 text-slate-500 text-[10px] rounded border border-slate-100">{tag}</span>
                    ))}
                  </div>
                </div>
                
                <div className="text-right shrink-0 ml-4 flex flex-col items-end">
                  <div className="flex items-baseline gap-1 mb-1">
                    <span className="text-xs font-bold text-slate-400">缺额</span>
                    <span className={`text-2xl font-black font-mono leading-none ${item.urgent ? 'text-orange-500' : 'text-slate-900 group-hover:text-cyan-600'}`}>
                      {item.count}
                    </span>
                  </div>
                  <div className="flex gap-2 mt-1">
                    <button onClick={(event) => { event.stopPropagation(); openProtectedPage('/watchlist'); }} className="p-1 text-slate-300 hover:text-yellow-400 transition-colors"><Star size={14}/></button>
                    {item.urgent && <span className="text-[9px] font-bold text-orange-600 bg-orange-50 px-1.5 py-0.5 rounded-sm uppercase tracking-wider">Urgent</span>}
                  </div>
                </div>
              </motion.div>
            )) : !portalAuth && adjustmentView === 'watching' ? (
              <HomepageEmptyState
                title="登录后查看我的调剂关注"
                detail="首页会把你收藏院校、专业或雷达订阅对应的调剂结果自动拉回首页。"
                ctaLabel="立即登录"
                onClick={() => setAuthOpen(true)}
              />
            ) : portalAuth && adjustmentView === 'watching' && !focusedAdjustment ? (
              <HomepageEmptyState
                title="还没有调剂关注"
                detail="先在搜索页或工作台保存学校、专业或雷达订阅，首页才能展示对应的调剂汇总。"
                ctaLabel="去设置关注"
                onClick={() => router.push('/watchlist')}
              />
            ) : portalAuth && adjustmentView === 'watching' ? (
              <HomepageEmptyState
                title="当前关注暂无调剂新信号"
                detail={focusedAdjustment ? `已按 ${focusedAdjustment.focusLabel} 追踪调剂结果，新的异动会直接回流到首页。` : '收藏院校和专业仍在持续扫描中。'}
                ctaLabel="进入调剂汇总"
                onClick={() => router.push('/search?tab=adjustments')}
              />
            ) : !portalAuth ? (
              <HomepageEmptyState
                title="登录后查看最新调剂异动"
                detail="调剂数据受登录权限保护，登录后首页会展示最新调剂异动和你的关注结果。"
                ctaLabel="立即登录"
                onClick={() => setAuthOpen(true)}
              />
            ) : (
              <HomepageEmptyState
                title="暂时没有新的调剂数据"
                detail="可以进入调剂汇总页查看更多实时结果，或稍后刷新首页。"
                ctaLabel="进入调剂汇总"
                onClick={() => router.push('/search?tab=adjustments')}
              />
            )}
          </div>
        </div>

      </div>
    </div>
  );
};

// 🚀 整合登录与注册双形态 Modal
const AuthModal = () => {
  const { isAuthOpen, setAuthOpen, setUser, addToast } = useAppStore();
  const setPortalAuthFromToken = usePortalStore((state) => state.setPortalAuthFromToken);
  const setPortalProfile = usePortalStore((state) => state.setPortalProfile);
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [registerUsername, setRegisterUsername] = useState('');
  const [loginName, setLoginName] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting) return;

    const authUsername = mode === 'register' ? registerUsername.trim() : loginName.trim();
    if (!authUsername || !password.trim()) {
      addToast({ msg: '请先输入账号与密码', type: 'warning' });
      return;
    }

    setSubmitting(true);
    try {
      if (mode === 'register') {
        await registerUser({
          username: authUsername,
          password,
          nickname: loginName.trim() || undefined,
        });
      }

      const session = await loginUser({ username: authUsername, password });
      setPortalAuthFromToken({
        tokenType: session.token_type,
        accessToken: session.access_token,
        expiresIn: session.expires_in,
        refreshExpiresIn: session.refresh_expires_in,
        userId: session.user_id,
        username: session.username,
      });

      const profile = await getCurrentUser(session.access_token);
      setPortalProfile({
        nickname: profile.nickname,
        status: profile.status,
        isAdmin: profile.is_admin,
        isPremium: profile.is_premium,
        role: profile.role,
        premiumExpiresAt: profile.premium_expires_at,
      });
      setUser({
        id: profile.user_id,
        name: profile.nickname || profile.username,
        email: profile.username,
        role: profile.is_admin ? 'admin' : 'user',
      });
      setAuthOpen(false);
      addToast({ msg: mode === 'login' ? '系统授权成功，欢迎回来' : '账号已激活，已完成接入', type: 'success' });
      setRegisterUsername('');
      setLoginName('');
      setPassword('');
      return;
    } catch (error) {
      addToast({ msg: error instanceof Error ? error.message : '授权失败，请稍后重试', type: 'warning' });
      return;
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AnimatePresence>
      {isAuthOpen && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-[100] flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-slate-900/20 backdrop-blur-sm" onClick={() => setAuthOpen(false)} />
          <motion.div initial={{ scale: 0.95, y: 10 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.95, y: 10 }} className="bg-white w-full max-w-sm p-8 rounded-3xl relative z-10 shadow-2xl border border-slate-100">
            <button onClick={() => setAuthOpen(false)} className="absolute top-5 right-5 text-slate-400 hover:text-slate-900 transition-colors"><X size={18}/></button>
            <div className="mb-6">
              <div className="w-10 h-10 bg-slate-900 text-white rounded-lg flex items-center justify-center font-black text-sm mb-4 shadow-md">GW</div>
              <h3 className="text-2xl font-bold text-slate-900 tracking-tight">
                {mode === 'login' ? '接入控制台' : '创建新干员档案'}
              </h3>
              <p className="text-sm text-slate-500 mt-1">
                {mode === 'login' ? '使用企业邮箱或管理员账号验证' : '解锁全网雷达监控权限'}
              </p>
            </div>
            
            <form onSubmit={handleSubmit} className="space-y-3">
              {mode === 'register' && <input value={registerUsername} onChange={(e) => setRegisterUsername(e.target.value)} type="text" placeholder="干员代号 (Username)" required className="w-full bg-slate-50 border border-slate-200 rounded-xl py-3 px-4 text-sm text-slate-900 outline-none focus:border-cyan-500 focus:bg-white transition-colors" />}
              <input value={loginName} onChange={(e) => setLoginName(e.target.value)} type="text" placeholder="name@example.com" required className="w-full bg-slate-50 border border-slate-200 rounded-xl py-3 px-4 text-sm text-slate-900 outline-none focus:border-cyan-500 focus:bg-white transition-colors" />
              <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" placeholder="********" required className="w-full bg-slate-50 border border-slate-200 rounded-xl py-3 px-4 text-sm text-slate-900 outline-none focus:border-cyan-500 focus:bg-white transition-colors" />
              
              <button type="submit" disabled={submitting} className="w-full bg-slate-900 text-white font-bold rounded-xl py-3.5 mt-2 hover:bg-slate-800 transition-all active:scale-[0.98] text-sm shadow-md flex items-center justify-center gap-2 disabled:opacity-70">
                {submitting ? '处理中...' : mode === 'login' ? '授权登录' : '激活档案'} <CheckCircle2 size={16}/>
              </button>
            </form>

            <div className="mt-6 pt-4 border-t border-slate-100 text-center">
              <button onClick={() => setMode(mode === 'login' ? 'register' : 'login')} className="text-sm font-bold text-cyan-600 hover:text-cyan-700 transition-colors">
                {mode === 'login' ? '没有白名单许可？点击申请' : '已有系统档案？返回验证'}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

// ==========================================
// 4. 应用主入口
// ==========================================
export default function App() {
  const { addToast, setUser } = useAppStore();
  const portalAuth = usePortalStore((state) => state.portalAuth);
  const clearPortalAuth = usePortalStore((state) => state.clearPortalAuth);

  useEffect(() => {
    setUser(mapPortalUser(portalAuth));
  }, [portalAuth, setUser]);

  useEffect(() => {
    const accessToken = portalAuth?.accessToken;
    const activeUserId = portalAuth?.userId;
    if (!accessToken) {
      return;
    }

    const abortController = new AbortController();
    void fetchEventSource(notificationsStreamUrl(), {
      method: 'GET',
      headers: {
        Accept: 'text/event-stream',
        'X-User-Token': accessToken,
      },
      signal: abortController.signal,
      credentials: 'include',
      openWhenHidden: false,
      async onopen(response) {
        if (response.ok) return;
        if (response.status === 401) {
          clearPortalAuth();
          throw new Error('Unauthorized');
        }
        throw new Error(`SSE open failed: ${response.status}`);
      },
      onmessage(event) {
        if (event.event !== 'notice' || !event.data) {
          return;
        }
        try {
          const item = JSON.parse(event.data) as NotificationEventItem;
          if (!item?.id) return;
          if (activeUserId) {
            queryClient.setQueryData(
              watchlistNoticeQueryKey(activeUserId),
              (oldData: NotificationEventItem[] | undefined) => mergeNoticeList(oldData, [item]),
            );
          }
          addToast({
            msg: buildRealtimeToast(item),
            type: 'warning',
          });
        } catch (error) {
          console.error('Failed to parse SSE message', error);
        }
      },
      onerror(error) {
        if (abortController.signal.aborted) return;
        console.error('Home SSE stream failed', error);
      }
    });
    return () => abortController.abort();
  }, [addToast, clearPortalAuth, portalAuth?.accessToken, portalAuth?.userId]);

  return (
    <QueryClientProvider client={queryClient}>
      <div className="min-h-screen bg-[#fcfcfc] text-slate-900 font-sans selection:bg-cyan-100 selection:text-cyan-900 relative">
        <GlobalBackground />
        <Header />
        
        <main className="relative z-10">
           <DashboardHome />
        </main>

        <AuthModal />
        <ToastContainer />
      </div>
    </QueryClientProvider>
  );
}
