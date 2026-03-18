"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type Dispatch, type ReactNode, type SetStateAction, useEffect, useMemo, useState } from "react";
import {
  BellRing,
  CreditCard,
  ShieldCheck,
  Sparkles,
  UserCircle2,
} from "lucide-react";
import {
  ApiError,
  changeCurrentUserPassword,
  createCurrentUserPaymentOrder,
  createWechatBindCode,
  getCurrentUserAccountOverview,
  getCurrentUserNotificationHistory,
  getCurrentUserPaymentOrders,
  logoutUser,
} from "@/lib/api";
import { useAppStore } from "@/lib/store";

export type AccountSection = "overview" | "billing" | "security" | "notifications";

type AccountOverviewState = {
  role: "user" | "premium" | "admin";
  status: string;
  premium_expires_at: string | null;
  wechatBound: boolean;
  items: Array<{ identity_type: string; status: string; login_name: string | null }>;
  roles: Array<{ role_code: string; status: string }>;
  entitlements: Array<{ entitlement_code: string; status: string; expires_at: string | null }>;
};

const EMPTY_OVERVIEW: AccountOverviewState = {
  role: "user",
  status: "active",
  premium_expires_at: null,
  wechatBound: false,
  items: [],
  roles: [],
  entitlements: [],
};

const NAV_ITEMS: Array<{
  section: AccountSection;
  href: string;
  label: string;
  description: string;
  icon: typeof UserCircle2;
}> = [
  {
    section: "overview",
    href: "/account",
    label: "用户主页",
    description: "账号概览、身份与权益",
    icon: UserCircle2,
  },
  {
    section: "billing",
    href: "/account/billing",
    label: "会员与支付",
    description: "套餐、订单和支付框架",
    icon: CreditCard,
  },
  {
    section: "security",
    href: "/account/security",
    label: "安全设置",
    description: "密码、绑定和会话控制",
    icon: ShieldCheck,
  },
  {
    section: "notifications",
    href: "/account/notifications",
    label: "通知中心",
    description: "最近投递和推送框架",
    icon: BellRing,
  },
];

