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

interface ToastState {
  open: boolean;
  title: string;
  message: string;
  type: "info" | "urgent";
}

interface AppState {
  isAuthOpen: boolean;
  setAuthOpen: (open: boolean) => void;
  isWatchlistOpen: boolean;
  setWatchlistOpen: (open: boolean) => void;
  authBootstrapped: boolean;
  setAuthBootstrapped: (done: boolean) => void;
  hasServerSessionHint: boolean;
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
  logout: () => void;
  toast: ToastState;
  showToast: (title: string, message: string, type?: "info" | "urgent") => void;
  hideToast: () => void;
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
      hasServerSessionHint: false,
      portalAuth: null,
      setPortalAuthFromToken: (payload) =>
        set({
          hasServerSessionHint: true,
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
      clearPortalAuth: () => set({ portalAuth: null, hasServerSessionHint: false }),
      logout: () =>
        set({
          portalAuth: null,
          hasServerSessionHint: false,
          isAuthOpen: true,
        }),
      toast: { open: false, title: "", message: "", type: "info" },
      showToast: (title, message, type = "info") => {
        set({
          toast: {
            open: true,
            title,
            message,
            type,
          },
        });
      },
      hideToast: () =>
        set((state) => ({
          toast: {
            ...state.toast,
            open: false,
          },
        })),
    }),
    {
      name: "gewu_portal_auth",
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        hasServerSessionHint: state.hasServerSessionHint,
        portalAuth: state.portalAuth,
      }),
    },
  ),
);
