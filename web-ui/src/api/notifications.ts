import { api, type NotificationPendingResponse } from "@/lib/api";

export const fetchPendingNotices = () =>
  api.get<NotificationPendingResponse>("/notifications/pending").then((response) => response.data);
