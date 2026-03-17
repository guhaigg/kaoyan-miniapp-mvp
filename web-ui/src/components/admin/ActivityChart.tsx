"use client";

import { motion } from "framer-motion";

interface ActivityChartProps {
  dataPoints?: number[];
}

export default function ActivityChart({ dataPoints = [20, 35, 25, 60, 85, 45, 90, 120, 105, 140, 110, 160] }: ActivityChartProps) {
  const safePoints = dataPoints.length >= 2 ? dataPoints : [20, 35, 25, 60, 85, 45, 90, 120, 105, 140, 110, 160];
  const max = Math.max(...safePoints, 1);

  const points = safePoints
    .map((value, index) => {
      const x = (index / (safePoints.length - 1)) * 100;
      const y = 100 - (value / max) * 100;
      return `${x},${y}`;
    })
    .join(" L ");

  const pathD = `M ${points}`;
  const fillD = `M 0,100 L ${points} L 100,100 Z`;
  const lastValue = safePoints[safePoints.length - 1];
  const lastY = 100 - (lastValue / max) * 100;

  return (
    <div className="relative mt-4 h-[120px] w-full">
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="h-full w-full overflow-visible">
        <defs>
          <linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgba(6, 182, 212, 0.4)" />
            <stop offset="100%" stopColor="rgba(6, 182, 212, 0)" />
          </linearGradient>
          <filter id="glow">
            <feGaussianBlur stdDeviation="2" result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <motion.path
          d={fillD}
          fill="url(#chartGradient)"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 1.5, delay: 0.5 }}
        />

        <motion.path
          d={pathD}
          fill="none"
          stroke="#06b6d4"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          filter="url(#glow)"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 2, ease: "easeInOut" }}
        />

        <motion.circle
          cx="100"
          cy={lastY}
          r="3"
          fill="#ffffff"
          initial={{ scale: 0, opacity: 0 }}
          animate={{ scale: 1, opacity: [1, 0.5, 1] }}
          transition={{ delay: 2, duration: 1.5, repeat: Number.POSITIVE_INFINITY }}
          className="drop-shadow-[0_0_8px_#ffffff]"
        />
      </svg>
    </div>
  );
}
