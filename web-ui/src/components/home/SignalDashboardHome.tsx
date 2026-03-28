'use client';

import React, { useEffect, useState } from 'react';
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
import { useAppStore as usePortalStore } from '@/lib/store';

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

type AnnouncementFeedItem = {
  id: string;
  type: string;
  title: string;
  content: string;
  school: string;
  time: string;
  isNew: boolean;
};

type AdjustmentFeedItem = {
  id: string;
  school: string;
  title: string;
  tags: string[];
  major: string;
  count: number;
  urgent: boolean;
};

function formatRelativeTime(input: string | null) {
  if (!input) return 'Just Now';
  const date = new Date(input);
  if (Number.isNaN(date.getTime())) return 'Just Now';

  const diffMs = Date.now() - date.getTime();
  if (diffMs < 60 * 1000) return 'Just Now';
  if (diffMs < 60 * 60 * 1000) return `${Math.floor(diffMs / (60 * 1000))} mins ago`;
  if (diffMs < 24 * 60 * 60 * 1000) return `${Math.floor(diffMs / (60 * 60 * 1000))} hours ago`;
  return `${Math.floor(diffMs / (24 * 60 * 60 * 1000))} days ago`;
}

function isFresh(input: string | null) {
  if (!input) return true;
  const date = new Date(input);
  if (Number.isNaN(date.getTime())) return false;
  return Date.now() - date.getTime() < 90 * 60 * 1000;
}

function mapAnnouncementItem(item: SearchItem): AnnouncementFeedItem {
  const timestamp = item.published_at || item.updated_at;
  return {
    id: item.id,
    type: (item.notice_kind || item.channel_label || item.source_type || '公告').slice(0, 8),
    title: item.title,
    content: item.summary || item.school_intelligence?.signal_detail || '点击查看完整公告内容...',
    school: item.school_name || item.department_name || '目标院校',
    time: formatRelativeTime(timestamp),
    isNew: isFresh(timestamp),
  };
}

