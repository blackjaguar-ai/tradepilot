import { Space_Grotesk, IBM_Plex_Sans, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";

const display = Space_Grotesk({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  variable: "--font-display-loaded",
});

const body = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-body-loaded",
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-mono-loaded",
});

export const metadata = {
  title: "TradePilot — Ops Console",
  description:
    "Copiloto de operaciones cross-border para Shenzhen Aurora Audio Co. Cotización, repricing y reorden con aprobación humana.",
};

export default function RootLayout({ children }) {
  return (
    <html
      lang="es"
      suppressHydrationWarning
      className={`${display.variable} ${body.variable} ${mono.variable}`}
    >
      <body>{children}</body>
    </html>
  );
}
