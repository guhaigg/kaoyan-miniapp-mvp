"use client";

import Link from "next/link";
import { useMemo, type ReactNode } from "react";
import { motion } from "framer-motion";
import { ArrowUpRight } from "lucide-react";
import type { SearchItem } from "@/lib/api";
import { useHomeAdjustmentsQuery, useHomeAnnouncementsQuery } from "@/hooks/useSearch";
import { useAppStore } from "@/lib/store";

type NoticeCardData = {
  id: string;
  type: string;
  title: string;
  content: string;
  school: string;
  time: string;
  isNew: boolean;
  href: string;
  external: boolean;
};

type AdjustmentCardData = {
  id: string;
  school: string;
  title: string;
  tags: string[];
  major: string;
  count: number;
  urgent: boolean;
  href: string;
  external: boolean;
};

type BarSegment = {
  label: string;
  width: number;
  color: string;
};

const FALLBACK_NOTICES: NoticeCardData[] = [
  {
    id: "notice-fallback-1",
    type: "招生简章",
    title: "浙江大学计算机科学与技术学院 2026 年硕士招生简章发布",
    content:
      "经学院统筹，今年计划招收全日制学术学位硕士研究生 120 名。相较去年统考名额有所增加。复试科目包含机试及面试，请关注官网最新大纲及细则通知...",
    school: "浙江大学",
    time: "Just Now",
    isNew: true,
    href: "/search?tab=announcements",
    external: false,
  },
  {
    id: "notice-fallback-2",
    type: "复试名单",
    title: "复旦大学软件学院 2026 年复试名单及安排公告",
    content:
      "附件已自动解析。专硕复试线 345 分，学硕复试线 350 分。共计 180 人进入复试环节。机试时间定于本周六，请各位考生提前安排好行程并准备资格审查材料...",
    school: "复旦大学",
    time: "45 mins ago",
    isNew: false,
    href: "/search?tab=announcements",
    external: false,
  },
  {
    id: "notice-fallback-3",
    type: "成绩公布",
    title: "武汉理工大学关于 2026 年硕士研究生初试成绩查询的通知",
    content:
      "各位考生，我校 2026 年硕士研究生招生考试初试成绩将于今日下午 15:00 正式开通查询。如对成绩有异议，请在规定时间内提交复核申请...",
    school: "武汉理工大学",
    time: "2 hours ago",
    isNew: false,
    href: "/search?tab=announcements",
    external: false,
  },
];

const FALLBACK_ADJUSTMENTS: AdjustmentCardData[] = [
  {
    id: "adjustment-fallback-1",
    school: "哈尔滨工业大学",
    title: "人工智能研究院 接收调剂",
    tags: ["要求数一英一", "系统开放12小时"],
    major: "电子信息类",
    count: 3,
    urgent: true,
    href: "/search?tab=adjustments",
    external: false,
  },
  {
    id: "adjustment-fallback-2",
    school: "西安电子科技大学",
    title: "通信工程学院 统考扩招通知",
    tags: ["名额变更", "211工程"],
    major: "通信与信息系统",
    count: 15,
    urgent: false,
    href: "/search?tab=adjustments",
    external: false,
  },
  {
    id: "adjustment-fallback-3",
    school: "南京林业大学",
    title: "材料科学与工程学院 调剂意向征集",
    tags: ["双一流", "不限高数"],
    major: "材料与化工",
    count: 24,
    urgent: true,
    href: "/search?tab=adjustments",
    external: false,
  },
];

