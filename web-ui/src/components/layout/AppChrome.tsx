"use client";

import type { ReactNode } from "react";
import Background from "@/components/layout/Background";
import Header from "@/components/layout/Header";
import Modals from "@/components/shared/Modals";
import Toast from "@/components/shared/Toast";

export default function AppChrome({ children }: { children: ReactNode }) {
  return (
    <>
      <Background />
      <Header />
      <main className="relative z-10 min-h-screen pb-20 pt-16 md:pt-[4.5rem]">{children}</main>
      <Modals />
      <Toast />
    </>
  );
}
