/**
 * layout.tsx — Root layout
 * Light theme with Inter font, no disclaimer banner.
 */
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Mirae Asset Fund Explorer",
  description:
    "Explore Mirae Asset mutual fund schemes with real-time NAV data, " +
    "performance analytics, and an AI-powered FAQ assistant.",
  keywords: [
    "mutual funds",
    "Mirae Asset",
    "NAV",
    "SIP",
    "expense ratio",
    "fund explorer",
  ],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <meta name="robots" content="noindex" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
