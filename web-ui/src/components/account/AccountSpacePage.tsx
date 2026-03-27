"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import {
  ApiError,
  getCurrentUserAccountOverview,
  logoutUser,
  type UserAccountOverviewResponse,
} from "@/lib/api";
import { useAppStore } from "@/lib/store";
import { AccountSpaceHero } from "./AccountSpaceHero";
import { AccountSpaceSidebar } from "./AccountSpaceSidebar";
import { AccountSpaceTabs } from "./AccountSpaceTabs";
import { parseAccountSpacePanel, parseAccountSpaceTab, type AccountSpacePanel, type AccountSpaceTab } from "./account-space-query";

const PANEL_COPY: Record<Exclude<AccountSpacePanel, null>, string> = {
  billing: "旧的会员入口会收敛到新的会员与订单区块。",
  security: "旧的安全入口会收敛到新的密码、绑定和会话区块。",
  notifications: "旧的通知入口会收敛到动态流里的通知视图。",
};

export default function AccountSpacePage({
  initialTab = "activity",
  initialPanel = null,
}: {
  initialTab?: AccountSpaceTab;
  initialPanel?: AccountSpacePanel;
}) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { portalAuth, clearPortalAuth } = useAppStore();
  const [accountOverview, setAccountOverview] = useState<UserAccountOverviewResponse | null>(null);

  const currentTab = parseAccountSpaceTab(searchParams.get("tab") || initialTab);
  const currentPanel = parseAccountSpacePanel(searchParams.get("panel") || initialPanel || undefined);

  useEffect(() => {
    if (!portalAuth?.accessToken) {
      setAccountOverview(null);
      return;
    }

    let cancelled = false;
    getCurrentUserAccountOverview(portalAuth.accessToken)
      .then((payload) => {
        if (!cancelled) {
          setAccountOverview(payload);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setAccountOverview(null);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [portalAuth?.accessToken]);

  async function handleLogout() {
    try {
      await logoutUser();
    } catch (error) {
      if (!(error instanceof ApiError)) {
        throw error;
      }
    } finally {
      clearPortalAuth();
      router.push("/login");
    }
  }

  const displayName = portalAuth?.nickname || portalAuth?.username || "我的空间";
  const membershipLabel =
    accountOverview?.role === "admin" ? "管理员" : accountOverview?.is_premium ? "高级会员" : "普通用户";
  const signature = portalAuth
    ? "把最近动态、关注范围和雷达信号聚合到一个更像个人空间的首页。"
    : "登录后，你关注的学校、栏目和雷达信号都会在这里聚合。";
  const stats = [
    { label: "关注", value: "--", tone: "pink" as const },
    { label: "雷达", value: "--", tone: "blue" as const },
    { label: "动态", value: "--", tone: "slate" as const },
  ];
  const wechatBound = Boolean(
    accountOverview?.identities.some((item) => item.identity_type === "wechat_miniapp" && item.status === "active"),
  );
  const securityHint = wechatBound
    ? "微信已绑定，后续只需要把密码和会话安全继续维护在账号页。"
    : "建议尽快补齐微信绑定和密码安全，后续跨端体验会更顺。";

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,#f6f8fd_0%,#eef4ff_42%,#fbfdff_100%)] text-slate-900">
      <div className="mx-auto max-w-7xl px-4 pb-20 pt-8 md:px-6">
        <AccountSpaceHero
          displayName={displayName}
          username={portalAuth?.username || "guest"}
          membershipLabel={membershipLabel}
          signature={signature}
          stats={stats}
        />

        <AccountSpaceTabs activeTab={currentTab} activePanel={currentPanel} />

        <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
          <main className="min-w-0 space-y-5">
            <section className="rounded-[2rem] border border-white/80 bg-white/90 p-6 shadow-[0_20px_60px_rgba(122,147,192,0.16)]">
              <div className="text-xs uppercase tracking-[0.24em] text-sky-500">Space Shell</div>
              <h1 className="mt-3 text-2xl font-bold text-slate-900">当前激活的是 {currentTab} tab</h1>
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
                <div className="mt-3 text-lg font-bold text-slate-900">动态流、关注墙和雷达卡会放在这里</div>
              </div>
              <div className="rounded-[2rem] border border-white/80 bg-white/90 p-6 shadow-[0_20px_60px_rgba(122,147,192,0.16)]">
                <div className="text-xs uppercase tracking-[0.24em] text-slate-400">Content Rule</div>
                <div className="mt-3 text-lg font-bold text-slate-900">这版先把空间页骨架和 tab 语义跑通，不改现有账号业务逻辑。</div>
              </div>
            </section>
          </main>

          <aside className="min-w-0">
            <AccountSpaceSidebar
              membershipLabel={membershipLabel}
              wechatBound={wechatBound}
              securityHint={securityHint}
              onLogout={handleLogout}
              loggedIn={Boolean(portalAuth)}
            />
          </aside>
        </div>
      </div>
    </div>
  );
}