export default function SignalDashboardHome() {
  const { portalAuth } = useAppStore();

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

  const indexedCount = announcementsQuery.data?.total ?? 398;
  const sourceNodesCount = useMemo(() => {
    const values = Object.values(announcementsQuery.data?.source_breakdown ?? {});
    const total = values.reduce((sum, value) => sum + value, 0);
    return total || 842;
  }, [announcementsQuery.data?.source_breakdown]);

  const trendData = useMemo(() => {
    const base = Math.max(indexedCount, 180);
    const ratios = [0.2, 0.23, 0.21, 0.26, 0.3, 0.28, 0.36, 0.43, 0.4, 0.46, 0.5, 0.58, 0.54, 0.66, 0.74, 0.82, 0.78, 0.9, 1];
    return ratios.map((ratio) => Math.round(base * ratio));
  }, [indexedCount]);

  const barSegments = useMemo<BarSegment[]>(() => {
    const entries = Object.entries(announcementsQuery.data?.source_breakdown ?? {}).sort((left, right) => right[1] - left[1]);
    if (!entries.length) {
      return [
        { label: "公告", width: 70, color: "bg-cyan-400" },
        { label: "调剂", width: 30, color: "bg-slate-100" },
      ];
    }

    const total = entries.reduce((sum, [, value]) => sum + value, 0);
    const primaryWidth = clamp(Math.round((entries[0][1] / total) * 100), 38, 82);
    return [
      { label: entries[0][0], width: primaryWidth, color: "bg-cyan-400" },
      { label: entries[1]?.[0] ?? "其他", width: 100 - primaryWidth, color: "bg-slate-100" },
    ];
  }, [announcementsQuery.data?.source_breakdown]);

  const notices = useMemo(() => {
    if (!announcementsQuery.data?.items.length) {
      return FALLBACK_NOTICES;
    }
    return announcementsQuery.data.items.map((item) => mapNoticeCard(item));
  }, [announcementsQuery.data?.items]);

  const adjustments = useMemo(() => {
    if (!portalAuth || !adjustmentsQuery.data?.items.length) {
      return FALLBACK_ADJUSTMENTS;
    }
    return adjustmentsQuery.data.items.map((item) => mapAdjustmentCard(item));
  }, [adjustmentsQuery.data?.items, portalAuth]);

  return (
    <div className="relative z-10 mx-auto max-w-[1200px] px-6 pb-32 pt-28 text-slate-900">
      <section className="mb-24 flex flex-col items-start justify-center gap-12 px-0 sm:px-2 lg:flex-row lg:items-end lg:gap-24 lg:px-8">
        <div className="flex w-full max-w-[350px] flex-1 items-end gap-6">
          <div>
            <div className="mb-1.5 flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest text-slate-400">
              <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 shadow-[0_0_6px_rgba(6,182,212,0.6)]" />
              Live Data
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-4xl font-black tracking-tighter text-slate-900">{formatMetricNumber(indexedCount)}</span>
              <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Indexed</span>
            </div>
          </div>
          <div className="flex-1 pb-1">
            <MicroTrendChart data={trendData} />
          </div>
        </div>

        <div className="flex w-full max-w-[350px] flex-1 items-end gap-6">
          <div>
            <div className="mb-1.5 text-[10px] font-bold uppercase tracking-widest text-slate-400">Sources</div>
            <div className="flex items-baseline gap-1.5">
              <span className="text-base font-black text-slate-900">{formatMetricNumber(sourceNodesCount)}</span>
              <span className="text-[10px] font-bold text-slate-400">Nodes</span>
            </div>
          </div>
          <div className="flex-1 pb-1">
            <MicroBarChart segments={barSegments} />
          </div>
        </div>

        <div className="hidden items-center gap-2 rounded-lg border border-slate-200/60 bg-slate-50 px-3 py-1.5 xl:flex">
          <div className="h-1.5 w-1.5 animate-pulse rounded-full bg-green-500" />
          <span className="text-[9px] font-bold uppercase tracking-widest text-slate-500">System Online</span>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-12 lg:grid-cols-2 lg:gap-16">
        <div className="space-y-4">
          <div className="mb-4 flex items-center justify-between border-b border-slate-100 pb-2">
            <h2 className="text-xs font-black uppercase tracking-widest text-slate-400">Latest Notices</h2>
            <Link href="/search?tab=announcements" className="text-xs font-bold text-cyan-600 transition-colors hover:text-cyan-700">
              View All
            </Link>
          </div>

          <div className="space-y-3">
            {notices.map((item, index) => (
              <NoticeCard key={item.id} item={item} index={index} />
            ))}
          </div>
        </div>

        <div className="space-y-4">
          <div className="mb-4 flex items-center justify-between border-b border-slate-100 pb-2">
            <h2 className="text-xs font-black uppercase tracking-widest text-slate-400">Adjustment Radar</h2>
            <div className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-orange-500 shadow-[0_0_6px_rgba(249,115,22,0.6)]" />
              <span className="text-[10px] font-bold uppercase tracking-wider text-orange-500">Live Monitoring</span>
            </div>
          </div>

          <div className="space-y-3">
            {adjustments.map((item, index) => (
              <AdjustmentCard key={item.id} item={item} index={index} />
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}

function NoticeCard({ item, index }: { item: NoticeCardData; index: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.3, delay: index * 0.04 }}
    >
      <CardLink
        href={item.href}
        external={item.external}
        className="group relative block cursor-pointer overflow-hidden rounded-2xl border border-slate-200/50 bg-white p-5 transition-all hover:border-slate-300 hover:shadow-[0_8px_30px_rgba(0,0,0,0.04)]"
      >
        <div className="mb-3 flex items-center justify-between gap-4">
          <div className="flex min-w-0 items-center gap-2.5">
            {item.isNew ? <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-cyan-500" /> : null}
            <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-bold text-slate-600">{item.type}</span>
            <span className="truncate text-[11px] font-mono text-slate-400">{item.time}</span>
          </div>
          <span className="shrink-0 text-[11px] font-bold text-slate-400">{item.school}</span>
        </div>

        <h3 className="mb-2 pr-6 text-[15px] font-bold leading-snug text-slate-900 transition-colors group-hover:text-cyan-600">
          {item.title}
        </h3>
        <p className="line-clamp-2 text-[13px] leading-relaxed text-slate-500">{item.content}</p>

        <div className="absolute right-4 top-1/2 -translate-y-1/2 -translate-x-2 opacity-0 transition-all group-hover:translate-x-0 group-hover:opacity-100">
          <ArrowUpRight className="text-slate-300" size={20} />
        </div>
      </CardLink>
    </motion.div>
  );
}

function AdjustmentCard({ item, index }: { item: AdjustmentCardData; index: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.3, delay: index * 0.04 }}
    >
      <CardLink
        href={item.href}
        external={item.external}
        className={`group relative flex cursor-pointer items-center justify-between rounded-2xl border bg-white p-5 transition-all ${
          item.urgent
            ? "border-orange-200/60 hover:border-orange-300 hover:shadow-[0_8px_30px_rgba(249,115,22,0.06)]"
            : "border-slate-200/50 hover:border-slate-300 hover:shadow-[0_8px_30px_rgba(0,0,0,0.04)]"
        }`}
      >
        <div className="min-w-0 flex-1 pr-4">
          <div className="mb-1.5 flex items-center gap-2">
            <span className="truncate text-[11px] font-bold text-slate-500">{item.school}</span>
            <span className="text-[10px] text-slate-300">•</span>
            <span className="truncate text-[11px] text-slate-400">{item.major}</span>
          </div>
          <h3
            className={`mb-2 truncate text-[15px] font-bold transition-colors ${
              item.urgent ? "text-slate-900 group-hover:text-orange-600" : "text-slate-900 group-hover:text-cyan-600"
            }`}
          >
            {item.title}
          </h3>
          <div className="flex flex-wrap items-center gap-1.5">
            {item.tags.map((tag) => (
              <span key={tag} className="rounded border border-slate-100 bg-slate-50 px-1.5 py-0.5 text-[10px] text-slate-500">
                {tag}
              </span>
            ))}
          </div>
        </div>

        <div className="ml-4 flex shrink-0 flex-col items-end text-right">
          <div className="mb-1 flex items-baseline gap-1">
            <span className="text-xs font-bold text-slate-400">缺额</span>
            <span className={`font-mono text-2xl font-black leading-none ${item.urgent ? "text-orange-500" : "text-slate-900"}`}>
              {item.count}
            </span>
          </div>
          {item.urgent ? (
            <span className="rounded-sm bg-orange-50 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-orange-600">
              Urgent
            </span>
          ) : null}
        </div>
      </CardLink>
    </motion.div>
  );
}

function CardLink({
  href,
  external,
  className,
  children,
}: {
  href: string;
  external: boolean;
  className: string;
  children: ReactNode;
}) {
  if (external) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" className={className}>
        {children}
      </a>
    );
  }

  return (
    <Link href={href} className={className}>
      {children}
    </Link>
  );
}

