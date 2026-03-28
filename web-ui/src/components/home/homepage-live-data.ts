"use client";

import {
  buildAnnouncementDetailHref,
  buildAdjustmentDetailHref,
  buildSearchDestination,
} from "@/components/layout/site-navigation";
import type {
  AdjustmentSearchRequest,
  MonitorTargetItem,
  NotificationEventItem,
  SearchItem,
  SubscriptionItem,
} from "@/lib/api";

export type HomeSectionView = "latest" | "watching";

export type AnnouncementFeedItem = {
  id: string;
  type: string;
  title: string;
  content: string;
  school: string;
  time: string;
  isNew: boolean;
  href: string | null;
  sourceUrl: string | null;
};

export type AdjustmentFeedItem = {
  id: string;
  school: string;
  title: string;
  tags: string[];
  major: string;
  count: number;
  urgent: boolean;
  href: string | null;
  sourceUrl: string | null;
};

export type HomeLiveSummary = {
  pendingCount: number;
  activeTargetCount: number;
  latestTitle: string | null;
  latestSchool: string | null;
};

export type TrendPoint = {
  label: string;
  value: number;
};

export type TierBreakdownLabel = "985" | "211" | "doubleFirst" | "other";

export type TierBreakdownItem = {
  label: TierBreakdownLabel;
  count: number;
};

type FocusedAdjustmentPayload = {
  focusLabel: string;
  payload: AdjustmentSearchRequest;
};

function parseTimestamp(input: string | null | undefined) {
  if (!input) return null;
  const date = new Date(input);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return date.getTime();
}

function formatClockLabel(timestamp: number) {
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(timestamp));
}

function buildAnnouncementSearchHref(item: SearchItem) {
  if (item.id) {
    return buildAnnouncementDetailHref(item.id);
  }
  const keyword = item.school_name || item.department_name || item.title;
  return buildSearchDestination("announcements", keyword || "");
}

function buildAdjustmentSearchHref(item: SearchItem) {
  if (item.id) {
    return buildAdjustmentDetailHref(item.id, item.item_kind);
  }
  const keyword = item.school_name || item.major || item.department_name || item.title;
  return buildSearchDestination("adjustments", keyword || "");
}

function buildAdjustmentTags(item: SearchItem) {
  return Array.from(
    new Set(
      [
        ...(item.tags || []),
        ...(item.system_tags || []),
        item.adjustment_year ? `${item.adjustment_year}\u8c03\u5242` : null,
        item.school_tier,
        item.region,
      ].filter((value): value is string => Boolean(value && value.trim())),
    ),
  ).slice(0, 2);
}

function classifyTier(item: SearchItem): TierBreakdownLabel {
  const text = [item.school_tier, ...(item.tags || []), ...(item.system_tags || [])]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();

  if (text.includes("985")) return "985";
  if (text.includes("211")) return "211";
  if (text.includes("\u53cc\u4e00\u6d41") || text.includes("double first") || text.includes("d1l")) {
    return "doubleFirst";
  }
  return "other";
}

function dedupeAnnouncementFeed(items: AnnouncementFeedItem[]) {
  const map = new Map<string, AnnouncementFeedItem>();
  for (const item of items) {
    const key = [item.sourceUrl || "", item.title, item.school].join("::");
    if (!map.has(key)) {
      map.set(key, item);
    }
  }
  return Array.from(map.values());
}

export function formatRelativeTime(input: string | null | undefined) {
  const timestamp = parseTimestamp(input);
  if (!timestamp) return "Just Now";

  const diffMs = Date.now() - timestamp;
  if (diffMs < 60 * 1000) return "Just Now";
  if (diffMs < 60 * 60 * 1000) return `${Math.floor(diffMs / (60 * 1000))} mins ago`;
  if (diffMs < 24 * 60 * 60 * 1000) return `${Math.floor(diffMs / (60 * 60 * 1000))} hours ago`;
  return `${Math.floor(diffMs / (24 * 60 * 60 * 1000))} days ago`;
}

export function isFresh(input: string | null | undefined) {
  const timestamp = parseTimestamp(input);
  if (!timestamp) return true;
  return Date.now() - timestamp < 90 * 60 * 1000;
}

export function mapAnnouncementSearchItem(item: SearchItem): AnnouncementFeedItem {
  const timestamp = item.published_at || item.updated_at;
  return {
    id: item.id,
    type: (item.notice_kind || item.channel_label || item.source_type || "\u516c\u544a").slice(0, 8),
    title: item.title,
    content: item.summary || item.school_intelligence?.signal_detail || "\u70b9\u51fb\u67e5\u770b\u5b8c\u6574\u516c\u544a\u5185\u5bb9...",
    school: item.school_name || item.department_name || "\u76ee\u6807\u9662\u6821",
    time: formatRelativeTime(timestamp),
    isNew: isFresh(timestamp),
    href: buildAnnouncementSearchHref(item),
    sourceUrl: item.source_url,
  };
}

