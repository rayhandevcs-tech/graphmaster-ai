"use client";

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
 * **Deliberately a toy, and that is a requirement rather than a style choice.**
 * FR-7.6 says the lowest tier must never read as humiliating. The reference
 * for this drawing is a cartoon axe, and everything about *how* it is drawn is
 * taken from it — but the object is a fairground mallet, because a blade
 * swinging at a student who scored badly is precisely what the specification
 * rules out. A head with a cutting edge would say something the rest of this
 * screen spends its whole length not saying.
 *
 * **What makes the reference read the way it does**, and what a first attempt
 * at "thick outline, two tones" misses entirely:
 *
 * - **A big pale ellipse on the striking end.** This is most of it. The head
 *   is a cylinder seen from three-quarters on, and that ellipse is its near
 *   face catching the light. Without it the head is a rounded rectangle, and
 *   a rounded rectangle at any outline weight is a sticker of a brick.
 * - **The handle is cut, not tapered.** A second pale ellipse closes its end.
 *   Two ellipses on the same object, at the same angle, are what say *both*
 *   of these things are round.
 * - **One long highlight down the handle's lit side**, running its whole
 *   length rather than sitting in the middle of it.
 * - **The whole tool is tilted.** Square to the page it is a diagram; at an
 *   angle it is a thing someone is holding.
 *
 * Each pale shape is painted twice: once in `currentColor` with the outline,
 * then again in `fill-card` at half strength with no stroke. That is what
 * makes a *tint of the tier's own colour* — a `fill-card` shape on its own
 * would be white where it overhangs the body, and a lighter second token
 * would need a third colour per tier for no gain.
 */
export function TierMallet({ className }: { className?: string }) {
  const tilt = "rotate(-18 36 47)";

  return (
    <svg viewBox="0 0 72 94" className={cn("size-14", className)} aria-hidden>
      <g
        className="stroke-tier-hammer-line"
        strokeWidth="4.5"
        style={STICKER}
        {...LINE}
        transform={tilt}
      >
        {/* Handle first, so the head sits over its top end. Long — half again
            the height of the head — and flat-bottomed: the cut end is closed
            by its own ellipse below, the way a sawn dowel is, rather than
            rounded off into a nub. */}
        <path d="M29 42h14v42H29z" fill="currentColor" />

        {/* The head. Wide, deep, and four times the width of its own handle —
            nothing shaped like this swings at anyone. */}
        <rect x="3" y="8" width="58" height="38" rx="15" fill="currentColor" />

        {/* The near face of the head, and the cut end of the handle. Both are
            filled in the body colour here and tinted in the group below, so
            the outline has something opaque to sit against.
            
            The face is *inset*: a rim of the body colour all the way round it
            is what makes it read as a plane at the end of a cylinder. Sized
            to the end cap exactly, it split the head into a pale half and an
            orange half instead. */}
        <ellipse cx="49" cy="27" rx="9.5" ry="14.5" fill="currentColor" />
        <ellipse cx="36" cy="84" rx="7" ry="4.5" fill="currentColor" />
      </g>

      {/* The lit tones, over the outlined shapes and carrying no outline of
          their own: a stroke around a highlight turns it into a second
          object. */}
      <g className="fill-card" transform={tilt}>
        <ellipse cx="49" cy="27" rx="9.5" ry="14.5" opacity="0.5" />
        <ellipse cx="36" cy="84" rx="7" ry="4.5" opacity="0.5" />
        {/* Along the top of the head, where the light grazes it. */}
        <path d="M13 14h20a4.5 4.5 0 0 1 0 9H13a4.5 4.5 0 0 1 0-9z" opacity="0.4" />
        {/* And the full length of the handle's lit side, not a mark in the
            middle of it. */}
        <path d="M31.5 46h5v36h-5z" opacity="0.42" />
      </g>
    </svg>
  );
}
