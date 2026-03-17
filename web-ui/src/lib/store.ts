import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

interface PortalAuthSession {
  tokenType: "bearer";
  accessToken: string;
  userId: string;
  username: string;
  nickname: string | null;
  status: string;
  accessExpiresAt: number;
  refreshExpiresAt: number;
}

interface AppState {
  isAuthOpen: boolean;
  setAuthOpen: (open: boolean) => void;
  isWatchlistOpen: boolean;
  setWatchlistOpen: (open: boolean) => void;
  authBootstrapped: boolean;
  setAuthBootstrapped: (done: boolean) => void;
  portalAuth: PortalAuthSession | null;
  setPortalAuthFromToken: (payload: {
    tokenType: "bearer";
    accessToken: string;
    expiresIn: number;
    refreshExpiresIn: number;
    userId: string;
    username: string;
  }) => void;
  setPortalProfile: (payload: { nickname: string | null; status: string }) => void;
  clearPortalAuth: () => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      isAuthOpen: false,
      setAuthOpen: (open) => set({ isAuthOpen: open }),
      isWatchlistOpen: false,
      setWatchlistOpen: (open) => set({ isWatchlistOpen: open }),
      authBootstrapped: false,
      setAuthBootstrapped: (done) => set({ authBootstrapped: done }),
      portalAuth: null,
      setPortalAuthFromToken: (payload) =>
        set({
          portalAuth: {
            tokenType: payload.tokenType,
            accessToken: payload.accessToken,
            userId: payload.userId,
            username: payload.username,
            nickname: null,
            status: "active",
            accessExpiresAt: Date.now() + payload.expiresIn * 1000,
            refreshExpiresAt: Date.now() + payload.refreshExpiresIn * 1000,
          },
        }),
      setPortalProfile: (payload) =>
        set((state) => {
          if (!state.portalAuth) return state;
          return {
            portalAuth: {
              ...state.portalAuth,
              nickname: payload.nickname,
              status: payload.status,
            },
          };
        }),
      clearPortalAuth: () => set({ portalAuth: null }),
    }),
    {
      name: "gewu_portal_auth",
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        portalAuth: state.portalAuth,
      }),
    },
  ),
);