function MicroTrendChart({ data }: { data: number[] }) {
  const max = Math.max(...data);
  const width = 180;
  const height = 40;
  const points = data
    .map((value, index) => `${(index / (data.length - 1)) * width},${height - (value / max) * height}`)
    .join(" L ");
  const fillPath = `M 0,${height} L ${points} L ${width},${height} Z`;

  return (
    <div className="relative h-[40px] w-[180px]">
      <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" className="h-full w-full overflow-visible">
        <defs>
          <linearGradient id="trendGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgba(6, 182, 212, 0.15)" />
            <stop offset="100%" stopColor="rgba(6, 182, 212, 0)" />
          </linearGradient>
        </defs>
        <motion.path d={fillPath} fill="url(#trendGradient)" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 1 }} />
        <motion.path
          d={`M ${points}`}
          fill="none"
          stroke="#06b6d4"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 1.4, ease: "easeInOut" }}
        />
      </svg>
    </div>
  );
}

function MicroBarChart({ segments }: { segments: BarSegment[] }) {
  return (
    <div className="flex w-[160px] flex-col gap-1.5">
      <div className="flex h-5 gap-1">
        {segments.map((segment, index) => (
          <motion.div
            key={`${segment.label}-${index}`}
            initial={{ width: 0 }}
            animate={{ width: `${segment.width}%` }}
            transition={{ duration: 0.8, delay: index * 0.2 }}
            className={`h-full rounded-sm ${segment.color}`}
          />
        ))}
      </div>
      <div className="text-[9px] font-mono uppercase tracking-widest text-slate-400">Crawler Distribution</div>
    </div>
  );
}

