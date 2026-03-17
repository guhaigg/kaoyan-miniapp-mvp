import type { NotificationEventItem } from "@/lib/api";

const MAX_NOTICE_CACHE = 80;

export function watchlistNoticeQueryKey(userId: string | undefined) {
  return ["portal", "watchlistNotices", userId] as const;
}

export function mergeNoticeList(
  base: NotificationEventItem[] | undefined,
  incoming: NotificationEventItem[] | undefined,
) {
  const map = new Map<string, NotificationEventItem>();
  for (const item of base || []) {
    map.set(item.id, item);
  }
  for (const item of incoming || []) {
    if (!map.has(item.id)) {
      map.set(item.id, item);
    }
  }
  const merged = Array.from(map.values()).sort((a, b) => {
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
  });
  if (merged.length > MAX_NOTICE_CACHE) {
    merged.length = MAX_NOTICE_CACHE;
  }
  return merged;
}
