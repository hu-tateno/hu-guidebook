import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "履修の手引き読解支援システム",
  description: "入学年度別の履修の手引きを、段階的な検索と根拠付き回答で読む教材アプリ",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja">
      <body>{children}</body>
    </html>
  );
}
