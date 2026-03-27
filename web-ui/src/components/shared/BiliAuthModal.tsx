"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  CheckCircle2,
  KeyRound,
  LogOut,
  MessageSquareText,
  QrCode,
  ShieldCheck,
  Sparkles,
  UserCircle2,
  UserPlus2,
  X,
} from "lucide-react";
import { ApiError, getCurrentUser, loginUser, logoutUser, registerUser } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import {
  AUTH_FEATURE_PILLS,
  AUTH_LOCKED_COPY,
  AUTH_PANE_LABELS,
  AUTH_SCENE_CARDS,
  AUTH_SOCIAL_ENTRIES,
  AUTH_VALUE_POINTS,
  type AuthPane,
} from "./bili-auth-copy";

type AuthMode = "login" | "register";
type NoticeTone = "info" | "success" | "error";

type NoticeState = {
  tone: NoticeTone;
  text: string;
};

export default function BiliAuthModal({
  initialMode,
  presentation,
  onClose,
}: {
  initialMode: AuthMode;
  presentation: "page" | "dialog";
  onClose?: () => void;
}) {
  const router = useRouter();
  const { portalAuth, setPortalAuthFromToken, setPortalProfile, clearPortalAuth, showToast } = useAppStore();
  const [pane, setPane] = useState<AuthPane>(initialMode === "register" ? "register" : "password");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [nickname, setNickname] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [notice, setNotice] = useState<NoticeState | null>(null);

  useEffect(() => {
    setPane(initialMode === "register" ? "register" : "password");
    setNotice(null);
  }, [initialMode]);

  const isPage = presentation === "page";
  const showUpgradePanel = Boolean(portalAuth && !portalAuth.isAdmin && !portalAuth.isPremium);
  const displayName = portalAuth?.nickname || portalAuth?.username || "格物账号";
  const heroTitle = portalAuth ? "账号已接入" : pane === "register" ? "创建你的格物账号" : "欢迎回来";
  const heroDescription = portalAuth
    ? "当前会话已经接入统一账号体系。你可以直接回到搜索、进入账号空间，或者在这里退出当前会话。"
    : pane === "register"
      ? "注册后会自动完成登录，继续进入搜索页与关注体系。"
      : pane === "sms"
        ? "短信入口先保留视觉位，当前请使用账号密码登录。"
        : "统一管理公告搜索、调剂雷达、通知与账号安全。";

  const pageShellClassName = isPage
    ? "relative mx-auto flex min-h-[calc(100vh-7.5rem)] max-w-6xl items-center justify-center px-4 py-8 md:px-6 md:py-12"
    : "";

  const modalClassName = [
    "relative overflow-hidden rounded-[36px] border border-white/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(249,251,255,0.96))] shadow-[0_44px_140px_rgba(73,110,170,0.22)]",
    isPage ? "w-full max-w-[1040px]" : "w-full max-w-[1024px]",
  ].join(" ");

  const tabItems: Array<{ key: AuthPane; icon: typeof KeyRound }> = [
    { key: "password", icon: KeyRound },
    { key: "sms", icon: MessageSquareText },
    { key: "register", icon: UserPlus2 },
  ];

  const modeSummary = useMemo(
    () =>
      pane === "register"
        ? "创建账号后自动登录"
        : pane === "sms"
          ? "占位入口"
          : "账号密码登录",
    [pane],
  );

  function setInfoNotice(text: string, tone: NoticeTone = "info") {
    setNotice({ text, tone });
  }

  function handleUnavailable(key: keyof typeof AUTH_LOCKED_COPY) {
    const text = AUTH_LOCKED_COPY[key];
    setInfoNotice(text, "info");
    showToast("暂未开放", text, "info");
  }

  async function hydrateProfile(accessToken: string) {
    try {
      const profile = await getCurrentUser(accessToken);
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
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;

    if (pane === "sms") {
      handleUnavailable("sms");
      return;
    }
    if (username.trim().length < 3) {
      setInfoNotice("用户名至少 3 位。", "error");
      return;
    }
    if (password.length < 8) {
      setInfoNotice("密码至少 8 位。", "error");
      return;
    }

    setSubmitting(true);
    setNotice(null);
    try {
      if (pane === "register") {
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
      await hydrateProfile(login.access_token);
      setInfoNotice(pane === "register" ? "注册成功，正在进入搜索页。" : "登录成功，正在进入搜索页。", "success");
      onClose?.();
      router.push("/search");
    } catch (error) {
      setInfoNotice(error instanceof ApiError ? error.message : "操作失败，请稍后重试。", "error");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleLogout() {
    if (submitting) return;
    setSubmitting(true);
    setNotice(null);
    try {
      await logoutUser();
      clearPortalAuth();
      setInfoNotice("已退出当前账号。", "success");
    } catch (error) {
      setInfoNotice(error instanceof ApiError ? error.message : "退出失败，请稍后重试。", "error");
    } finally {
      setSubmitting(false);
    }
  }

  function renderForm() {
    if (portalAuth) {
      return (
        <div className="space-y-5">
          <div className="rounded-[28px] border border-sky-100 bg-[linear-gradient(135deg,rgba(255,255,255,0.95),rgba(238,247,255,0.92))] p-5 shadow-[0_18px_50px_rgba(96,165,250,0.12)]">
            <div className="flex items-start gap-4">
              <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-[20px] bg-[linear-gradient(135deg,#fb7185,#60a5fa)] text-white shadow-[0_14px_30px_rgba(96,165,250,0.24)]">
                <UserCircle2 size={26} />
              </div>
              <div className="min-w-0">
                <div className="text-[11px] font-semibold uppercase tracking-[0.26em] text-slate-400">Current Session</div>
                <div className="mt-2 truncate text-2xl font-black text-slate-900">{displayName}</div>
                <div className="mt-2 text-sm leading-7 text-slate-500">
                  角色：{portalAuth.role} · 状态：{portalAuth.status}
                </div>
              </div>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <StatusCard label="账号中心" value="统一管理个人资料、通知与权益" />
            <StatusCard label="搜索入口" value="认证成功后继续回到搜索主路径" />
          </div>

          {showUpgradePanel ? (
            <div className="rounded-[24px] border border-amber-200 bg-[linear-gradient(135deg,rgba(255,247,237,0.96),rgba(255,255,255,0.92))] p-5">
              <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-amber-500">Membership</div>
              <div className="mt-2 text-lg font-bold text-slate-900">会员入口已经迁到账号空间。</div>
              <div className="mt-2 text-sm leading-7 text-slate-500">
                这里保留登录壳和账号状态，订单与权益继续在账号中心维护。
              </div>
              <Link
                href="/account"
                onClick={onClose}
                className="mt-4 inline-flex items-center gap-2 rounded-full bg-[linear-gradient(90deg,#fb923c,#fb7185)] px-5 py-3 text-sm font-semibold text-white shadow-[0_16px_30px_rgba(251,113,133,0.2)]"
              >
                <Sparkles size={16} />
                去账号中心查看
              </Link>
            </div>
          ) : null}

          <div className="grid gap-3 sm:grid-cols-3">
            <ActionLink href="/account" label="进入账号中心" accent onClick={onClose} />
            <ActionLink href="/search" label="去搜索页" onClick={onClose} />
            <button
              type="button"
              onClick={handleLogout}
              disabled={submitting}
              className="inline-flex items-center justify-center gap-2 rounded-full border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-600 transition-colors hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-70"
            >
              <LogOut size={16} />
              {submitting ? "处理中..." : "退出登录"}
            </button>
          </div>
        </div>
      );
    }

    if (pane === "sms") {
      return (
        <div className="space-y-5">
          <div className="rounded-[28px] border border-dashed border-sky-200 bg-sky-50/70 p-6 text-center">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-white text-sky-500 shadow-[0_12px_28px_rgba(96,165,250,0.16)]">
              <MessageSquareText size={26} />
            </div>
            <div className="mt-4 text-xl font-black text-slate-900">短信登录暂未开放</div>
            <p className="mt-3 text-sm leading-7 text-slate-500">
              当前只接通账号密码登录与注册。短信入口先保留在同一套登录窗中，后续再接真实能力。
            </p>
            <button
              type="button"
              onClick={() => {
                handleUnavailable("sms");
                setPane("password");
              }}
              className="mt-5 inline-flex items-center gap-2 rounded-full bg-[linear-gradient(90deg,#60a5fa,#38bdf8)] px-5 py-3 text-sm font-semibold text-white shadow-[0_14px_28px_rgba(56,189,248,0.24)]"
            >
              <KeyRound size={16} />
              返回密码登录
            </button>
          </div>
          <LockedSocialRow onUnavailable={handleUnavailable} />
        </div>
      );
    }

    return (
      <form onSubmit={handleSubmit} className="space-y-5">
        <div className="grid gap-3 sm:grid-cols-2">
          <StatusCard label="当前入口" value={modeSummary} />
          <StatusCard label="成功后" value="自动跳转到 /search" />
        </div>

        <div className="space-y-3">
          <label className="block text-sm font-semibold text-slate-700">用户名</label>
          <input
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            type="text"
            autoComplete="username"
            placeholder="请输入用户名"
            className="w-full rounded-[22px] border border-slate-200 bg-white px-5 py-4 text-base text-slate-900 outline-none transition-colors placeholder:text-slate-400 focus:border-sky-300 focus:ring-4 focus:ring-sky-100"
          />
        </div>

        {pane === "register" ? (
          <div className="space-y-3">
            <label className="block text-sm font-semibold text-slate-700">昵称</label>
            <input
              value={nickname}
              onChange={(event) => setNickname(event.target.value)}
              type="text"
              maxLength={120}
              placeholder="可选，用于账号展示"
              className="w-full rounded-[22px] border border-slate-200 bg-white px-5 py-4 text-base text-slate-900 outline-none transition-colors placeholder:text-slate-400 focus:border-sky-300 focus:ring-4 focus:ring-sky-100"
            />
          </div>
        ) : null}

        <div className="space-y-3">
          <label className="block text-sm font-semibold text-slate-700">密码</label>
          <input
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            type="password"
            autoComplete={pane === "register" ? "new-password" : "current-password"}
            placeholder="至少 8 位密码"
            className="w-full rounded-[22px] border border-slate-200 bg-white px-5 py-4 text-base text-slate-900 outline-none transition-colors placeholder:text-slate-400 focus:border-sky-300 focus:ring-4 focus:ring-sky-100"
          />
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="inline-flex w-full items-center justify-center gap-2 rounded-full bg-[linear-gradient(90deg,#fb7299,#60a5fa)] px-5 py-4 text-base font-semibold text-white shadow-[0_18px_34px_rgba(96,165,250,0.24)] transition-transform hover:scale-[1.01] disabled:cursor-not-allowed disabled:opacity-70"
        >
          <ArrowRight size={18} />
          {submitting ? "提交中..." : pane === "register" ? "注册并进入搜索" : "登录并进入搜索"}
        </button>

        <LockedSocialRow onUnavailable={handleUnavailable} />
      </form>
    );
  }

  return (
    <div className={pageShellClassName}>
      {isPage ? (
        <>
          <div className="pointer-events-none absolute inset-x-6 top-6 h-56 rounded-[38px] bg-[radial-gradient(circle_at_top_left,rgba(251,114,153,0.22),transparent_45%),radial-gradient(circle_at_top_right,rgba(96,165,250,0.2),transparent_35%),linear-gradient(180deg,rgba(255,255,255,0.8),rgba(245,248,255,0.32))]" />
          <div className="pointer-events-none absolute inset-y-16 left-0 w-48 rounded-full bg-[radial-gradient(circle,rgba(191,219,254,0.34),transparent_70%)] blur-3xl" />
          <div className="pointer-events-none absolute bottom-6 right-0 h-64 w-64 rounded-full bg-[radial-gradient(circle,rgba(251,207,232,0.28),transparent_72%)] blur-3xl" />
        </>
      ) : null}

      <section className={modalClassName}>
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(255,255,255,0.95),transparent_28%),radial-gradient(circle_at_bottom_right,rgba(191,219,254,0.34),transparent_24%)]" />
        <div className="relative grid lg:grid-cols-[0.95fr_1.05fr]">
          <div className="relative overflow-hidden bg-[linear-gradient(180deg,#fef9fb_0%,#eef6ff_55%,#f9fbff_100%)] p-7 md:p-9">
            <div className="absolute inset-x-10 top-0 h-32 rounded-b-[32px] bg-[linear-gradient(180deg,rgba(255,255,255,0.9),rgba(255,255,255,0))]" />
            <div className="relative">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <div className="inline-flex items-center gap-2 rounded-full bg-white/90 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.26em] text-slate-500 shadow-[0_10px_26px_rgba(148,163,184,0.14)]">
                    <ShieldCheck size={14} className="text-sky-500" />
                    Account Portal
                  </div>
                  <h2 className="mt-5 max-w-sm text-[2rem] font-black leading-tight text-slate-900 md:text-[2.25rem]">
                    {heroTitle}
                  </h2>
                  <p className="mt-4 max-w-md text-sm leading-7 text-slate-500">{heroDescription}</p>
                </div>
                {!isPage && onClose ? (
                  <button
                    type="button"
                    onClick={onClose}
                    className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-white/80 bg-white/90 text-slate-500 shadow-[0_10px_24px_rgba(148,163,184,0.16)] transition-colors hover:text-slate-900"
                    aria-label="关闭认证弹窗"
                  >
                    <X size={18} />
                  </button>
                ) : null}
              </div>

              <div className="mt-7 flex flex-wrap gap-2">
                {AUTH_FEATURE_PILLS.map((item) => (
                  <span
                    key={item}
                    className="rounded-full border border-white/90 bg-white/90 px-3 py-1.5 text-xs font-semibold text-slate-500 shadow-[0_10px_24px_rgba(148,163,184,0.12)]"
                  >
                    {item}
                  </span>
                ))}
              </div>

              <button
                type="button"
                onClick={() => handleUnavailable("qrcode")}
                className="mt-7 block w-full rounded-[32px] border border-white/90 bg-white/90 p-5 text-left shadow-[0_24px_60px_rgba(96,165,250,0.15)] transition-transform hover:-translate-y-0.5"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-slate-900">扫码登录预留位</div>
                    <div className="mt-2 text-sm leading-7 text-slate-500">
                      保留 B 站式左列二维码视觉位，当前点击后会明确提示“暂未开放”。
                    </div>
                  </div>
                  <div className="relative flex h-24 w-24 shrink-0 items-center justify-center rounded-[28px] bg-[linear-gradient(135deg,#f8fbff,#e8f2ff)]">
                    <QrCode size={42} className="text-slate-900" />
                    <span className="absolute inset-2 rounded-[20px] border border-dashed border-sky-200" />
                  </div>
                </div>
                <div className="mt-4 flex items-center gap-2 text-xs font-semibold text-sky-500">
                  <Sparkles size={14} />
                  当前先使用账号密码登录
                </div>
              </button>

              <div className="mt-6 grid gap-3 sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3">
                {AUTH_SCENE_CARDS.map((card) => (
                  <div
                    key={card.title}
                    className="rounded-[24px] border border-white/80 bg-white/80 px-4 py-4 shadow-[0_12px_28px_rgba(148,163,184,0.12)]"
                  >
                    <div className="text-sm font-semibold text-slate-900">{card.title}</div>
                    <div className="mt-2 text-xs leading-6 text-slate-500">{card.description}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="relative p-7 md:p-9">
            <div className="mx-auto max-w-[440px]">
              <div className="flex flex-wrap gap-2 rounded-full bg-slate-100/90 p-2">
                {tabItems.map((item) => {
                  const Icon = item.icon;
                  const active = pane === item.key;
                  return (
                    <button
                      key={item.key}
                      type="button"
                      onClick={() => {
                        setPane(item.key);
                        setNotice(null);
                        if (item.key === "sms") {
                          handleUnavailable("sms");
                        }
                      }}
                      className={`inline-flex flex-1 items-center justify-center gap-2 rounded-full px-4 py-3 text-sm font-semibold transition-colors ${
                        active
                          ? "bg-white text-slate-900 shadow-[0_12px_24px_rgba(148,163,184,0.16)]"
                          : "text-slate-500 hover:text-slate-900"
                      }`}
                    >
                      <Icon size={16} />
                      {AUTH_PANE_LABELS[item.key]}
                    </button>
                  );
                })}
              </div>

              <div className="mt-6 flex items-center justify-between gap-3">
                <div>
                  <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-400">Auth Entry</div>
                  <div className="mt-2 text-2xl font-black text-slate-900">
                    {portalAuth ? "账号入口已接入" : AUTH_PANE_LABELS[pane]}
                  </div>
                </div>
                <div className="rounded-full bg-sky-50 px-3 py-1.5 text-xs font-semibold text-sky-600">{modeSummary}</div>
              </div>

              <div className="mt-4 text-sm leading-7 text-slate-500">
                {portalAuth
                  ? "你已经处在统一账号会话中，当前弹窗保留同一套视觉与操作语义。"
                  : pane === "register"
                    ? "目前开放的是账号密码注册，注册成功后自动登录并跳转到搜索页。"
                    : pane === "sms"
                      ? "短信页只保留高保真占位，方便后续接真实能力。"
                      : "当前真实可用的是账号密码登录，其他入口仅保留视觉位。"}
              </div>

              <div className="mt-6">{renderForm()}</div>

              <div className="mt-6 grid gap-3 sm:grid-cols-3">
                {AUTH_VALUE_POINTS.map((item) => (
                  <div key={item.label} className="rounded-[22px] border border-slate-100 bg-slate-50/80 px-4 py-4">
                    <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">{item.label}</div>
                    <div className="mt-2 text-sm leading-6 text-slate-500">{item.value}</div>
                  </div>
                ))}
              </div>

              {notice ? (
                <div
                  className={`mt-5 rounded-[22px] border px-4 py-4 text-sm leading-7 ${
                    notice.tone === "error"
                      ? "border-rose-200 bg-rose-50 text-rose-600"
                      : notice.tone === "success"
                        ? "border-emerald-200 bg-emerald-50 text-emerald-600"
                        : "border-sky-200 bg-sky-50 text-sky-600"
                  }`}
                >
                  <div className="flex items-start gap-2">
                    <CheckCircle2 size={18} className="mt-1 shrink-0" />
                    <span>{notice.text}</span>
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

function StatusCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[22px] border border-slate-100 bg-slate-50/80 px-4 py-4">
      <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">{label}</div>
      <div className="mt-2 text-sm leading-6 text-slate-600">{value}</div>
    </div>
  );
}

function LockedSocialRow({
  onUnavailable,
}: {
  onUnavailable: (key: keyof typeof AUTH_LOCKED_COPY) => void;
}) {
  return (
    <div className="rounded-[28px] border border-slate-100 bg-slate-50/80 p-5">
      <div className="text-sm font-semibold text-slate-900">社交登录入口</div>
      <div className="mt-2 text-sm leading-7 text-slate-500">
        微信、QQ、微博入口保留 hover 和点击反馈，当前统一提示“暂未开放”。
      </div>
      <div className="mt-4 flex flex-wrap gap-3">
        {AUTH_SOCIAL_ENTRIES.map((entry) => (
          <button
            key={entry.key}
            type="button"
            onClick={() => onUnavailable(entry.key)}
            className="inline-flex items-center gap-3 rounded-full border border-white bg-white px-4 py-3 text-sm font-semibold text-slate-700 shadow-[0_12px_24px_rgba(148,163,184,0.12)] transition-transform hover:-translate-y-0.5 hover:border-sky-200 hover:text-slate-900"
          >
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[linear-gradient(135deg,#fb7299,#60a5fa)] text-xs font-black text-white">
              {entry.badge}
            </span>
            {entry.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function ActionLink({
  href,
  label,
  onClick,
  accent = false,
}: {
  href: string;
  label: string;
  onClick?: () => void;
  accent?: boolean;
}) {
  return (
    <Link
      href={href}
      onClick={onClick}
      className={`inline-flex items-center justify-center rounded-full px-4 py-3 text-sm font-semibold transition-colors ${
        accent
          ? "bg-[linear-gradient(90deg,#fb7299,#60a5fa)] text-white shadow-[0_16px_30px_rgba(96,165,250,0.22)]"
          : "border border-slate-200 bg-white text-slate-700 hover:border-sky-200 hover:text-slate-900"
      }`}
    >
      {label}
    </Link>
  );
}
