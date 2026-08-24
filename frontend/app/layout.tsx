import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";

import "./globals.css";
import { Providers } from "./providers";
import { SiteHeader } from "@/components/layout/site-header";
import { SkipLink } from "@/components/layout/skip-link";

// Downloaded at build time and served from our own origin, so there is no
// third-party request on first paint (06-frontend-architecture §11).
const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "GraphMaster",
    template: "%s · GraphMaster",
  },
  description:
    "Practise describing graphs in academic English, and get marked on the vocabulary you used.",
};

export const viewport: Viewport = {
  // No `maximum-scale`: capping zoom locks out anyone who needs to magnify
  // the page (NFR-4.x).
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // `suppressHydrationWarning` because next-themes writes the theme class on
    // this element before React hydrates, which is by definition a mismatch.
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.variable} min-h-dvh`}>
        <Providers>
          <SkipLink />
          <SiteHeader />
          <main id="main" className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6">
            {children}
          </main>
        </Providers>
      </body>
    </html>
  );
}
