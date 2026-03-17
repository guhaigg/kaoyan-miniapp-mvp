import { api, type SubscriptionItem, type SubscriptionListResponse, type SubscriptionType } from "@/lib/api";

type CreateSubscriptionPayload = {
  subscription_type: SubscriptionType;
  value: string;
  category?: "all" | "announcement" | "adjustment";
};

export const fetchSubscriptions = () =>
  api.get<SubscriptionListResponse>("/subscriptions").then((response) => response.data);

export const createSubscriptionEntry = (payload: CreateSubscriptionPayload) =>
  api.post<SubscriptionItem>("/subscriptions", payload).then((response) => response.data);

export const removeSubscriptionEntry = (subscriptionId: string) =>
  api.delete<{ status: "ok" }>(`/subscriptions/${encodeURIComponent(subscriptionId)}`).then((response) => response.data);
