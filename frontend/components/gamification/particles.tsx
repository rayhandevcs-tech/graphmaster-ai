"use client";

import { useMemo } from "react";
import { m } from "framer-motion";
import { Sparkle, Star } from "lucide-react";

import { DURATION, EASE, STAGGER } from "@/lib/motion/tokens";
import { cn } from "@/lib/utils";

/**
 * The pieces a celebration is made of.
 *
 * All of them are absolutely positioned inside a `relative` stage and none of
 * them affects layout, so a burst of confetti cannot push the feedback below
 * it down the page halfway through being read.
 *
 * Randomness is **seeded**. Confetti scattered with `Math.random` differs
 * between the server render and the client's, and React's recovery from that
 * mismatch is throwing away the subtree — at the one moment the whole sequence
 * is on screen. A seeded generator produces the same scatter every time, which
 * also means a screenshot of this page is comparable with the last one.
 */

/** mulberry32 — small, fast, and good enough for scattering paper. */
function seeded(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * Confetti colours.
 *
 * This module may use gold: it is one of the reward surfaces the palette
 * reserves it for (06-frontend-architecture §4). The crown's own colour leads
 * the mix rather than filling it — twenty-four gold pieces would read as a
 * gold rectangle rather than as confetti.
 */
const CONFETTI_COLOURS = [
  "bg-tier-crown",
  "bg-primary",
  "bg-secondary",
  "bg-tier-flower",
  "bg-chart-6",
  "bg-chart-4",
];

export function Confetti({ pieces = 24, className }: { pieces?: number; className?: string }) {
  const scatter = useMemo(() => {
    const random = seeded(0x9e3779b9);
    return Array.from({ length: pieces }, (_, index) => ({
      key: index,
      x: (random() - 0.5) * 190,
      lift: 60 + random() * 60,
      fall: 150 + random() * 90,
      spin: (random() - 0.5) * 720,
      delay: random() * 0.22,
      width: 5 + Math.round(random() * 4),
      height: 8 + Math.round(random() * 6),
      colour: CONFETTI_COLOURS[index % CONFETTI_COLOURS.length] as string,
      round: random() > 0.7,
    }));
  }, [pieces]);

  return (
    <div
      className={cn("pointer-events-none absolute inset-0 overflow-visible", className)}
      aria-hidden
    >
      {scatter.map((piece) => (
        <m.span
          key={piece.key}
          className={cn(
            "absolute top-1/2 left-1/2",
            piece.colour,
            piece.round ? "rounded-full" : "rounded-[1px]",
          )}
          style={{ width: piece.width, height: piece.height }}
          initial={{ x: 0, y: 0, opacity: 0, rotate: 0 }}
          animate={{
            x: [0, piece.x * 0.55, piece.x],
            y: [0, -piece.lift, piece.fall],
            rotate: [0, piece.spin * 0.4, piece.spin],
            opacity: [0, 1, 0],
          }}
          transition={{ duration: 1.7, delay: piece.delay, times: [0, 0.34, 1], ease: EASE.out }}
        />
      ))}
    </div>
  );
}

/** Sparkles radiating from the centre of the stage. */
export function Sparkles({ count = 6, className }: { count?: number; className?: string }) {
  const points = useMemo(
    () =>
      Array.from({ length: count }, (_, index) => {
        const angle = (index / count) * Math.PI * 2 - Math.PI / 2;
        return {
          key: index,
          x: Math.cos(angle) * 62,
          y: Math.sin(angle) * 52,
          delay: index * (STAGGER * 0.7),
        };
      }),
    [count],
  );

  return (
    <div className={cn("pointer-events-none absolute inset-0", className)} aria-hidden>
      {points.map((point) => (
        <m.span
          key={point.key}
          className="text-tier-crown absolute top-1/2 left-1/2"
          initial={{ x: 0, y: 0, scale: 0, opacity: 0 }}
          animate={{ x: point.x, y: point.y, scale: [0, 1, 0.4], opacity: [0, 1, 0] }}
          transition={{ duration: DURATION.beat, delay: point.delay, ease: EASE.standard }}
        >
          <Sparkle className="size-4 fill-current" />
        </m.span>
      ))}
    </div>
  );
}

/** Two rings breathing outward — the steady tier's encouragement. */
export function Pulse({ className }: { className?: string }) {
  return (
    <div
      className={cn("pointer-events-none absolute inset-0 grid place-items-center", className)}
      aria-hidden
    >
      {[0, 0.28].map((delay) => (
        <m.span
          key={delay}
          className="border-tier-steady absolute size-24 rounded-full border-[3px]"
          initial={{ scale: 0.7, opacity: 0.7 }}
          animate={{ scale: 1.9, opacity: 0 }}
          transition={{ duration: 1.1, delay, ease: EASE.out }}
        />
      ))}
    </div>
  );
}

/**
 * Stars orbiting a dazed head.
 *
 * One rotating container rather than three independently animated stars: three
 * transforms meant to stay in formation, timed separately, eventually will not
 * be. The radius clears the head — stars orbiting *inside* the face read as
 * decoration on it rather than as a character seeing stars.
 */
export function OrbitStars({ scale = 1, className }: { scale?: number; className?: string }) {
  return (
    <m.div
      className={cn("pointer-events-none absolute inset-0 grid place-items-center", className)}
      aria-hidden
      initial={{ rotate: 0, opacity: 0 }}
      animate={{ rotate: 360, opacity: 1 }}
      transition={{
        rotate: { duration: 1.4, repeat: Infinity, ease: "linear" },
        opacity: { duration: DURATION.quick },
      }}
    >
      {/* Sized from `scale` rather than a fixed class, because the same
          formation has to clear a 90px head in a card and a 400px head on the
          full-screen stage. Left fixed, the stars orbited *inside* the face
          at the larger size and read as freckles. */}
      <div className="relative" style={{ width: 128 * scale, height: 128 * scale }}>
        {[0, 120, 240].map((angle) => (
          <span
            key={angle}
            className="text-tier-hammer absolute top-1/2 left-1/2"
            style={{
              transform: `rotate(${angle}deg) translate(${54 * scale}px) rotate(-${angle}deg) translate(-50%, -50%)`,
            }}
          >
            <Star className="fill-current" style={{ width: 16 * scale, height: 16 * scale }} />
          </span>
        ))}
      </div>
    </m.div>
  );
}
