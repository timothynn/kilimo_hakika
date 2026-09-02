import type { Metadata } from "next";
import { Oswald, Source_Sans_3, Geist_Mono } from "next/font/google";
import "./globals.css";

// next/font downloads and self-hosts these at build time — no runtime request
// to Google. Farmers on intermittent connectivity should never wait on a CDN,
// and a condensed header falling back to a system font loses the signage feel.
const oswald = Oswald({
  variable: "--font-oswald",
  subsets: ["latin"],
  display: "swap",
});

const sourceSans = Source_Sans_3({
  variable: "--font-source-sans",
  subsets: ["latin"],
  display: "swap",
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Kilimo Hakika — DepotReady",
  description:
    "Check whether a government depot will serve you before you travel. Official caps and gazetted prices, nothing else.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${sourceSans.variable} ${oswald.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
