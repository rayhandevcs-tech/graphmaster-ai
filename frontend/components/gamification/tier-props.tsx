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
 * reward drawn in it cannot read as an object worth earning.
 *
 * **What makes a drawing read as a solid object.** Not detail. Three things,
 * and every prop here now has all three:
 *
 * - *Two planes at least.* A lit face and a face turned away. One flat fill is
 *   a silhouette however many edges it has.
 * - *A rim light.* A bright hairline along the top edge, where the light
 *   grazes it. This is the cheapest way to sit a shape in space, and the first
 *   version of these props had none at all.
 * - *A specular hit.* One small, hard highlight — on the gem, on a metal
 *   collar, on the mallet's shoulder. It is what separates gold from mustard.
 *
 * **No colour literals.** Each prop is a `text-tier-*` group and every shade is
 * `currentColor` at a different opacity, which is what lets the same drawing
 * work in both themes — the crown is gold leaf on white and burnished gold on
 * near-black without this file knowing either colour. The highlights are
 * `fill-card`, the lightest surface in whichever theme is running.
 *
 * Gradient ids come from `useId`. Two celebrations mounted on one page with a
 * hard-coded id would both paint with whichever one rendered first.
 */

/**
 * The crown.
 *
 * A band, five points, pearls on the peaks and a faceted centre stone. The
 * band is split into a lit face and a shadow face; each tall point gets a
 * lighter inner facet and a rim light down its lit edge. The asymmetry is the
 * whole trick — a symmetrical crown in one flat fill is a silhouette, and a
 * silhouette has no volume no matter how many points you give it.
 */
export function TierCrown({ className }: { className?: string }) {
  const uid = useId().replace(/:/g, "");
  const pearls: [number, number][] = [
    [2, 14],
    [32, 6],
    [62, 14],
  ];

  return (
    <svg viewBox="0 0 64 60" className={cn("size-12", className)} aria-hidden>
      <defs>
        <linearGradient id={`${uid}-metal`} x1="0" y1="0" x2="1" y2="0.4">
          <stop offset="0" stopColor="currentColor" stopOpacity="1" />
          <stop offset="0.5" stopColor="currentColor" stopOpacity="0.86" />
          <stop offset="1" stopColor="currentColor" stopOpacity="0.58" />
        </linearGradient>
        <linearGradient id={`${uid}-band`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="currentColor" stopOpacity="0.95" />
          <stop offset="1" stopColor="currentColor" stopOpacity="0.62" />
        </linearGradient>
      </defs>

      {/* The points and the hollows between them, as one path, so the peaks
          and the valleys share an outline the way a cast object would. */}
      <path
        d="M4 42 2 14l14 11L32 6l16 19 14-11-2 28z"
        fill={`url(#${uid}-metal)`}
        stroke="currentColor"
        strokeOpacity="0.4"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      {/* Inner facets: a lighter wedge inside each tall point, catching the
          light the way a bevelled edge does. */}
      <path
        d="M32 11 24 23h16zM7 19l7 6-2 12zM57 19l-7 6 2 12z"
        className="fill-card"
        opacity="0.22"
      />
      {/* The rim light — the lit edge of each point, drawn as a hairline. */}
      <path
        d="M2 14 16 25M32 6 16 25M32 6l16 19M62 14 48 25"
        className="stroke-card fill-none"
        strokeOpacity="0.5"
        strokeWidth="1.4"
        strokeLinecap="round"
      />

      {/* Pearls on the peaks — the detail that stops the points reading as a
          paper cut-out. */}
      {pearls.map(([cx, cy]) => (
        <g key={cx}>
          <circle cx={cx} cy={cy} r="3.4" fill="currentColor" fillOpacity="0.92" />
          <circle cx={cx - 1} cy={cy - 1.2} r="1.2" className="fill-card" opacity="0.7" />
        </g>
      ))}

      {/* The band. Darker than the points because it faces down and away. */}
      <rect x="3" y="41" width="58" height="14" rx="4" fill={`url(#${uid}-band)`} />
      <rect x="3" y="49" width="58" height="6" rx="3" fill="currentColor" fillOpacity="0.32" />
      <g fill="currentColor" fillOpacity="0.5">
        {[10, 18, 26, 34, 42, 50, 58].map((cx) => (
          <circle key={cx} cx={cx} cy="52" r="1.6" />
        ))}
      </g>
      <rect x="5" y="41.5" width="54" height="1.6" rx="0.8" className="fill-card" opacity="0.45" />

      {/* The centre stone: a table facet, a pavilion below it, one hard
          specular hit. A circle with a dot on it is a bubble, not a gem. */}
      <path d="M32 15l6 5-6 8-6-8z" fill="currentColor" fillOpacity="0.95" />
      <path d="M32 15l6 5H26z" className="fill-card" opacity="0.4" />
      <circle cx="30" cy="19" r="1.3" className="fill-card" opacity="0.85" />

      {[16, 48].map((cx) => (
        <g key={cx}>
          <circle cx={cx} cy="46" r="3.2" fill="currentColor" fillOpacity="0.55" />
          <circle cx={cx - 1} cy="45" r="1" className="fill-card" opacity="0.6" />
        </g>
      ))}
    </svg>
  );
}

/**
 * The flower, opening.
 *
 * Petals in two layers: a back layer rotated 36° and darker, a front layer over
 * it with a curled tip, a crease and a highlight along the lit side. The
 * overlap is what reads as a flower — five ellipses around a dot reads as a
 * diagram of one.
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
          <stop offset="0" stopColor="currentColor" stopOpacity="0.68" />
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
            fillOpacity="0.5"
            style={{ transformBox: "view-box", transformOrigin: "32px 32px" }}
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: DURATION.settle, delay: index * STAGGER, ease: EASE.standard }}
          />
        </g>
      ))}

      {front.map((angle, index) => (
        <g key={`f${angle}`} transform={`rotate(${angle} 32 32)`}>
          <m.g
            style={{ transformBox: "view-box", transformOrigin: "32px 32px" }}
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{
              duration: DURATION.settle,
              delay: (back.length + index) * STAGGER,
              ease: EASE.standard,
            }}
          >
            {/* A petal with a curled tip, rather than an ellipse. */}
            <path
              d="M32 32c-7-2-9-9-7-15 1-4 4-7 7-8 3 1 6 4 7 8 2 6 0 13-7 15z"
              fill={`url(#${uid}-petal)`}
            />
            {/* The crease down the middle and a highlight along the lit side —
                the two marks that give a petal a front and a back. */}
            <path
              d="M32 28c-2-4-2-10 0-14"
              stroke="currentColor"
              strokeOpacity="0.32"
              strokeWidth="1.2"
              fill="none"
              strokeLinecap="round"
            />
            <path
              d="M28 24c-1-5 0-9 2-12"
              className="stroke-card fill-none"
              strokeOpacity="0.45"
              strokeWidth="1.6"
              strokeLinecap="round"
            />
          </m.g>
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
        <circle cx="32" cy="32" r="8.5" className="fill-tier-crown" />
        {/* The centre is a dome, not a disc: a shadow crescent down the lower
            right, stipple for the seed head, one highlight at the upper left. */}
        <path
          d="M32 23.5a8.5 8.5 0 0 1 0 17 6 8.5 0 0 0 0-17z"
          fill="currentColor"
          fillOpacity="0.3"
        />
        <g className="fill-tier-crown-foreground" opacity="0.55">
          <circle cx="30" cy="30" r="1" />
          <circle cx="34" cy="31" r="1" />
          <circle cx="31" cy="34" r="1" />
          <circle cx="34.5" cy="34.5" r="1" />
        </g>
        <circle cx="29" cy="29" r="1.6" className="fill-card" opacity="0.5" />
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
 * rounded head, a short fat handle with a knob on the end, a bright rim light
 * along the top.
 *
 * "Make it look real" was the request that started this work, and it is worth
 * being precise about what that can mean here. The *materials* are now real —
 * a turned wooden handle with a grain line, metal collars where it enters the
 * head, a lit top face and a shadowed striking face. The *object* is still a
 * fairground mallet, because a plausible claw hammer swinging at a student who
 * scored badly is exactly what the specification rules out.
 */