export function mapAdjustmentSearchItem(item: SearchItem): AdjustmentFeedItem {
  const count = item.adjustment_vacancy_count ?? item.historical_adjustment?.sample_count ?? 0;
  const tags = buildAdjustmentTags(item);
  return {
    id: item.id,
    school: item.school_name || "\u76ee\u6807\u9662\u6821",
    title: item.title,
    tags: tags.length ? tags : ["\u8c03\u5242\u60c5\u62a5", "\u5b9e\u65f6\u66f4\u65b0"],
    major: item.major || item.department_name || item.channel_label || "\u8c03\u5242\u4fe1\u606f",
    count,
    urgent: count > 0 && count <= 5,
    href: buildAdjustmentSearchHref(item),
    sourceUrl: item.source_url,
  };
}

export function mapPendingAnnouncementNotice(item: NotificationEventItem): AnnouncementFeedItem {
  const school = item.payload.school_name || item.payload.department_name || "\u6211\u7684\u5173\u6ce8";
  const detailHref = item.payload.content_id ? buildAnnouncementDetailHref(item.payload.content_id) : null;
  return {
    id: item.id,
    type: item.payload.category === "adjustment" ? "\u8c03\u5242\u63d0\u9192" : "\u5173\u6ce8\u516c\u544a",
    title: item.payload.title || item.payload.summary || "\u65b0\u7684\u5173\u6ce8\u63d0\u9192",
    content:
      item.payload.summary ||
      item.payload.body ||
      "\u70b9\u51fb\u67e5\u770b\u5173\u6ce8\u8303\u56f4\u5185\u7684\u6700\u65b0\u516c\u544a\u63d0\u9192...",
    school,
    time: formatRelativeTime(item.payload.published_at || item.created_at),
    isNew: true,
    href: detailHref || buildSearchDestination("announcements", school),
    sourceUrl: item.payload.source_url || null,
  };
}

export function mapMonitorTargetSignal(target: MonitorTargetItem): AnnouncementFeedItem | null {
  const latest = target.recent_signal?.latest_announcement;
  if (!latest?.title) {
    return null;
  }

  const school = latest.school_name || latest.department_name || target.display_label || "\u6211\u7684\u5173\u6ce8";
  return {
    id: `${target.id}:${latest.content_id || latest.title}`,
    type: "\u6536\u85cf\u9662\u6821",
    title: latest.title,
    content: latest.summary || "\u70b9\u51fb\u67e5\u770b\u6536\u85cf\u9662\u6821\u7684\u6700\u65b0\u516c\u544a...",
    school,
    time: formatRelativeTime(latest.published_at || target.last_hit_at || target.updated_at),
    isNew: isFresh(latest.published_at || target.last_hit_at || target.updated_at),
    href: latest.content_id
      ? buildAnnouncementDetailHref(latest.content_id)
      : buildSearchDestination("announcements", school),
    sourceUrl: latest.source_url || null,
  };
}

export function buildWatchedAnnouncementFeed(
  pending: NotificationEventItem[],
  targets: MonitorTargetItem[],
) {
  const pendingCards = pending
    .filter((item) => item.payload.category !== "adjustment")
    .map((item) => mapPendingAnnouncementNotice(item));
  const targetCards = targets
    .filter((item) => item.status === "active")
    .map((item) => mapMonitorTargetSignal(item))
    .filter((item): item is AnnouncementFeedItem => Boolean(item));
  return dedupeAnnouncementFeed([...pendingCards, ...targetCards]);
}

export function buildFocusedAdjustmentPayload(
  subscriptions: SubscriptionItem[],
): FocusedAdjustmentPayload | null {
  const active = subscriptions
    .filter((item) => item.status === "active" && item.category !== "announcement")
    .sort((left, right) => (parseTimestamp(right.updated_at) || 0) - (parseTimestamp(left.updated_at) || 0));

  const radar = active.find((item) => item.subscription_type === "radar");
  const school = active.find((item) => item.subscription_type === "school");
  const major = active.find((item) => item.subscription_type === "major");
  const focus = radar || school || major;

  if (!focus) {
    return null;
  }

  const payload: AdjustmentSearchRequest = {
    page: 1,
    page_size: 3,
  };

  if (focus.target_university) {
    payload.school_name = focus.target_university;
  }

  if (focus.target_major_name || focus.target_major_code) {
    payload.major = focus.target_major_name || focus.target_major_code || undefined;
  } else if (focus.subscription_type === "major" && focus.value.trim()) {
    payload.major = focus.value.trim();
  }

  if (!payload.school_name && !payload.major && focus.value.trim()) {
    payload.keywords = focus.value.trim();
  }

  return {
    focusLabel:
      focus.display_label ||
      focus.target_university ||
      focus.target_major_name ||
      focus.target_major_code ||
      focus.value,
    payload,
  };
}

