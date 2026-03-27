import type { SearchCommandCenterFilters } from "@/components/search/SearchCommandCenter";

export type SearchRouteQueryType = "announcements" | "adjustments";

const DEFAULT_SEARCH_FILTERS: SearchCommandCenterFilters = {
  schoolName: "",
  announcementSystemTags: [],
  announcementStartDate: "",
  announcementEndDate: "",
  major: "",
  region: "不限",
  city: "",
  year: "",
  level: "不限",
  type: "all",
  score: "",
  historyBackedOnly: false,
  longTrackOnly: false,
  referenceLinksOnly: false,
  hideMentorWarnings: false,
};

export function readSearchKeywordsFromParams(searchParams: Pick<URLSearchParams, "get">) {
  return readSearchParam(searchParams, ["q", "keyword", "keywords"]);
}

export function resolveSearchQueryTypeFromParams(
  searchParams: Pick<URLSearchParams, "get">,
  fallbackQueryType: SearchRouteQueryType = "announcements",
): SearchRouteQueryType {
  const tab = searchParams.get("tab");
  if (tab === "announcements" || tab === "adjustments") {
    return tab;
  }

  const keywords = readSearchKeywordsFromParams(searchParams);
  const region = readSearchParam(searchParams, ["region"]);
  const level = readSearchParam(searchParams, ["level"]);
  const type = readSearchParam(searchParams, ["type"]);
  const hasAdjustmentOnlySignals = Boolean(
    readSearchParam(searchParams, ["major"]) ||
      (region && region !== DEFAULT_SEARCH_FILTERS.region) ||
      readSearchParam(searchParams, ["city"]) ||
      readSearchParam(searchParams, ["year"]) ||
      (level && level !== DEFAULT_SEARCH_FILTERS.level) ||
      (type && type !== DEFAULT_SEARCH_FILTERS.type) ||
      readSearchParam(searchParams, ["score"]) ||
      parseBooleanParam(readSearchParam(searchParams, ["history", "historyBackedOnly", "history_backed_only"])) ||
      parseBooleanParam(readSearchParam(searchParams, ["long", "longTrackOnly", "long_track_only"])) ||
      parseBooleanParam(readSearchParam(searchParams, ["refs", "referenceLinksOnly", "reference_links_only"])) ||
      parseBooleanParam(readSearchParam(searchParams, ["safe", "hideMentorWarnings", "exclude_mentor_warnings"])) ||
      isMajorCodeLikeQuery(keywords),
  );

  return hasAdjustmentOnlySignals ? "adjustments" : fallbackQueryType;
}

export function buildSearchRouteParams(state: {
  queryType: SearchRouteQueryType;
  keywords: string;
  filters: SearchCommandCenterFilters;
}) {
  const params = new URLSearchParams();
  params.set("tab", state.queryType);

  const keywords = state.keywords.trim();
  if (keywords) {
    params.set("q", keywords);
  }

  const schoolName = state.filters.schoolName.trim();
  if (schoolName) {
    params.set("schoolName", schoolName);
  }

  if (state.filters.announcementSystemTags.length > 0) {
    params.set("systemTags", state.filters.announcementSystemTags.join(","));
  }
  if (state.filters.announcementStartDate.trim()) {
    params.set("startDate", state.filters.announcementStartDate.trim());
  }
  if (state.filters.announcementEndDate.trim()) {
    params.set("endDate", state.filters.announcementEndDate.trim());
  }
  if (state.filters.major.trim()) {
    params.set("major", state.filters.major.trim());
  }
  if (state.filters.region !== DEFAULT_SEARCH_FILTERS.region) {
    params.set("region", state.filters.region);
  }
  if (state.filters.city.trim()) {
    params.set("city", state.filters.city.trim());
  }
  if (state.filters.year.trim()) {
    params.set("year", state.filters.year.trim());
  }
  if (state.filters.level !== DEFAULT_SEARCH_FILTERS.level) {
    params.set("level", state.filters.level);
  }
  if (state.filters.type !== DEFAULT_SEARCH_FILTERS.type) {
    params.set("type", state.filters.type);
  }
  if (state.filters.score.trim()) {
    params.set("score", state.filters.score.trim());
  }
  if (state.filters.historyBackedOnly) {
    params.set("historyBackedOnly", "1");
  }
  if (state.filters.longTrackOnly) {
    params.set("longTrackOnly", "1");
  }
  if (state.filters.referenceLinksOnly) {
    params.set("referenceLinksOnly", "1");
  }
  if (state.filters.hideMentorWarnings) {
    params.set("hideMentorWarnings", "1");
  }

  return params;
}

export function updateSearchRouteParams(
  baseParams: string,
  patch: {
    queryType: SearchRouteQueryType;
    keywords: string;
  },
) {
  const params = new URLSearchParams(baseParams);
  params.set("tab", patch.queryType);

  const keywords = patch.keywords.trim();
  params.delete("keyword");
  params.delete("keywords");
  if (keywords) {
    params.set("q", keywords);
  } else {
    params.delete("q");
  }

  return params;
}

function readSearchParam(searchParams: Pick<URLSearchParams, "get">, keys: string[]) {
  for (const key of keys) {
    const value = searchParams.get(key);
    if (value !== null) {
      return value.trim();
    }
  }
  return "";
}

function parseBooleanParam(value: string) {
  return /^(1|true|yes|on)$/i.test(value);
}

function isMajorCodeLikeQuery(value: string) {
  const compact = value.replace(/\s+/g, "");
  return /^\d{4,6}$/.test(compact);
}
