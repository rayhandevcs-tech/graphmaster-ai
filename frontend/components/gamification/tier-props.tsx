"use client";

import { useId } from "react";
import { m } from "framer-motion";

import { MotionStage } from "@/components/motion/stage";
import { DURATION, EASE, STAGGER } from "@/lib/motion/tokens";
import { cn } from "@/lib/utils";

/**
 * The three objects the celebration hands over, drawn as stickers.
 *
 * **The style is the point, and it changed.** The previous version modelled
 * each prop with gradients and facets, which is how you draw a thing that is
 * *lit*. Beside a flat-shape character it read as a different product — an
 * illustration borrowed from somewhere else and dropped in. These are drawn
 * the way the character is: flat colour, one lighter plane, and a thick dark
 * outline right round the silhouette.
 *
 * Three rules do all the work:
 *
 * - **The outline is under the fill.** `paint-order: stroke` puts the whole
 *   stroke width outside the shape instead of straddling its edge, so the
 *   line is even and the fill keeps its full size. Straddling, a 5px stroke
 *   eats 2.5px of a 12px highlight.
 * - **Two planes, not a gradient.** One base colour and one lighter shape
 *   sitting on the lit side. A gradient reads as a rendered object; two flat
 *   planes read as a drawn one, and the character beside it is drawn.
 * - **A highlight that follows the form.** The pale stripe down the mallet's
 *   handle and across its head is one continuous shape bending with the
 *   object, which is what tells you it is round.
 *
 * **No colour literals.** Each prop is a `text-tier-*` group: the fill is
 * `currentColor`, the lighter plane is `currentColor` under a `fill-card`
 * wash, and the outline is that tier's own `--tier-*-line` token. The same
 * drawing works in both themes without this file knowing either colour.
 */

/** The sticker outline, as one set of props. */
const LINE = { strokeLinejoin: "round" as const, strokeLinecap: "round" as const };
const STICKER = { paintOrder: "stroke" } as const;

/**
 * The crown.
 *
 * A band, five points, pearls on the peaks and a stone in the middle. The
 * lighter plane runs down the left of every point and along the top of the
 * band, so the light has one direction across the whole object rather than
 * per-part.
 */
export function TierCrown({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 72 66" className={cn("size-12", className)} aria-hidden>
      <g className="stroke-tier-crown-line" strokeWidth="4" style={STICKER} {...LINE}>
        {/* The points and the hollows between them, as one path, so the peaks
            and the valleys share an outline the way a cast object would. */}
        <path d="M8 44 5 15l14 12L36 6l17 21 14-12-3 29z" fill="currentColor" />
        {/* The lit plane: the left face of each point. */}
        <path
          d="M36 6 25 27h8zM5 15l14 12-3 6-8-9zM53 27 44 27 36 6z"
          className="fill-card"
          opacity="0.35"
          stroke="none"
        />

        {/* Pearls. The one detail that stops the points reading as a cut-out. */}
        <circle cx="5" cy="15" r="5" fill="currentColor" />
        <circle cx="36" cy="6" r="5.5" fill="currentColor" />
        <circle cx="67" cy="15" r="5" fill="currentColor" />

        {/* The band, drawn over the feet of the points. */}
        <rect x="5" y="42" width="62" height="18" rx="6" fill="currentColor" />
        <rect
          x="10"
          y="45"
          width="52"
          height="5"
          rx="2.5"
          className="fill-card"
          opacity="0.4"
          stroke="none"
        />

        {/* The stone: a table facet over a pavilion, not a circle with a dot. */}
        <path d="M36 15l7 6-7 9-7-9z" fill="currentColor" strokeWidth="3.4" />
      </g>
      {/* The highlight on the stone sits outside the outlined group, or the
          stroke would trace a 2px dot into a blob. */}
      <circle cx="33" cy="20" r="2" className="fill-card" opacity="0.85" />
    </svg>
  );
}

