"use client";

import { motion } from "framer-motion";
import { Crown, ShieldCheck, Sparkles } from "lucide-react";

export function AccountSpaceHero({
  displayName,
  username,
  membershipLabel,
  signature,
  stats,
}: {
  displayName: string;
  username: string;
  membershipLabel: string;
  signature: string;
  stats: Array<{ label: string; value: string; tone?: "pink" | "blue" | "slate" }>;
}) {
  return (
    <section className="relative overflow-hidden border-b border-black/5 bg-white">
      <motion.div
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45, ease: "easeOut" }}
        className="relative h-[180px] bg-[linear-gradient(120deg,#7bd9ff_0%,#9ee4ff_20%,#ffd6e7_60%,#ffa6cc_100%)] md:h-[220px]"
      >
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(255,255,255,0.7),transparent_24%),radial-gradient(circle_at_78%_26%,rgba(255,255,255,0.35),transparent_18%),linear-gradient(180deg,rgba(255,255,255,0.08),transparent)]" />
      </motion.div>

      <div className="mx-auto flex max-w-[1440px] flex-col gap-6 px-4 pb-6 md:px-6 lg:flex-row lg:items-end">
        <div className="-mt-12 flex items-end gap-4 md:-mt-14">
          <div className="flex h-24 w-24 items-center justify-center rounded-full border-[5px] border-white bg-[linear-gradient(135deg,#ffb8d6,#86dbff)] text-3xl font-black text-white shadow-[0_18px_44px_rgba(96,122,177,0.25)] md:h-28 md:w-28 md:border-[6px]">
            {displayName.slice(0, 1).toUpperCase()}
          </div>
          <div className="pb-2">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-3xl font-black tracking-tight text-slate-900 md:text-[2.1rem]">{displayName}</h1>
              <span className="inline-flex items-center gap-1 rounded-full bg-white/80 px-3 py-1 text-xs font-semibold text-pink-600 shadow-[0_8px_20px_rgba(255,140,188,0.2)]">
                <Crown size={12} />
                {membershipLabel}
              </span>
            </div>
            <div className="mt-1 text-sm text-slate-500">@{username}</div>
            <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-500">
              <span className="inline-flex items-center gap-1 rounded-full bg-sky-50 px-3 py-1 text-sky-600">
                <Sparkles size={12} />
                个人空间首页
              </span>
              <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-3 py-1 text-slate-600">
                <ShieldCheck size={12} />
                研招动态中心
              </span>
            </div>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-600">{signature}</p>
          </div>
        </div>

        <div className="grid flex-1 grid-cols-2 gap-3 sm:grid-cols-4 lg:max-w-[640px]">
          {stats.map((item, index) => (
            <motion.div
              key={item.label}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.08 * index, duration: 0.35, ease: "easeOut" }}
              className={`rounded-2xl border px-4 py-3 ${
                item.tone === "pink"
                  ? "border-pink-100 bg-pink-50/70"
                  : item.tone === "blue"
                    ? "border-sky-100 bg-sky-50/70"
                    : "border-slate-100 bg-slate-50/80"
              }`}
            >
              <div className="text-xs uppercase tracking-[0.18em] text-slate-400">{item.label}</div>
              <div className="mt-2 text-2xl font-black text-slate-900">{item.value}</div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
