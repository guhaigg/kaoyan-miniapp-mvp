"use client";

import type { ReactNode } from "react";
import { QrCode, X } from "lucide-react";

type Props = {
  mode: "login" | "register";
  onClose: () => void;
  children: ReactNode;
};

export default function BiliAuthModal({ mode, onClose, children }: Props) {
  return (
    <div className="fixed inset-0 z-[95] flex items-center justify-center bg-black/35 px-4 py-8 md:px-6 md:py-10">
      <button type="button" onClick={onClose} aria-label="关闭" className="absolute inset-0 cursor-default" />
      <div className="bili-surface relative z-10 grid w-full max-w-[1080px] overflow-hidden rounded-[24px] lg:grid-cols-[360px_minmax(0,1fr)]">
        <aside className="relative hidden bg-[linear-gradient(180deg,#ffffff,#f3f7ff)] p-8 lg:block">
          <div className="inline-flex items-center rounded-full bg-[#fff0f6] px-3 py-1 text-xs font-semibold text-[#fb7299]">
            GEWU AUTH
          </div>
          <h2 className="mt-4 text-3xl font-black text-[#18191c]">{mode === "login" ? "欢迎回来" : "创建账号"}</h2>
          <p className="mt-3 text-sm leading-7 text-[#61666d]">
            公告检索、调剂雷达、关注提醒和账号权益都统一在这套主账号体系里。
          </p>
          <div className="mt-8 rounded-2xl border border-black/5 bg-white/90 p-5">
            <div className="inline-flex h-24 w-24 items-center justify-center rounded-2xl bg-[linear-gradient(135deg,#ffe3ee,#dff4ff)] text-[#00aeec]">
              <QrCode size={40} />
            </div>
            <p className="mt-4 text-sm font-semibold text-slate-700">扫码登录（预留位）</p>
            <p className="mt-2 text-xs leading-6 text-slate-500">当前保留视觉位，后续接入正式扫码能力。</p>
          </div>
        </aside>

        <section className="relative p-6 md:p-8">
          <button
            type="button"
            onClick={onClose}
            className="absolute right-4 top-4 inline-flex h-8 w-8 items-center justify-center rounded-full text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
            aria-label="关闭"
          >
            <X size={16} />
          </button>
          {children}
        </section>
      </div>
    </div>
  );
}
