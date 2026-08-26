"use client";

import { domAnimation, LazyMotion } from "framer-motion";

/**
 * The animation feature set, declared once.
 *
 * `LazyMotion` with `domAnimation` and the `m` component rather than the full
 * `motion` component: the full one bundles the layout and drag engines, and
 * nothing in this product drags or animates layout. `strict` makes reaching
 * for `motion.*` by accident a runtime error rather than a silent 30kB.
 *
 * Wrapping per surface rather than at the root keeps the library out of the
 * first load of the pages that never animate — the landing page and the sign
 * in form among them.
 */
export function MotionStage({ children }: { children: React.ReactNode }) {
  return (
    <LazyMotion features={domAnimation} strict>
      {children}
    </LazyMotion>
  );
}
