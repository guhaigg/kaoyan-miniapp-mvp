import "./globals.css";
import Providers from "@/lib/query-provider";
import Header from "@/components/layout/Header";
import Background from "@/components/layout/Background";
import BootLoader from "@/components/shared/BootLoader";
import Modals from "@/components/shared/Modals";
import Toast from "@/components/shared/Toast";
import AuthBootstrap from "@/components/shared/AuthBootstrap";
import SSEClient from "@/components/shared/SSEClient";

export const metadata = {
  title: "格物简录 GW | 考研情报中枢",
  description: "全网极速考研调剂雷达",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body>
        <Providers>
          <BootLoader />
          <AuthBootstrap />
          <SSEClient />
          <Background />
          <Header />
          <main className="relative z-10 min-h-screen pb-20 pt-16 md:pt-[4.5rem]">
            {children}
          </main>
          <Modals />
          <Toast />
        </Providers>
      </body>
    </html>
  );
}
