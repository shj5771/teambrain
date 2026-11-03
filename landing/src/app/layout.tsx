import type { Metadata } from "next";
import "../styles.css";

// 배포 도메인이 확정되면 Vercel 프로젝트 설정에서 NEXT_PUBLIC_SITE_URL 환경변수만 넣으면 됨(코드 수정 불필요).
// 그전까지는 Vercel이 배포마다 자동으로 주는 VERCEL_URL로 대체.
const siteUrl =
  process.env.NEXT_PUBLIC_SITE_URL ??
  (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : "http://localhost:3000");

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: "TeamBrain — 팀이 채팅만 해도 저절로 똑똑해집니다",
  description:
    "평소 쓰는 팀 메신저에서 AI를 부르기만 하면, 대화가 그대로 팀의 지식이 되고 각자에겐 나를 아는 개인 AI가 생깁니다. 비개발자를 위한 AI 협업 두뇌, TeamBrain.",
  openGraph: {
    title: "TeamBrain — 비개발자를 위한 AI 협업 두뇌",
    description: "흩어지는 AI 활용을, 쌓이는 팀 지능으로. 데이터는 우리 서버에.",
    type: "website",
    locale: "ko_KR",
  },
  twitter: {
    card: "summary_large_image",
    title: "TeamBrain — 비개발자를 위한 AI 협업 두뇌",
    description: "흩어지는 AI 활용을, 쌓이는 팀 지능으로. 데이터는 우리 서버에.",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
