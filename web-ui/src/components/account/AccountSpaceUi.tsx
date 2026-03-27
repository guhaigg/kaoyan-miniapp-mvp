import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function AccountSurface({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cn(
        "rounded-[2rem] border border-white/80 bg-white/90 p-6 shadow-[0_20px_60px_rgba(122,147,192,0.16)]",
        className,
      )}
    >
      {children}
    </section>
  );
}

export function AccountTabIntro({
  eyebrow,
  title,
  description,
  action,
  className,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <AccountSurface className={className}>
      <div className="text-xs uppercase tracking-[0.24em] text-sky-500">{eyebrow}</div>
      <h2 className="mt-3 text-2xl font-bold text-slate-900">{title}</h2>
      <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-600">{description}</p>
      {action ? <div className="mt-6 flex flex-wrap gap-3">{action}</div> : null}
    </AccountSurface>
  );
}

export function AccountEmptyState({
  eyebrow,
  title,
  description,
  actions,
  className,
}: {
  eyebrow: string;
  title: string;
  description: string;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <AccountSurface className={className}>
      <div className="text-xs uppercase tracking-[0.24em] text-sky-500">{eyebrow}</div>
      <h2 className="mt-3 text-2xl font-bold text-slate-900">{title}</h2>
      <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-600">{description}</p>
      {actions ? <div className="mt-6 flex flex-wrap gap-3">{actions}</div> : null}
    </AccountSurface>
  );
}

export function AccountSkeletonGrid({
  count,
  className,
  itemClassName,
}: {
  count: number;
  className: string;
  itemClassName: string;
}) {
  return (
    <div className={className}>
      {Array.from({ length: count }).map((_, index) => (
        <div
          key={index}
          className={cn(
            "animate-pulse rounded-[2rem] border border-white/80 bg-white/75 shadow-[0_20px_60px_rgba(122,147,192,0.1)]",
            itemClassName,
          )}
        />
      ))}
    </div>
  );
}
