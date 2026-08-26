"use client";

import { useEffect, useRef } from "react";

import { useReducedMotion } from "@/lib/hooks/use-reduced-motion";

/**
 * A number that counts to itself.
 *
 * Used on the dashboard's headline figures, where the count is the difference
 * between a statement and an achievement. Four deliberate details:
 *
 * 1. **The server-rendered text is the final value**, and the count starts
 *    only after mount. A component that rendered `0` and animated upwards
 *    would show zero to anyone without JavaScript and would disagree with
 *    itself during hydration.
 * 2. **The text is written imperatively.** Sixty renders a second through
 *    React state re-renders the card, and on this page that card sits beside a
 *    chart.
 * 3. **There is no `aria-live`.** A screen reader announces the figure once,
 *    when the reader reaches it — not sixty times on the way up.
 * 4. **It is a `requestAnimationFrame` loop rather than the animation
 *    library.** Tweening one number into `textContent` is not what a motion
 *    library is for, and importing one to do it would ship its whole engine
 *    for four numerals.
 */
const DURATION_MS = 900;

/** Decelerating, so the number settles rather than stopping dead. */
function easeOut(progress: number): number {
  return 1 - Math.pow(1 - progress, 3);
}

export function CountUp({
  value,
  format,
  className,
}: {
  value: number;
  /** How the number is written — "1,240", "72.4%". Also used for the static text. */
  format: (value: number) => string;
  className?: string;
}) {
  const ref = useRef<HTMLSpanElement | null>(null);

  // Read inside the loop so a re-created formatter does not restart the count
  // on every parent render.
  const formatRef = useRef(format);
  formatRef.current = format;

  const reducedMotion = useReducedMotion();

  useEffect(() => {
    const node = ref.current;
    if (!node || reducedMotion || !Number.isFinite(value)) return;

    let frame = 0;
    const started = performance.now();

    const step = (now: number) => {
      const progress = Math.min((now - started) / DURATION_MS, 1);
      // The final frame writes the exact value: rounding on the way up can
      // leave it a hair short, which on a score is the difference between 79
      // and 80.
      node.textContent = formatRef.current(progress === 1 ? value : value * easeOut(progress));
      if (progress < 1) frame = requestAnimationFrame(step);
    };

    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [value, reducedMotion]);

  return (
    <span ref={ref} className={className}>
      {format(value)}
    </span>
  );
}