export function buildTrendSeries(items: SearchItem[]) {
  const bucketCount = 10;
  if (!items.length) {
    return [] satisfies TrendPoint[];
  }

  const timestamps = items
    .map((item) => parseTimestamp(item.published_at || item.updated_at))
    .filter((value): value is number => value !== null);

  if (!timestamps.length) {
    return items.slice(0, bucketCount).map((_, index) => ({
      label: `${index + 1}`,
      value: index + 1,
    }));
  }

  const newest = Math.max(...timestamps);
  const oldest = Math.min(...timestamps);
  const windowMs = Math.max(
    6 * 60 * 60 * 1000,
    Math.min(24 * 60 * 60 * 1000, newest - oldest || 6 * 60 * 60 * 1000),
  );
  const start = newest - windowMs;
  const bucketMs = windowMs / bucketCount;

  const weightedBuckets = Array.from({ length: bucketCount }, (_, index) => {
    const bucketStart = start + bucketMs * index;
    const bucketEnd = index === bucketCount - 1 ? newest + 1 : bucketStart + bucketMs;
    const weight = items.reduce((sum, item) => {
      const timestamp = parseTimestamp(item.published_at || item.updated_at);
      if (timestamp === null || timestamp < bucketStart || timestamp >= bucketEnd) {
        return sum;
      }
      const vacancyWeight =
        item.adjustment_vacancy_count && item.adjustment_vacancy_count > 0
          ? Math.min(4, Math.max(1, Math.round(item.adjustment_vacancy_count / 10) + 1))
          : 1;
      return sum + vacancyWeight;
    }, 0);

    return {
      label: formatClockLabel(Math.round(bucketStart + bucketMs / 2)),
      value: weight,
    };
  });

  let running = 0;
  const series = weightedBuckets.map((bucket, index) => {
    const previous = weightedBuckets[index - 1]?.value ?? bucket.value;
    const smoothed = Math.max(bucket.value, Math.round((previous + bucket.value * 2) / 3));
    running += smoothed;
    return {
      label: bucket.label,
      value: running,
    };
  });

  if (series.every((item) => item.value === 0)) {
    return items.slice(0, bucketCount).map((_, index) => ({
      label: `${index + 1}`,
      value: index + 1,
    }));
  }

  return series;
}

export function buildTierBreakdown(items: SearchItem[]) {
  const counts: Record<TierBreakdownLabel, number> = {
    "985": 0,
    "211": 0,
    doubleFirst: 0,
    other: 0,
  };

  for (const item of items) {
    counts[classifyTier(item)] += 1;
  }

  return (Object.entries(counts) as [TierBreakdownLabel, number][])
    .map(([label, count]) => ({ label, count }))
    .filter((item) => item.count > 0);
}

export function buildHomeLiveSummary(
  pending: NotificationEventItem[],
  targets: MonitorTargetItem[],
): HomeLiveSummary {
  const pendingLead = pending[0];
  const targetLead = targets
    .filter((item) => item.status === "active" && item.recent_signal?.latest_announcement?.title)
    .sort((left, right) => {
      const rightTimestamp =
        parseTimestamp(
          right.recent_signal?.latest_announcement?.published_at || right.last_hit_at || right.updated_at,
        ) || 0;
      const leftTimestamp =
        parseTimestamp(
          left.recent_signal?.latest_announcement?.published_at || left.last_hit_at || left.updated_at,
        ) || 0;
      return rightTimestamp - leftTimestamp;
    })[0];

  return {
    pendingCount: pending.length,
    activeTargetCount: targets.filter((item) => item.status === "active").length,
    latestTitle:
      pendingLead?.payload.title ||
      pendingLead?.payload.summary ||
      targetLead?.recent_signal?.latest_announcement?.title ||
      null,
    latestSchool:
      pendingLead?.payload.school_name ||
      pendingLead?.payload.department_name ||
      targetLead?.recent_signal?.latest_announcement?.school_name ||
      targetLead?.recent_signal?.latest_announcement?.department_name ||
      targetLead?.display_label ||
      null,
  };
}
