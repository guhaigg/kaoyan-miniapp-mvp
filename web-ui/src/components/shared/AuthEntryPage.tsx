"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useMemo, useState } from "react";
import { ArrowRight, CreditCard, LogOut, UserCircle2 } from "lucide-react";
import { ApiError, getCurrentUser, loginUser, logoutUser, registerUser } from "@/lib/api";
import { useAppStore } from "@/lib/store";

type AuthMode = "login" | "register";

export default function AuthEntryPage({ initialMode }: { initialMode: AuthMode }) {
  const router = useRouter();
  const { portalAuth, setPortalAuthFromToken, setPortalProfile, clearPortalAuth } = useAppStore();
  const [mode, setMode] = useState<AuthMode>(initialMode);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [nickname, setNickname] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const title = useMemo(() => (mode === "register" ? "创建账户" : "登录账户"), [mode]);
  const switchHref = mode === "register" ? "/login" : "/register";
  const switchLabel = mode === "register" ? "已有账号，去登录" : "没有账号，去注册";
  const showUpgradePanel = Boolean(portalAuth && !portalAuth.isAdmin && !portalAuth.isPremium);
  const shellItems = [
    {
      title: "登录",
      description: "恢复主账号会话，进入检索、收藏和通知体系。",
      active: mode === "login",
      href: "/login",
    },
    {
      title: "注册",
      description: "先创建主账号，再进入后续的支付、绑定和通知设置。",
      active: mode === "register",
      href: "/register",
    },
    {
      title: "退出",
      description: "退出控制不再埋在小弹窗里，登录后会在这里和账号侧栏稳定出现。",
      active: Boolean(portalAuth),
      href: "/account/security",
    },
  ];

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

      router.push("/search");
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
      setMessage("已退出登录");
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : "退出失败，请稍后重试");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-[calc(100vh-10rem)] max-w-7xl items-center px-4 py-10 text-white">
      <div className="grid w-full gap-8 xl:grid-cols-[320px_minmax(0,1fr)]">
        <aside className="rounded-[2rem] border border-white/10 bg-[linear-gradient(180deg,rgba(7,11,21,0.96),rgba(5,10,19,0.98))] p-5 shadow-2xl backdrop-blur-xl">
          <div className="rounded-[1.6rem] border border-cyan-500/20 bg-cyan-500/10 p-5">
            <div className="font-mono text-xs uppercase tracking-[0.24em] text-cyan-300">GeWu Auth</div>
            <h1 className="mt-3 text-3xl font-black leading-tight">
              {portalAuth ? "当前会话已接入" : mode === "register" ? "创建主账号" : "登录主账号"}
            </h1>
            <p className="mt-3 text-sm leading-7 text-slate-200">
              这里现在只做认证入口和会话控制。会员、订单、通知、绑定和安全设置都走稳定页面，不再塞进弹窗。
            </p>
          </div>

          <div className="mt-5 space-y-2">
            {shellItems.map((item) => (
              <Link
                key={item.title}
                href={item.href}
                onClick={() => {
                  if (item.title === "登录") setMode("login");
                  if (item.title === "注册") setMode("register");
                }}
                className={`block rounded-[1.3rem] border px-4 py-4 transition-all ${
                  item.active
                    ? "border-cyan-400/30 bg-cyan-500/10"
                    : "border-white/5 bg-white/[0.03] hover:border-white/10 hover:bg-white/[0.06]"
                }`}
              >
                <div className="text-sm font-semibold text-white">{item.title}</div>
                <div className="mt-1 text-xs leading-6 text-slate-400">{item.description}</div>
              </Link>
            ))}
          </div>

          <div className="mt-5 rounded-[1.3rem] border border-amber-400/15 bg-amber-500/10 p-4">
            <div className="text-xs uppercase tracking-[0.24em] text-amber-300">Routing</div>
            <div className="mt-2 text-sm font-semibold text-white">登录、注册、退出都回到稳定路径。</div>
            <div className="mt-2 text-xs leading-6 text-amber-50/80">
              Header、账号侧栏和安全页会同时提供这些入口，避免操作丢失。
            </div>
          </div>
        </aside>

        <section className="rounded-[2rem] border border-white/10 bg-[radial-gradient(circle_at_top_left,rgba(34,211,238,0.14),transparent_28%),linear-gradient(180deg,rgba(7,11,21,0.96),rgba(4,8,18,0.98))] p-8 shadow-2xl backdrop-blur-xl">
          <div className="mb-6 flex items-center justify-between">
            <h2 className="text-2xl font-bold text-white">{portalAuth ? "当前会话" : title}</h2>
            {!portalAuth ? (
              <Link
                href={switchHref}
                onClick={() => setMode(mode === "register" ? "login" : "register")}
                className="text-sm text-cyan-300 hover:text-cyan-200"
              >
                {switchLabel}
              </Link>
            ) : null}
          </div>

          {portalAuth ? (
            <div className="space-y-4">
              <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
                <div className="rounded-[1.6rem] border border-white/10 bg-white/[0.04] p-5">
                  <div className="flex items-center gap-3">
                    <div className="rounded-2xl border border-cyan-400/20 bg-cyan-500/10 p-3 text-cyan-200">
                      <UserCircle2 size={22} />
                    </div>
                    <div>
                      <div className="text-xs uppercase tracking-[0.22em] text-slate-400">当前账号</div>
                      <div className="mt-1 text-xl font-semibold text-white">{portalAuth.nickname || portalAuth.username}</div>
                    </div>
                  </div>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2">
                    <div className="rounded-2xl border border-white/10 bg-black/20 p-4 text-sm text-slate-200">
                      <div className="text-xs uppercase tracking-[0.22em] text-slate-400">角色</div>
                      <div className="mt-2 text-lg font-semibold text-white">{portalAuth.role}</div>
                    </div>
                    <div className="rounded-2xl border border-white/10 bg-black/20 p-4 text-sm text-slate-200">
                      <div className="text-xs uppercase tracking-[0.22em] text-slate-400">状态</div>
                      <div className="mt-2 text-lg font-semibold text-white">{portalAuth.status}</div>
                    </div>
                  </div>
                </div>
                <div className="rounded-[1.6rem] border border-white/10 bg-white/[0.04] p-5">
                  <div className="text-xs uppercase tracking-[0.22em] text-slate-400">下一步</div>
                  <div className="mt-3 space-y-3 text-sm leading-7 text-slate-300">
                    <div>长期操作进账号中心，会员和订单进支付页，退出控制在这里和账号侧栏都能找到。</div>
                    <div className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3">
                      登录和注册只是入口，不再承载整个用户中心。
                    </div>
                  </div>
                </div>
              </div>
              {showUpgradePanel ? (
                <div className="rounded-2xl border border-amber-400/20 bg-[linear-gradient(135deg,rgba(120,53,15,0.35),rgba(20,24,36,0.9))] p-5">
                  <div className="text-xs uppercase tracking-[0.28em] text-amber-300">Membership</div>
                  <div className="mt-2 text-lg font-bold text-white">会员入口已迁到账号中心。</div>
                  <div className="mt-2 text-sm leading-7 text-amber-50/85">
                    普通账户开通高级会员、查看订单和处理支付，不再堆在这个登录页里。
                  </div>
                  <Link
                    href="/account/billing"
                    className="mt-4 inline-flex items-center gap-2 rounded-xl bg-amber-500 px-4 py-3 text-sm font-semibold text-slate-950 transition-colors hover:bg-amber-400"
                  >
                    <CreditCard size={16} />
                    去账号中心开通会员
                  </Link>
                </div>
              ) : null}
              <div className="grid gap-3 sm:grid-cols-3">
                <Link
                  href="/account"
                  className="rounded-xl border border-white/20 bg-white/10 px-4 py-3 text-center text-sm font-semibold text-white transition-colors hover:bg-white/20"
                >
                  进入账号中心
                </Link>
                <Link
                  href="/account/security"
                  className="rounded-xl border border-white/20 bg-white/5 px-4 py-3 text-center text-sm font-semibold text-white transition-colors hover:bg-white/10"
                >
                  去安全设置
                </Link>
                <Link
                  href="/search"
                  className="rounded-xl border border-cyan-400/30 bg-cyan-500/10 px-4 py-3 text-center text-sm font-semibold text-cyan-100 transition-colors hover:bg-cyan-500/20"
                >
                  去检索页
                </Link>
              </div>
              <button
                type="button"
                onClick={handleLogout}
                disabled={submitting}
                className="flex w-full items-center justify-center gap-2 rounded-xl border border-red-400/25 bg-red-500/10 py-3 font-semibold text-red-50 transition-colors hover:bg-red-500/20 disabled:cursor-not-allowed disabled:opacity-70"
              >
                <LogOut size={16} />
                {submitting ? "处理中..." : "退出登录"}
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-3">
                <StatChip label="主账号" value="统一登录" />
                <StatChip label="会员" value="独立权益" />
                <StatChip label="退出" value="稳定可见" />
              </div>
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
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-cyan-500 py-4 font-bold text-white transition-colors hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-70"
              >
                <ArrowRight size={18} />
                {submitting ? "提交中..." : mode === "register" ? "创建账户并登录" : "登录并进入"}
              </button>
              <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4 text-sm leading-7 text-slate-300">
                认证完成后，会员、通知、绑定和安全操作统一进入账号中心，不再停留在登录页处理。
              </div>
            </form>
          )}

          {message ? (
            <p className="mt-4 rounded-lg border border-white/10 bg-black/30 px-4 py-3 text-sm text-slate-300">{message}</p>
          ) : null}
        </section>
      </div>
    </div>
  );
}

function StatChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3">
      <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">{label}</div>
      <div className="mt-2 text-sm font-semibold text-white">{value}</div>
    </div>
  );
}
