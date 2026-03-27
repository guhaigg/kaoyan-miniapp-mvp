export type AccountSpaceTab = "activity" | "following" | "radar" | "account";
export type AccountSpacePanel = "billing" | "security" | "notifications" | null;

const VALID_TABS = new Set<AccountSpaceTab>(["activity", "following", "radar", "account"]);
const VALID_PANELS = new Set<Exclude<AccountSpacePanel, null>>(["billing", "security", "notifications"]);

function readSingle(value: string | string[] | undefined): string | null {
  if (typeof value === "string" && value.trim()) {
    return value.trim().toLowerCase();
  }
  if (Array.isArray(value) && typeof value[0] === "string" && value[0].trim()) {
    return value[0].trim().toLowerCase();
  }
  return null;
}

export function parseAccountSpaceTab(value: string | string[] | undefined): AccountSpaceTab {
  const next = readSingle(value);
  return next && VALID_TABS.has(next as AccountSpaceTab) ? (next as AccountSpaceTab) : "activity";
}

export function parseAccountSpacePanel(value: string | string[] | undefined): AccountSpacePanel {
  const next = readSingle(value);
  return next && VALID_PANELS.has(next as Exclude<AccountSpacePanel, null>)
    ? (next as Exclude<AccountSpacePanel, null>)
    : null;
}
