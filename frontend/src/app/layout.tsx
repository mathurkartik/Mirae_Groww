/**
 * layout.tsx — Root layout
 * Mounts DisclaimerBanner (fixed top) and sets page metadata.
 */
import type { Metadata } from "next";
import "./globals.css";
import { DisclaimerBanner } from "@/components/DisclaimerBanner";

export const metadata: Metadata = {
  title: "Mirae Asset FAQ Assistant",
  description:
    "Facts-only FAQ assistant for Mirae Asset mutual fund schemes. " +
    "Answers sourced from official Groww pages. No investment advice.",
  keywords: ["mutual funds", "Mirae Asset", "FAQ", "expense ratio", "SIP", "ELSS"],
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
      <body>
        {/* Disclaimer banner — fixed, always visible */}
        <DisclaimerBanner />
        {children}
      </body>
    </html>
  );
}
