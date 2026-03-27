import type { MonitorTargetItem, NotificationEventItem, SubscriptionItem } from "@/lib/api";
import type { PortalAuthSession } from "@/lib/store";

export type BiliHeaderTier = "basic" | "premium" | "admin";
export type BiliHeaderCounterState = "ready" | "loading" | "unavailable" | "locked";

export interface BiliHeaderCounter {
  label: string;
  value: number | null;
  state: BiliHeaderCounterState;
}

export interface BiliHeaderSummary {
  displayName: string;
  levelLabel: string;
  tier: BiliHeaderTier;
  isPremium: boolean;
  counterState: BiliHeaderCounterState;
  counters: BiliHeaderCounter[];
}

type HeaderCounterInput<TItem> = {
  items: TItem[];
  state: BiliHeaderCounterState;
};

function buildTier(portalAuth: PortalAuthSession): BiliHeaderTier {
  if (portalAuth.isAdmin || portalAuth.role === "admin") {
    return "admin";
  }
  if (portalAuth.isPremium || portalAuth.role === "premium") {
    return "premium";
  }
  return "basic";
}

function buildLevelLabel(tier: BiliHeaderTier) {
  if (tier === "admin") {
    return "管理员";
  }
  if (tier === "premium") {
    return "高级会员";
  }
  return "普通账户";
}

function buildCounter<TItem>(label: string, source: HeaderCounterInput<TItem>): BiliHeaderCounter {
  return {
    label,
    value: source.state === "ready" ? source.items.length : null,
    state: source.state,
  };
}

function aggregateCounterState(counters: BiliHeaderCounter[]): BiliHeaderCounterState {
  if (counters.some((item) => item.state === "loading")) {
    return "loading";
  }
  if (counters.some((item) => item.state === "unavailable")) {
    return "unavailable";
  }
  if (counters.some((item) => item.state === "locked")) {
    return "locked";
  }
  return "ready";
}

export function buildBiliHeaderSummary(args: {
  portalAuth: PortalAuthSession;
  subscriptions: HeaderCounterInput<SubscriptionItem>;
  monitorTargets: HeaderCounterInput<MonitorTargetItem>;
  pendingNotices: HeaderCounterInput<NotificationEventItem>;
}): BiliHeaderSummary {
  const tier = buildTier(args.portalAuth);
  const counters = [
    buildCounter("订阅", args.subscriptions),
    buildCounter("监控", args.monitorTargets),
    buildCounter("提醒", args.pendingNotices),
  ];

  return {
    displayName: args.portalAuth.nickname || args.portalAuth.username,
    levelLabel: buildLevelLabel(tier),
    tier,
    isPremium: args.portalAuth.isPremium,
    counterState: aggregateCounterState(counters),
    counters,
  };
}
