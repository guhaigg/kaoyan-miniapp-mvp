import Link from "next/link";
import { BellRing, ExternalLink, Radar, Sparkles } from "lucide-react";
import type { AccountActivityItem } from "./account-space-data";
import { formatAccountSpaceDate } from "./account-space-data";
import type { AccountSpacePanel } from "./account-space-query";
import { AccountEmptyState, AccountSkeletonGrid, AccountSurface } from "./AccountSpaceUi";

function kindLabel(kind: AccountActivityItem["kind"]) {
  if (kind === "signal") return "雷达命中";
  if (kind === "notice") return "关注更新";
  return "通知历史";
}

function ActivityIcon({ kind }: { kind: AccountActivityItem["kind"] }) {
  if (kind === "signal") {
    return <Radar size={14} />;
  }
  if (kind === "notice") {
    return <Sparkles size={14} />;
  }
  return <BellRing size={14} />;
}

export function AccountActivityTab({
  items,
  loggedIn,
  loading,
  panel,
}: {
  items: AccountActivityItem[];
  loggedIn: boolean;
  loading: boolean;
  panel: AccountSpacePanel;
}) {
  if (!loggedIn) {
    return (
      <AccountEmptyState
        eyebrow="Activity"
        title="登录后，这里会变成你的个人动态流"
        description="新公告、雷达命中、已送达通知都会按时间线聚在这里，先看到发生了什么，再决定下一步要盯谁。"
        actions={
          <>
          <Link
            href="/login"
            className="rounded-full bg-[linear-gradient(90deg,#ff7fb7,#68d2ff)] px-5 py-3 text-sm font-semibold text-white shadow-[0_12px_28px_rgba(253,146,195,0.28)]"
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

  if (loading) {
    return (
      <AccountSkeletonGrid count={3} className="space-y-4" itemClassName="h-40" />
    );
  }

  return (
    <section className="space-y-4">
      {panel === "notifications" ? (
        <div className="rounded-[1.8rem] border border-pink-100 bg-pink-50/90 px-5 py-4 text-sm leading-7 text-pink-700 shadow-[0_16px_36px_rgba(255,151,201,0.16)]">
          旧的通知页已经并入这里了。现在通知历史、关注更新和雷达命中会统一落在这条动态流里。
        </div>
      ) : null}

      {items.length === 0 ? (
        <AccountEmptyState
          eyebrow="No Activity Yet"
          title="你的空间还没有长出第一条动态"
          description="先去搜索学校、加一点关注或补一个雷达范围，之后新的公告和命中信号就会开始在这里累积。"
          actions={
            <>
            <Link href="/announcements" className="rounded-full border border-sky-100 bg-sky-50 px-5 py-3 text-sm font-semibold text-sky-700">
              去搜索页加关注
            </Link>
            <Link href="/watchlist" className="rounded-full border border-slate-200 bg-slate-50 px-5 py-3 text-sm font-semibold text-slate-700">
              去工作台设置雷达
            </Link>
            </>
          }
        />
      ) : null}

      {items.map((item) => (
        <AccountSurface
          key={item.id}
          interactive
          className="p-5 shadow-[0_18px_44px_rgba(122,147,192,0.14)] transition-transform duration-200 hover:-translate-y-0.5"
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
              <ActivityIcon kind={item.kind} />
              {kindLabel(item.kind)}
            </div>
            <div className="text-xs tracking-[0.14em] text-slate-400">{formatAccountSpaceDate(item.timestamp) || "时间未知"}</div>
          </div>

          <h3 className="mt-4 text-xl font-bold leading-8 text-slate-900">{item.title}</h3>
          <p className="mt-2 text-sm leading-7 text-slate-600">{item.subtitle || "这条动态没有额外摘要，但已经进入你的个人流。"} </p>

          <div className="mt-4 flex flex-wrap gap-2">
            {item.tags.map((tag) => (
              <span key={`${item.id}-${tag}`} className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-500">
                {tag}
              </span>
            ))}
          </div>

          {item.href ? (
            <div className="mt-5">
              <a
                href={item.href}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 rounded-full border border-pink-100 bg-pink-50 px-4 py-2 text-sm font-semibold text-pink-700 transition-colors hover:bg-pink-100"
              >
                查看源站
                <ExternalLink size={14} />
              </a>
            </div>
          ) : null}
        </AccountSurface>
      ))}
    </section>
  );
}