/**
 * The flower, opening.
 *
 * Petals in two layers: a back layer rotated 36° and darker, a front layer
 * over it, each with a pale crescent along its lit edge. The overlap is what
 * reads as a flower — five ellipses around a dot reads as a diagram of one.
 *
 * The back layer opens first, so the bloom unfolds rather than appearing.
 *
 * **It provides its own `MotionStage`.** Every petal starts at `scale: 0`, and
 * an `m.*` element outside a `LazyMotion` provider never leaves its initial
 * state — so rendered anywhere but inside the celebration, this drew five
 * outlines and no petals at all. A nested provider with the same feature set
 * is a no-op inside the celebration and the difference between a flower and
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
  const front = [0, 72, 144, 216, 288];
  const back = front.map((angle) => angle + 36);

  return (
    <svg viewBox="0 0 72 72" className={cn("size-16", className)} aria-hidden>
      <g className="stroke-tier-flower-line" strokeWidth="3.6" style={STICKER} {...LINE}>
        {back.map((angle, index) => (
          <g key={`b${angle}`} transform={`rotate(${angle} 36 36)`}>
            <m.ellipse
              cx="36"
              cy="20"
              rx="6.5"
              ry="14"
              fill="currentColor"
              opacity="0.75"
              style={{ transformBox: "view-box", transformOrigin: "36px 36px" }}
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{
                duration: DURATION.settle,
                delay: index * STAGGER,
                ease: EASE.standard,
              }}
            />
          </g>
        ))}

        {front.map((angle, index) => (
          <g key={`f${angle}`} transform={`rotate(${angle} 36 36)`}>
            <m.g
              style={{ transformBox: "view-box", transformOrigin: "36px 36px" }}
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{
                duration: DURATION.settle,
                delay: (back.length + index) * STAGGER,
                ease: EASE.standard,
              }}
            >
              {/* Longer than the back layer's ellipses, which is the whole
                  reason the two layers read as one flower: the back tips show
                  in the gaps *between* the front petals. Drawn shorter, the
                  front layer sits inside the back one and the flower reads as
                  a cluster of blobs with a ring behind it. */}
              <path
                d="M36 36c-10-2-14-12-10-20 2-6 6-10 10-11 4 1 8 5 10 11 4 8 0 18-10 20z"
                fill="currentColor"
              />
              {/* The lit crescent down one side. */}
              <path
                d="M31 26c-2-7 0-13 3-17 2 4 2 10 1 17z"
                className="fill-card"
                opacity="0.4"
                stroke="none"
              />
            </m.g>
          </g>
        ))}

        <m.g
          style={{ transformBox: "view-box", transformOrigin: "36px 36px" }}
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{
            duration: DURATION.base,
            delay: (back.length + front.length) * STAGGER,
            ease: EASE.standard,
          }}
        >
          <circle cx="36" cy="36" r="10" className="fill-tier-crown" />
        </m.g>
      </g>

      {/* The seed head, outside the outlined group so the stipple stays
          stipple rather than five outlined discs. */}
      <m.g
        className="fill-tier-crown-foreground"
        opacity="0.6"
        style={{ transformBox: "view-box", transformOrigin: "36px 36px" }}
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{
          duration: DURATION.base,
          delay: (back.length + front.length) * STAGGER,
          ease: EASE.standard,
        }}
      >
        <circle cx="33" cy="33" r="1.4" />
        <circle cx="39" cy="34" r="1.4" />
        <circle cx="34" cy="39" r="1.4" />
        <circle cx="39.5" cy="39" r="1.4" />
      </m.g>
    </svg>
  );
}

/**
 * The mallet.
 *
 * **Deliberately a mallet, and that is a requirement rather than a style
 * choice.** FR-7.6 says the lowest tier must never read as humiliating, so
 * the head is a turned wooden barrel and not a claw, a blade or a sledge.
 * The *materials* are drawn as convincingly as the palette allows; the
 * *object* stays a carpenter's mallet, because what the shape says matters
 * more than how well it is rendered.
 *
 * **What "realistic" means for a flat two-token drawing.** Not more outline
 * and not more geometry — four specific things, none of which the sticker
 * version had:
 *
 * - **End grain.** The face of the head shows concentric rings and a pith
 *   line. It is the single most recognisable thing about cut timber, and it
 *   turns a pale ellipse into the end of a log.
 * - **Grain along the length.** Three long, uneven arcs down the barrel and
 *   the handle. Evenly spaced lines read as a barcode; wood is irregular.
 * - **Steel ferrules.** Two bands in `--silver` with a hard highlight along
 *   the top of each. They are also what says the head is *fitted* to the
 *   handle rather than drawn continuous with it.
 * - **A terminator on the shadow side.** One dark shape down the underside
 *   of both the barrel and the handle, sitting inside the silhouette rather
 *   than tracing it. Two flat planes make a cartoon; a plane plus a
 *   terminator makes a cylinder.
 *
 * The outline stays, thinner than the crown's and the flower's. Dropped
 * entirely, the head disappears against a light card; at the sticker weight
 * it flattens everything the shading just bought.
 */
