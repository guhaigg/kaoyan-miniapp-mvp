"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { CreditCard, Link2, LogOut, ShieldCheck, Sparkles } from "lucide-react";
import {
  ApiError,
  changeCurrentUserPassword,
  createCurrentUserPaymentOrder,
  createWechatBindCode,
  getCurrentUserPaymentOrders,
  type UserPaymentOrderItem,
} from "@/lib/api";
import type { AccountSpacePanel } from "./account-space-query";
import { AccountEmptyState, AccountSkeletonGrid, AccountSurface } from "./AccountSpaceUi";

const ACCOUNT_PANEL_COPY: Record<Exclude<AccountSpacePanel, null>, string> = {
  billing: "旧的会员页已经并到当前 tab，会员方案、订单列表和升级入口都会留在这里。",
  security: "旧的安全页已经并到当前 tab，密码修改、微信绑定和退出登录会留在这里。",
  notifications: "通知入口已经并入动态 tab，这里只保留账号相关动作。",
};

function formatMoney(item: UserPaymentOrderItem) {
  return `${(item.amount_cents / 100).toFixed(2)} ${item.currency}`;
}

function formatOrderStatus(status: string) {
  if (status === "pending") return "待支付确认";
  if (status === "paid") return "已支付";
  if (status === "canceled") return "已取消";
  return status;
}

function formatOrderSource(source: string) {
  if (source === "web_pay") return "网页支付";
  if (source === "wechat_pay") return "微信支付";
  return source;
}

