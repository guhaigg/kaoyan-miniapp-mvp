import "./globals.css";
import Providers from "@/lib/query-provider";
import Header from "@/components/layout/Header";
import Background from "@/components/layout/Background";
import BootLoader from "@/components/shared/BootLoader";
import Modals from "@/components/shared/Modals";
import AuthBootstrap from "@/components/shared/AuthBootstrap";

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
          <Background />
          <Header />
          <main className="relative z-10 pb-20 pt-24">{children}</main>
          <Modals />
        </Providers>
      </body>
    </html>
  );
}
