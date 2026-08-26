"use client";

import { useEffect, useState } from "react";

const QUERY = "(prefers-reduced-motion: reduce)";

/**
 * Whether the student has asked their operating system to stop animating.
 *
 * `globals.css` already collapses CSS transitions for them, but a canvas
 * animation and a JavaScript reward sequence are not transitions — a sequence
 * that never starts is not the same as one that runs at 0.01ms (FR-7.10), so
 * the components check the query themselves.
 *
 * Starts `false` so the server render and the first client render agree; the
 * effect corrects it before anything animates.
 */
export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    const media = window.matchMedia(QUERY);
    setReduced(media.matches);

    const onChange = (event: MediaQueryListEvent) => setReduced(event.matches);
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

  return reduced;
}
