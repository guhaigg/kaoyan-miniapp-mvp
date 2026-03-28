"use client";

import Link from "next/link";
import { FolderKanban, LockKeyhole, LogOut, QrCode, Sparkles, WalletCards } from "lucide-react";

export function AccountSpaceSidebar({
  membershipLabel,
  wechatBound,
  securityHint,
  onLogout,
  loggedIn,
}: {
  membershipLabel: string;
  wechatBound: boolean;
  securityHint: string;
  onLogout: () => void;
  loggedIn: boolean;
}) {
  if (!loggedIn) {
    return (
      <div className="space-y-4">
        <section className="bili-surface p-6">
          <div className="text-xs uppercase tracking-[0.24em] text-sky-500">Guest</div>
          <div className="mt-3 text-xl font-bold text-slate-900">登录后，这里会变成你的账号侧栏</div>
          <p className="mt-3 text-sm leading-7 text-slate-600">会员入口、微信绑定、安全设置和退出动作都会稳定收敛在右侧面板。</p>
          <div className="mt-4 grid gap-3">
            <Link href="/login" className="rounded-2xl bg-[linear-gradient(90deg,#ff7fb7,#68d2ff)] px-4 py-3 text-center text-sm font-semibold text-white">
              去登录
            </Link>
            <Link href="/register" className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-center text-sm font-semibold text-slate-700">
              去注册
            </Link>
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="space-y-4 xl:sticky xl:top-24">
      <section className="bili-surface p-6">
        <div className="text-xs uppercase tracking-[0.24em] text-sky-500">Membership</div>
        <div className="mt-3 text-xl font-bold text-slate-900">{membershipLabel}</div>
        <p className="mt-3 text-sm leading-7 text-slate-600">
          会员权益、订单、绑定和安全管理统一在这里处理；关注库里的订阅、雷达和实时提醒改由独立工作台承载。
        </p>
      </section>

      <section className="bili-surface p-6">
        <div className="text-xs uppercase tracking-[0.24em] text-slate-400">Quick Actions</div>
        <div className="mt-4 grid gap-3">
          <Link href="/watchlist" className="flex items-center gap-3 rounded-2xl bg-sky-50 px-4 py-3 text-sm font-semibold text-sky-700 transition-colors hover:bg-sky-100">
            <FolderKanban size={16} />
            打开关注库
          </Link>
          <Link href="/account?tab=account&panel=billing" className="flex items-center gap-3 rounded-2xl bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-100">
            <WalletCards size={16} />
            会员与订单
          </Link>
          <Link href="/account?tab=account&panel=security" className="flex items-center gap-3 rounded-2xl bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-100">
            <LockKeyhole size={16} />
            账号安全
          </Link>
          <Link href="/account?tab=account" className="flex items-center gap-3 rounded-2xl bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-100">
            <QrCode size={16} />
            {wechatBound ? "微信已绑定" : "绑定微信"}
          </Link>
          <button
            type="button"
            onClick={onLogout}
            className="flex items-center gap-3 rounded-2xl bg-rose-50 px-4 py-3 text-left text-sm font-semibold text-rose-600 transition-colors hover:bg-rose-100"
          >
            <LogOut size={16} />
            退出登录
          </button>
        </div>
      </section>

      <section className="bili-surface p-6">
        <div className="flex items-center gap-2 text-xs uppercase tracking-[0.24em] text-pink-500">
          <Sparkles size={14} />
          Security Hint
        </div>
        <p className="mt-3 text-sm leading-7 text-slate-600">{securityHint}</p>
      </section>
    </div>
  );
}
