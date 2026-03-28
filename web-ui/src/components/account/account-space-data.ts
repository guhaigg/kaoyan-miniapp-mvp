import type {
  MonitorTargetItem,
  NotificationEventItem,
  SubscriptionItem,
  UserAccountOverviewResponse,
  UserNotificationHistoryItem,
} from "@/lib/api";

export type AccountSpaceSummary = {
  displayName: string;
  username: string;
  membershipLabel: string;
  signature: string;
  wechatBound: boolean;
  followCount: number;
  radarCount: number;
  recentActivityCount: number;
  securityHint: string;
};

export type AccountActivityItem = {
  id: string;
  kind: "history" | "notice" | "signal";
  title: string;
  subtitle: string;
  timestamp: string | null;
  href: string | null;
  tags: string[];
};

function buildMembershipLabel(args: {
  isLoggedIn: boolean;
  isAdmin: boolean;
  isPremium: boolean;
  overview: UserAccountOverviewResponse | null;
}) {
  if (!args.isLoggedIn) {
    return "游客";
  }
  if (args.overview?.role === "admin" || args.isAdmin) {
    return "管理员";
  }
  if (args.overview?.is_premium || args.isPremium) {
    return "高级会员";
  }
  return "普通用户";
}

function buildSignature(args: {
  isLoggedIn: boolean;
  membershipLabel: string;
  followCount: number;
  radarCount: number;
}) {
  if (!args.isLoggedIn) {
    return "登录后，账号摘要、通知历史和会员状态会在这里聚合成你的个人空间首页。";
  }
  if (args.membershipLabel === "管理员") {
    return "把账号动态、通知历史和管理员身份摘要集中在一个更像个人空间的首页里，方便日常巡检。";
  }
  if (args.membershipLabel === "高级会员") {
    return "最近动态、通知历史和会员状态会在这里形成一条连续的信息流，保持你的研招盯盘节奏。";
  }
  if (args.followCount > 0 || args.radarCount > 0) {
    return "先从最近动态和通知开始，再回看你的关注库与雷达范围，个人空间会逐渐长出来。";
  }
  return "先从动态和通知开始，等你补齐关注库后，这里会慢慢长成完整的个人摘要页。";
}

function joinBits(parts: Array<string | null | undefined>) {
  return parts.filter(Boolean).join(" · ");
}

function normalizeDate(value?: string | null) {
  if (!value) {
    return null;
  }
  const timestamp = Date.parse(value);
  return Number.isNaN(timestamp) ? null : value;
}

function categoryLabel(category?: string | null) {
  if (category === "adjustment") {
    return "调剂";
  }
  if (category === "announcement") {
    return "公告";
  }
  return "动态";
}

export function formatAccountSpaceDate(value?: string | null) {
  const normalized = normalizeDate(value);
  if (!normalized) {
    return null;
  }
  return new Date(normalized).toLocaleString("zh-CN", { hour12: false });
}

export function subscriptionTypeLabel(type: SubscriptionItem["subscription_type"]) {
  if (type === "school") return "院校订阅";
  if (type === "major") return "专业订阅";
  if (type === "keyword") return "关键词订阅";
  if (type === "region") return "地区订阅";
  return "雷达订阅";
}

export function subscriptionCardTitle(item: SubscriptionItem) {
  return (
    item.display_label ||
    item.target_university ||
    item.target_major_name ||
    item.target_major_code ||
    item.value
  );
}

export function subscriptionCardDetail(item: SubscriptionItem) {
  return joinBits([
    item.category === "adjustment" ? "范围：调剂" : item.category === "announcement" ? "范围：公告" : "范围：全站",
    item.target_university,
    item.target_department_name,
    item.target_major_name || item.target_major_code,
    item.source_title,
  ]);
}

export function monitorScopeTypeLabel(type: MonitorTargetItem["scope_type"]) {
  if (type === "school") return "学校雷达";
  if (type === "department") return "院系雷达";
  return "栏目雷达";
}

export function monitorCardTitle(item: MonitorTargetItem) {
  return (
    joinBits([item.school_name, item.department_name, item.site_section_name]) ||
    item.display_label ||
    monitorScopeTypeLabel(item.scope_type)
  );
}

export function monitorCardDetail(item: MonitorTargetItem) {
  return joinBits([
    item.scope_type === "school" ? "锁定该学校公告" : null,
    item.scope_type === "department" ? "锁定该院系公告" : null,
    item.scope_type === "section" ? "精确盯住栏目更新" : null,
    item.last_hit_at ? `最近命中 ${formatAccountSpaceDate(item.last_hit_at)}` : null,
    !item.last_hit_at && item.last_checked_at ? `最近检查 ${formatAccountSpaceDate(item.last_checked_at)}` : null,
  ]);
}

