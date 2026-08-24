"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";
import type { ComponentProps } from "react";

/**
 * Dark mode (NFR-4.2).
 *
 * `class` rather than a media query, so a student can override the operating
 * system — a lecture theatre projector and a late-night library have opposite
 * needs. The choice is stored in `localStorage`; `suppressHydrationWarning` on
 * `<html>` covers the class next-themes writes before React hydrates.
 */
export function ThemeProvider({ children, ...props }: ComponentProps<typeof NextThemesProvider>) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      // Without this every colour in the page transitions at once when the
      // theme flips, which reads as a fault rather than a setting.
      disableTransitionOnChange
      {...props}
    >
      {children}
    </NextThemesProvider>
  );
}
