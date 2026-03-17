"use client";

import { FormEvent, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { BellRing, Star, X } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  NotificationEventItem,
  createSubscription,
  deleteSubscription,
  getCurrentUser,
  listPendingNotifications,
  listSubscriptions,
  loginUser,
  logoutUser,
  registerUser,
} from "@/lib/api";
import { useAppStore } from "@/lib/store";

export default function Modals() {
  const queryClient = useQueryClient();
  const {
    isAuthOpen,
    setAuthOpen,
    isWatchlistOpen,
    setWatchlistOpen,
    portalAuth,
    setPortalAuthFromToken,
    setPortalProfile,
    clearPortalAuth,
  } = useAppStore();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [nickname, setNickname] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState("");
  const [watchType, setWatchType] = useState<"school" | "major" | "keyword" | "region">("school");
  const [watchValue, setWatchValue] = useState("");

  const submitLabel = useMemo(
    () => (mode === "register" ? "创建账户并登录" : "确认授权"),
    [mode],
  );
  const noticeQueryKey = useMemo(
    () => ["portal", "watchlistNotices", portalAuth?.userId] as const,
    [portalAuth?.userId],
  );

  const subscriptionsQuery = useQuery({
    queryKey: ["portal", "subscriptions", portalAuth?.userId],
    queryFn: () => listSubscriptions(portalAuth!.accessToken),
    enabled: Boolean(portalAuth?.accessToken) && isWatchlistOpen,
  });

  const realtimeNoticesQuery = useQuery({
    queryKey: noticeQueryKey,
    queryFn: async () => {
      if (!portalAuth?.accessToken) return [] as NotificationEventItem[];
      const response = await listPendingNotifications(portalAuth.accessToken);
      const existing = queryClient.getQueryData<NotificationEventItem[]>(noticeQueryKey) || [];
      return mergeNoticeList(existing, response.items);
    },
    enabled: Boolean(portalAuth?.accessToken) && isWatchlistOpen,
    refetchOnWindowFocus: false,
  });

  const createSubscriptionMutation = useMutation({
    mutationFn: async (payload: { subscription_type: "school" | "major" | "keyword" | "region"; value: string }) => {
      if (!portalAuth?.accessToken) {
        throw new ApiError("请先登录后再添加关注", 401, null);
      }
      return createSubscription({ ...payload, category: "all" }, portalAuth.accessToken);
    },
    onSuccess: async () => {
      setWatchValue("");
      await queryClient.invalidateQueries({ queryKey: ["portal", "subscriptions", portalAuth?.userId] });
    },
  });

  const deleteSubscriptionMutation = useMutation({
    mutationFn: async (subscriptionId: string) => {
      if (!portalAuth?.accessToken) {
        throw new ApiError("请先登录后再管理关注库", 401, null);
      }
      return deleteSubscription(subscriptionId, portalAuth.accessToken);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["portal", "subscriptions", portalAuth?.userId] });
    },
  });

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;

    if (username.trim().length < 3) {
      setMessage("用户名至少 3 位");
      return;
    }
    if (password.length < 8) {
      setMessage("密码至少 8 位");
      return;
    }

    setSubmitting(true);
    setMessage("");
    try {
      if (mode === "register") {
        await registerUser({
          username: username.trim(),
          password,
          nickname: nickname.trim() || undefined,
        });
      }

      const login = await loginUser({
        username: username.trim(),
        password,
      });
      setPortalAuthFromToken({
        tokenType: login.token_type,
        accessToken: login.access_token,
        expiresIn: login.expires_in,
        refreshExpiresIn: login.refresh_expires_in,
        userId: login.user_id,
        username: login.username,
      });

      try {
        const profile = await getCurrentUser(login.access_token);
        setPortalProfile({ nickname: profile.nickname, status: profile.status });
      } catch {
        setPortalProfile({ nickname: null, status: "active" });
      }

      setMessage(mode === "register" ? "注册并登录成功" : "登录成功");
      setTimeout(() => {
        setAuthOpen(false);
      }, 350);
    } catch (error) {
      if (error instanceof ApiError) {
        setMessage(`操作失败：${error.message}`);
      } else {
        setMessage("操作失败，请稍后重试");
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function handleLogout() {
    setSubmitting(true);
    setMessage("");
    try {
      await logoutUser();
      clearPortalAuth();
      setMessage("已退出登录");
    } catch (error) {
      if (error instanceof ApiError) {
        setMessage(`退出失败：${error.message}`);
      } else {
        setMessage("退出失败，请稍后重试");
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCreateSubscription() {
    const value = watchValue.trim();
    if (!value) {
      setMessage("请输入你要关注的关键词或院校");
      return;
    }
    try {
      setMessage("");
      await createSubscriptionMutation.mutateAsync({
        subscription_type: watchType,
        value,
      });
      setMessage("卡片已归档。");
    } catch (error) {
      if (error instanceof ApiError) {
        setMessage(`操作失败：${error.message}`);
      } else {
        setMessage("操作失败，请稍后重试");
      }
    }
  }

  async function handleDeleteSubscription(subscriptionId: string) {
    try {
      setMessage("");
      await deleteSubscriptionMutation.mutateAsync(subscriptionId);
      setMessage("已移出归档。");
    } catch (error) {
      if (error instanceof ApiError) {
        setMessage(`操作失败：${error.message}`);
      } else {
        setMessage("操作失败，请稍后重试");
      }
    }
  }

  return (
    <>
      <AnimatePresence>
        {isAuthOpen ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] flex items-center justify-center p-4"
          >
            <div
              className="absolute inset-0 bg-black/60 backdrop-blur-md"
              onClick={() => setAuthOpen(false)}
            />
            <motion.div
              initial={{ scale: 0.95, y: 20 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.95, y: 20 }}
              transition={{ type: "spring", bounce: 0.3 }}
              className="relative z-10 w-full max-w-md rounded-3xl border border-white/10 bg-slate-900/80 p-10 shadow-2xl backdrop-blur-2xl"
            >
              <button
                onClick={() => setAuthOpen(false)}
                className="absolute right-6 top-6 text-slate-400 transition-colors hover:text-white"
              >
                <X size={20} />
              </button>
              <div className="mb-8 flex justify-center">
                <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-white drop-shadow-[0_0_20px_rgba(255,255,255,0.2)]">
                  <span className="text-4xl font-black tracking-tighter text-[#2c3e50]">GW</span>
                </div>
              </div>
              <h3 className="mb-8 text-center text-2xl font-bold text-white">接入系统</h3>
              <div className="mb-4 grid grid-cols-2 overflow-hidden rounded-xl border border-white/10 bg-black/30 p-1">
                <button
                  type="button"
                  onClick={() => {
                    setMode("register");
                    setMessage("");
                  }}
                  className={`rounded-lg px-3 py-2 text-sm transition-colors ${
                    mode === "register"
                      ? "bg-cyan-500 text-white"
                      : "text-slate-300 hover:bg-white/10"
                  }`}
                >
                  创建账户
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setMode("login");
                    setMessage("");
                  }}
                  className={`rounded-lg px-3 py-2 text-sm transition-colors ${
                    mode === "login"
                      ? "bg-cyan-500 text-white"
                      : "text-slate-300 hover:bg-white/10"
                  }`}
                >
                  登录账户
                </button>
              </div>

              {portalAuth ? (
                <div className="space-y-4">
                  <div className="rounded-xl border border-white/10 bg-black/30 p-4 text-sm text-slate-200">
                    当前账号：{portalAuth.nickname || portalAuth.username}
                  </div>
                  <button
                    type="button"
                    onClick={handleLogout}
                    disabled={submitting}
                    className="w-full rounded-xl border border-white/20 bg-white/10 py-3 font-semibold text-white transition-all hover:bg-white/20 disabled:cursor-not-allowed disabled:opacity-70"
                  >
                    {submitting ? "处理中..." : "退出登录"}
                  </button>
                </div>
              ) : (
                <form onSubmit={handleSubmit} className="space-y-4">
                  <input
                    value={username}
                    onChange={(event) => setUsername(event.target.value)}
                    type="text"
                    autoComplete="username"
                    placeholder="用户名（3-64位）"
                    className="w-full rounded-xl border border-white/10 bg-black/40 px-5 py-4 text-white outline-none transition-colors focus:border-cyan-400"
                  />
                  {mode === "register" ? (
                    <input
                      value={nickname}
                      onChange={(event) => setNickname(event.target.value)}
                      type="text"
                      maxLength={120}
                      placeholder="昵称（选填）"
                      className="w-full rounded-xl border border-white/10 bg-black/40 px-5 py-4 text-white outline-none transition-colors focus:border-cyan-400"
                    />
                  ) : null}
                  <input
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    type="password"
                    autoComplete={mode === "register" ? "new-password" : "current-password"}
                    placeholder="密码（至少8位）"
                    className="w-full rounded-xl border border-white/10 bg-black/40 px-5 py-4 text-white outline-none transition-colors focus:border-cyan-400"
                  />
                  <button
                    disabled={submitting}
                    className="mt-6 w-full rounded-xl bg-white py-4 font-bold text-black shadow-[0_0_20px_rgba(255,255,255,0.1)] transition-all hover:bg-cyan-400 hover:text-white active:scale-95 disabled:cursor-not-allowed disabled:opacity-70"
                  >
                    {submitting ? "提交中..." : submitLabel}
                  </button>
                </form>
              )}
              {message ? (
                <p className="mt-4 rounded-lg border border-white/10 bg-black/30 px-4 py-2 text-xs text-slate-300">
                  {message}
                </p>
              ) : null}
            </motion.div>
          </motion.div>
        ) : null}
      </AnimatePresence>

      <AnimatePresence>
        {isWatchlistOpen ? (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-[90] bg-black/40 backdrop-blur-sm"
              onClick={() => setWatchlistOpen(false)}
            />
            <motion.div
              initial={{ x: "100%" }}
              animate={{ x: 0 }}
              exit={{ x: "100%" }}
              transition={{ type: "spring", bounce: 0, duration: 0.4 }}
              className="fixed right-0 top-0 z-[100] flex h-full w-80 flex-col border-l border-white/10 bg-slate-900/95 shadow-[-20px_0_50px_rgba(0,0,0,0.5)] backdrop-blur-2xl md:w-96"
            >
              <div className="flex items-center justify-between border-b border-white/10 p-6 text-white">
                <h3 className="flex items-center gap-2 text-lg font-bold">
                  <Star className="text-yellow-400" size={20} /> 我的关注库
                </h3>
                <button
                  onClick={() => setWatchlistOpen(false)}
                  className="text-slate-400 transition-colors hover:text-white"
                >
                  <X size={20} />
                </button>
              </div>
              <div className="flex-1 space-y-4 overflow-y-auto p-4">
                {portalAuth ? (
                  <>
                    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                      <div className="mb-3 flex items-center gap-2 text-xs text-slate-400">
                        <BellRing size={14} />
                        添加新关注
                      </div>
                      <div className="mb-2 grid grid-cols-4 gap-2">
                        {[
                          { key: "school", label: "院校" },
                          { key: "major", label: "专业" },
                          { key: "keyword", label: "关键词" },
                          { key: "region", label: "地区" },
                        ].map((x) => (
                          <button
                            key={x.key}
                            type="button"
                            onClick={() => setWatchType(x.key as "school" | "major" | "keyword" | "region")}
                            className={`rounded-lg px-2 py-1.5 text-xs transition-colors ${
                              watchType === x.key
                                ? "bg-cyan-500 text-white"
                                : "bg-white/5 text-slate-300 hover:bg-white/10"
                            }`}
                          >
                            {x.label}
                          </button>
                        ))}
                      </div>
                      <div className="flex gap-2">
                        <input
                          value={watchValue}
                          onChange={(event) => setWatchValue(event.target.value)}
                          placeholder="例如：电子科技大学 / 0854 / 复试线"
                          className="flex-1 rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-white outline-none focus:border-cyan-400"
                        />
                        <button
                          type="button"
                          disabled={createSubscriptionMutation.isPending}
                          onClick={handleCreateSubscription}
                          className="rounded-lg bg-cyan-500 px-3 py-2 text-sm font-semibold text-white transition-colors hover:bg-cyan-400 disabled:opacity-70"
                        >
                          添加
                        </button>
                      </div>
                    </div>

                    {subscriptionsQuery.isLoading ? (
                      <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-xs text-slate-300">
                        探针巡航中，拉取最新节点...
                      </div>
                    ) : null}

                    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                      <div className="mb-2 text-xs text-slate-400">
                        实时情报流（SSE）
                      </div>
                      {realtimeNoticesQuery.isLoading ? (
                        <div className="text-xs text-slate-300">探针巡航中，拉取最新节点...</div>
                      ) : realtimeNoticesQuery.data?.length ? (
                        <div className="space-y-2">
                          <AnimatePresence initial={false}>
                            {realtimeNoticesQuery.data.map((item) => (
                              <motion.div
                                key={item.id}
                                initial={{ opacity: 0, y: -8 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -8 }}
                                transition={{ duration: 0.2 }}
                                className="rounded-xl border border-white/10 bg-black/30 p-3"
                              >
                                <div className="text-sm text-white">
                                  {formatNoticeTitle(item)}
                                </div>
                                <div className="mt-1 text-xs text-slate-400">
                                  {formatNoticeSubline(item)}
                                </div>
                              </motion.div>
                            ))}
                          </AnimatePresence>
                        </div>
                      ) : (
                        <div className="text-xs text-slate-300">暂无最新公告。底层探针正在持续观测。</div>
                      )}
                    </div>

                    {subscriptionsQuery.data?.items.length ? (
                      subscriptionsQuery.data.items.map((item) => (
                        <div
                          key={item.id}
                          className="rounded-2xl border border-white/10 bg-white/5 p-4 transition-colors hover:bg-white/10"
                        >
                          <div className="mb-2 flex items-center justify-between">
                            <div className="flex items-center gap-2 font-mono text-xs text-cyan-400">
                              <BellRing size={12} />
                              正在监控 · {watchTypeLabel(item.subscription_type)}
                            </div>
                            <button
                              type="button"
                              disabled={deleteSubscriptionMutation.isPending}
                              onClick={() => handleDeleteSubscription(item.id)}
                              className="rounded-md border border-white/20 px-2 py-1 text-[11px] text-slate-300 transition-colors hover:bg-white/10"
                            >
                              移除
                            </button>
                          </div>
                          <div className="mb-2 text-sm font-medium text-white">{item.value}</div>
                          <div className="text-xs text-slate-400">
                            类别：{item.category} · 创建于{" "}
                            {new Date(item.created_at).toLocaleString("zh-CN", { hour12: false })}
                          </div>
                        </div>
                      ))
                    ) : subscriptionsQuery.isSuccess ? (
                      <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-xs text-slate-300">
                        暂无归档。将有价值的卡片留存于此。
                      </div>
                    ) : null}
                  </>
                ) : (
                  <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-xs text-slate-300">
                    执行归档（收藏）或个性化订阅，需要建立身份映射。请先登录后再管理关注库。
                  </div>
                )}

                <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-xs text-slate-300">
                  {portalAuth
                    ? `当前登录：${portalAuth.nickname || portalAuth.username}`
                    : "登录后可同步你的关注列表与检索偏好。"}
                </div>
              </div>
            </motion.div>
          </>
        ) : null}
      </AnimatePresence>
    </>
  );
}

function watchTypeLabel(type: string) {
  if (type === "school") return "院校";
  if (type === "major") return "专业";
  if (type === "keyword") return "关键词";
  if (type === "region") return "地区";
  return "未知";
}

function mergeNoticeList(base: NotificationEventItem[], incoming: NotificationEventItem[]) {
  const map = new Map<string, NotificationEventItem>();
  for (const item of base) {
    map.set(item.id, item);
  }
  for (const item of incoming) {
    if (!map.has(item.id)) {
      map.set(item.id, item);
    }
  }
  return Array.from(map.values()).sort((a, b) => {
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
  });
}

function formatNoticeTitle(item: NotificationEventItem) {
  const school = item.payload.school_name || "未知院校";
  const category = item.payload.category === "adjustment" ? "调剂更新" : "公告更新";
  return `${school} · ${category}`;
}

function formatNoticeSubline(item: NotificationEventItem) {
  const title = item.payload.title || "无标题";
  const major = item.payload.major ? ` · ${item.payload.major}` : "";
  const time = new Date(item.created_at).toLocaleString("zh-CN", { hour12: false });
  return `${title}${major} · ${time}`;
}