export function buildAccountSpaceSummary(args: {
  displayName: string;
  username: string;
  overview: UserAccountOverviewResponse | null;
  subscriptions: SubscriptionItem[];
  monitorTargets: MonitorTargetItem[];
  activityCount: number;
  isLoggedIn: boolean;
  isAdmin: boolean;
  isPremium: boolean;
}) {
  const wechatBound = Boolean(
    args.overview?.identities.some((item) => item.identity_type === "wechat_miniapp" && item.status === "active"),
  );
  const membershipLabel = buildMembershipLabel(args);
  const followCount = args.subscriptions.length + args.monitorTargets.length;
  const radarCount = args.monitorTargets.length;

  return {
    displayName: args.displayName,
    username: args.username,
    membershipLabel,
    signature: buildSignature({
      isLoggedIn: args.isLoggedIn,
      membershipLabel,
      followCount,
      radarCount,
    }),
    wechatBound,
    followCount,
    radarCount,
    recentActivityCount: args.activityCount,
    securityHint: wechatBound
      ? "微信已经绑定，后续主要维护密码和会话安全即可。"
      : "建议补齐微信绑定和密码安全，后续跨端登录会更顺。",
  } satisfies AccountSpaceSummary;
}

function buildHistoryItem(item: UserNotificationHistoryItem): AccountActivityItem {
  const title =
    item.payload.title ||
    joinBits([item.payload.school_name, item.payload.department_name, item.payload.site_section_name]) ||
    "站内通知已送达";
  return {
    id: `history-${item.id}`,
    kind: "history",
    title,
    subtitle: joinBits([
      item.payload.summary || item.payload.body || null,
      item.payload.school_name,
      item.payload.department_name,
      item.channel ? `渠道：${item.channel}` : null,
    ]),
    timestamp: item.sent_at || item.created_at,
    href: item.payload.source_url || null,
    tags: [categoryLabel(item.payload.category), "已发送", item.status || null].filter(Boolean) as string[],
  };
}

function buildPendingNoticeItem(item: NotificationEventItem): AccountActivityItem {
  const title =
    item.payload.title ||
    joinBits([item.payload.school_name, item.payload.department_name, item.payload.site_section_name]) ||
    "新的关注动态";
  return {
    id: `notice-${item.id}`,
    kind: "notice",
    title,
    subtitle: joinBits([
      item.payload.summary || item.payload.body || null,
      item.payload.school_name,
      item.payload.department_name,
      item.payload.major_name || item.payload.major || item.payload.major_code || null,
    ]),
    timestamp: item.payload.published_at || item.created_at,
    href: item.payload.source_url || null,
    tags: [categoryLabel(item.payload.category), item.payload.site_section_name || null].filter(Boolean) as string[],
  };
}

function buildSignalItem(item: MonitorTargetItem): AccountActivityItem | null {
  const latest = item.recent_signal?.latest_announcement;
  if (!latest) {
    return null;
  }
  return {
    id: `signal-${item.id}-${latest.content_id}`,
    kind: "signal",
    title: latest.title || monitorCardTitle(item),
    subtitle: joinBits([
      monitorCardTitle(item),
      latest.department_name,
      latest.site_section_name,
      latest.summary || null,
    ]),
    timestamp: latest.published_at || item.last_hit_at || item.updated_at,
    href: latest.source_url || null,
    tags: [
      monitorScopeTypeLabel(item.scope_type),
      item.recent_signal?.recent_announcement_count
        ? `${item.recent_signal.recent_announcement_count} 条近况`
        : null,
      item.recent_signal?.recruitment_announcement_count
        ? `${item.recent_signal.recruitment_announcement_count} 条研招相关`
        : null,
    ].filter(Boolean) as string[],
  };
}

export function buildAccountActivityItems(args: {
  history: UserNotificationHistoryItem[];
  pending: NotificationEventItem[];
  monitorTargets: MonitorTargetItem[];
}) {
  return [
    ...args.history.map(buildHistoryItem),
    ...args.pending.map(buildPendingNoticeItem),
    ...args.monitorTargets.map(buildSignalItem).filter(Boolean),
  ]
    .sort((left, right) => {
      const leftTime = Date.parse(left?.timestamp || "") || 0;
      const rightTime = Date.parse(right?.timestamp || "") || 0;
      return rightTime - leftTime;
    })
    .slice(0, 18) as AccountActivityItem[];
}