export function TierMallet({ className }: { className?: string }) {
  const uid = useId().replace(/:/g, "");
  const tilt = "rotate(-16 36 46)";

  return (
    <svg viewBox="0 0 72 94" className={cn("size-14", className)} aria-hidden>
      <defs>
        {/* Across the barrel: lit along the top, turning under at the bottom.
            Both stops are `currentColor`, so this is a shape of light rather
            than a pair of colours and survives either theme. */}
        <linearGradient id={`${uid}-barrel`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="currentColor" stopOpacity="0.82" />
          <stop offset="0.42" stopColor="currentColor" stopOpacity="1" />
          <stop offset="1" stopColor="currentColor" stopOpacity="0.72" />
        </linearGradient>
        <linearGradient id={`${uid}-shaft`} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="currentColor" stopOpacity="0.78" />
          <stop offset="0.35" stopColor="currentColor" stopOpacity="1" />
          <stop offset="1" stopColor="currentColor" stopOpacity="0.68" />
        </linearGradient>
        {/* Clips the grain to the timber it runs through, so a long arc can be
            drawn past the edge and still stop at it. */}
        <clipPath id={`${uid}-barrel-clip`}>
          <rect x="3" y="8" width="58" height="38" rx="15" />
        </clipPath>
        <clipPath id={`${uid}-shaft-clip`}>
          <path d="M29 42h14v42H29z" />
        </clipPath>
      </defs>

      <g transform={tilt}>
        {/* ── The handle ─────────────────────────────────────────────────── */}
        <g>
          <path
            d="M29 42h14v42H29z"
            fill={`url(#${uid}-shaft)`}
            className="stroke-tier-hammer-line"
            strokeWidth="2.4"
            strokeLinejoin="round"
            style={STICKER}
          />
          <g clipPath={`url(#${uid}-shaft-clip)`}>
            {/* The shadow side, inside the silhouette. */}
            <path d="M39 42h4v42h-4z" className="fill-tier-hammer-line" opacity="0.3" />
            {/* Two grain lines, neither straight nor parallel. */}
            <path
              d="M33 44c-1 12 1 20 0 40M36.5 43c1 14-1 22 0 41"
              className="stroke-tier-hammer-line fill-none"
              strokeOpacity="0.3"
              strokeWidth="1"
            />
            {/* And the lit side. */}
            <path d="M30.5 43h2.5v41h-2.5z" className="fill-card" opacity="0.34" />
          </g>
        </g>

        {/* The cut end of the handle: a disc of end grain, not a rounded nub. */}
        <g>
          <ellipse
            cx="36"
            cy="84"
            rx="7"
            ry="4.5"
            fill="currentColor"
            className="stroke-tier-hammer-line"
            strokeWidth="2.2"
            style={STICKER}
          />
          <ellipse cx="36" cy="84" rx="7" ry="4.5" className="fill-card" opacity="0.42" />
          <ellipse
            cx="36"
            cy="84"
            rx="3.4"
            ry="2.1"
            className="stroke-tier-hammer-line fill-none"
            strokeOpacity="0.35"
            strokeWidth="0.9"
          />
        </g>

        {/* ── The head ───────────────────────────────────────────────────── */}
        <g>
          <rect
            x="3"
            y="8"
            width="58"
            height="38"
            rx="15"
            fill={`url(#${uid}-barrel)`}
            className="stroke-tier-hammer-line"
            strokeWidth="2.6"
            strokeLinejoin="round"
            style={STICKER}
          />
          <g clipPath={`url(#${uid}-barrel-clip)`}>
            {/* The terminator along the underside. */}
            <path d="M3 36h58v10H3z" className="fill-tier-hammer-line" opacity="0.26" />
            {/* Grain running the length of the barrel — three uneven arcs. */}
            <path
              d="M8 17c14-3 30-3 48 1M6 25c16 3 32 2 50-2M9 34c14 4 30 3 46-1"
              className="stroke-tier-hammer-line fill-none"
              strokeOpacity="0.26"
              strokeWidth="1.1"
            />
            {/* And the lit band along the top. */}
            <path
              d="M12 11h30a4 4 0 0 1 0 8H12a4 4 0 0 1 0-8z"
              className="fill-card"
              opacity="0.4"
            />
          </g>

          {/* Two steel ferrules. They are also what says the head is fitted
              to the handle rather than carved out of one piece with it. */}
          {[14, 52].map((x) => (
            <g key={x}>
              <rect
                x={x}
                y="8"
                width="6"
                height="38"
                className="fill-silver stroke-tier-hammer-line"
                strokeWidth="1.8"
                clipPath={`url(#${uid}-barrel-clip)`}
              />
              <rect
                x={x + 0.8}
                y="12"
                width="1.8"
                height="28"
                className="fill-card"
                opacity="0.6"
              />
            </g>
          ))}
        </g>

        {/* The striking face: end grain, which is what a mallet is used on
            its ends for. Rings and a pith line, inset so a rim of the barrel
            shows all the way round and it reads as a plane at the end of a
            cylinder rather than a hole in one. */}
        <g>
          <ellipse
            cx="49"
            cy="27"
            rx="9.5"
            ry="14.5"
            fill="currentColor"
            className="stroke-tier-hammer-line"
            strokeWidth="2.4"
            style={STICKER}
          />
          <ellipse cx="49" cy="27" rx="9.5" ry="14.5" className="fill-card" opacity="0.46" />
          <g className="stroke-tier-hammer-line fill-none" strokeOpacity="0.32" strokeWidth="1">
            <ellipse cx="49" cy="27" rx="6.4" ry="10" />
            <ellipse cx="49.5" cy="27" rx="3.4" ry="5.4" />
            <path d="M49.5 22v10" strokeOpacity="0.22" />
          </g>
        </g>
      </g>
    </svg>
  );
}
