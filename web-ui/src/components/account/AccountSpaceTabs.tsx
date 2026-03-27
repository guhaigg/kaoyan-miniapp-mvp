"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import { BellRing, Radar, UserRound, WalletCards } from "lucide-react";
import type { AccountSpacePanel, AccountSpaceTab } from "./account-space-query";

const TAB_ITEMS: Array<{
  id: AccountSpaceTab;
  label: string;
  icon: typeof BellRing;
}> = [
  { id: "activity", label: "动态", icon: BellRing },
  { id: "following", label: "关注", icon: UserRound },
  { id: "radar", label: "雷达", icon: Radar },
  { id: "account", label: "账号", icon: WalletCards },
];

export function AccountSpaceTabs({
  activeTab,
  activePanel,
}: {
  activeTab: AccountSpaceTab;
  activePanel: AccountSpacePanel;
}) {
  const pathname = usePathname();
  const searchParams = useSearchParams();

  return (
    <nav className="mt-5 rounded-[1.8rem] border border-white/80 bg-white/85 p-2 shadow-[0_20px_50px_rgba(122,147,192,0.14)] backdrop-blur">
      <div className="flex gap-2 overflow-x-auto">
        {TAB_ITEMS.map((item) => {
          const Icon = item.icon;
          const params = new URLSearchParams(searchParams.toString());
          params.set("tab", item.id);
          if (item.id === "account" && (activePanel === "billing" || activePanel === "security")) {
            params.set("panel", activePanel);
          } else if (item.id === "activity" && activePanel === "notifications") {
            params.set("panel", activePanel);
          } else {
            params.delete("panel");
          }
          const active = item.id === activeTab;
          return (
            <Link
              key={item.id}
              href={`${pathname}?${params.toString()}`}
              className="relative inline-flex items-center gap-2 rounded-full px-5 py-3 text-sm font-semibold"
            >
              {active ? (
                <motion.span
                  layoutId="account-space-tab-highlight"
                  transition={{ type: "spring", stiffness: 340, damping: 28 }}
                  className="absolute inset-0 rounded-full bg-[linear-gradient(90deg,#ff7fb7,#68d2ff)] shadow-[0_12px_28px_rgba(253,146,195,0.3)]"
                />
              ) : null}
              <span className={`relative z-10 inline-flex items-center gap-2 ${active ? "text-white" : "text-slate-600"}`}>
                <Icon size={16} />
                {item.label}
              </span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
