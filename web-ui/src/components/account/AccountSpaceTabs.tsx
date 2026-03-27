"use client";

import Link from "next/link";
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
              className={`relative inline-flex shrink-0 items-center py-4 text-sm font-semibold transition-colors after:absolute after:bottom-0 after:left-0 after:h-[3px] after:w-full after:rounded-full after:transition-opacity ${
                active
                  ? "text-[#00aeec] after:opacity-100 after:bg-[#00aeec]"
                  : "text-slate-600 hover:text-slate-900 after:opacity-0 after:bg-transparent"
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
