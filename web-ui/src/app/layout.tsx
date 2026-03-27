import "./globals.css";
import Providers from "@/lib/query-provider";
import AppChrome from "@/components/layout/AppChrome";
import BootLoader from "@/components/shared/BootLoader";
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
          <AppChrome>{children}</AppChrome>
        </Providers>
      </body>
    </html>
  );
}
