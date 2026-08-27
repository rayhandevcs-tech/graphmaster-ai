"use client";

import { useId } from "react";
import { m } from "framer-motion";

import { MotionStage } from "@/components/motion/stage";
import { DURATION, EASE, STAGGER } from "@/lib/motion/tokens";
import { cn } from "@/lib/utils";

/**
 * The three objects the celebration hands over.
 *
 * These replaced `lucide-react`'s `Crown` and `Hammer`. A 2px stroke icon is
 * interface furniture — the same weight of line as the settings cog — and a
 * reward drawn in it cannot read as an object worth earning. What makes a
 * shape read as solid is having a lit face and a shadow face, so every prop
 * here is built from at least two planes.
 *
 * **No colour literals.** Each prop is a `text-tier-*` group and every shade is
 * `currentColor` at a different opacity, which is what lets the same drawing
 * work in both themes — the crown is gold leaf on white and burnished gold on
 * near-black without this file knowing either colour.
 *
 * Gradient ids come from `useId`. Two celebrations mounted on one page with a
 * hard-coded id would both paint with whichever one rendered first.
 */

/**
 * The crown.
 *
 * A band, five points and a centre gem. The band is split down the middle into
 * a lit face and a shadow face; each point gets a lighter inner facet. The
 * asymmetry is the whole trick — a symmetrical crown in one flat fill is a
 * silhouette, and a silhouette has no volume no matter how detailed it is.
 */
export function TierCrown({ className }: { className?: string }) {
  const uid = useId().replace(/:/g, "");

  return (
    <svg viewBox="0 0 64 56" className={cn("size-12", className)} aria-hidden>
      <defs>
        <linearGradient id={`${uid}-metal`} x1="0" y1="0" x2="1" y2="0.4">
          <stop offset="0" stopColor="currentColor" stopOpacity="1" />
          <stop offset="0.55" stopColor="currentColor" stopOpacity="0.82" />
          <stop offset="1" stopColor="currentColor" stopOpacity="0.55" />
        </linearGradient>
      </defs>

      {/* The points, and the hollows between them. One path so the peaks and
          the valleys share an outline the way a cast object would. */}
      <path
        d="M4 40 2 12l14 11L32 4l16 19 14-11-2 28z"
        fill={`url(#${uid}-metal)`}
        stroke="currentColor"
        strokeOpacity="0.35"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      {/* Inner facets: a lighter wedge inside each of the three tall points,
          catching the light the way a bevelled edge does. */}
      <path
        d="M32 9 24 21h16zM7 17l7 6-2 12zM57 17l-7 6 2 12z"
        fill="currentColor"
        fillOpacity="0.22"
        className="text-primary-foreground"
      />

      {/* The band. Darker than the points because it faces down and away. */}
      <rect x="3" y="39" width="58" height="13" rx="4" fill={`url(#${uid}-metal)`} />
      <rect x="3" y="46" width="58" height="6" rx="3" fill="currentColor" fillOpacity="0.28" />

      {/* Gems: one on the centre point, two on the band. */}
      <circle cx="32" cy="18" r="4.5" fill="currentColor" fillOpacity="0.9" />
      <circle cx="30.5" cy="16.5" r="1.6" className="fill-card" opacity="0.75" />
      <circle cx="16" cy="45.5" r="3" fill="currentColor" fillOpacity="0.55" />
      <circle cx="48" cy="45.5" r="3" fill="currentColor" fillOpacity="0.55" />
    </svg>
  );
}

/**
 * The flower, opening.
 *
 * Petals in two layers: a back layer rotated 36° and darker, a front layer over
 * it with a curled tip. The overlap is what reads as a flower — five ellipses
 * around a dot reads as a diagram of one.
 *
 * The back layer opens first, so the bloom unfolds rather than appearing.
 *
 * **It provides its own `MotionStage`.** Every petal starts at `scale: 0`, and
 * an `m.*` element outside a `LazyMotion` provider never leaves its initial
 * state — so rendered anywhere but inside the celebration, this drew five
 * creases and no petals at all. A nested provider with the same feature set is
 * a no-op inside the celebration and the difference between a flower and
 * nothing anywhere else.
 */
export function TierFlower({ className }: { className?: string }) {
  return (
    <MotionStage>
      <FlowerDrawing className={className} />
    </MotionStage>
  );
}