function mapAdjustmentItem(item: SearchItem): AdjustmentFeedItem {
  const tags = Array.from(
    new Set(
      [
        ...(item.tags || []),
        ...(item.system_tags || []),
        item.adjustment_year ? `${item.adjustment_year}调剂` : null,
        item.school_tier,
      ].filter((value): value is string => Boolean(value && value.trim())),
    ),
  ).slice(0, 2);
  const count = item.adjustment_vacancy_count ?? item.historical_adjustment?.sample_count ?? 0;
  return {
    id: item.id,
    school: item.school_name || '目标院校',
    title: item.title,
    tags: tags.length ? tags : ['调剂情报', '实时更新'],
    major: item.major || item.department_name || item.channel_label || '调剂信息',
    count,
    urgent: count > 0 && count <= 5,
  };
}

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
const QuotaTrendChart = () => {
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  const data = [12, 24, 18, 42, 68, 125, 95, 140, 210, 180, 250, 320, 280, 410, 380, 520, 460, 680, 842];
  const timeLabels = ["00:00", "01:00", "02:00", "03:00", "04:00", "05:00", "06:00", "07:00", "08:00", "09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00", "NOW"];
  const max = Math.max(...data);
  const width = 180;
  const height = 48; 
  const points = data.map((val, i) => `${(i / (data.length - 1)) * width},${height - (val / max) * height}`).join(' L ');
  const fillD = `M 0,${height} L ${points} L ${width},${height} Z`;

  return (
    <div className="relative h-[48px] w-full min-w-[180px] max-w-[320px] xl:max-w-[420px]" onMouseLeave={() => setHoverIdx(null)}>
      <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" className="w-full h-full overflow-visible">
        <defs>
          <linearGradient id="trendGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgba(6, 182, 212, 0.3)" />
            <stop offset="100%" stopColor="rgba(6, 182, 212, 0)" />
          </linearGradient>
        </defs>
        <motion.path d={fillD} fill="url(#trendGradient)" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 1 }} />
        <motion.path d={`M ${points}`} fill="none" stroke="#06b6d4" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 1.5, ease: "easeInOut" }} />
        
        <circle cx={width} cy={height - (data[data.length-1]/max)*height} r="3" fill="#ffffff" stroke="#06b6d4" strokeWidth="2" className="drop-shadow-sm" />

        {hoverIdx !== null && (
          <g>
            <line x1={(hoverIdx / (data.length - 1)) * width} y1="0" x2={(hoverIdx / (data.length - 1)) * width} y2={height} stroke="#cbd5e1" strokeWidth="1" strokeDasharray="2 2" />
            <circle cx={(hoverIdx / (data.length - 1)) * width} cy={height - (data[hoverIdx] / max) * height} r="3.5" fill="#06b6d4" stroke="#ffffff" strokeWidth="1.5" className="drop-shadow-md" />
          </g>
        )}

        {data.map((_, i) => (
          <rect key={i} x={i === 0 ? 0 : ((i - 0.5) / (data.length - 1)) * width} y="0" width={width / (data.length - 1)} height={height} fill="transparent" onMouseEnter={() => setHoverIdx(i)} className="cursor-crosshair" />
        ))}
      </svg>

      <AnimatePresence>
        {hoverIdx !== null && (
          <motion.div 
            initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="absolute -top-10 px-2.5 py-1.5 bg-slate-800 text-white text-[10px] font-bold rounded-lg shadow-lg pointer-events-none z-10 whitespace-nowrap flex flex-col items-center"
            style={{ left: `${(hoverIdx / (data.length - 1)) * 100}%`, transform: 'translateX(-50%)' }}
          >
            <span className="text-cyan-400 font-mono">+{data[hoverIdx]} 个缺额</span>
            <span className="text-[9px] text-slate-400 font-normal">{timeLabels[hoverIdx]}</span>
            <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-2 h-2 bg-slate-800 rotate-45"></div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

// ✨ 重构 2：今日调剂名额层级画像 (Tier Distribution)
const TierDistributionChart = () => {
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  
  // 更有意义的业务数据：院校层级的缺额分布
  const tiers = [
    { label: '985', count: 142, color: 'bg-cyan-500' },
    { label: '211', count: 356, color: 'bg-blue-500' },
    { label: '双一流', count: 284, color: 'bg-indigo-400' },
    { label: '普本', count: 890, color: 'bg-slate-200' },
  ];
  const max = Math.max(...tiers.map(t => t.count));
  const total = tiers.reduce((acc, curr) => acc + curr.count, 0);

  return (
    <div className="flex h-[36px] w-full min-w-[160px] max-w-[260px] items-end gap-1.5 xl:max-w-[320px]" onMouseLeave={() => setHoverIdx(null)}>
      {tiers.map((tier, i) => {
        const isHovered = hoverIdx === i;
        const heightPercent = (tier.count / max) * 100;
        const percentage = Math.round((tier.count / total) * 100);

        return (
          <div key={i} className="flex-1 flex flex-col justify-end h-full relative cursor-pointer group" onMouseEnter={() => setHoverIdx(i)}>
            <motion.div 
              initial={{ height: 0 }} animate={{ height: `${heightPercent}%` }} transition={{ duration: 0.8, delay: i * 0.1 }}
              className={`w-full rounded-t-sm transition-all duration-200 ${tier.color} ${hoverIdx !== null && !isHovered ? 'opacity-40' : 'opacity-100 hover:brightness-110'}`} 
            />
            
            <AnimatePresence>
              {isHovered && (
                <motion.div 
                  initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} 
                  className="absolute -top-12 left-1/2 -translate-x-1/2 px-3 py-1.5 bg-slate-800 text-white text-[10px] font-bold rounded-lg shadow-lg pointer-events-none whitespace-nowrap z-10 flex flex-col items-center"
                >
                  <span>{tier.label}：<span className="text-cyan-400 font-mono">{tier.count}</span> 个</span>
                  <span className="text-[9px] text-slate-400 font-normal">占总缺额 {percentage}%</span>
                  <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-2 h-2 bg-slate-800 rotate-45"></div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )
      })}
    </div>
  );
};

// ==========================================
// 3. 核心布局与视图
// ==========================================

const Header = ({ onGlobalSearch }: { onGlobalSearch: (kw: string, mode: string) => void }) => {
  const { user, setAuthOpen, setUser, addToast } = useAppStore();
  const clearPortalAuth = usePortalStore((state) => state.clearPortalAuth);
  const [searchMode, setSearchMode] = useState<'公告' | '调剂'>('公告');
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const [localKw, setLocalKw] = useState('');

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
    onGlobalSearch(localKw, searchMode);
    addToast({ msg: `正在${searchMode}库中检索: ${localKw || '全部'}`, type: 'info' });
  };

  return (
    <header className="fixed top-0 z-50 w-full border-b border-slate-200/50 bg-white/80 px-6 py-3 backdrop-blur-2xl transition-all duration-300 md:px-8 xl:px-10 2xl:px-12">
      <div className="grid w-full grid-cols-[auto_1fr_auto] items-center gap-6 xl:grid-cols-[minmax(max-content,360px)_minmax(0,1fr)_minmax(max-content,360px)]">
        
        {/* 左侧：Logo & 主导航 */}
        <div className="flex min-w-0 items-center gap-6">
          <div className="flex items-center gap-2 cursor-pointer group" onClick={() => { setLocalKw(''); onGlobalSearch('', '公告'); }}>
            <div className="w-7 h-7 bg-slate-900 text-white rounded flex items-center justify-center font-black text-xs transition-transform group-hover:scale-105">GW</div>
            <span className="font-bold text-sm text-slate-900 tracking-tight">GewuJL.</span>
          </div>
          
          <nav className="hidden lg:flex items-center gap-6 text-sm font-medium text-slate-500">
            <a href="#" className="text-slate-900 transition-colors">情报速报</a>
            <a href="#" className="hover:text-slate-900 transition-colors">智能查询</a>
            <a href="#" className="hover:text-slate-900 transition-colors flex items-center gap-1">
               调剂雷达 <span className="bg-orange-100 text-orange-600 text-[9px] px-1.5 py-0.5 rounded uppercase font-bold tracking-wider">Beta</span>
            </a>
          </nav>
        </div>

        {/* 中间：全站统一快捷搜索 */}
        <div className="group hidden w-full items-center justify-self-center rounded-xl border border-slate-200/60 bg-slate-100/50 p-1 transition-all hover:bg-slate-100 focus-within:border-cyan-300 focus-within:bg-white focus-within:shadow-[0_0_0_2px_rgba(6,182,212,0.1)] md:flex md:max-w-[560px] lg:max-w-[720px] xl:max-w-[920px] 2xl:max-w-[1080px]">
           <div className="flex items-center bg-white/80 rounded-lg shadow-sm p-0.5 border border-slate-200/50 shrink-0">
             {(['公告', '调剂'] as const).map(mode => (
               <button 
                 key={mode} 
                  onClick={() => { setSearchMode(mode); onGlobalSearch(localKw, mode); }} 
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
               onChange={(e) => setLocalKw(e.target.value)}
               onKeyDown={(e) => e.key === 'Enter' && executeSearch()}
               placeholder={`输入院校或专业, 在${searchMode}库检索...`} 
               className="w-full bg-transparent border-none outline-none text-sm text-slate-800 placeholder-slate-400 font-medium" 
             />
             {localKw && <button onClick={() => {setLocalKw(''); onGlobalSearch('', searchMode);}} className="text-slate-400 hover:text-slate-600 mr-2"><X size={14}/></button>}
           </div>
        </div>

        {/* 右侧：用户状态 */}
        <div className="flex min-w-0 items-center justify-self-end gap-4">
          <div className="hidden sm:flex items-center gap-1.5 bg-green-50 px-2.5 py-1 rounded-md border border-green-100 cursor-help" onClick={() => addToast({msg:'SSE 实时通道已连接', type:'success'})}>
            <span className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse shadow-[0_0_8px_#22c55e]"></span>
            <span className="text-[10px] font-mono text-green-700 uppercase">SSE Live</span>
          </div>

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
                      <a href="#" className="flex items-center gap-2 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50 hover:text-cyan-600 rounded-lg transition-colors"><Star size={16} /> 雷达工作台</a>
                      <a href="#" className="flex items-center gap-2 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50 hover:text-cyan-600 rounded-lg transition-colors"><User size={16} /> 账号中心</a>
                      {user.role === 'admin' && (
                        <a href="#" className="flex items-center gap-2 px-3 py-2 text-sm text-purple-600 hover:bg-purple-50 rounded-lg transition-colors"><Terminal size={16} /> 爬虫监控台</a>
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

// 🚀 模拟接口 Hooks
const useAnnouncements = (keyword: string) => {
  return useQuery({
    queryKey: ['home', 'announcements', keyword],
    queryFn: async () => {
      const response = await fetchAnnouncementResults({
        keywords: keyword || undefined,
        page: 1,
        page_size: 3,
      });
      return response.items.map((item) => mapAnnouncementItem(item));
    }
  });
};

const useAdjustments = (keyword: string) => {
  return useQuery({
    queryKey: ['home', 'adjustments', keyword],
    queryFn: async () => {
      const response = await fetchAdjustmentResults({
        keywords: keyword || undefined,
        page: 1,
        page_size: 3,
      });
      return response.items.map((item) => mapAdjustmentItem(item));
    }
  });
};

const DashboardHome = ({ searchKw, searchMode }: { searchKw: string, searchMode: string }) => {
  const { data: notices, isLoading: loadingNotices } = useAnnouncements(searchMode === '公告' ? searchKw : '');
  const { data: adjustments, isLoading: loadingAdjustments } = useAdjustments(searchMode === '调剂' ? searchKw : '');
  const { addToast } = useAppStore();
  const releaseVelocity = adjustments?.length || 0;
  const qualityTierRate = adjustments?.length
    ? Math.round(
        (adjustments.filter((item: AdjustmentFeedItem) => item.tags.some((tag: string) => ['985', '211', '双一流'].includes(tag))).length /
          adjustments.length) *
          100,
      )
    : 0;

  return (
    <div className="relative z-10 w-full px-6 pb-32 pt-28 md:px-8 xl:px-10 2xl:px-12">
      
      {/* === 顶部无边框数据总览 (赋能业务意义) === */}
      <div className="mb-20 flex w-full flex-col gap-12 lg:flex-row lg:items-end lg:gap-10 xl:gap-12">
        
        {/* 指标 1: 缺额流速 */}
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
            <QuotaTrendChart />
            <div className="text-[8px] text-slate-400 font-mono tracking-widest uppercase mt-2">全网调剂新增趋势</div>
          </div>
        </div>

        {/* 指标 2: 质量画像 */}
        <div className="flex w-full flex-1 min-w-0 items-end gap-6">
          <div>
            <div className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1.5">QUALITY TIER</div>
            <div className="flex items-baseline gap-1.5">
              <span className="text-base font-black text-slate-900">{qualityTierRate}%</span>
              <span className="text-[10px] font-bold text-slate-400">来自 985/211</span>
            </div>
          </div>
          <div className="flex-1 pb-1">
            <TierDistributionChart />
            <div className="mt-2 flex w-full max-w-[260px] justify-between text-[8px] font-mono uppercase text-slate-400 xl:max-w-[320px]">
              <span>985</span><span>211</span><span>D1L</span><span>ORD</span>
            </div>
          </div>
        </div>

        {/* 指标 3: 个人雷达匹配 */}
        <div 
          className="hidden flex-col items-start gap-1.5 rounded-xl border border-orange-200/50 bg-orange-50/60 px-5 py-3 shadow-sm backdrop-blur-sm transition-colors group cursor-pointer hover:bg-orange-100/60 xl:flex xl:min-w-[220px] xl:flex-none"
          onClick={() => addToast({msg:'拦截成功：12 条调剂动态与你的目标高度重合', type:'warning'})}
        >
           <div className="flex items-center gap-2">
             <div className="w-1.5 h-1.5 bg-orange-500 rounded-full animate-pulse"></div>
             <span className="text-[10px] font-bold text-orange-600 uppercase tracking-widest">RADAR MATCH</span>
           </div>
           <div className="flex items-end gap-2 mt-0.5">
              <span className="text-xl font-bold font-mono text-orange-500 leading-none">{adjustments?.length || 0}</span>
              <span className="text-[10px] text-slate-500 mb-0.5 group-hover:text-orange-600 transition-colors">条高优情报命中</span>
           </div>
        </div>
      </div>

      {/* === 核心内容双栏 === */}
      <div className="grid w-full grid-cols-1 gap-12 lg:grid-cols-2 lg:gap-10 xl:gap-12">
        
        {/* 左栏：公告流 */}
        <div className={`space-y-4 transition-opacity duration-300 ${searchMode === '调剂' && searchKw ? 'opacity-40 grayscale pointer-events-none' : 'opacity-100'}`}>
          <div className="flex items-center justify-between mb-4 pb-2 border-b border-slate-100">
            <h2 className="text-xs font-black text-slate-400 uppercase tracking-widest flex items-center gap-2">
              <FileText size={14} className="text-cyan-500"/> 全网公告流 {searchMode === '公告' && searchKw && <span className="text-cyan-500">&quot;{searchKw}&quot;</span>}
            </h2>
            <button onClick={() => addToast({msg:'即将跳转至高级检索库', type:'info'})} className="text-xs font-bold text-cyan-600 hover:text-cyan-700 transition-colors flex items-center gap-1">
              高级检索 <ChevronRight size={12}/>
            </button>
          </div>
          
          <div className="space-y-3 min-h-[300px]">
            {loadingNotices ? (
              Array(3).fill(0).map((_, i) => <div key={i} className="p-5 rounded-2xl border border-slate-100 bg-white/50 animate-pulse h-32"></div>)
            ) : notices && notices.length > 0 ? notices.map((item: AnnouncementFeedItem) => (
              <motion.div 
                key={item.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
                className="group relative bg-white rounded-2xl p-5 border border-slate-200/50 hover:border-cyan-300 hover:shadow-[0_8px_30px_rgba(6,182,212,0.08)] transition-all cursor-pointer"
                onClick={() => addToast({msg: `已打开快照: ${item.title}`, type: 'success'})}
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
            )) : (
              <div className="py-10 text-center text-slate-400 text-sm font-mono border-2 border-dashed border-slate-100 rounded-2xl">
                No records found for &quot;{searchKw}&quot;
              </div>
            )}
          </div>
        </div>

        {/* 右栏：调剂雷达 */}
        <div className={`space-y-4 transition-opacity duration-300 ${searchMode === '公告' && searchKw ? 'opacity-40 grayscale pointer-events-none' : 'opacity-100'}`}>
          <div className="flex items-center justify-between mb-4 pb-2 border-b border-slate-100">
            <h2 className="text-xs font-black text-slate-400 uppercase tracking-widest flex items-center gap-2">
              <Activity size={14} className="text-orange-500"/> 调剂异动雷达 {searchMode === '调剂' && searchKw && <span className="text-orange-500">&quot;{searchKw}&quot;</span>}
            </h2>
            <div className="flex items-center gap-2 cursor-help" onClick={() => addToast({msg:'SSE 长连接监听中', type:'info'})}>
              <span className="w-1.5 h-1.5 bg-orange-500 rounded-full animate-pulse shadow-[0_0_6px_rgba(249,115,22,0.6)]"></span>
              <span className="text-[10px] font-bold text-orange-500 uppercase tracking-wider">Live Sync</span>
            </div>
          </div>

          <div className="space-y-3 min-h-[300px]">
            {loadingAdjustments ? (
              Array(3).fill(0).map((_, i) => <div key={i} className="p-5 rounded-2xl border border-slate-100 bg-white/50 animate-pulse h-32"></div>)
            ) : adjustments && adjustments.length > 0 ? adjustments.map((item: AdjustmentFeedItem) => (
              <motion.div 
                key={item.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
                className={`group relative bg-white rounded-2xl p-5 border transition-all cursor-pointer flex items-center justify-between 
                  ${item.urgent ? 'border-orange-200/60 hover:border-orange-400 hover:shadow-[0_8px_30px_rgba(249,115,22,0.08)]' : 'border-slate-200/50 hover:border-cyan-300 hover:shadow-[0_8px_30px_rgba(6,182,212,0.08)]'}
                `}
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
                    {item.tags.map((tag: string, i: number) => (
                      <span key={i} className="px-1.5 py-0.5 bg-slate-50 text-slate-500 text-[10px] rounded border border-slate-100">{tag}</span>
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
                    <button onClick={(e) => { e.stopPropagation(); addToast({msg: `已将 [${item.school}] 加入工作台雷达`, type: 'success'}); }} className="p-1 text-slate-300 hover:text-yellow-400 transition-colors"><Star size={14}/></button>
                    {item.urgent && <span className="text-[9px] font-bold text-orange-600 bg-orange-50 px-1.5 py-0.5 rounded-sm uppercase tracking-wider">Urgent</span>}
                  </div>
                </div>
              </motion.div>
            )) : (
              <div className="py-10 text-center text-slate-400 text-sm font-mono border-2 border-dashed border-slate-100 rounded-2xl">
                No adjustments found for &quot;{searchKw}&quot;
              </div>
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
      addToast({ msg: '璇峰厛杈撳叆璐﹀彿涓庡瘑鐮?', type: 'warning' });
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
      addToast({ msg: mode === 'login' ? '绯荤粺鎺堟潈鎴愬姛锛屾杩庡洖鏉?' : '妗ｆ宸叉縺娲伙紝宸插畬鎴愭帴鍏?', type: 'success' });
      setRegisterUsername('');
      setLoginName('');
      setPassword('');
      return;
    } catch (error) {
      addToast({ msg: error instanceof Error ? error.message : '鎺堟潈澶辫触锛岃绋嶅悗閲嶈瘯', type: 'warning' });
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
              {mode === 'register' && <input value={registerUsername} onChange={(e) => setRegisterUsername(e.target.value)} type="text" placeholder="骞插憳浠ｅ彿 (Username)" required className="w-full bg-slate-50 border border-slate-200 rounded-xl py-3 px-4 text-sm text-slate-900 outline-none focus:border-cyan-500 focus:bg-white transition-colors" />}
              <input value={loginName} onChange={(e) => setLoginName(e.target.value)} type="text" placeholder="name@example.com" required className="w-full bg-slate-50 border border-slate-200 rounded-xl py-3 px-4 text-sm text-slate-900 outline-none focus:border-cyan-500 focus:bg-white transition-colors" />
              <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" placeholder="********" required className="w-full bg-slate-50 border border-slate-200 rounded-xl py-3 px-4 text-sm text-slate-900 outline-none focus:border-cyan-500 focus:bg-white transition-colors" />
              
              <button type="submit" disabled={submitting} className="w-full bg-slate-900 text-white font-bold rounded-xl py-3.5 mt-2 hover:bg-slate-800 transition-all active:scale-[0.98] text-sm shadow-md flex items-center justify-center gap-2 disabled:opacity-70">
                {submitting ? '澶勭悊涓?...' : mode === 'login' ? '鎺堟潈鐧诲綍' : '婵€娲绘。妗?'} <CheckCircle2 size={16}/>
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
  const [globalSearchKw, setGlobalSearchKw] = useState('');
  const [globalSearchMode, setGlobalSearchMode] = useState('公告');
  const { addToast, setUser } = useAppStore();
  const portalAuth = usePortalStore((state) => state.portalAuth);
  const clearPortalAuth = usePortalStore((state) => state.clearPortalAuth);

  useEffect(() => {
    setUser(mapPortalUser(portalAuth));
  }, [portalAuth, setUser]);

  useEffect(() => {
    const accessToken = portalAuth?.accessToken;
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
  }, [addToast, clearPortalAuth, portalAuth?.accessToken]);

  return (
    <QueryClientProvider client={queryClient}>
      <div className="min-h-screen bg-[#fcfcfc] text-slate-900 font-sans selection:bg-cyan-100 selection:text-cyan-900 relative">
        <GlobalBackground />
        <Header onGlobalSearch={(kw, mode) => { setGlobalSearchKw(kw); setGlobalSearchMode(mode); }} />
        
        <main className="relative z-10">
           <DashboardHome searchKw={globalSearchKw} searchMode={globalSearchMode} />
        </main>

        <AuthModal />
        <ToastContainer />
      </div>
    </QueryClientProvider>
  );
}
