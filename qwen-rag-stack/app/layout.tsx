import type { Metadata } from "next";
import { headers } from "next/headers";
import "./globals.css";

export async function generateMetadata(): Promise<Metadata> {
  const requestHeaders = await headers();
  const host = requestHeaders.get("host") ?? "localhost:5173";
  const local = /^(localhost|127\.0\.0\.1)(:\d+)?$/.test(host);
  const origin = new URL(`${local ? "http" : "https"}://${host}`);
  const title = "MedAI — Meddies Health AI";
  const description = "Hiểu triệu chứng, chủ động chăm sóc. Trợ lý thông tin sức khỏe bằng tiếng Việt.";
  const image = new URL("/og.png", origin).href;
  return {
    title, description, metadataBase: origin,
    icons: { icon: "/favicon.svg", shortcut: "/favicon.svg" },
    openGraph: { title, description, type: "website", locale: "vi_VN", images: [{ url: image, alt: "MedAI — Hiểu triệu chứng, chủ động chăm sóc." }] },
    twitter: { card: "summary_large_image", title, description, images: [image] },
  };
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="vi"><body>{children}</body></html>;
}
