export interface BiliHeaderSummary {
  displayName: string;
  levelLabel: string;
  isPremium: boolean;
  counters: Array<{ label: string; value: number }>;
}

export function buildHeaderSummary(input: {
  username: string;
  nickname: string | null;
  isPremium: boolean;
  followingCount: number;
  radarCount: number;
  activityCount: number;
}): BiliHeaderSummary {
  return {
    displayName: input.nickname || input.username,
    levelLabel: input.isPremium ? "PRO" : "LV1",
    isPremium: input.isPremium,
    counters: [
      { label: "关注", value: input.followingCount },
      { label: "雷达", value: input.radarCount },
      { label: "动态", value: input.activityCount },
    ],
  };
}
