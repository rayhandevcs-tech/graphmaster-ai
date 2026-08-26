/**
 * The product's movement vocabulary.
 *
 * Four durations and three curves, and every animation in the interface is
 * built from them. The point is not tidiness: motion is read as character, and
 * a page where one card eases in over 200ms while another springs over 600ms
 * reads as two products stitched together. A component that wants a number not
 * on this list is describing a movement GraphMaster does not make.
 */

/** A cubic-bezier, in the tuple shape the animation library expects. */
export type Cubic = [number, number, number, number];

export const DURATION = {
  /** A control acknowledging a press. */
  quick: 0.18,
  /** The default: something arriving or changing state. */
  base: 0.34,
  /** Something coming to rest — a crown settling, a bar refilling. */
  settle: 0.6,
  /** One beat of a celebration. */
  beat: 0.9,
} as const;

export const EASE: Record<"standard" | "out" | "anticipate", Cubic> = {
  /** Fast out, slow in. Everything, unless there is a reason. */
  standard: [0.22, 1, 0.36, 1],
  /** A linear-ish exit for something leaving the frame. */
  out: [0.4, 0, 1, 1],
  /**
   * Winds back before it moves, and overshoots on arrival.
   *
   * Reserved for the hammer swing and the recovery that answers it. An
   * anticipation curve is what makes a movement read as *cartoon* rather than
   * physical, which is the difference between slapstick and something landing
   * on a student who scored badly.
   */
  anticipate: [0.68, -0.5, 0.27, 1.4],
};

/** Arrivals that should feel physical rather than timed. */
export const SPRING = { type: "spring", stiffness: 420, damping: 26, mass: 0.8 } as const;

/** A softer spring, for something heavy settling into place. */
export const SPRING_SOFT = { type: "spring", stiffness: 260, damping: 22, mass: 1 } as const;

/** Gap between items in a staggered group. Six hundredths, never more. */
export const STAGGER = 0.06;
