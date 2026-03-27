import Link from "next/link";
import { BellRing, Compass, Radar, Sparkles } from "lucide-react";
import type { MonitorTargetItem, SubscriptionItem } from "@/lib/api";
import {
  formatAccountSpaceDate,
  monitorCardDetail,
  monitorCardTitle,
  monitorScopeTypeLabel,
  subscriptionCardDetail,
  subscriptionCardTitle,
  subscriptionTypeLabel,
} from "./account-space-data";
import { AccountEmptyState, AccountSkeletonGrid, AccountSurface } from "./AccountSpaceUi";

function SubscriptionWall({ subscriptions }: { subscriptions: SubscriptionItem[] }) {
  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.24em] text-pink-500">Following</div>
          <h3 className="mt-2 text-xl font-bold text-slate-900">我的订阅</h3>
        </div>
        <div className="rounded-full bg-pink-50 px-3 py-1 text-sm font-semibold text-pink-600">{subscriptions.length} 项</div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {subscriptions.map((item) => (
          <AccountSurface
            key={item.id}
            interactive
            className="p-5 shadow-[0_18px_44px_rgba(122,147,192,0.14)]"
          >
            <div className="inline-flex items-center gap-2 rounded-full bg-pink-50 px-3 py-1 text-xs font-semibold text-pink-600">
              <BellRing size={14} />
              {subscriptionTypeLabel(item.subscription_type)}
            </div>
            <h4 className="mt-4 text-lg font-bold leading-7 text-slate-900">{subscriptionCardTitle(item)}</h4>
            <p className="mt-2 text-sm leading-7 text-slate-600">{subscriptionCardDetail(item) || "这是一条已经归档进空间的关注项。"}</p>
            <div className="mt-4 text-xs tracking-[0.14em] text-slate-400">
              创建于 {formatAccountSpaceDate(item.created_at) || "时间未知"}
            </div>
          </AccountSurface>
        ))}
      </div>
    </section>
  );
}

function RadarWall({ targets }: { targets: MonitorTargetItem[] }) {
  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.24em] text-sky-500">Radar</div>
          <h3 className="mt-2 text-xl font-bold text-slate-900">我的雷达范围</h3>
        </div>
        <div className="rounded-full bg-sky-50 px-3 py-1 text-sm font-semibold text-sky-600">{targets.length} 项</div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {targets.map((item) => (
          <AccountSurface
            key={item.id}
            interactive
            className="p-5 shadow-[0_18px_44px_rgba(122,147,192,0.14)]"
          >
            <div className="inline-flex items-center gap-2 rounded-full bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-600">
              <Radar size={14} />
              {monitorScopeTypeLabel(item.scope_type)}
            </div>
            <h4 className="mt-4 text-lg font-bold leading-7 text-slate-900">{monitorCardTitle(item)}</h4>
            <p className="mt-2 text-sm leading-7 text-slate-600">{monitorCardDetail(item) || "这条雷达范围已经加入个人空间。"} </p>
            {item.recent_signal?.has_recent_announcements ? (
              <div className="mt-4 rounded-[1.4rem] border border-sky-100 bg-sky-50/80 px-4 py-3 text-sm leading-7 text-sky-700">
                近 {item.recent_signal.window_days} 天捕获 {item.recent_signal.recent_announcement_count} 条动态，
                其中 {item.recent_signal.recruitment_announcement_count} 条与研招直接相关。
              </div>
            ) : null}
          </AccountSurface>
        ))}
      </div>
    </section>
  );
}

export function AccountFollowingTab({
  loggedIn,
  loading,
  subscriptions,
  monitorTargets,
  canManageScopeTargets,
}: {
  loggedIn: boolean;
  loading: boolean;
  subscriptions: SubscriptionItem[];
  monitorTargets: MonitorTargetItem[];
  canManageScopeTargets: boolean;
}) {
  if (!loggedIn) {
    return (
      <AccountEmptyState
        eyebrow="Following"
        title="先登录，再把你想盯的学校和雷达装进这里"
        description="订阅墙会展示你显式保存的学校、专业和关键词；雷达墙会展示你设置过的学校、院系和栏目级盯盘范围。"
        actions={
          <>
          <Link href="/login" className="rounded-full bg-[linear-gradient(90deg,#ff7fb7,#68d2ff)] px-5 py-3 text-sm font-semibold text-white">
            去登录
          </Link>
          <Link href="/search" className="rounded-full border border-slate-200 bg-slate-50 px-5 py-3 text-sm font-semibold text-slate-700">
            先看看搜索页
          </Link>
          </>
        }
      />
    );
  }

  if (loading) {
    return (
      <AccountSkeletonGrid count={4} className="grid gap-4 md:grid-cols-2" itemClassName="h-48" />
    );
  }

  if (subscriptions.length === 0 && monitorTargets.length === 0) {
    return (
      <AccountEmptyState
        eyebrow="Following"
        title="你的关注墙还是空的"
        description="先加几条院校、专业、关键词订阅，再决定要不要把学校、院系或栏目级雷达也拉进来。"
        actions={
          <>
          <Link href="/search" className="rounded-full border border-sky-100 bg-sky-50 px-5 py-3 text-sm font-semibold text-sky-700">
            去搜索页加关注
          </Link>
          <Link href="/watchlist" className="rounded-full border border-slate-200 bg-slate-50 px-5 py-3 text-sm font-semibold text-slate-700">
            去工作台补雷达
          </Link>
          </>
        }
      />
    );
  }

  return (
    <section className="space-y-6">
      <div className="grid gap-4 md:grid-cols-3">
        <AccountSurface interactive className="p-5 shadow-[0_18px_44px_rgba(122,147,192,0.14)]">
          <div className="inline-flex items-center gap-2 rounded-full bg-pink-50 px-3 py-1 text-xs font-semibold text-pink-600">
            <Compass size={14} />
            已归档订阅
          </div>
          <div className="mt-4 text-3xl font-black text-slate-900">{subscriptions.length}</div>
          <p className="mt-2 text-sm leading-7 text-slate-600">这里放学校、专业、关键词和地区级的显式关注。</p>
        </AccountSurface>

        <AccountSurface interactive className="p-5 shadow-[0_18px_44px_rgba(122,147,192,0.14)]">
          <div className="inline-flex items-center gap-2 rounded-full bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-600">
            <Radar size={14} />
            雷达范围
          </div>
          <div className="mt-4 text-3xl font-black text-slate-900">{monitorTargets.length}</div>
          <p className="mt-2 text-sm leading-7 text-slate-600">学校、院系和栏目级盯盘会集中在这一块。</p>
        </AccountSurface>

        <AccountSurface interactive className="p-5 shadow-[0_18px_44px_rgba(122,147,192,0.14)]">
          <div className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
            <Sparkles size={14} />
            下一步
          </div>
          <div className="mt-4 text-lg font-bold text-slate-900">
            {canManageScopeTargets ? "继续补雷达范围" : "先把订阅墙铺起来"}
          </div>
          <p className="mt-2 text-sm leading-7 text-slate-600">
            {canManageScopeTargets
              ? "你已经可以直接去工作台继续加学校、院系和栏目级雷达。"
              : "学校、院系和栏目级雷达属于会员能力，但普通订阅已经能先把动态流喂起来。"}
          </p>
        </AccountSurface>
      </div>

      {subscriptions.length > 0 ? <SubscriptionWall subscriptions={subscriptions} /> : null}
      {monitorTargets.length > 0 ? <RadarWall targets={monitorTargets} /> : null}
    </section>
  );
}
