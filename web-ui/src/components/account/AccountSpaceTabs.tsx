"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { usePathname, useSearchParams } from "next/navigation";
import type { AccountSpacePanel, AccountSpaceTab } from "./account-space-query";

const TAB_ITEMS: Array<{
  id: AccountSpaceTab;
  label: string;
}> = [
  { id: "activity", label: "动态" },
  { id: "following", label: "关注" },
  { id: "radar", label: "雷达" },
  { id: "account", label: "账号" },
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
    <nav className="border-b border-black/6 bg-white/92 backdrop-blur">
      <div className="mx-auto flex max-w-[1440px] items-center gap-1 overflow-x-auto px-4 md:gap-5 md:px-6">
        {TAB_ITEMS.map((item) => {
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
              className={`relative inline-flex shrink-0 items-center rounded-full px-4 py-3 text-sm font-semibold transition-colors ${
                active ? "text-[#00aeec]" : "text-slate-600 hover:text-slate-900"
              }`}
            >
              {active ? (
                <motion.span
                  layoutId="account-space-active-tab"
                  className="absolute inset-0 rounded-full bg-[#00aeec]/12"
                  transition={{ type: "spring", stiffness: 340, damping: 28 }}
                />
              ) : null}
              <span className="relative">{item.label}</span>
              {active ? (
                <motion.span
                  layoutId="account-space-active-underline"
                  className="absolute -bottom-[1px] left-2 right-2 h-[3px] rounded-full bg-[#00aeec]"
                  transition={{ type: "spring", stiffness: 380, damping: 32 }}
                />
              ) : null}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