export function TierMallet({ className }: { className?: string }) {
  const uid = useId().replace(/:/g, "");

  return (
    <svg viewBox="0 0 64 64" className={cn("size-14", className)} aria-hidden>
      <defs>
        <linearGradient id={`${uid}-head`} x1="0" y1="0" x2="0.25" y2="1">
          <stop offset="0" stopColor="currentColor" stopOpacity="1" />
          <stop offset="0.55" stopColor="currentColor" stopOpacity="0.82" />
          <stop offset="1" stopColor="currentColor" stopOpacity="0.55" />
        </linearGradient>
        <linearGradient id={`${uid}-grip`} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="currentColor" stopOpacity="0.42" />
          <stop offset="0.4" stopColor="currentColor" stopOpacity="0.72" />
          <stop offset="1" stopColor="currentColor" stopOpacity="0.4" />
        </linearGradient>
        {/* The head's own outline, reused to clip the striking face. Hand
            building that face as a path meant matching two rounded corners by
            eye, and the arcs left a visible notch at the right shoulder. */}
        <clipPath id={`${uid}-block`}>
          <rect x="7" y="9" width="50" height="24" rx="11" />
        </clipPath>
      </defs>

      {/* Handle first, so the head sits over its top end. Turned, not a
          rectangle: a shaft, a swell at the bottom and a knob. */}
      <g transform="rotate(-8 32 43)">
        <rect x="27.5" y="24" width="10" height="34" rx="5" fill={`url(#${uid}-grip)`} />
        <path
          d="M30.5 30v22"
          className="stroke-card fill-none"
          strokeOpacity="0.35"
          strokeWidth="1.4"
          strokeLinecap="round"
        />
        {/* The knob, so the handle terminates instead of stopping. */}
        <ellipse cx="32.5" cy="57" rx="7" ry="5" fill="currentColor" fillOpacity="0.75" />
        <ellipse cx="30.5" cy="55.5" rx="2.4" ry="1.4" className="fill-card" opacity="0.35" />
      </g>

      {/* The head: wide, round-cornered, and much too big for the handle. */}
      <rect x="7" y="9" width="50" height="24" rx="11" fill={`url(#${uid}-head)`} />
      {/* The striking face, a shade darker so the block has a top and a front. */}
      <rect
        x="7"
        y="24"
        width="50"
        height="9"
        fill="currentColor"
        fillOpacity="0.32"
        clipPath={`url(#${uid}-block)`}
      />
      {/* Metal collars at each end — the detail that reads as "made of parts". */}
      <rect x="11" y="11" width="5" height="20" rx="2.5" fill="currentColor" fillOpacity="0.5" />
      <rect x="48" y="11" width="5" height="20" rx="2.5" fill="currentColor" fillOpacity="0.5" />
      {/* Rim light along the top, and one specular hit on the shoulder. */}
      <rect
        x="14"
        y="11.5"
        width="30"
        height="3.5"
        rx="1.75"
        className="fill-card"
        opacity="0.42"
      />
      <ellipse cx="20" cy="17" rx="3.5" ry="2" className="fill-card" opacity="0.3" />
    </svg>
  );
}
