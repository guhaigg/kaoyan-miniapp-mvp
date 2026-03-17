"use client";

import { useRef } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { motion } from "framer-motion";
import { AlertTriangle, Clock, FileText } from "lucide-react";
import { useHomeAnnouncementsQuery } from "@/hooks/useSearch";

if (typeof window !== "undefined") {
  gsap.registerPlugin(ScrollTrigger, useGSAP);
}

export default function HomePage() {
  const container = useRef<HTMLDivElement>(null);
  const { data, isLoading } = useHomeAnnouncementsQuery({
    page: 1,
    page_size: 6,
  });

  useGSAP(
    () => {
      gsap.to(".data-stream", {
        height: "100%",
        ease: "none",
        scrollTrigger: {
          trigger: ".timeline-container",
          start: "top center",
          end: "bottom center",
          scrub: 1,
        },
      });

      gsap.utils.toArray<HTMLElement>(".timeline-item").forEach((item) => {
        const isUrgent = item.classList.contains("is-urgent");
        const glowColor = isUrgent ? "#f97316" : "#06b6d4";
        const dot = item.querySelector<HTMLElement>(".node-dot");
        const cardAndTime = item.querySelectorAll<HTMLElement>(".feed-card, .time-label");
        if (!dot || cardAndTime.length === 0) return;

        const tl = gsap.timeline({
          scrollTrigger: {
            trigger: item,
            start: "top 85%",
            toggleActions: "play none none reverse",
          },
        });

        tl.fromTo(
          dot,
          {
            borderColor: "rgba(255,255,255,0.2)",
            backgroundColor: "#050b14",
            boxShadow: "none",
          },
          {
            borderColor: glowColor,
            backgroundColor: glowColor,
            boxShadow: `0 0 20px ${glowColor}`,
            duration: 0.3,
          },
        );
        tl.fromTo(
          cardAndTime,
          { y: 30, opacity: 0 },
          {
            y: 0,
            opacity: 1,
            duration: 0.6,
            stagger: 0.1,
            ease: "back.out(1.5)",
          },
          "-=0.1",
        );
      });
    },
    { scope: container },
  );

  const timelineItems = data?.items || [];
  const indexedCount = data?.total || 0;

  return (
    <motion.div
      ref={container}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.98 }}
      transition={{ duration: 0.4 }}
      className="pt-10"
    >
      <div className="mx-auto max-w-4xl px-4 pb-20 text-center">
        <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-cyan-500/20 bg-cyan-500/10 px-4 py-1.5 font-mono text-xs text-cyan-400 shadow-[0_0_15px_rgba(6,182,212,0.15)]">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-cyan-400 opacity-75"></span>
            <span className="relative inline-flex h-2 w-2 rounded-full bg-cyan-500"></span>
          </span>
          GW Core Engine Online · 已索引 {indexedCount || "..."} 条情报
        </div>
        <h1 className="mb-6 text-5xl font-extrabold leading-tight tracking-tight text-white md:text-7xl">
          比别人快一步的 <br />
          <span className="bg-gradient-to-r from-cyan-400 to-white bg-clip-text text-transparent drop-shadow-[0_0_20px_rgba(6,182,212,0.4)]">
            考研情报中枢
          </span>
        </h1>
        <p className="mx-auto max-w-2xl text-lg text-slate-400">
          彻底告别反复刷新官网的焦虑。当调剂名额或复试线产生异动，数据会像光一样坠入这里。
        </p>
      </div>

      <div className="timeline-container relative mx-auto max-w-5xl">
        <div className="absolute bottom-0 left-6 top-0 w-1 -translate-x-1/2 rounded-full bg-white/5 md:left-1/2" />
        <div className="data-stream absolute left-6 top-0 h-0 w-1 -translate-x-1/2 rounded-full bg-cyan-400 shadow-[0_0_20px_#06b6d4] md:left-1/2" />

        <div className="space-y-16 px-4 pb-16 pt-10 md:space-y-24 md:px-0">
          {isLoading ? (
            <div className="rounded-2xl border border-white/10 bg-white/5 p-6 text-sm text-slate-300">
              正在重构数据卡片...
            </div>
          ) : null}

          {!isLoading && timelineItems.length === 0 ? (
            <div className="rounded-2xl border border-white/10 bg-white/5 p-6 text-sm text-slate-300">
              暂无最新公告。底层探针正在持续观测。
            </div>
          ) : null}

          {timelineItems.map((item, index) => {
            const isRight = index % 2 === 1;
            const isUrgent = item.source_type === "manual";
            const timeText = formatRelativeTime(item.published_at || item.updated_at);
            return (
              <div
                key={item.id}
                className={`timeline-item ${isUrgent ? "is-urgent" : ""} group relative flex flex-col items-center justify-between md:flex-row`}
              >
                <div className="node-dot absolute left-6 z-10 h-5 w-5 -translate-x-1/2 rounded-full border-[3px] border-white/20 bg-[#050b14] md:left-1/2" />
                {isRight ? <div className="hidden md:block md:w-[45%]" /> : null}
                <div
                  className={`w-full pl-14 text-left md:w-[45%] ${
                    isRight ? "md:pl-12" : "md:pl-0 md:pr-12 md:text-right"
                  }`}
                >
                  <div
                    className={`time-label mb-2 flex items-center gap-1 font-mono text-xs opacity-0 ${
                      isUrgent ? "text-orange-400" : "text-cyan-400"
                    } ${isRight ? "" : "md:justify-end"}`}
                  >
                    {isUrgent ? <AlertTriangle size={14} /> : <Clock size={14} />}
                    {timeText}
                  </div>
                  <a
                    href={item.source_url || "#"}
                    target={item.source_url ? "_blank" : undefined}
                    rel={item.source_url ? "noopener noreferrer" : undefined}
                    className={`feed-card block cursor-pointer rounded-2xl border p-6 opacity-0 shadow-xl backdrop-blur-xl transition-all ${
                      isUrgent
                        ? "relative overflow-hidden border-orange-500/30 bg-orange-950/20 hover:border-orange-500 hover:bg-orange-900/30"
                        : "border-white/10 bg-white/5 hover:border-cyan-400/50 hover:bg-cyan-900/10"
                    }`}
                  >
                    {isUrgent ? (
                      <div className="absolute right-0 top-0 h-32 w-32 -translate-y-1/2 translate-x-1/2 rounded-full bg-orange-500/10 blur-3xl" />
                    ) : null}
                    <h3 className="mb-2 text-lg font-bold leading-snug text-white">{item.title}</h3>
                    <p className="mb-4 line-clamp-2 text-sm text-slate-400">
                      {item.summary || "暂无摘要，点击查看原文。"}
                    </p>
                    <div
                      className={`flex flex-wrap items-center gap-2 text-xs ${
                        isRight ? "" : "md:justify-end"
                      }`}
                    >
                      <span className="flex items-center gap-1 rounded border border-white/10 bg-slate-800 px-2 py-1 text-white">
                        <FileText size={12} />
                        {item.school_name || "未知院校"}
                      </span>
                      <span className="rounded border border-white/10 bg-black/40 px-2 py-1 text-slate-300">
                        {item.source_type}
                      </span>
                    </div>
                  </a>
                </div>
                {!isRight ? <div className="hidden md:block md:w-[45%]" /> : null}
              </div>
            );
          })}
        </div>
      </div>
    </motion.div>
  );
}

function formatRelativeTime(input: string | null): string {
  if (!input) return "时间未知";
  const date = new Date(input);
  if (Number.isNaN(date.getTime())) return "时间未知";
  const diffMs = Date.now() - date.getTime();
  if (diffMs < 60 * 1000) return "刚刚抓取";
  if (diffMs < 60 * 60 * 1000) return `${Math.floor(diffMs / (60 * 1000))} 分钟前`;
  if (diffMs < 24 * 60 * 60 * 1000) return `${Math.floor(diffMs / (60 * 60 * 1000))} 小时前`;
  return `${Math.floor(diffMs / (24 * 60 * 60 * 1000))} 天前`;
}
