"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import {
  ApiError,
  getCurrentUserAccountOverview,
  getCurrentUserNotificationHistory,
  logoutUser,
  type UserAccountOverviewResponse,
  type UserNotificationHistoryItem,
} from "@/lib/api";
import { useMonitorTargetsQuery } from "@/hooks/useMonitoringTargets";
import { useWatchlistNoticesQuery } from "@/hooks/useNotifications";
import { useSubscriptionsQuery } from "@/hooks/useSubscriptions";
import { useAppStore } from "@/lib/store";
import { AccountActivityTab } from "./AccountActivityTab";
import { AccountFollowingTab } from "./AccountFollowingTab";
import { AccountRadarTab } from "./AccountRadarTab";
import { AccountSpaceHero } from "./AccountSpaceHero";
import { AccountSpaceSidebar } from "./AccountSpaceSidebar";
import { AccountSpaceTabs } from "./AccountSpaceTabs";
import {
  buildAccountActivityItems,
  buildAccountSpaceSummary,
} from "./account-space-data";
import {
  parseAccountSpacePanel,
  parseAccountSpaceTab,
  type AccountSpacePanel,
  type AccountSpaceTab,
} from "./account-space-query";

const ACCOUNT_PANEL_COPY: Record<Exclude<AccountSpacePanel, null>, string> = {
  billing: "旧的会员入口会收敛到新的会员与订单区块里。",
  security: "旧的安全入口会收敛到新的密码、绑定和会话区块里。",
  notifications: "旧的通知入口会收敛到动态流里的通知视图。",
};

function AccountTabPlaceholder({
  panel,
  membershipLabel,
  loggedIn,
}: {
  panel: AccountSpacePanel;
  membershipLabel: string;
  loggedIn: boolean;
}) {
  return (
    <section className="space-y-4">
      <div className="rounded-[2rem] border border-white/80 bg-white/90 p-6 shadow-[0_20px_60px_rgba(122,147,192,0.16)]">
        <div className="text-xs uppercase tracking-[0.24em] text-sky-500">Account</div>
        <h2 className="mt-3 text-2xl font-bold text-slate-900">账号相关操作下一步会集中到这里</h2>
        <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-600">
          会员、微信绑定、密码修改和退出登录都会继续保留，只是从旧的 dashboard 形态收敛成空间页里的二级区块。
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <span className="rounded-full bg-pink-50 px-4 py-2 text-sm font-semibold text-pink-600">{membershipLabel}</span>
          {loggedIn ? (
            <Link
              href="/account?tab=account&panel=billing"
              className="rounded-full border border-slate-200 bg-slate-50 px-4 py-2 text-sm font-semibold text-slate-700"
            >
              先看会员入口
            </Link>
          ) : (
            <Link
              href="/login"
              className="rounded-full border border-slate-200 bg-slate-50 px-4 py-2 text-sm font-semibold text-slate-700"
            >
              先登录
            </Link>
          )}
        </div>
      </div>

      {panel ? (
        <div className="rounded-[1.8rem] border border-pink-100 bg-pink-50/90 px-5 py-4 text-sm leading-7 text-pink-700 shadow-[0_16px_36px_rgba(255,151,201,0.16)]">
          当前面板：<span className="font-semibold">{panel}</span>。{ACCOUNT_PANEL_COPY[panel]}
        </div>
      ) : null}
    </section>
  );
}

