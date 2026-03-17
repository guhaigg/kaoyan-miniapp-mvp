"use client";

import { useEffect } from "react";
import { fetchEventSource } from "@microsoft/fetch-event-source";
import { useQueryClient } from "@tanstack/react-query";
import { NotificationEventItem, notificationsStreamUrl } from "@/lib/api";
import { mergeNoticeList, watchlistNoticeQueryKey } from "@/lib/notice-cache";
import { useAppStore } from "@/lib/store";

function buildToastContent(item: NotificationEventItem) {
  const school = item.payload.school_name || "目标院校";
  const title = item.payload.title || "有新的信息变更";
  const isUrgent = /紧急|截止|补录|缺额|复试|调剂/i.test(`${title} ${item.payload.summary || ""}`);
  return {
    toastTitle: isUrgent ? "紧急调剂提醒" : "数据源更新提醒",
    toastMessage: `${school}：${title}`,
    toastType: isUrgent ? ("urgent" as const) : ("info" as const),
  };
}

export default function SSEClient() {
  const queryClient = useQueryClient();
  const portalAuth = useAppStore((state) => state.portalAuth);
  const logout = useAppStore((state) => state.logout);
  const showToast = useAppStore((state) => state.showToast);

  useEffect(() => {
    const userId = portalAuth?.userId;
    const token = portalAuth?.accessToken;
    if (!userId || !token) {
      return;
    }

    const abortController = new AbortController();
    const streamUrl = notificationsStreamUrl();

    void fetchEventSource(streamUrl, {
      method: "GET",
      headers: {
        Accept: "text/event-stream",
        "X-User-Token": token,
      },
      signal: abortController.signal,
      credentials: "include",
      openWhenHidden: true,
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

          queryClient.setQueryData(
            watchlistNoticeQueryKey(userId),
            (oldData: NotificationEventItem[] | undefined) => mergeNoticeList(oldData, [item]),
          );
          const toast = buildToastContent(item);
          showToast(toast.toastTitle, toast.toastMessage, toast.toastType);
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
  }, [logout, portalAuth?.accessToken, portalAuth?.userId, queryClient, showToast]);

  return null;
}
