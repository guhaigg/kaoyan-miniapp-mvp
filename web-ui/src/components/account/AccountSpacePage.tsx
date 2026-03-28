"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
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
import { AccountAccountTab } from "./AccountAccountTab";
import { AccountActivityTab } from "./AccountActivityTab";
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
    { label: "关注库", value: String(spaceSummary.followCount), tone: "blue" as const },
    { label: "雷达范围", value: String(spaceSummary.radarCount), tone: "pink" as const },
    { label: "通知流", value: String(spaceSummary.recentActivityCount), tone: "slate" as const },
    {
      label: "会员状态",
      value: portalAuth?.isPremium || portalAuth?.isAdmin ? "已开通" : "普通",
      tone: "blue" as const,
    },
  ];

  let content: ReactNode;
  if (currentTab === "account") {
    content = (
      <AccountAccountTab
        accessToken={portalAuth?.accessToken || null}
        panel={currentPanel}
        membershipLabel={spaceSummary.membershipLabel}
        loggedIn={Boolean(portalAuth)}
        premiumExpiresAt={accountOverview?.premium_expires_at || portalAuth?.premiumExpiresAt || null}
        wechatBound={spaceSummary.wechatBound}
        onLoggedOut={handleLogout}
      />
    );
  } else if (currentTab === "notifications") {
    content = (
      <AccountActivityTab
        items={activityItems}
        loggedIn={Boolean(portalAuth)}
        loading={activityLoading || noticesQuery.isLoading}
        panel="notifications"
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
    <div className="pb-16 text-slate-900 md:pb-20">
      <AccountSpaceHero
        displayName={spaceSummary.displayName}
        username={spaceSummary.username}
        membershipLabel={spaceSummary.membershipLabel}
        signature={spaceSummary.signature}
        stats={stats}
      />

      <AccountSpaceTabs activeTab={currentTab} activePanel={currentPanel} />

      <div className="mx-auto grid max-w-[1440px] gap-4 px-4 py-4 md:gap-6 md:px-6 md:py-6 xl:grid-cols-[minmax(0,1fr)_320px]">
        <main className="min-w-0">
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={`${currentTab}-${currentPanel || "base"}`}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.18, ease: "easeOut" }}
            >
              {content}
            </motion.div>
          </AnimatePresence>
        </main>

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
  );
}
