import type { Metadata } from "next";
import { IBM_Plex_Sans, IBM_Plex_Mono } from "next/font/google";
import { Toaster } from "@/components/ui/toast";
import "./globals.css";
import "./prism.css";

const plexSans = IBM_Plex_Sans({
  subsets: ["latin", "cyrillic"],
  weight: ["400", "500", "600"],
  variable: "--font-plex-sans",
  display: "swap",
});

const plexMono = IBM_Plex_Mono({
  subsets: ["latin", "cyrillic"],
  weight: ["400", "500"],
  variable: "--font-plex-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "1С Аналитик",
  description: "Чат-консоль для бизнес-аналитиков 1С",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ru" className={`dark ${plexSans.variable} ${plexMono.variable}`}>
      <body>
        {children}
        <Toaster />
      </body>
    </html>
  );
}
