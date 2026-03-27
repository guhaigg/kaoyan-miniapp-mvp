export type SearchRouteQueryType = "announcements" | "adjustments";

export function readSearchKeywordsFromParams(searchParams: Pick<URLSearchParams, "get">) {
  return readSearchParam(searchParams, ["q", "keyword", "keywords"]);
}

export function resolveSearchQueryTypeFromParams(
  searchParams: Pick<URLSearchParams, "get">,
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
      (region && region !== "不限") ||
      readSearchParam(searchParams, ["city"]) ||
      readSearchParam(searchParams, ["year"]) ||
      (level && level !== "不限") ||
      (type && type !== "all") ||
      readSearchParam(searchParams, ["score"]) ||
      parseBooleanParam(readSearchParam(searchParams, ["history", "historyBackedOnly", "history_backed_only"])) ||
      parseBooleanParam(readSearchParam(searchParams, ["long", "longTrackOnly", "long_track_only"])) ||
      parseBooleanParam(readSearchParam(searchParams, ["refs", "referenceLinksOnly", "reference_links_only"])) ||
      parseBooleanParam(readSearchParam(searchParams, ["safe", "hideMentorWarnings", "exclude_mentor_warnings"])) ||
      isMajorCodeLikeQuery(keywords),
  );

  return hasAdjustmentOnlySignals ? "adjustments" : "announcements";
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
