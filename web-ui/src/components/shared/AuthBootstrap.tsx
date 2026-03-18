"use client";

import { useEffect } from "react";
import { ApiError, getCurrentUser, refreshUserSession } from "@/lib/api";
import { useAppStore } from "@/lib/store";

export default function AuthBootstrap() {
  const {
    portalAuth,
    authBootstrapped,
    hasServerSessionHint,
    setAuthBootstrapped,
    setPortalAuthFromToken,
    setPortalProfile,
    clearPortalAuth,
  } = useAppStore();

  useEffect(() => {
    if (authBootstrapped) return;
    let alive = true;

    async function bootstrap() {
      try {
        if (portalAuth?.accessToken) {
          const profile = await getCurrentUser(portalAuth.accessToken);
          if (!alive) return;
          setPortalProfile({
            nickname: profile.nickname,
            status: profile.status,
            isAdmin: profile.is_admin,
            isPremium: profile.is_premium,
            role: profile.role,
            premiumExpiresAt: profile.premium_expires_at,
          });
          return;
        }

        if (!hasServerSessionHint) {
          return;
        }

        const refreshed = await refreshUserSession();
        if (!alive) return;
        setPortalAuthFromToken({
          tokenType: refreshed.token_type,
          accessToken: refreshed.access_token,
          expiresIn: refreshed.expires_in,
          refreshExpiresIn: refreshed.refresh_expires_in,
          userId: refreshed.user_id,
          username: refreshed.username,
        });

        const profile = await getCurrentUser(refreshed.access_token);
        if (!alive) return;
        setPortalProfile({
          nickname: profile.nickname,
          status: profile.status,
          isAdmin: profile.is_admin,
          isPremium: profile.is_premium,
          role: profile.role,
          premiumExpiresAt: profile.premium_expires_at,
        });
      } catch (error) {
        const isUnauthorized = error instanceof ApiError && error.status === 401;
        if (!isUnauthorized) {
          console.error(error);
        }
        if (alive) {
          clearPortalAuth();
        }
      } finally {
        if (alive) {
          setAuthBootstrapped(true);
        }
      }
    }

    void bootstrap();

    return () => {
      alive = false;
    };
  }, [
    authBootstrapped,
    clearPortalAuth,
    hasServerSessionHint,
    portalAuth?.accessToken,
    setAuthBootstrapped,
    setPortalAuthFromToken,
    setPortalProfile,
  ]);

  return null;
}
