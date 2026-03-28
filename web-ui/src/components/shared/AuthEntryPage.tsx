"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { ArrowRight, CreditCard, LogOut, ShieldCheck, UserCircle2 } from "lucide-react";
import { ApiError, getCurrentUser, loginUser, logoutUser, registerUser } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import BiliAuthModal from "./BiliAuthModal";
import { authCopy } from "./bili-auth-copy";

type AuthMode = "login" | "register";

type Props = {
  initialMode: AuthMode;
  routeMode?: boolean;
  onRequestClose?: () => void;
};

export default function AuthEntryPage({ initialMode, routeMode = true, onRequestClose }: Props) {
  const router = useRouter();
  const {
    portalAuth,
    setPortalAuthFromToken,
    setPortalProfile,
    clearPortalAuth,
    setAuthOpen,
    showToast,
  } = useAppStore();

  const [mode, setMode] = useState<AuthMode>(initialMode);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [nickname, setNickname] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    setMode(initialMode);
  }, [initialMode]);

  const title = useMemo(() => (mode === "register" ? "创建主账号" : "登录主账号"), [mode]);
  const showUpgradePanel = Boolean(portalAuth && !portalAuth.isAdmin && !portalAuth.isPremium);

  function handleClose() {
    setMessage("");
    if (routeMode) {
      router.push("/");
      return;
    }
    setAuthOpen(false);
    onRequestClose?.();
  }

  function handleModeChange(nextMode: AuthMode) {
    if (submitting) {
      return;
    }
    setMode(nextMode);
    setMessage("");
    if (routeMode) {
      router.replace(nextMode === "login" ? "/login" : "/register");
      return;
    }
    setAuthOpen(true, nextMode);
  }

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
        setPortalProfile({
          nickname: profile.nickname,
          status: profile.status,
          isAdmin: profile.is_admin,
          isPremium: profile.is_premium,
          role: profile.role,
          premiumExpiresAt: profile.premium_expires_at,
        });
      } catch {
        setPortalProfile({
          nickname: null,
          status: "active",
          isAdmin: false,
          isPremium: false,
          role: "user",
          premiumExpiresAt: null,
        });
      }

      setAuthOpen(false);
      router.push("/announcements");
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : "操作失败，请稍后重试");
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
      setAuthOpen(false);
      showToast("已退出登录", "当前会话已结束", "info");
      if (routeMode) {
        router.push("/");
      }
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : "退出失败，请稍后重试");
    } finally {
      setSubmitting(false);
    }
  }

  function handleUnavailable() {
    setMessage(`${authCopy.unavailableTitle}：${authCopy.unavailableBody}`);
  }

  return (
    <BiliAuthModal mode={mode} onClose={handleClose}>
      <div className="mx-auto max-w-[560px]">
        <div className="mb-5 flex items-center justify-between pr-8">
          <h3 className="text-2xl font-black text-slate-900">{portalAuth ? "当前会话" : title}</h3>
          {!portalAuth ? (
            <div className="inline-flex rounded-full border border-black/5 bg-slate-100 p-1 text-xs font-semibold">
              <button
                type="button"
                onClick={() => handleModeChange("login")}
                className={`rounded-full px-3 py-1.5 transition-colors ${
                  mode === "login" ? "bg-white text-slate-900 shadow" : "text-slate-500"
                }`}
              >
                {authCopy.loginTabs[0]}
              </button>
              <button
                type="button"
                onClick={handleUnavailable}
                className="rounded-full px-3 py-1.5 text-slate-500 transition-colors hover:text-slate-700"
              >
                {authCopy.loginTabs[1]}
              </button>
              <button
                type="button"
                onClick={() => handleModeChange(mode === "login" ? "register" : "login")}
                className="rounded-full px-3 py-1.5 text-slate-500 transition-colors hover:text-slate-700"
              >
                {mode === "login" ? "去注册" : "去登录"}
              </button>
            </div>
          ) : null}
        </div>

        {portalAuth ? (
          <div className="space-y-4">
            <div className="bili-surface p-4">
              <div className="flex items-center gap-3">
                <div className="rounded-2xl border border-sky-100 bg-sky-50 p-3 text-sky-600">
                  <UserCircle2 size={22} />
                </div>
                <div>
                  <div className="text-xs uppercase tracking-[0.2em] text-slate-400">当前账号</div>
                  <div className="mt-1 text-lg font-bold text-slate-900">{portalAuth.nickname || portalAuth.username}</div>
                </div>
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <div className="rounded-xl border border-black/5 bg-slate-50 p-3">
                  <div className="text-xs uppercase tracking-[0.2em] text-slate-400">角色</div>
                  <div className="mt-1 text-base font-semibold text-slate-800">{portalAuth.role}</div>
                </div>
                <div className="rounded-xl border border-black/5 bg-slate-50 p-3">
                  <div className="text-xs uppercase tracking-[0.2em] text-slate-400">状态</div>
                  <div className="mt-1 text-base font-semibold text-slate-800">{portalAuth.status}</div>
                </div>
              </div>
            </div>

            {showUpgradePanel ? (
              <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
                <div className="text-xs uppercase tracking-[0.24em] text-amber-500">Membership</div>
                <div className="mt-2 text-base font-bold text-amber-900">会员入口已迁到账号中心</div>
                <p className="mt-2 text-sm leading-7 text-amber-800/80">当前认证页只保留会话入口，订单与权益统一在个人空间处理。</p>
                <Link
                  href="/account?tab=account&panel=billing"
                  onClick={() => setAuthOpen(false)}
                  className="mt-3 inline-flex items-center gap-2 rounded-xl bg-amber-400 px-3 py-2 text-sm font-semibold text-amber-950 transition-colors hover:bg-amber-300"
                >
                  <CreditCard size={15} />
                  去开通会员
                </Link>
              </div>
            ) : null}

            <div className="grid gap-3 sm:grid-cols-3">
              <Link
                href="/account"
                onClick={() => setAuthOpen(false)}
                className="rounded-xl border border-black/5 bg-white px-3 py-2 text-center text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-50"
              >
                账号中心
              </Link>
              <Link
                href="/announcements"
                onClick={() => setAuthOpen(false)}
                className="rounded-xl border border-black/5 bg-white px-3 py-2 text-center text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-50"
              >
                公告汇总
              </Link>
              <button
                type="button"
                onClick={handleLogout}
                disabled={submitting}
                className="inline-flex items-center justify-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm font-semibold text-rose-600 transition-colors hover:bg-rose-100 disabled:opacity-70"
              >
                <LogOut size={15} />
                退出登录
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-3">
              <StatChip label="主账号" value="统一登录" />
              <StatChip label="权益" value="会员独立" />
              <StatChip label="安全" value="可追踪" />
            </div>

            <input
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              type="text"
              autoComplete="username"
              placeholder="用户名（3-64位）"
              className="w-full rounded-xl border border-black/10 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition-colors focus:border-sky-300"
            />

            {mode === "register" ? (
              <input
                value={nickname}
                onChange={(event) => setNickname(event.target.value)}
                type="text"
                maxLength={120}
                placeholder="昵称（选填）"
                className="w-full rounded-xl border border-black/10 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition-colors focus:border-sky-300"
              />
            ) : null}

            <input
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              type="password"
              autoComplete={mode === "register" ? "new-password" : "current-password"}
              placeholder="密码（至少8位）"
              className="w-full rounded-xl border border-black/10 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition-colors focus:border-sky-300"
            />

            <div className="grid gap-2 sm:grid-cols-2">
              <button
                type="button"
                onClick={handleUnavailable}
                className="rounded-xl border border-black/10 bg-slate-50 px-3 py-3 text-sm font-semibold text-slate-600 transition-colors hover:bg-slate-100"
              >
                微信登录（预留）
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="inline-flex items-center justify-center gap-2 rounded-xl bg-[linear-gradient(90deg,#fb7299,#00aeec)] px-3 py-3 text-sm font-semibold text-white disabled:opacity-70"
              >
                <ArrowRight size={16} />
                {submitting ? "提交中..." : mode === "register" ? "创建账户并登录" : "登录并进入"}
              </button>
            </div>

            <div className="rounded-xl border border-black/5 bg-slate-50 p-3 text-xs leading-6 text-slate-500">
              认证完成后，会员、通知、绑定和安全设置统一在个人空间处理。
            </div>
          </form>
        )}

        {message ? (
          <p className="mt-4 rounded-xl border border-black/10 bg-slate-50 px-3 py-2 text-sm text-slate-600">{message}</p>
        ) : null}
      </div>
    </BiliAuthModal>
  );
}

function StatChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-black/5 bg-slate-50 px-3 py-2">
      <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">{label}</div>
      <div className="mt-1 inline-flex items-center gap-1 text-sm font-semibold text-slate-700">
        <ShieldCheck size={14} className="text-sky-500" />
        {value}
      </div>
    </div>
  );
}
