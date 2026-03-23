"use client";

const CLAIM_TTL_MS = 24 * 60 * 60 * 1000;
const MAX_CLAIMS = 200;
const CLAIMS_STORAGE_PREFIX = "gewu_notice_toast_claims:";
const CLAIM_LOCK_PREFIX = "gewu_notice_toast_lock:";

type StoredClaim = {
  id: string;
  ts: number;
};

function claimsStorageKey(userId: string) {
  return `${CLAIMS_STORAGE_PREFIX}${userId}`;
}

function claimLockKey(userId: string, noticeId: string) {
  return `${CLAIM_LOCK_PREFIX}${userId}:${noticeId}`;
}

function loadClaims(userId: string): StoredClaim[] {
  if (typeof window === "undefined") {
    return [];
  }

  try {
    const raw = window.localStorage.getItem(claimsStorageKey(userId));
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed
      .filter((value): value is StoredClaim => {
        return Boolean(
          value &&
            typeof value === "object" &&
            typeof value.id === "string" &&
            typeof value.ts === "number",
        );
      })
      .sort((a, b) => b.ts - a.ts);
  } catch {
    return [];
  }
}

function saveClaims(userId: string, claims: StoredClaim[]) {
  if (typeof window === "undefined") {
    return;
  }

  try {
    window.localStorage.setItem(claimsStorageKey(userId), JSON.stringify(claims));
  } catch {
    // Ignore storage write failures and degrade to per-tab toasts.
  }
}

function pruneClaims(claims: StoredClaim[], now: number) {
  return claims.filter((claim) => now - claim.ts < CLAIM_TTL_MS).slice(0, MAX_CLAIMS);
}

function hasClaim(userId: string, noticeId: string, now: number) {
  const claims = pruneClaims(loadClaims(userId), now);
  return claims.some((claim) => claim.id === noticeId);
}

function persistClaim(userId: string, noticeId: string, now: number) {
  const claims = pruneClaims(loadClaims(userId), now).filter((claim) => claim.id !== noticeId);
  claims.unshift({ id: noticeId, ts: now });
  saveClaims(userId, claims.slice(0, MAX_CLAIMS));
}

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function claimWithStorageLease(userId: string, noticeId: string, now: number) {
  if (typeof window === "undefined") {
    return true;
  }
  if (hasClaim(userId, noticeId, now)) {
    return false;
  }

  const lockKey = claimLockKey(userId, noticeId);
  const token = `${now}:${Math.random().toString(36).slice(2)}`;
  try {
    window.localStorage.setItem(lockKey, token);
    await sleep(80);
    if (window.localStorage.getItem(lockKey) !== token) {
      return false;
    }
    if (hasClaim(userId, noticeId, Date.now())) {
      return false;
    }
    persistClaim(userId, noticeId, Date.now());
    return true;
  } catch {
    return false;
  } finally {
    try {
      if (window.localStorage.getItem(lockKey) === token) {
        window.localStorage.removeItem(lockKey);
      }
    } catch {
      // Ignore cleanup failures.
    }
  }
}

export async function claimNoticeToast(userId: string, noticeId: string) {
  if (typeof window === "undefined") {
    return true;
  }

  const now = Date.now();
  if (hasClaim(userId, noticeId, now)) {
    return false;
  }

  const lockManager = navigator.locks;
  if (lockManager?.request) {
    let claimed = false;
    await lockManager.request(
      claimLockKey(userId, noticeId),
      { ifAvailable: true, mode: "exclusive" },
      async (lock) => {
        if (!lock) {
          return;
        }
        const nextNow = Date.now();
        if (hasClaim(userId, noticeId, nextNow)) {
          return;
        }
        persistClaim(userId, noticeId, nextNow);
        claimed = true;
      },
    );
    return claimed;
  }

  return claimWithStorageLease(userId, noticeId, now);
}
