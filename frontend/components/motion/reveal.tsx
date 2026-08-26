"use client";

import { m } from "framer-motion";

import { MotionStage } from "./stage";

import { useReducedMotion } from "@/lib/hooks/use-reduced-motion";

/**
 * A section arriving.
 *
 * The dashboard paints several cards at once, and everything appearing in the
 * same frame reads as a screenshot rather than a page. A short, staggered rise
 * gives the eye an order to read them in — hero first, then the numbers, then
 * the detail — which is the only job this component has. It is not decoration
 * on individual controls: motion that draws attention to a card the student
 * did not act on is the kind this product does without.
 *
 * `LazyMotion` with `domAnimation` and the `m` component rather than
 * `motion.div`: the full `motion` component bundles the layout and drag
 * engines, and a fade that costs a student on a phone an extra download of
 * animation code they will never trigger is not a subtle animation. The
 * feature set here is the DOM one, which is what a transform and an opacity
 * need.
 *
 * `initial={false}` is what honours `prefers-reduced-motion`: it skips the
 * entrance and mounts the content in its final state, rather than playing a
 * faster version of the same movement. The element type never changes between
 * the two, so flipping the system setting does not remount the subtree — a
 * chart inside would otherwise be destroyed and rebuilt.
 */
export function Reveal({
  children,
  delay = 0,
  className,
}: {
  children: React.ReactNode;
  /** Seconds. Keep the whole sequence under ~0.4s; this is orientation, not a show. */
  delay?: number;
  className?: string;
}) {
  const reducedMotion = useReducedMotion();

  return (
    <MotionStage>
      <m.div
        className={className}
        initial={reducedMotion ? false : { opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.34, delay, ease: [0.22, 1, 0.36, 1] }}
      >
        {children}
      </m.div>
    </MotionStage>
  );
}