export default function AccountSpacePage({
  initialTab = "activity",
  initialPanel = null,
}: {
  initialTab?: AccountSpaceTab;
  initialPanel?: AccountSpacePanel;
}) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { portalAuth, clearPortalAuth } = useAppStore();
  const [accountOverview, setAccountOverview] = useState<UserAccountOverviewResponse | null>(null);
  const [notificationHistory, setNotificationHistory] = useState<UserNotificationHistoryItem[]>([]);
  const [activityLoading, setActivityLoading] = useState(false);

  const currentTab = parseAccountSpaceTab(searchParams.get("tab") || initialTab);
  const currentPanel = parseAccountSpacePanel(searchParams.get("panel") || initialPanel || undefined);
  const canManageScopeTargets = Boolean(portalAuth?.isPremium || portalAuth?.isAdmin);

  const subscriptionsQuery = useSubscriptionsQuery(Boolean(portalAuth));
  const monitorTargetsQuery = useMonitorTargetsQuery(Boolean(portalAuth && canManageScopeTargets));
  const noticesQuery = useWatchlistNoticesQuery(Boolean(portalAuth));

  useEffect(() => {
    if (!portalAuth?.accessToken) {
      setAccountOverview(null);
      setNotificationHistory([]);
      setActivityLoading(false);
      return;
    }

    let cancelled = false;
    setActivityLoading(true);

    Promise.allSettled([
      getCurrentUserAccountOverview(portalAuth.accessToken),
      getCurrentUserNotificationHistory(portalAuth.accessToken, 12),
    ])
      .then((results) => {
        if (cancelled) {
          return;
        }

        const [overviewResult, historyResult] = results;
        setAccountOverview(overviewResult.status === "fulfilled" ? overviewResult.value : null);
        setNotificationHistory(historyResult.status === "fulfilled" ? historyResult.value.items : []);
      })
      .finally(() => {
        if (!cancelled) {
          setActivityLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [portalAuth?.accessToken]);

  async function handleLogout() {
    try {
      await logoutUser();
    } catch (error) {
      if (!(error instanceof ApiError)) {
        throw error;
      }
    } finally {
      clearPortalAuth();
      router.push("/login");
    }
  }

  const subscriptions = subscriptionsQuery.data?.items || [];
  const monitorTargets = monitorTargetsQuery.data?.items || [];
  const pendingNotices = noticesQuery.data || [];
  const activityItems = buildAccountActivityItems({
    history: notificationHistory,
    pending: pendingNotices,
    monitorTargets,
  });
  const spaceSummary = buildAccountSpaceSummary({
    displayName: portalAuth?.nickname || portalAuth?.username || "我的空间",
    username: portalAuth?.username || "guest",
    overview: accountOverview,
    subscriptions,
    monitorTargets,
    activityCount: activityItems.length,
    isLoggedIn: Boolean(portalAuth),
    isAdmin: Boolean(portalAuth?.isAdmin),
    isPremium: Boolean(portalAuth?.isPremium),
  });

  const stats = [
    { label: "关注", value: String(spaceSummary.followCount), tone: "pink" as const },
    { label: "雷达", value: String(spaceSummary.radarCount), tone: "blue" as const },
    { label: "动态", value: String(spaceSummary.recentActivityCount), tone: "slate" as const },
  ];

  const followingLoading = Boolean(portalAuth) && subscriptionsQuery.isLoading;
  const radarLoading = Boolean(portalAuth) && canManageScopeTargets && monitorTargetsQuery.isLoading;

  let content: ReactNode;
  if (currentTab === "following") {
    content = (
      <AccountFollowingTab
        loggedIn={Boolean(portalAuth)}
        loading={followingLoading}
        subscriptions={subscriptions}
        monitorTargets={monitorTargets}
        canManageScopeTargets={canManageScopeTargets}
      />
    );
  } else if (currentTab === "radar") {
    content = (
      <AccountRadarTab
        loggedIn={Boolean(portalAuth)}
        loading={radarLoading}
        canManageScopeTargets={canManageScopeTargets}
        targets={monitorTargets}
        overview={monitorTargetsQuery.data?.recent_signal_overview || null}
      />
    );
  } else if (currentTab === "account") {
    content = (
      <AccountTabPlaceholder
        panel={currentPanel}
        membershipLabel={spaceSummary.membershipLabel}
        loggedIn={Boolean(portalAuth)}
      />
    );
  } else {
    content = (
      <AccountActivityTab
        items={activityItems}
        loggedIn={Boolean(portalAuth)}
        loading={activityLoading || noticesQuery.isLoading}
        panel={currentPanel}
      />
    );
  }

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,#f6f8fd_0%,#eef4ff_42%,#fbfdff_100%)] text-slate-900">
      <div className="mx-auto max-w-7xl px-4 pb-20 pt-8 md:px-6">
        <AccountSpaceHero
          displayName={spaceSummary.displayName}
          username={spaceSummary.username}
          membershipLabel={spaceSummary.membershipLabel}
          signature={spaceSummary.signature}
          stats={stats}
        />

        <AccountSpaceTabs activeTab={currentTab} activePanel={currentPanel} />

        <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
          <main className="min-w-0">{content}</main>

          <aside className="min-w-0">
            <AccountSpaceSidebar
              membershipLabel={spaceSummary.membershipLabel}
              wechatBound={spaceSummary.wechatBound}
              securityHint={spaceSummary.securityHint}
              onLogout={handleLogout}
              loggedIn={Boolean(portalAuth)}
            />
          </aside>
        </div>
      </div>
    </div>
  );
}
