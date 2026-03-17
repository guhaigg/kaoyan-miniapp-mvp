"use client";

import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, Download, ShieldAlert, UserCog } from "lucide-react";
import ActivityChart from "@/components/admin/ActivityChart";
import {
  ApiError,
  adminAudits,
  adminLogin,
  adminLogout,
  adminMe,
  adminPromoteUser,
  adminUsers,
  healthCheck,
} from "@/lib/api";

export default function AdminPage() {
  const queryClient = useQueryClient();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [promotingId, setPromotingId] = useState<string | null>(null);

  const meQuery = useQuery({
    queryKey: ["admin", "me"],
    queryFn: adminMe,
    retry: false,
  });
  const isAuthenticated = meQuery.isSuccess && meQuery.data.authenticated;

  const healthQuery = useQuery({
    queryKey: ["admin", "health"],
    queryFn: healthCheck,
    refetchInterval: 20_000,
  });

  const usersQuery = useQuery({
    queryKey: ["admin", "users"],
    queryFn: () => adminUsers({ page: 1, page_size: 10 }),
    enabled: isAuthenticated,
  });

  const auditsQuery = useQuery({
    queryKey: ["admin", "audits"],
    queryFn: () => adminAudits({ page: 1, page_size: 24, prefix: "admin." }),
    enabled: isAuthenticated,
  });

  const loginMutation = useMutation({
    mutationFn: adminLogin,
    onSuccess: async () => {
      setMessage("管理员登录成功");
      setPassword("");
      await queryClient.invalidateQueries({ queryKey: ["admin", "me"] });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["admin", "users"] }),
        queryClient.invalidateQueries({ queryKey: ["admin", "audits"] }),
      ]);
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        setMessage(`登录失败：${error.message}`);
      } else {
        setMessage("登录失败，请稍后重试");
      }
    },
  });

  const logoutMutation = useMutation({
    mutationFn: adminLogout,
    onSuccess: async () => {
      setMessage("已退出管理员会话");
      await queryClient.invalidateQueries({ queryKey: ["admin", "me"] });
      queryClient.removeQueries({ queryKey: ["admin", "users"] });
      queryClient.removeQueries({ queryKey: ["admin", "audits"] });
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        setMessage(`退出失败：${error.message}`);
      } else {
        setMessage("退出失败，请稍后重试");
      }
    },
  });

  const promoteMutation = useMutation({
    mutationFn: (userId: string) => adminPromoteUser(userId),
    onSuccess: async () => {
      setMessage("用户已提升为管理员");
      await queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
      await queryClient.invalidateQueries({ queryKey: ["admin", "audits"] });
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        setMessage(`提升失败：${error.message}`);
      } else {
        setMessage("提升失败，请稍后重试");
      }
    },
    onSettled: () => setPromotingId(null),
  });

  const dashboard = useMemo(() => {
    const audits = auditsQuery.data?.items || [];
    const urgentCount = audits.filter((item) => item.event_type.includes("offline")).length;
    const activeServices = (healthQuery.data?.db === "up" ? 1 : 0) + (healthQuery.data?.redis === "up" ? 1 : 0);
    const chartPoints = buildChartPoints(audits);
    const firstHalf = average(chartPoints.slice(0, 6));
    const secondHalf = average(chartPoints.slice(6));
    const trend = firstHalf === 0 ? 100 : ((secondHalf - firstHalf) / firstHalf) * 100;
    return {
      requests: auditsQuery.data?.total ?? 0,
      urgentCount,
      activeServices,
      dbState: healthQuery.data?.db || "--",
      redisState: healthQuery.data?.redis || "--",
      audits,
      chartPoints,
      trend,
    };
  }, [auditsQuery.data, healthQuery.data]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.98 }}
      transition={{ duration: 0.4 }}
      className="mx-auto max-w-6xl px-4 pb-20 pt-10"
    >
      <div className="mb-8 flex items-center justify-between text-white">
        <h2 className="text-3xl font-bold tracking-tight">爬虫阵列中控</h2>
        {isAuthenticated ? (
          <button
            type="button"
            onClick={() => logoutMutation.mutate()}
            className="flex items-center gap-2 rounded-xl bg-white/10 px-5 py-2.5 text-sm font-medium transition-colors hover:bg-white/20 active:scale-95"
          >
            <Download size={16} /> 退出管理员
          </button>
        ) : null}
      </div>

      {!isAuthenticated ? (
        <div className="mb-8 rounded-3xl border border-white/10 bg-white/5 p-6 shadow-xl backdrop-blur-xl">
          <div className="mb-4 flex items-center gap-2 text-white">
            <ShieldAlert className="text-cyan-400" size={20} />
            <h3 className="text-lg font-semibold">管理员登录</h3>
          </div>
          <div className="grid gap-3 md:grid-cols-[1fr_1fr_auto]">
            <input
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              placeholder="管理员用户名"
              className="rounded-xl border border-white/10 bg-black/30 px-4 py-3 text-white outline-none transition-colors focus:border-cyan-400"
            />
            <input
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              type="password"
              placeholder="管理员密码"
              className="rounded-xl border border-white/10 bg-black/30 px-4 py-3 text-white outline-none transition-colors focus:border-cyan-400"
            />
            <button
              type="button"
              onClick={() => {
                setMessage("");
                loginMutation.mutate({ username, password });
              }}
              disabled={loginMutation.isPending}
              className="rounded-xl bg-cyan-500 px-6 py-3 font-semibold text-white transition-colors hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-70"
            >
              {loginMutation.isPending ? "登录中..." : "登录"}
            </button>
          </div>
          {message ? <p className="mt-3 text-sm text-slate-300">{message}</p> : null}
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-6 md:grid-cols-4">
        <div className="overflow-hidden rounded-3xl border border-white/10 bg-white/5 p-6 shadow-xl backdrop-blur-xl md:col-span-2">
          <div className="flex items-start justify-between">
            <div>
              <div className="mb-1 font-mono text-xs uppercase tracking-wider text-slate-400">
                24H 爬虫全网吞吐量 (Requests)
              </div>
              <div className="text-4xl font-bold text-white">{dashboard.requests}</div>
            </div>
            <span className="rounded-md border border-cyan-500/30 bg-cyan-500/20 px-2 py-1 text-xs text-cyan-400">
              {dashboard.trend >= 0 ? "+" : ""}
              {dashboard.trend.toFixed(1)}%
            </span>
          </div>
          <ActivityChart dataPoints={dashboard.chartPoints} />
        </div>

        <div className="flex flex-col justify-between rounded-3xl border border-orange-500/30 bg-orange-950/20 p-6 shadow-xl backdrop-blur-xl">
          <div className="mb-2 font-mono text-xs uppercase tracking-wider text-slate-400">
            Urgent Alerts
          </div>
          <div className="font-mono text-4xl font-bold text-orange-400">{dashboard.urgentCount}</div>
          <div className="mt-4 text-xs text-slate-400">离线事件和异常告警会在这里累计。</div>
        </div>

        <div className="flex flex-col justify-between rounded-3xl border border-white/10 bg-white/5 p-6 shadow-xl backdrop-blur-xl">
          <div className="mb-2 font-mono text-xs uppercase tracking-wider text-slate-400">
            Service Status
          </div>
          <div className={`font-mono text-4xl font-bold ${dashboard.activeServices === 2 ? "text-cyan-400" : "text-yellow-400"}`}>
            {dashboard.activeServices}/2
          </div>
          <div className="mt-4 text-xs text-slate-400">
            DB {dashboard.dbState.toUpperCase()} · Redis {dashboard.redisState.toUpperCase()}
          </div>
        </div>

        <div className="rounded-3xl border border-white/10 bg-black/40 p-6 shadow-2xl md:col-span-2">
          <h3 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
            <UserCog size={18} className="text-cyan-400" />
            用户管理（最近 10 条）
          </h3>
          <div className="space-y-3">
            {(usersQuery.data?.items || []).map((item) => (
              <div
                key={item.id}
                className="flex items-center justify-between rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3"
              >
                <div>
                  <div className="text-sm font-semibold text-white">{item.nickname || item.username}</div>
                  <div className="text-xs text-slate-400">
                    {item.username} · {item.status}
                  </div>
                </div>
                {item.is_admin ? (
                  <span className="rounded-md border border-cyan-500/30 bg-cyan-500/10 px-2 py-1 text-xs text-cyan-300">
                    管理员
                  </span>
                ) : (
                  <button
                    type="button"
                    disabled={promotingId === item.id}
                    onClick={() => {
                      setPromotingId(item.id);
                      promoteMutation.mutate(item.id);
                    }}
                    className="rounded-md border border-white/20 bg-white/10 px-2 py-1 text-xs text-white transition-colors hover:bg-white/20 disabled:cursor-not-allowed disabled:opacity-70"
                  >
                    {promotingId === item.id ? "处理中..." : "提升为管理员"}
                  </button>
                )}
              </div>
            ))}
            {isAuthenticated && usersQuery.isLoading ? (
              <div className="text-sm text-slate-400">正在加载用户列表...</div>
            ) : null}
          </div>
        </div>

        <div className="rounded-3xl border border-white/10 bg-black/40 p-6 shadow-2xl md:col-span-2">
          <h3 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
            <Activity size={18} className="text-cyan-400" />
            审计事件（admin.*）
          </h3>
          <div className="space-y-2">
            {dashboard.audits.map((item) => (
              <div key={item.id} className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3">
                <div className="mb-1 text-sm font-medium text-cyan-300">{item.event_type}</div>
                <div className="text-xs text-slate-400">
                  {new Date(item.created_at).toLocaleString("zh-CN", { hour12: false })}
                </div>
              </div>
            ))}
            {isAuthenticated && auditsQuery.isLoading ? (
              <div className="text-sm text-slate-400">正在拉取审计日志...</div>
            ) : null}
          </div>
        </div>

        <div className="mt-2 overflow-hidden rounded-3xl border border-white/10 bg-black/40 shadow-2xl md:col-span-4">
          <div className="flex items-center gap-2 border-b border-white/10 bg-black/60 px-6 py-4">
            <div className="flex gap-2">
              <div className="h-3 w-3 rounded-full bg-red-500/80" />
              <div className="h-3 w-3 rounded-full bg-yellow-500/80" />
              <div className="h-3 w-3 rounded-full bg-green-500/80" />
            </div>
            <span className="ml-4 font-mono text-xs text-slate-500">
              health status · app={healthQuery.data?.app_env || "--"} · db={dashboard.dbState} · redis={dashboard.redisState}
            </span>
          </div>
          <div className="h-60 overflow-y-auto p-6 font-mono text-sm leading-relaxed text-slate-300">
            {dashboard.audits.length === 0 ? (
              <div className="text-slate-400">暂无审计日志，登录并执行管理员动作后会出现。</div>
            ) : (
              dashboard.audits.map((item) => (
                <div key={item.id} className="mb-2">
                  <span className="text-slate-500">
                    [{new Date(item.created_at).toLocaleTimeString("zh-CN", { hour12: false })}]
                  </span>{" "}
                  <span className="text-cyan-300">{item.event_type}</span> · {item.endpoint}
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {message ? (
        <div className="mt-6 rounded-2xl border border-white/10 bg-black/30 p-4 text-sm text-slate-300">
          {message}
        </div>
      ) : null}
    </motion.div>
  );
}

function buildChartPoints(
  audits: Array<{
    created_at: string;
  }>,
) {
  if (audits.length === 0) {
    return [20, 35, 25, 60, 85, 45, 90, 120, 105, 140, 110, 160];
  }

  const now = Date.now();
  const buckets = new Array(12).fill(0);

  audits.forEach((item) => {
    const diffHours = (now - new Date(item.created_at).getTime()) / 3_600_000;
    const bucket = 11 - Math.min(11, Math.max(0, Math.floor(diffHours / 2)));
    buckets[bucket] += 1;
  });

  return buckets.map((value, index) => value * 18 + 18 + index * 2);
}

function average(values: number[]) {
  if (values.length === 0) return 0;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}
