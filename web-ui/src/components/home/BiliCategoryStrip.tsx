"use client";

import Link from "next/link";

const CATEGORY_ITEMS = [
  { label: "院校公告", href: "/search?system_tags=%E5%AD%A6%E6%A0%A1%E5%85%AC%E5%91%8A" },
  { label: "复试通知", href: "/search?keywords=%E5%A4%8D%E8%AF%95" },
  { label: "调剂信息", href: "/search?keywords=%E8%B0%83%E5%89%82" },
  { label: "导师风险", href: "/radar" },
  { label: "关注学校", href: "/watchlist" },
  { label: "账号权益", href: "/account?tab=account" },
];

export default function BiliCategoryStrip() {
  return (
    <section className="border-b border-black/5 bg-white/70 backdrop-blur">
      <div className="mx-auto flex max-w-[1440px] gap-3 overflow-x-auto px-4 py-4 md:px-6">
        {CATEGORY_ITEMS.map((item, index) => (
          <Link
            key={item.label}
            href={item.href}
            className={`shrink-0 rounded-full border px-4 py-2 text-sm font-semibold transition-colors ${
              index % 2 === 0
                ? "border-[#00aeec]/20 bg-[#00aeec]/10 text-[#0093d0] hover:bg-[#00aeec]/16"
                : "border-[#fb7299]/20 bg-[#fb7299]/10 text-[#f25c89] hover:bg-[#fb7299]/16"
            }`}
          >
            {item.label}
          </Link>
        ))}
      </div>
    </section>
  );
}