function FlowerDrawing({ className }: { className?: string }) {
  const uid = useId().replace(/:/g, "");
  const front = [0, 72, 144, 216, 288];
  const back = front.map((angle) => angle + 36);

  return (
    <svg viewBox="0 0 64 64" className={cn("size-16", className)} aria-hidden>
      <defs>
        <linearGradient id={`${uid}-petal`} x1="0.5" y1="0" x2="0.5" y2="1">
          <stop offset="0" stopColor="currentColor" stopOpacity="0.72" />
          <stop offset="1" stopColor="currentColor" stopOpacity="1" />
        </linearGradient>
      </defs>

      {back.map((angle, index) => (
        <g key={`b${angle}`} transform={`rotate(${angle} 32 32)`}>
          <m.ellipse
            cx="32"
            cy="17"
            rx="6"
            ry="14"
            fill="currentColor"
            fillOpacity="0.55"
            style={{ transformBox: "view-box", transformOrigin: "32px 32px" }}
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: DURATION.settle, delay: index * STAGGER, ease: EASE.standard }}
          />
        </g>
      ))}

      {front.map((angle, index) => (
        <g key={`f${angle}`} transform={`rotate(${angle} 32 32)`}>
          <m.path
            // A petal with a curled tip and a crease, rather than an ellipse.
            d="M32 32c-7-2-9-9-7-15 1-4 4-7 7-8 3 1 6 4 7 8 2 6 0 13-7 15z"
            fill={`url(#${uid}-petal)`}
            style={{ transformBox: "view-box", transformOrigin: "32px 32px" }}
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{
              duration: DURATION.settle,
              delay: (back.length + index) * STAGGER,
              ease: EASE.standard,
            }}
          />
          <path
            d="M32 27c-2-4-2-9 0-13"
            stroke="currentColor"
            strokeOpacity="0.3"
            strokeWidth="1.2"
            fill="none"
            strokeLinecap="round"
          />
        </g>
      ))}

      <m.g
        style={{ transformBox: "view-box", transformOrigin: "32px 32px" }}
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{
          duration: DURATION.base,
          delay: (back.length + front.length) * STAGGER,
          ease: EASE.standard,
        }}
      >
        <circle cx="32" cy="32" r="8" className="fill-tier-crown" />
        <circle cx="32" cy="32" r="8" fill="currentColor" fillOpacity="0.18" />
        {/* Stipple, so the centre is a seed head rather than a dot. */}
        <g className="fill-tier-crown-foreground" opacity="0.55">
          <circle cx="30" cy="30" r="1" />
          <circle cx="34" cy="31" r="1" />
          <circle cx="31" cy="34" r="1" />
          <circle cx="34.5" cy="34.5" r="1" />
        </g>
      </m.g>
    </svg>
  );
}

/**
 * The mallet.
 *
 * **Deliberately a toy, and this is a requirement rather than a style choice.**
 * FR-7.6 says the lowest tier must never read as humiliating, so the prop that
 * delivers it is drawn with comic proportions no real tool has: an oversized
 * rounded head, a fat stubby handle, a highlight along the top.
 *
 * "Make it more realistic" was the request that started this work, and for
 * this one object it is the wrong answer — a plausible claw hammer swinging at
 * a student who scored badly is exactly what the specification rules out.
 */
export function TierMallet({ className }: { className?: string }) {
  const uid = useId().replace(/:/g, "");

  return (
    <svg viewBox="0 0 64 64" className={cn("size-14", className)} aria-hidden>
      <defs>
        <linearGradient id={`${uid}-head`} x1="0" y1="0" x2="0.3" y2="1">
          <stop offset="0" stopColor="currentColor" stopOpacity="0.95" />
          <stop offset="1" stopColor="currentColor" stopOpacity="0.6" />
        </linearGradient>
      </defs>

      {/* Handle first, so the head sits over it. */}
      <rect
        x="28"
        y="26"
        width="9"
        height="34"
        rx="4.5"
        fill="currentColor"
        fillOpacity="0.45"
        transform="rotate(-8 32 43)"
      />
      <rect
        x="28"
        y="52"
        width="9"
        height="8"
        rx="4"
        fill="currentColor"
        fillOpacity="0.7"
        transform="rotate(-8 32 43)"
      />

      {/* The head: wide, round-cornered, and much too big for the handle. */}
      <rect x="8" y="10" width="48" height="22" rx="10" fill={`url(#${uid}-head)`} />
      {/* The striking face, a shade darker so the block has a front and a top. */}
      <rect x="8" y="24" width="48" height="8" rx="4" fill="currentColor" fillOpacity="0.3" />
      {/* One highlight along the lit edge. */}
      <rect x="14" y="14" width="24" height="4" rx="2" className="fill-card" opacity="0.4" />
    </svg>
  );
}
