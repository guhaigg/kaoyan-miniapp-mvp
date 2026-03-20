import { api, type SubscriptionItem, type SubscriptionListResponse, type SubscriptionType } from "@/lib/api";

type CreateSubscriptionPayload = {
  subscription_type: SubscriptionType;
  value?: string;
  category?: "all" | "announcement" | "adjustment";
  source_record_id?: string;
  source_item_kind?: "content" | "opportunity";
  source_title?: string;
  source_url?: string;
  target_university?: string;
  target_department_name?: string;
  target_major_code?: string;
  target_major_name?: string;
};

export const fetchSubscriptions = () =>
  api.get<SubscriptionListResponse>("/subscriptions").then((response) => response.data);

export const createSubscriptionEntry = (payload: CreateSubscriptionPayload) =>
  api.post<SubscriptionItem>("/subscriptions", payload).then((response) => response.data);

export const removeSubscriptionEntry = (subscriptionId: string) =>
  api.delete<{ status: "ok" }>(`/subscriptions/${encodeURIComponent(subscriptionId)}`).then((response) => response.data);
