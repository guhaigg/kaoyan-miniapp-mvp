"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { fetchEventSource } from "@microsoft/fetch-event-source";
import { useQueryClient } from "@tanstack/react-query";
import { NotificationEventItem, notificationsStreamUrl } from "@/lib/api";
import { mergeNoticeList, watchlistNoticeQueryKey } from "@/lib/notice-cache";
import { claimNoticeToast } from "@/lib/notice-toast-gate";
import { useDocumentVisibility } from "@/hooks/useDocumentVisibility";
import { useAppStore } from "@/lib/store";

function buildToastContent(item: NotificationEventItem) {
  const school = item.payload.school_name || "目标院校";
  const major = item.payload.major_name || item.payload.major || item.payload.major_code || "";
  const title = item.payload.title || "有新的信息变更";
  const tags = (item.payload.tags || []).join(" ");
  const isUrgent = /紧急|截止|补录|缺额|复试|调剂/i.test(`${title} ${item.payload.summary || ""} ${tags}`);
  const targetLabel = [school, major].filter(Boolean).join(" · ");
  return {
    toastTitle: isUrgent ? "雷达异动预警" : "雷达追踪更新",
    toastMessage: targetLabel ? `${targetLabel}：${title}` : `${school}：${title}`,
    toastType: isUrgent ? ("urgent" as const) : ("info" as const),
  };
}

export default function SSEClient() {
  const pathname = usePathname();
  const queryClient = useQueryClient();
  const portalAuth = useAppStore((state) => state.portalAuth);
  const logout = useAppStore((state) => state.logout);
  const showToast = useAppStore((state) => state.showToast);
  const isDocumentVisible = useDocumentVisibility();

  useEffect(() => {
    if (pathname === "/") {
      return;
    }
    const userId = portalAuth?.userId;
    const token = portalAuth?.accessToken;
    if (!userId || !token || !isDocumentVisible) {
      return;
    }
    const activeUserId = userId;
    const accessToken = token;

    const abortController = new AbortController();
    const streamUrl = notificationsStreamUrl();

    async function handleNotice(item: NotificationEventItem) {
      queryClient.setQueryData(
        watchlistNoticeQueryKey(activeUserId),
        (oldData: NotificationEventItem[] | undefined) => mergeNoticeList(oldData, [item]),
      );

      if (!(await claimNoticeToast(activeUserId, item.id))) {
        return;
      }

      const toast = buildToastContent(item);
      showToast(toast.toastTitle, toast.toastMessage, toast.toastType);
    }

    void fetchEventSource(streamUrl, {
      method: "GET",
      headers: {
        Accept: "text/event-stream",
        "X-User-Token": accessToken,
      },
      signal: abortController.signal,
      credentials: "include",
      openWhenHidden: false,
      async onopen(response) {
        if (response.ok) return;
        if (response.status === 401) {
          logout();
          throw new Error("Unauthorized");
        }
        throw new Error(`SSE open failed: ${response.status}`);
      },
      onmessage(event) {
        if (event.event !== "notice" || !event.data) {
          return;
        }
        try {
          const item = JSON.parse(event.data) as NotificationEventItem;
          if (!item?.id) return;
          void handleNotice(item);
        } catch (error) {
          console.error("Failed to parse SSE message", error);
        }
      },
      onerror(error) {
        if (abortController.signal.aborted) return;
        if (error instanceof Error && error.message === "Unauthorized") {
          throw error;
        }
      },
    });

    return () => {
      abortController.abort();
    };
  }, [isDocumentVisible, logout, pathname, portalAuth?.accessToken, portalAuth?.userId, queryClient, showToast]);

  return null;
}
