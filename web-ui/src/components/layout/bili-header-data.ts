import type { MonitorTargetItem, NotificationEventItem, SubscriptionItem } from "@/lib/api";
import type { PortalAuthSession } from "@/lib/store";

export interface BiliHeaderSummary {
  displayName: string;
  levelLabel: string;
  isPremium: boolean;
  counters: Array<{ label: string; value: number }>;
}

function buildLevelLabel(portalAuth: PortalAuthSession) {
  if (portalAuth.isAdmin || portalAuth.role === "admin") {
    return "管理员";
  }
  if (portalAuth.isPremium || portalAuth.role === "premium") {
    return "高级会员";
  }
  return "普通账户";
}

export function buildBiliHeaderSummary(args: {
  portalAuth: PortalAuthSession;
  subscriptions: SubscriptionItem[];
  monitorTargets: MonitorTargetItem[];
  pendingNotices: NotificationEventItem[];
}): BiliHeaderSummary {
  return {
    displayName: args.portalAuth.nickname || args.portalAuth.username,
    levelLabel: buildLevelLabel(args.portalAuth),
    isPremium: args.portalAuth.isPremium,
    counters: [
      {
        label: "关注项",
        value: args.subscriptions.length + args.monitorTargets.length,
      },
      {
        label: "雷达位",
        value: args.monitorTargets.length,
      },
      {
        label: "待查看",
        value: args.pendingNotices.length,
      },
    ],
  };
}
