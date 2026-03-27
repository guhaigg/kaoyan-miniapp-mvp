"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { BellRing, Radar, UserRound, WalletCards } from "lucide-react";
import { parseAccountSpacePanel, parseAccountSpaceTab, type AccountSpacePanel, type AccountSpaceTab } from "./account-space-query";

const TAB_ITEMS: Array<{ id: AccountSpaceTab; label: string; icon: typeof BellRing }> = [
  { id: "activity", label: "动态", icon: BellRing },
  { id: "following", label: "关注", icon: UserRound },
  { id: "radar", label: "雷达", icon: Radar },
  { id: "account", label: "账号", icon: WalletCards },
];

const PANEL_COPY: Record<Exclude<AccountSpacePanel, null>, string> = {
  billing: "当前从旧的会员入口跳转而来，后续会落到会员与订单区块。",
  security: "当前从旧的安全入口跳转而来，后续会落到密码、绑定和会话区块。",
  notifications: "当前从旧的通知入口跳转而来，后续会落到动态流里的通知视图。",
};

export default function AccountSpacePage({
  initialTab = "activity",
  initialPanel = null,
}: {
  initialTab?: AccountSpaceTab;
  initialPanel?: AccountSpacePanel;
}) {
  const searchParams = useSearchParams();
  const currentTab = parseAccountSpaceTab(searchParams.get("tab") || initialTab);
  const currentPanel = parseAccountSpacePanel(searchParams.get("panel") || initialPanel || undefined);

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,#f6f8fd_0%,#eef4ff_42%,#fbfdff_100%)] text-slate-900">
      <div className="mx-auto max-w-7xl px-4 pb-20 pt-8 md:px-6">
        <section className="overflow-hidden rounded-[2.2rem] border border-sky-100 bg-white shadow-[0_32px_100px_rgba(122,147,192,0.18)]">
          <div className="h-40 bg-[linear-gradient(135deg,#6fd6ff_0%,#9edfff_22%,#ffd7e7_68%,#ff8fbe_100%)]" />
          <div className="px-5 pb-6 md:px-8">
            <div className="-mt-12 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
              <div className="flex items-end gap-4">
                <div className="flex h-24 w-24 items-center justify-center rounded-full border-[6px] border-white bg-[linear-gradient(135deg,#ffb9d7,#85dbff)] text-3xl font-black text-white shadow-[0_18px_48px_rgba(110,133,184,0.22)]">
                  G
                </div>
                <div className="pb-2">
                  <div className="text-3xl font-black tracking-tight text-slate-900">我的空间</div>
                  <div className="mt-1 text-sm text-slate-500">新的账号首页会在这里承接动态、关注、雷达和账号动作。</div>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3 md:min-w-[360px]">
                {[
                  { label: "关注", value: "--" },
                  { label: "雷达", value: "--" },
                  { label: "动态", value: "--" },
                ].map((item) => (
                  <div key={item.label} className="rounded-2xl border border-slate-100 bg-slate-50/80 px-4 py-3">
                    <div className="text-xs uppercase tracking-[0.18em] text-slate-400">{item.label}</div>
                    <div className="mt-2 text-2xl font-black text-slate-900">{item.value}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <nav className="mt-5 rounded-[1.7rem] border border-white/80 bg-white/85 p-2 shadow-[0_18px_50px_rgba(122,147,192,0.14)] backdrop-blur">
          <div className="flex gap-2 overflow-x-auto">
            {TAB_ITEMS.map((item) => {
              const Icon = item.icon;
              const active = item.id === currentTab;
              const href = item.id === "account" && currentPanel ? `/account?tab=${item.id}&panel=${currentPanel}` : `/account?tab=${item.id}`;
              return (
                <Link
                  key={item.id}
                  href={href}
                  className={`inline-flex items-center gap-2 rounded-full px-5 py-3 text-sm font-semibold transition-colors ${
                    active
                      ? "bg-[linear-gradient(90deg,#ff7db6,#68d1ff)] text-white"
                      : "bg-transparent text-slate-600 hover:bg-slate-100"
                  }`}
                >
                  <Icon size={16} />
                  {item.label}
                </Link>
              );
            })}
          </div>
        </nav>

        <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
          <main className="min-w-0 space-y-5">
            <section className="rounded-[2rem] border border-white/80 bg-white/90 p-6 shadow-[0_20px_60px_rgba(122,147,192,0.16)]">
              <div className="text-xs uppercase tracking-[0.24em] text-sky-500">Space Shell</div>
              <h1 className="mt-3 text-2xl font-bold text-slate-900">
                当前激活的是 {TAB_ITEMS.find((item) => item.id === currentTab)?.label} tab
              </h1>
              <p className="mt-3 text-sm leading-7 text-slate-600">
                这里先落 URL 状态和新版空间壳子。下一步会把动态流、关注墙、雷达总览和账号动作逐个替换成真实区块。
              </p>
              {currentPanel ? (
                <div className="mt-4 rounded-2xl border border-pink-100 bg-pink-50 px-4 py-3 text-sm text-pink-700">
                  当前 panel: <span className="font-semibold">{currentPanel}</span>。{PANEL_COPY[currentPanel]}
                </div>
              ) : null}
            </section>
            <section className="grid gap-4 md:grid-cols-2">
              <div className="rounded-[2rem] border border-white/80 bg-white/90 p-6 shadow-[0_20px_60px_rgba(122,147,192,0.16)]">
                <div className="text-xs uppercase tracking-[0.24em] text-slate-400">Main Column</div>
                <div className="mt-3 text-lg font-bold text-slate-900">动态流、关注墙、雷达卡会放在这里</div>
              </div>
              <div className="rounded-[2rem] border border-white/80 bg-white/90 p-6 shadow-[0_20px_60px_rgba(122,147,192,0.16)]">
                <div className="text-xs uppercase tracking-[0.24em] text-slate-400">Content Rule</div>
                <div className="mt-3 text-lg font-bold text-slate-900">这版先把空间页骨架和 tab 语义跑通，不改现有账号业务逻辑。</div>
              </div>
            </section>
          </main>

          <aside className="min-w-0">
            <section className="rounded-[2rem] border border-white/80 bg-white/90 p-6 shadow-[0_20px_60px_rgba(122,147,192,0.16)]">
              <div className="text-xs uppercase tracking-[0.24em] text-sky-500">Sidebar</div>
              <div className="mt-3 text-lg font-bold text-slate-900">会员、安全、微信绑定和快捷动作会下沉到这里</div>
            </section>
          </aside>
        </div>
      </div>
    </div>
  );
}
