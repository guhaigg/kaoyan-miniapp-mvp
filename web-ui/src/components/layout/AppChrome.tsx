"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import Background from "@/components/layout/Background";
import Header from "@/components/layout/Header";
import Modals from "@/components/shared/Modals";
import Toast from "@/components/shared/Toast";

export default function AppChrome({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const isStandaloneHome = pathname === "/";

  return (
    <>
      {isStandaloneHome ? null : <Background />}
      {isStandaloneHome ? null : <Header />}
      <main className={isStandaloneHome ? "relative z-10 min-h-screen" : "relative z-10 min-h-screen pb-20 pt-16 md:pt-[4.5rem]"}>
        {children}
      </main>
      <Modals />
      <Toast />
    </>
  );
}
