import Link from "next/link";
import { ExternalLink, Radar, ShieldCheck, Sparkles, Zap } from "lucide-react";
import type { MonitorTargetItem, MonitorTargetRecentSignalOverview } from "@/lib/api";
import { formatAccountSpaceDate, monitorCardTitle } from "./account-space-data";
import { AccountEmptyState, AccountSkeletonGrid, AccountSurface } from "./AccountSpaceUi";

function MetricCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: string | number;
  tone: "blue" | "pink" | "slate";
}) {
  return (
    <AccountSurface
      interactive
      className={`rounded-[2rem] border p-5 shadow-[0_18px_44px_rgba(122,147,192,0.14)] ${
        tone === "pink"
          ? "border-pink-100 bg-pink-50/80"
          : tone === "blue"
            ? "border-sky-100 bg-sky-50/80"
            : "border-white/80 bg-white/90"
      }`}
    >
      <div className="text-xs uppercase tracking-[0.2em] text-slate-400">{label}</div>
      <div className="mt-3 text-3xl font-black text-slate-900">{value}</div>
    </AccountSurface>
  );
}

export function AccountRadarTab({
  loggedIn,
  loading,
  canManageScopeTargets,
  targets,
  overview,
}: {
  loggedIn: boolean;
  loading: boolean;
  canManageScopeTargets: boolean;
  targets: MonitorTargetItem[];
  overview: MonitorTargetRecentSignalOverview | null;
}) {
  if (!loggedIn) {
    return (
      <AccountEmptyState
        eyebrow="Radar"
        title="登录后，雷达页会告诉你最近哪几个范围最活跃"
        description="真正的雷达不是一个设置面板，而是一张信号看板。先登录，之后学校、院系和栏目级命中会在这里压缩成几张清晰的卡。"
        actions={
          <Link href="/login" className="rounded-full bg-[linear-gradient(90deg,#ff7fb7,#68d2ff)] px-5 py-3 text-sm font-semibold text-white">
            去登录
          </Link>
        }
      />
    );
  }

  if (loading) {
    return (
      <AccountSkeletonGrid count={4} className="grid gap-4 md:grid-cols-2 xl:grid-cols-4" itemClassName="h-40" />
    );
  }

  if (!canManageScopeTargets) {
    return (
      <AccountEmptyState
        eyebrow="会员能力"
        title="学校、院系和栏目级雷达会放在这里"
        description="当前账号仍然可以先用普通订阅铺出动态流；开通高级会员后，这一页会开始展示活跃范围、近窗命中和重点栏目变化。"
        actions={
          <>
          <span className="inline-flex items-center gap-2 rounded-full bg-pink-50 px-3 py-1 text-xs font-semibold text-pink-600">
          <ShieldCheck size={14} />
          会员能力
          </span>
          <Link
            href="/account?tab=account&panel=billing"
            className="rounded-full bg-[linear-gradient(90deg,#ff7fb7,#68d2ff)] px-5 py-3 text-sm font-semibold text-white"
          >
            去看会员方案
          </Link>
          <Link href="/watchlist" className="rounded-full border border-slate-200 bg-slate-50 px-5 py-3 text-sm font-semibold text-slate-700">
            先看工作台
          </Link>
          </>
        }
      />
    );
  }

  const activeTargets = targets.filter((item) => item.recent_signal?.has_recent_announcements);

  return (
    <section className="space-y-6">
      <div className="grid gap-4 md:grid-cols-4">
        <MetricCard label="已追踪范围" value={overview?.tracked_target_count || targets.length} tone="blue" />
        <MetricCard label="活跃范围" value={overview?.active_target_count || activeTargets.length} tone="pink" />
        <MetricCard label="近窗动态" value={overview?.total_recent_announcements || 0} tone="slate" />
        <MetricCard label="研招相关" value={overview?.total_recruitment_announcements || 0} tone="blue" />
      </div>

      {overview?.latest_announcement ? (
        <AccountSurface className="border-sky-100 bg-white/90 p-6">
          <div className="inline-flex items-center gap-2 rounded-full bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-600">
            <Zap size={14} />
            最新全局命中
          </div>
          <h3 className="mt-4 text-xl font-bold leading-8 text-slate-900">{overview.latest_announcement.title}</h3>
          <p className="mt-2 text-sm leading-7 text-slate-600">
            {[overview.latest_announcement.school_name, overview.latest_announcement.department_name, overview.latest_announcement.site_section_name]
              .filter(Boolean)
              .join(" · ")}
          </p>
          <div className="mt-4 text-xs tracking-[0.14em] text-slate-400">
            {formatAccountSpaceDate(overview.latest_announcement.published_at) || "发布时间未知"}
          </div>
        </AccountSurface>
      ) : null}

      {activeTargets.length === 0 ? (
        <AccountEmptyState
          eyebrow="Quiet Window"
          title="最近窗口里还没有明显活跃的雷达范围"
          description="这不代表雷达没工作，只是这几天命中比较安静。你可以继续去工作台补新范围，或者等下一次集中更新。"
          actions={
            <span className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
              <Sparkles size={14} />
              Quiet Window
            </span>
          }
        />
      ) : (
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs uppercase tracking-[0.24em] text-sky-500">Active Targets</div>
              <h3 className="mt-2 text-xl font-bold text-slate-900">最近有信号的范围</h3>
            </div>
            <Link href="/watchlist" className="rounded-full border border-slate-200 bg-slate-50 px-4 py-2 text-sm font-semibold text-slate-700">
              去工作台管理
            </Link>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            {activeTargets.map((item) => {
              const latest = item.recent_signal?.latest_announcement;
              return (
                <AccountSurface
                  key={item.id}
                  interactive
                  className="p-5 shadow-[0_18px_44px_rgba(122,147,192,0.14)]"
                >
                  <div className="inline-flex items-center gap-2 rounded-full bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-600">
                    <Radar size={14} />
                    {item.scope_type === "school" ? "学校雷达" : item.scope_type === "department" ? "院系雷达" : "栏目雷达"}
                  </div>
                  <h4 className="mt-4 text-lg font-bold leading-7 text-slate-900">{monitorCardTitle(item)}</h4>

                  <div className="mt-4 grid grid-cols-2 gap-3">
                    <div className="rounded-[1.4rem] border border-sky-100 bg-sky-50/80 px-4 py-3">
                      <div className="text-xs uppercase tracking-[0.18em] text-slate-400">近窗动态</div>
                      <div className="mt-2 text-2xl font-black text-slate-900">{item.recent_signal?.recent_announcement_count || 0}</div>
                    </div>
                    <div className="rounded-[1.4rem] border border-pink-100 bg-pink-50/80 px-4 py-3">
                      <div className="text-xs uppercase tracking-[0.18em] text-slate-400">研招相关</div>
                      <div className="mt-2 text-2xl font-black text-slate-900">{item.recent_signal?.recruitment_announcement_count || 0}</div>
                    </div>
                  </div>

                  {latest ? (
                    <div className="mt-4 rounded-[1.4rem] border border-slate-100 bg-slate-50/80 px-4 py-4">
                      <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Latest Hit</div>
                      <div className="mt-2 text-sm font-semibold leading-7 text-slate-900">{latest.title}</div>
                      <div className="mt-2 text-xs tracking-[0.14em] text-slate-400">
                        {formatAccountSpaceDate(latest.published_at) || "发布时间未知"}
                      </div>
                      {latest.source_url ? (
                        <a
                          href={latest.source_url}
                          target="_blank"
                          rel="noreferrer"
                          className="mt-4 inline-flex items-center gap-2 rounded-full border border-pink-100 bg-pink-50 px-4 py-2 text-sm font-semibold text-pink-700"
                        >
                          查看源站
                          <ExternalLink size={14} />
                        </a>
                      ) : null}
                    </div>
                  ) : null}
                </AccountSurface>
              );
            })}
          </div>
        </section>
      )}
    </section>
  );
}
