import type { Metadata } from "next";
import { IBM_Plex_Sans, IBM_Plex_Mono, JetBrains_Mono } from "next/font/google";
import { Toaster } from "@/components/ui/toast";
import "./globals.css";
import "./prism.css";

const plexSans = IBM_Plex_Sans({
  subsets: ["latin", "cyrillic"],
  weight: ["400", "500", "600"],
  variable: "--font-plex-sans",
  display: "swap",
});

// Plex Mono — для логотипа в Stencil (700 uppercase) + старого использования (400, 500)
const plexMono = IBM_Plex_Mono({
  subsets: ["latin", "cyrillic"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-plex-mono",
  display: "swap",
});

// JetBrains Mono — служебный технический текст (eyebrow, meta-строки, subtitle)
const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin", "cyrillic"],
  weight: ["400", "500"],
  variable: "--font-jb-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "1С Аналитик",
  description: "Чат-консоль для бизнес-аналитиков 1С",
};

// Force dynamic rendering — иначе process.env.NEXT_PUBLIC_BACKEND_URL inline-ится на build-time,
// а в Electron-сборке backend стартует на random порту runtime. Server-component читает env
// при каждом запросе и инжектит actual URL в window.__BACKEND_URL__.
export const dynamic = "force-dynamic";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8010";
  return (
    <html lang="ru" className={`dark ${plexSans.variable} ${plexMono.variable} ${jetbrainsMono.variable}`} data-accent="signal">
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `window.__BACKEND_URL__ = ${JSON.stringify(backendUrl)};`,
          }}
        />
      </head>
      <body>
        {children}
        <Toaster />
      </body>
    </html>
  );
}
