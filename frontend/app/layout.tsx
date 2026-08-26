import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";

import "./globals.css";
import { Providers } from "./providers";
import { SiteHeader } from "@/components/layout/site-header";
import { SkipLink } from "@/components/layout/skip-link";
import { MobileNav } from "@/components/layout/mobile-nav";

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
          {/* The bottom padding clears the phone's navigation bar, which is
              fixed over the end of the page. */}
          <main id="main" className="mx-auto w-full max-w-7xl px-4 pt-8 pb-28 sm:px-6 md:pb-8">
            {children}
          </main>
          <MobileNav />
        </Providers>
      </body>
    </html>
  );
}