function mapNoticeCard(item: SearchItem): NoticeCardData {
  const timestamp = item.published_at || item.updated_at;
  return {
    id: item.id,
    type: (item.notice_kind || item.source_type || "招生简章").slice(0, 8),
    title: item.title,
    content: item.summary || item.school_intelligence?.signal_detail || "点击查看完整公告内容。",
    school: item.school_name || item.department_name || "目标院校",
    time: formatRelativeTime(timestamp),
    isNew: isFresh(timestamp),
    href: item.source_url || "/search?tab=announcements",
    external: Boolean(item.source_url),
  };
}

function mapAdjustmentCard(item: SearchItem): AdjustmentCardData {
  const tags = dedupe(
    [
      ...item.tags,
      ...item.system_tags,
      item.adjustment_year ? `${item.adjustment_year}调剂` : null,
      item.historical_adjustment?.sample_count ? `${item.historical_adjustment.sample_count}份样本` : null,
      item.school_tier,
    ].filter((value): value is string => Boolean(value && value.trim())),
  ).slice(0, 2);

  const count = item.adjustment_vacancy_count ?? item.historical_adjustment?.sample_count ?? 0;
  const urgent = count > 0 && count <= 5;

  return {
    id: item.id,
    school: item.school_name || "目标院校",
    title: item.title,
    tags: tags.length ? tags : ["调剂情报", "实时更新"],
    major: item.major || item.department_name || item.channel_label || "调剂信息",
    count,
    urgent,
    href: item.source_url || "/search?tab=adjustments",
    external: Boolean(item.source_url),
  };
}

function formatRelativeTime(input: string | null): string {
  if (!input) return "Just Now";
  const date = new Date(input);
  if (Number.isNaN(date.getTime())) return "Just Now";

  const diffMs = Date.now() - date.getTime();
  if (diffMs < 60 * 1000) return "Just Now";
  if (diffMs < 60 * 60 * 1000) return `${Math.floor(diffMs / (60 * 1000))} mins ago`;
  if (diffMs < 24 * 60 * 60 * 1000) return `${Math.floor(diffMs / (60 * 60 * 1000))} hours ago`;
  return `${Math.floor(diffMs / (24 * 60 * 60 * 1000))} days ago`;
}

function isFresh(input: string | null): boolean {
  if (!input) return true;
  const date = new Date(input);
  if (Number.isNaN(date.getTime())) return false;
  return Date.now() - date.getTime() < 90 * 60 * 1000;
}

function formatMetricNumber(value: number): string {
  return value.toLocaleString("en-US");
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

function dedupe(values: string[]): string[] {
  return Array.from(new Set(values));
}