export function AccountAccountTab({
  accessToken,
  loggedIn,
  membershipLabel,
  premiumExpiresAt,
  wechatBound,
  panel,
  onLoggedOut,
}: {
  accessToken: string | null;
  loggedIn: boolean;
  membershipLabel: string;
  premiumExpiresAt: string | null;
  wechatBound: boolean;
  panel: AccountSpacePanel;
  onLoggedOut: () => Promise<void>;
}) {
  const [message, setMessage] = useState("");
  const [paymentOrders, setPaymentOrders] = useState<UserPaymentOrderItem[]>([]);
  const [ordersLoading, setOrdersLoading] = useState(false);
  const [creatingBindCode, setCreatingBindCode] = useState(false);
  const [bindCode, setBindCode] = useState<{ code: string; expiresIn: number } | null>(null);
  const [passwordForm, setPasswordForm] = useState({ oldPassword: "", newPassword: "" });
  const [changingPassword, setChangingPassword] = useState(false);
  const [creatingPremiumDays, setCreatingPremiumDays] = useState<number | null>(null);
  const isUpgradeable = membershipLabel === "普通用户";

  useEffect(() => {
    if (!accessToken) {
      setPaymentOrders([]);
      setOrdersLoading(false);
      return;
    }

    let cancelled = false;
    setOrdersLoading(true);
    getCurrentUserPaymentOrders(accessToken)
      .then((payload) => {
        if (!cancelled) {
          setPaymentOrders(payload.items);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setPaymentOrders([]);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setOrdersLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [accessToken]);

  async function handleCreateBindCode() {
    if (!accessToken || creatingBindCode) {
      return;
    }
    setCreatingBindCode(true);
    setMessage("");
    try {
      const payload = await createWechatBindCode(accessToken);
      setBindCode({ code: payload.code, expiresIn: payload.expires_in });
      setMessage("微信绑定码已生成。");
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : "生成绑定码失败，请稍后重试。");
    } finally {
      setCreatingBindCode(false);
    }
  }

  async function handleChangePassword() {
    if (!accessToken || changingPassword) {
      return;
    }
    if (!passwordForm.oldPassword || !passwordForm.newPassword) {
      setMessage("请先填写当前密码和新密码。");
      return;
    }
    if (passwordForm.newPassword.length < 8) {
      setMessage("新密码至少 8 位。");
      return;
    }

    setChangingPassword(true);
    setMessage("");
    try {
      await changeCurrentUserPassword(accessToken, {
        old_password: passwordForm.oldPassword,
        new_password: passwordForm.newPassword,
      });
      setPasswordForm({ oldPassword: "", newPassword: "" });
      setMessage("密码已更新。");
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : "修改密码失败，请稍后重试。");
    } finally {
      setChangingPassword(false);
    }
  }

  async function handleCreateOrder(durationDays: 30 | 90 | 365) {
    if (!accessToken || creatingPremiumDays) {
      return;
    }
    setCreatingPremiumDays(durationDays);
    setMessage("");
    try {
      const order = await createCurrentUserPaymentOrder(accessToken, {
        duration_days: durationDays,
        source: "web_pay",
      });
      setPaymentOrders((current) => [order, ...current]);
      setMessage(`${durationDays} 天会员订单已创建，等待支付确认。`);
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : "创建会员订单失败，请稍后重试。");
    } finally {
      setCreatingPremiumDays(null);
    }
  }

  if (!loggedIn) {
    return (
      <AccountEmptyState
        eyebrow="Account"
        title="登录后，这里会变成你的账号操作区"
        description="会员订单、微信绑定、密码修改和退出登录都会集中在这个 tab 里，不再把首屏占满。"
        actions={
          <>
          <Link
            href="/login"
            className="rounded-full bg-[linear-gradient(90deg,#ff7fb7,#68d2ff)] px-5 py-3 text-sm font-semibold text-white"
          >
            去登录
          </Link>
          <Link
            href="/register"
            className="rounded-full border border-slate-200 bg-slate-50 px-5 py-3 text-sm font-semibold text-slate-700"
          >
            新建账号
          </Link>
          </>
        }
      />
    );
  }

  return (
    <section className="space-y-5">
      {panel ? (
        <div className="rounded-[1.8rem] border border-pink-100 bg-pink-50/90 px-5 py-4 text-sm leading-7 text-pink-700 shadow-[0_16px_36px_rgba(255,151,201,0.16)]">
          当前面板：<span className="font-semibold">{panel}</span>。{ACCOUNT_PANEL_COPY[panel]}
        </div>
      ) : null}

      <div className="grid gap-4 md:grid-cols-3">
        <AccountSurface interactive className="p-5 shadow-[0_18px_44px_rgba(122,147,192,0.14)]">
          <div className="inline-flex items-center gap-2 rounded-full bg-pink-50 px-3 py-1 text-xs font-semibold text-pink-600">
            <Sparkles size={14} />
            会员状态
          </div>
          <div className="mt-4 text-2xl font-black text-slate-900">{membershipLabel}</div>
          <p className="mt-2 text-sm leading-7 text-slate-600">
            {premiumExpiresAt
              ? `到期时间：${new Date(premiumExpiresAt).toLocaleString("zh-CN", { hour12: false })}`
              : "当前没有会员到期时间记录。"}
          </p>
        </AccountSurface>

        <AccountSurface interactive className="p-5 shadow-[0_18px_44px_rgba(122,147,192,0.14)]">
          <div className="inline-flex items-center gap-2 rounded-full bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-600">
            <Link2 size={14} />
            微信绑定
          </div>
          <div className="mt-4 text-2xl font-black text-slate-900">{wechatBound ? "已绑定" : "未绑定"}</div>
          <p className="mt-2 text-sm leading-7 text-slate-600">绑定后，小程序 silent-login 可以更稳定地命中当前主账号。</p>
        </AccountSurface>

        <AccountSurface interactive className="p-5 shadow-[0_18px_44px_rgba(122,147,192,0.14)]">
          <div className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
            <ShieldCheck size={14} />
            安全维护
          </div>
          <div className="mt-4 text-2xl font-black text-slate-900">密码与会话</div>
          <p className="mt-2 text-sm leading-7 text-slate-600">密码修改和退出登录都会保留在这块，不会再占账号页首屏。</p>
        </AccountSurface>
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
        <AccountSurface>
          <div className="text-xs uppercase tracking-[0.24em] text-sky-500">Membership</div>
          <h3 className="mt-3 text-2xl font-bold text-slate-900">会员与订单</h3>
          <p className="mt-2 text-sm leading-7 text-slate-600">
            这里保留现有订单能力。后续如果接真实支付回调，只需要继续沿这个面板扩展。
          </p>

          {isUpgradeable ? (
            <div className="mt-5 grid gap-4 md:grid-cols-3">
              {[
                { days: 30 as const, price: "29.00", label: "试用一个月" },
                { days: 90 as const, price: "79.00", label: "覆盖复试季" },
                { days: 365 as const, price: "199.00", label: "全年跟进" },
              ].map((plan) => (
                <button
                  key={plan.days}
                  type="button"
                  onClick={() => handleCreateOrder(plan.days)}
                  disabled={creatingPremiumDays !== null}
                  className="rounded-[1.6rem] border border-slate-100 bg-slate-50/80 p-5 text-left transition-transform hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <div className="text-xs uppercase tracking-[0.18em] text-pink-500">{plan.label}</div>
                  <div className="mt-3 text-3xl font-black text-slate-900">¥{plan.price}</div>
                  <div className="mt-2 text-sm text-slate-500">{plan.days} 天高级会员</div>
                  <div className="mt-4 text-sm font-semibold text-sky-700">
                    {creatingPremiumDays === plan.days ? "创建中..." : "创建订单"}
                  </div>
                </button>
              ))}
            </div>
          ) : (
            <div className="mt-5 rounded-[1.6rem] border border-emerald-100 bg-emerald-50/80 px-5 py-4 text-sm leading-7 text-emerald-700">
              当前账号已经拥有高级能力，无需重复下单。
            </div>
          )}

          <div className="mt-6 space-y-3">
            <div className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
              <CreditCard size={14} />
              订单记录
            </div>
            {ordersLoading ? (
              <AccountSkeletonGrid count={3} className="space-y-3" itemClassName="h-20 rounded-[1.4rem] border-slate-100 bg-slate-50/80 shadow-none" />
            ) : paymentOrders.length > 0 ? (
              <div className="space-y-3">
                {paymentOrders.map((item) => (
                  <div key={item.id} className="rounded-[1.4rem] border border-slate-100 bg-slate-50/80 px-4 py-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <div className="text-sm font-semibold text-slate-900">
                          {item.duration_days} 天 · {formatMoney(item)}
                        </div>
                        <div className="mt-1 text-xs text-slate-500">
                          {formatOrderSource(item.source)} · {new Date(item.created_at).toLocaleString("zh-CN", { hour12: false })}
                        </div>
                      </div>
                      <div className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate-600">
                        {formatOrderStatus(item.status)}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded-[1.4rem] border border-dashed border-slate-200 bg-slate-50/60 px-4 py-4 text-sm text-slate-500">
                暂无会员订单记录。
              </div>
            )}
          </div>
        </AccountSurface>

        <div className="space-y-5">
          <AccountSurface>
            <div className="text-xs uppercase tracking-[0.24em] text-sky-500">Security</div>
            <h3 className="mt-3 text-2xl font-bold text-slate-900">密码与绑定</h3>
            <div className="mt-5 space-y-3">
              <input
                value={passwordForm.oldPassword}
                onChange={(event) => setPasswordForm((prev) => ({ ...prev, oldPassword: event.target.value }))}
                type="password"
                autoComplete="current-password"
                placeholder="当前密码"
                className="w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-900 outline-none transition-colors focus:border-sky-300"
              />
              <input
                value={passwordForm.newPassword}
                onChange={(event) => setPasswordForm((prev) => ({ ...prev, newPassword: event.target.value }))}
                type="password"
                autoComplete="new-password"
                placeholder="新密码，至少 8 位"
                className="w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-900 outline-none transition-colors focus:border-sky-300"
              />
              <button
                type="button"
                onClick={handleChangePassword}
                disabled={changingPassword}
                className="rounded-xl border border-sky-100 bg-sky-50 px-4 py-3 text-sm font-semibold text-sky-700 transition-colors hover:bg-sky-100 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {changingPassword ? "更新中..." : "更新密码"}
              </button>
            </div>

            <div className="mt-6 rounded-[1.4rem] border border-slate-100 bg-slate-50/80 px-4 py-4 text-sm leading-7 text-slate-600">
              {wechatBound
                ? "当前账号已经绑定微信，小程序端可以直接认领这个主账号。"
                : "当前账号尚未绑定微信，可以先生成绑定码给小程序端认领。"}
            </div>

            {!wechatBound ? (
              <div className="mt-4">
                <button
                  type="button"
                  onClick={handleCreateBindCode}
                  disabled={creatingBindCode}
                  className="rounded-xl border border-pink-100 bg-pink-50 px-4 py-3 text-sm font-semibold text-pink-700 transition-colors hover:bg-pink-100 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {creatingBindCode ? "生成中..." : bindCode ? "重新生成绑定码" : "生成绑定码"}
                </button>

                {bindCode ? (
                  <div className="mt-4 rounded-[1.4rem] border border-pink-100 bg-pink-50/80 px-4 py-4">
                    <div className="text-xs uppercase tracking-[0.18em] text-pink-500">Bind Code</div>
                    <div className="mt-3 font-mono text-3xl font-black tracking-[0.28em] text-slate-900">{bindCode.code}</div>
                    <div className="mt-2 text-sm text-slate-600">
                      {Math.max(Math.floor(bindCode.expiresIn / 60), 1)} 分钟内有效。
                    </div>
                  </div>
                ) : null}
              </div>
            ) : null}
          </AccountSurface>

          <AccountSurface>
            <div className="text-xs uppercase tracking-[0.24em] text-slate-500">Session</div>
            <h3 className="mt-3 text-2xl font-bold text-slate-900">退出登录</h3>
            <p className="mt-2 text-sm leading-7 text-slate-600">
              退出操作保留在账号 tab 和侧栏里，避免再回到旧 dashboard 里找入口。
            </p>
            <button
              type="button"
              onClick={() => void onLoggedOut()}
              className="mt-5 inline-flex items-center gap-2 rounded-xl border border-rose-100 bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-700 transition-colors hover:bg-rose-100"
            >
              <LogOut size={16} />
              退出登录
            </button>
          </AccountSurface>

          {message ? (
            <div className="rounded-[1.4rem] border border-slate-200 bg-white/90 px-4 py-4 text-sm text-slate-600 shadow-[0_16px_36px_rgba(122,147,192,0.12)]">
              {message}
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