export default function AccountDashboard({ section }: { section: AccountSection }) {
  const router = useRouter();
  const { portalAuth, clearPortalAuth } = useAppStore();
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [accountOverview, setAccountOverview] = useState<AccountOverviewState>(EMPTY_OVERVIEW);
  const [bindCode, setBindCode] = useState<{ code: string; expiresIn: number } | null>(null);
  const [creatingBindCode, setCreatingBindCode] = useState(false);
  const [passwordForm, setPasswordForm] = useState({ oldPassword: "", newPassword: "" });
  const [changingPassword, setChangingPassword] = useState(false);
  const [creatingPremiumOrderDays, setCreatingPremiumOrderDays] = useState<number | null>(null);
  const [notificationHistory, setNotificationHistory] = useState<Array<{
    id: string;
    channel: string;
    status: string;
    created_at: string;
    payload: { title?: string; school_name?: string };
  }>>([]);
  const [paymentOrders, setPaymentOrders] = useState<Array<{
    id: string;
    source: string;
    status: string;
    duration_days: number;
    amount_cents: number;
    currency: string;
    created_at: string;
  }>>([]);

  useEffect(() => {
    if (!portalAuth?.accessToken) {
      setAccountOverview(EMPTY_OVERVIEW);
      setNotificationHistory([]);
      setPaymentOrders([]);
      setBindCode(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    Promise.all([
      getCurrentUserAccountOverview(portalAuth.accessToken),
      getCurrentUserNotificationHistory(portalAuth.accessToken, 10).catch(() => ({ items: [] })),
      getCurrentUserPaymentOrders(portalAuth.accessToken).catch(() => ({ items: [] })),
    ])
      .then(([payload, historyPayload, orderPayload]) => {
        if (cancelled) return;
        setAccountOverview({
          role: payload.role,
          status: payload.status,
          premium_expires_at: payload.premium_expires_at,
          wechatBound: payload.identities.some(
            (item) => item.identity_type === "wechat_miniapp" && item.status === "active",
          ),
          items: payload.identities.map((item) => ({
            identity_type: item.identity_type,
            status: item.status,
            login_name: item.login_name,
          })),
          roles: payload.roles.map((item) => ({ role_code: item.role_code, status: item.status })),
          entitlements: payload.entitlements.map((item) => ({
            entitlement_code: item.entitlement_code,
            status: item.status,
            expires_at: item.expires_at,
          })),
        });
        setNotificationHistory(
          historyPayload.items.map((item) => ({
            id: item.id,
            channel: item.channel,
            status: item.status,
            created_at: item.created_at,
            payload: {
              title: item.payload.title,
              school_name: item.payload.school_name,
            },
          })),
        );
        setPaymentOrders(
          orderPayload.items.map((item) => ({
            id: item.id,
            source: item.source,
            status: item.status,
            duration_days: item.duration_days,
            amount_cents: item.amount_cents,
            currency: item.currency,
            created_at: item.created_at,
          })),
        );
      })
      .catch(() => {
        if (cancelled) return;
        setAccountOverview(EMPTY_OVERVIEW);
        setNotificationHistory([]);
        setPaymentOrders([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [portalAuth?.accessToken]);

  const showUpgradePanel = accountOverview.role === "user" && accountOverview.status === "active";
  const activeNav = useMemo(() => NAV_ITEMS.find((item) => item.section === section) || NAV_ITEMS[0], [section]);

  async function handleCreateBindCode() {
    if (!portalAuth?.accessToken || creatingBindCode) return;
    setCreatingBindCode(true);
    setMessage("");
    try {
      const payload = await createWechatBindCode(portalAuth.accessToken);
      setBindCode({ code: payload.code, expiresIn: payload.expires_in });
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : "生成绑定码失败，请稍后重试");
    } finally {
      setCreatingBindCode(false);
    }
  }

  async function handleChangePassword() {
    if (!portalAuth?.accessToken || changingPassword) return;
    if (!passwordForm.oldPassword || !passwordForm.newPassword) {
      setMessage("请输入当前密码和新密码");
      return;
    }
    if (passwordForm.newPassword.length < 8) {
      setMessage("新密码至少 8 位");
      return;
    }
    setChangingPassword(true);
    setMessage("");
    try {
      await changeCurrentUserPassword(portalAuth.accessToken, {
        old_password: passwordForm.oldPassword,
        new_password: passwordForm.newPassword,
      });
      setPasswordForm({ oldPassword: "", newPassword: "" });
      setMessage("密码已更新");
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : "修改密码失败，请稍后重试");
    } finally {
      setChangingPassword(false);
    }
  }

  async function handleCreatePremiumOrder(durationDays: 30 | 90 | 365) {
    if (!portalAuth?.accessToken || creatingPremiumOrderDays) return;
    setCreatingPremiumOrderDays(durationDays);
    setMessage("");
    try {
      const order = await createCurrentUserPaymentOrder(portalAuth.accessToken, {
        duration_days: durationDays,
        source: "web_pay",
      });
      setPaymentOrders((current) => [
        {
          id: order.id,
          source: order.source,
          status: order.status,
          duration_days: order.duration_days,
          amount_cents: order.amount_cents,
          currency: order.currency,
          created_at: order.created_at,
        },
        ...current,
      ]);
      setMessage(`已创建 ${durationDays} 天会员订单，等待支付确认`);
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : "创建会员订单失败，请稍后重试");
    } finally {
      setCreatingPremiumOrderDays(null);
    }
  }

  async function handleLogout() {
    setMessage("");
    try {
      await logoutUser();
      clearPortalAuth();
      router.push("/login");
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : "退出失败，请稍后重试");
    }
  }

  if (!portalAuth) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-12">
        <div className="rounded-[2rem] border border-white/10 bg-black/35 p-8 text-white shadow-2xl backdrop-blur-xl">
          <div className="text-xs uppercase tracking-[0.24em] text-cyan-300">Account Framework</div>
          <h1 className="mt-3 text-3xl font-black">先登录，再进入业务框架页。</h1>
          <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-300">
            这套页面按用户中心模板组织成独立的业务区：用户主页、会员与支付、安全设置、通知中心。未登录时只提供接入入口。
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link href="/login" className="rounded-xl bg-cyan-500 px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-cyan-400">
              去登录
            </Link>
            <Link href="/register" className="rounded-xl border border-white/20 bg-white/5 px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-white/10">
              去注册
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-4 pb-20 pt-10 text-white">
      <section className="relative overflow-hidden rounded-[2rem] border border-cyan-400/15 bg-[radial-gradient(circle_at_top_left,rgba(34,211,238,0.16),transparent_32%),linear-gradient(180deg,rgba(8,12,22,0.92),rgba(4,8,18,0.98))] p-8 shadow-[0_30px_80px_rgba(0,0,0,0.35)]">
        <div className="absolute inset-y-0 right-0 hidden w-80 bg-[radial-gradient(circle_at_top,rgba(245,158,11,0.16),transparent_62%)] lg:block" />
        <div className="relative flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <div className="text-xs uppercase tracking-[0.28em] text-cyan-300">Shadcn-style Settings Shell</div>
            <h1 className="mt-3 text-3xl font-black sm:text-5xl">{activeNav.label}</h1>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-300">
              左侧是稳定导航，右侧是业务表单和记录区。后续接真实支付、通知设置或微信绑定时，只填对应页面，不再破坏整体结构。
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-3 lg:min-w-[420px]">
            <MetricCard label="当前账号" value={portalAuth.nickname || portalAuth.username} hint={portalAuth.role} />
            <MetricCard label="账号状态" value={loading ? "同步中" : accountOverview.status} hint="主账号运行状态" />
            <MetricCard
              label="高级权益"
              value={accountOverview.premium_expires_at ? "已开通" : "未开通"}
              hint={
                accountOverview.premium_expires_at
                  ? `至 ${new Date(accountOverview.premium_expires_at).toLocaleDateString("zh-CN")}`
                  : "可在会员与支付页开通"
              }
            />
          </div>
        </div>
      </section>

      <div className="mt-8 grid gap-6 xl:grid-cols-[280px_minmax(0,1fr)]">
        <aside className="rounded-[2rem] border border-white/10 bg-black/30 p-4 shadow-2xl backdrop-blur-xl xl:sticky xl:top-28 xl:self-start">
          <div className="mb-4 px-3 text-xs uppercase tracking-[0.24em] text-slate-500">Settings</div>
          <nav className="space-y-2">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              const active = item.section === section;
              return (
                <Link
                  key={item.section}
                  href={item.href}
                  className={`block rounded-[1.4rem] border px-4 py-4 transition-all ${
                    active
                      ? "border-cyan-400/30 bg-cyan-500/10 shadow-[0_12px_32px_rgba(34,211,238,0.08)]"
                      : "border-white/5 bg-white/[0.03] hover:border-white/10 hover:bg-white/[0.06]"
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <div className={`rounded-2xl p-2 ${active ? "bg-cyan-500/15 text-cyan-300" : "bg-white/5 text-slate-400"}`}>
                      <Icon size={18} />
                    </div>
                    <div>
                      <div className={`text-sm font-semibold ${active ? "text-white" : "text-slate-200"}`}>{item.label}</div>
                      <div className="mt-1 text-xs leading-6 text-slate-400">{item.description}</div>
                    </div>
                  </div>
                </Link>
              );
            })}
          </nav>
          <div className="mt-4 rounded-[1.4rem] border border-amber-400/15 bg-amber-500/10 p-4">
            <div className="flex items-center gap-2 text-xs uppercase tracking-[0.24em] text-amber-300">
              <Sparkles size={14} /> Template Frame
            </div>
            <div className="mt-2 text-sm font-semibold text-white">业务位已经拆开了。</div>
            <div className="mt-2 text-xs leading-6 text-amber-50/80">
              会员、支付、通知和安全不再互相挤占。后续接支付回调或小程序绑定时，只需要补对应模块。
            </div>
          </div>
          <div className="mt-4 rounded-[1.4rem] border border-white/10 bg-white/[0.03] p-4">
            <div className="text-xs uppercase tracking-[0.22em] text-slate-500">Session</div>
            <div className="mt-2 text-sm font-semibold text-white">{portalAuth.nickname || portalAuth.username}</div>
            <div className="mt-1 text-xs text-slate-400">
              {portalAuth.role} · {accountOverview.status || portalAuth.status}
            </div>
            <div className="mt-4 grid gap-2">
              <Link
                href="/search"
                className="rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-center text-sm font-semibold text-white transition-colors hover:bg-white/10"
              >
                返回检索页
              </Link>
              <button
                type="button"
                onClick={handleLogout}
                className="rounded-xl border border-red-400/25 bg-red-500/10 px-4 py-3 text-sm font-semibold text-red-50 transition-colors hover:bg-red-500/20"
              >
                退出登录
              </button>
            </div>
          </div>
        </aside>

        <main className="space-y-6">
          {section === "overview" ? (
            <OverviewSection
              accountOverview={accountOverview}
              loading={loading}
            />
          ) : null}
          {section === "billing" ? (
            <BillingSection
              accountOverview={accountOverview}
              creatingPremiumOrderDays={creatingPremiumOrderDays}
              onCreatePremiumOrder={handleCreatePremiumOrder}
              paymentOrders={paymentOrders}
              showUpgradePanel={showUpgradePanel}
            />
          ) : null}
          {section === "security" ? (
            <SecuritySection
              accountOverview={accountOverview}
              bindCode={bindCode}
              creatingBindCode={creatingBindCode}
              changingPassword={changingPassword}
              onChangePassword={handleChangePassword}
              onCreateBindCode={handleCreateBindCode}
              onLogout={handleLogout}
              passwordForm={passwordForm}
              setPasswordForm={setPasswordForm}
            />
          ) : null}
          {section === "notifications" ? (
            <NotificationsSection notificationHistory={notificationHistory} />
          ) : null}

          {message ? (
            <div className="rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-sm text-slate-300">{message}</div>
          ) : null}
        </main>
      </div>
    </div>
  );
}

function OverviewSection({
  accountOverview,
  loading,
}: {
  accountOverview: AccountOverviewState;
  loading: boolean;
}) {
  return (
    <>
      <SectionCard
        eyebrow="Profile"
        title="用户主页"
        description="这是主账号的稳定主页，承接身份、角色、权益和跨端绑定。它对应模板中的 Profile / Account 区域。"
      >
        <div className="grid gap-4 lg:grid-cols-2">
          <InfoTile label="主账号角色" value={loading ? "同步中..." : accountOverview.role} />
          <InfoTile label="微信绑定" value={loading ? "同步中..." : accountOverview.wechatBound ? "已绑定" : "未绑定"} />
        </div>
      </SectionCard>

      <SectionCard
        eyebrow="Linked Identities"
        title="身份凭证"
        description="主账号只保留一条用户记录，网站密码和后续微信小程序都归到独立身份表。"
      >
        <div className="grid gap-3">
          {accountOverview.items.length > 0 ? (
            accountOverview.items.map((item) => (
              <div key={`${item.identity_type}:${item.login_name || "none"}`} className="rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold text-white">{item.identity_type}</div>
                    <div className="mt-1 text-xs text-slate-400">{item.login_name || "无登录名"}</div>
                  </div>
                  <StatusPill text={item.status} tone={item.status === "active" ? "cyan" : "slate"} />
                </div>
              </div>
            ))
          ) : (
            <EmptyHint text="当前没有额外身份记录。" />
          )}
        </div>
      </SectionCard>

      <div className="grid gap-6 lg:grid-cols-2">
        <SectionCard eyebrow="Roles" title="角色分配" description="管理员是角色，不是另一套账号。">
          <div className="space-y-3">
            {accountOverview.roles.length > 0 ? (
              accountOverview.roles.map((item) => (
                <div key={`${item.role_code}:${item.status}`} className="rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-4 text-sm text-slate-200">
                  {item.role_code} ({item.status})
                </div>
              ))
            ) : (
              <EmptyHint text="当前账号没有额外角色分配。" />
            )}
          </div>
        </SectionCard>
        <SectionCard eyebrow="Entitlements" title="权益账本" description="高级会员是权益，不是账号类型。">
          <div className="space-y-3">
            {accountOverview.entitlements.length > 0 ? (
              accountOverview.entitlements.map((item) => (
                <div key={`${item.entitlement_code}:${item.status}:${item.expires_at || "none"}`} className="rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-4">
                  <div className="text-sm font-semibold text-white">{item.entitlement_code}</div>
                  <div className="mt-1 text-xs text-slate-400">
                    {item.status}
                    {item.expires_at ? ` · 到期 ${new Date(item.expires_at).toLocaleDateString("zh-CN")}` : ""}
                  </div>
                </div>
              ))
            ) : (
              <EmptyHint text="当前没有生效或历史权益。" />
            )}
          </div>
        </SectionCard>
      </div>
    </>
  );
}

function BillingSection({
  accountOverview,
  creatingPremiumOrderDays,
  onCreatePremiumOrder,
  paymentOrders,
  showUpgradePanel,
}: {
  accountOverview: AccountOverviewState;
  creatingPremiumOrderDays: number | null;
  onCreatePremiumOrder: (durationDays: 30 | 90 | 365) => Promise<void>;
  paymentOrders: Array<{
    id: string;
    source: string;
    status: string;
    duration_days: number;
    amount_cents: number;
    currency: string;
    created_at: string;
  }>;
  showUpgradePanel: boolean;
}) {
  return (
    <>
      <SectionCard
        eyebrow="Billing"
        title="会员与支付"
        description="这里是支付业务框架页。当前仍是下单后后台确认，后续真实支付只需要把回调接到这个页面和订单状态上。"
      >
        {showUpgradePanel ? (
          <div className="grid gap-4 md:grid-cols-3">
            {[
              { days: 30 as const, price: "29.00", label: "试用一个月", detail: "先验证院校收藏和新信息提示" },
              { days: 90 as const, price: "79.00", label: "覆盖复试季", detail: "适合调剂季密集检索和跟踪" },
              { days: 365 as const, price: "199.00", label: "全年跟踪", detail: "适合长期备考和多阶段监控" },
            ].map((plan) => (
              <button
                key={plan.days}
                type="button"
                onClick={() => onCreatePremiumOrder(plan.days)}
                disabled={creatingPremiumOrderDays !== null}
                className="group rounded-[1.5rem] border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.08),rgba(255,255,255,0.03))] p-5 text-left transition-all hover:border-amber-300/40 hover:-translate-y-0.5 hover:bg-[linear-gradient(180deg,rgba(245,158,11,0.16),rgba(255,255,255,0.04))] disabled:cursor-not-allowed disabled:opacity-60"
              >
                <div className="text-xs uppercase tracking-[0.22em] text-amber-200">{plan.label}</div>
                <div className="mt-3 text-3xl font-black text-white">¥{plan.price}</div>
                <div className="mt-1 text-sm text-slate-300">{plan.days} 天高级会员</div>
                <div className="mt-3 min-h-[44px] text-xs leading-6 text-slate-400">{plan.detail}</div>
                <div className="mt-4 text-sm font-semibold text-amber-200">
                  {creatingPremiumOrderDays === plan.days ? "创建中..." : "创建会员订单"}
                </div>
              </button>
            ))}
          </div>
        ) : (
          <div className="rounded-[1.5rem] border border-emerald-400/20 bg-emerald-500/10 p-5">
            <div className="text-xs uppercase tracking-[0.24em] text-emerald-300">Activated</div>
            <div className="mt-2 text-lg font-semibold text-white">当前账号已具备高级权益</div>
            <div className="mt-2 text-sm text-slate-300">
              {accountOverview.premium_expires_at
                ? `到期时间：${new Date(accountOverview.premium_expires_at).toLocaleString("zh-CN", { hour12: false })}`
                : "管理员账号默认具备高级权限。"}
            </div>
          </div>
        )}
      </SectionCard>

      <div className="grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
        <SectionCard eyebrow="Orders" title="订单账本" description="订单只记录交易过程，真实放权看权益表。">
          <div className="space-y-3">
            {paymentOrders.length > 0 ? (
              paymentOrders.map((item) => (
                <div key={item.id} className="rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="text-sm font-semibold text-white">
                      {item.duration_days} 天 / {(item.amount_cents / 100).toFixed(2)} {item.currency}
                    </div>
                    <StatusPill text={humanizeOrderStatus(item.status)} tone={item.status === "paid" ? "emerald" : item.status === "pending" ? "amber" : "slate"} />
                  </div>
                  <div className="mt-2 text-xs text-slate-400">
                    {humanizePaymentSource(item.source)} · {new Date(item.created_at).toLocaleString("zh-CN", { hour12: false })}
                  </div>
                </div>
              ))
            ) : (
              <EmptyHint text="暂无会员订单记录。" />
            )}
          </div>
        </SectionCard>
        <SectionCard eyebrow="Payment Frame" title="支付框架位" description="这里预留正式支付接入后的说明位。">
          <div className="space-y-3 text-sm leading-7 text-slate-300">
            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
              当前实现：创建订单，后台确认，再发放权益。
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
              后续接入：网页支付或微信支付回调，更新订单状态，再自动写入权益账本。
            </div>
          </div>
        </SectionCard>
      </div>
    </>
  );
}

function SecuritySection({
  accountOverview,
  bindCode,
  creatingBindCode,
  changingPassword,
  onChangePassword,
  onCreateBindCode,
  onLogout,
  passwordForm,
  setPasswordForm,
}: {
  accountOverview: AccountOverviewState;
  bindCode: { code: string; expiresIn: number } | null;
  creatingBindCode: boolean;
  changingPassword: boolean;
  onChangePassword: () => Promise<void>;
  onCreateBindCode: () => Promise<void>;
  onLogout: () => Promise<void>;
  passwordForm: { oldPassword: string; newPassword: string };
  setPasswordForm: Dispatch<SetStateAction<{ oldPassword: string; newPassword: string }>>;
}) {
  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_0.92fr]">
      <SectionCard eyebrow="Security" title="密码与登录安全" description="安全页只处理身份和密码，不再和订单、通知混在一起。">
        <div className="space-y-3">
          <input
            value={passwordForm.oldPassword}
            onChange={(event) => setPasswordForm((prev) => ({ ...prev, oldPassword: event.target.value }))}
            type="password"
            autoComplete="current-password"
            placeholder="当前密码"
            className="w-full rounded-xl border border-white/10 bg-black/40 px-4 py-3 text-sm text-white outline-none transition-colors focus:border-cyan-400"
          />
          <input
            value={passwordForm.newPassword}
            onChange={(event) => setPasswordForm((prev) => ({ ...prev, newPassword: event.target.value }))}
            type="password"
            autoComplete="new-password"
            placeholder="新密码（至少8位）"
            className="w-full rounded-xl border border-white/10 bg-black/40 px-4 py-3 text-sm text-white outline-none transition-colors focus:border-cyan-400"
          />
          <button
            type="button"
            onClick={onChangePassword}
            disabled={changingPassword}
            className="rounded-xl border border-white/20 bg-white/10 px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-white/20 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {changingPassword ? "更新中..." : "更新密码"}
          </button>
        </div>
      </SectionCard>

      <div className="space-y-6">
        <SectionCard eyebrow="Binding" title="跨端绑定框架" description="微信侧先保留接口位，Web 端这里只负责生成绑定码。">
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-sm text-slate-300">
            {accountOverview.wechatBound ? "微信小程序已绑定到当前主账号。" : "微信尚未绑定，后续可从这里生成绑定码。"}
          </div>
          {!accountOverview.wechatBound ? (
            <div className="mt-4 rounded-2xl border border-cyan-500/20 bg-cyan-500/10 p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-semibold text-white">生成微信绑定码</div>
                  <div className="mt-1 text-xs text-slate-300">给小程序绑定流程预留接口位置。</div>
                </div>
                <button
                  type="button"
                  onClick={onCreateBindCode}
                  disabled={creatingBindCode}
                  className="rounded-lg border border-cyan-400/40 bg-black/20 px-3 py-2 text-xs font-semibold text-cyan-200 transition-colors hover:bg-cyan-500/10 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {creatingBindCode ? "生成中..." : bindCode ? "重新生成" : "生成绑定码"}
                </button>
              </div>
              {bindCode ? (
                <div className="mt-4 rounded-lg border border-white/10 bg-black/30 px-4 py-3">
                  <div className="font-mono text-2xl font-black tracking-[0.3em] text-cyan-300">{bindCode.code}</div>
                  <div className="mt-2 text-xs text-slate-400">
                    {Math.max(Math.floor(bindCode.expiresIn / 60), 1)} 分钟内有效。
                  </div>
                </div>
              ) : null}
            </div>
          ) : null}
        </SectionCard>

        <SectionCard eyebrow="Session" title="会话控制" description="退出入口已经固定挂在左侧侧栏，这里保留说明和重登录路径。">
          <div className="space-y-3 text-sm leading-7 text-slate-300">
            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
              当前账号可以从左侧侧栏直接退出，不需要再回头找弹窗或顶部入口。
            </div>
            <button
              type="button"
              onClick={onLogout}
              className="inline-flex rounded-xl border border-red-400/30 bg-red-500/10 px-4 py-3 text-sm font-semibold text-red-100 transition-colors hover:bg-red-500/20"
            >
              立即退出
            </button>
          </div>
        </SectionCard>
      </div>
    </div>
  );
}

function NotificationsSection({
  notificationHistory,
}: {
  notificationHistory: Array<{
    id: string;
    channel: string;
    status: string;
    created_at: string;
    payload: { title?: string; school_name?: string };
  }>;
}) {
  return (
    <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
      <SectionCard eyebrow="Deliveries" title="最近通知" description="这里先展示投递历史，后续再把 Bark/WxPusher 等推送偏好设置接进来。">
        <div className="space-y-3">
          {notificationHistory.length > 0 ? (
            notificationHistory.map((item) => (
              <div key={item.id} className="rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-4">
                <div className="font-medium text-white">
                  {item.payload.school_name ? `${item.payload.school_name}：` : ""}
                  {item.payload.title || "无标题通知"}
                </div>
                <div className="mt-2 text-xs text-slate-400">
                  {humanizeChannel(item.channel)} · {humanizeDeliveryStatus(item.status)} · {new Date(item.created_at).toLocaleString("zh-CN", { hour12: false })}
                </div>
              </div>
            ))
          ) : (
            <EmptyHint text="暂无通知投递记录。" />
          )}
        </div>
      </SectionCard>
      <SectionCard eyebrow="Roadmap" title="通知业务框架位" description="通知中心后续会接入真实的渠道开关和推送配置。">
        <div className="space-y-3 text-sm leading-7 text-slate-300">
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
            当前能力：展示最近通知投递历史。
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
            下一步：把 Bark、微信模板消息、站内通知开关和失败重试策略接进这块模板区域。
          </div>
        </div>
      </SectionCard>
    </div>
  );
}

function SectionCard({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow: string;
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-[2rem] border border-white/10 bg-black/35 p-6 shadow-2xl backdrop-blur-xl">
      <div className="text-xs uppercase tracking-[0.24em] text-cyan-300">{eyebrow}</div>
      <h2 className="mt-2 text-2xl font-bold text-white">{title}</h2>
      <p className="mt-2 text-sm leading-7 text-slate-300">{description}</p>
      <div className="mt-6">{children}</div>
    </section>
  );
}

function MetricCard({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
      <div className="text-xs text-slate-400">{label}</div>
      <div className="mt-2 text-lg font-semibold text-white">{value}</div>
      <div className="mt-1 text-xs text-slate-400">{hint}</div>
    </div>
  );
}

function InfoTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-4">
      <div className="text-xs uppercase tracking-[0.18em] text-slate-500">{label}</div>
      <div className="mt-2 text-lg font-semibold text-white">{value}</div>
    </div>
  );
}

function EmptyHint({ text }: { text: string }) {
  return <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.02] px-4 py-4 text-sm text-slate-400">{text}</div>;
}

function StatusPill({ text, tone }: { text: string; tone: "cyan" | "amber" | "emerald" | "slate" }) {
  const toneClass =
    tone === "cyan"
      ? "border-cyan-400/20 bg-cyan-500/10 text-cyan-200"
      : tone === "amber"
        ? "border-amber-400/20 bg-amber-500/10 text-amber-100"
        : tone === "emerald"
          ? "border-emerald-400/20 bg-emerald-500/10 text-emerald-100"
          : "border-white/10 bg-white/5 text-slate-300";
  return <span className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] ${toneClass}`}>{text}</span>;
}

function humanizeOrderStatus(status: string) {
  if (status === "pending") return "待支付确认";
  if (status === "paid") return "已支付";
  if (status === "canceled") return "已取消";
  return status;
}

function humanizePaymentSource(source: string) {
  if (source === "web_pay") return "网页支付";
  if (source === "wechat_pay") return "微信支付";
  return source;
}

function humanizeChannel(channel: string) {
  if (channel === "sse") return "站内实时流";
  if (channel === "bark") return "Bark";
  return channel;
}

function humanizeDeliveryStatus(status: string) {
  if (status === "pending") return "待投递";
  if (status === "sent") return "已投递";
  if (status === "failed") return "投递失败";
  return status;
}
