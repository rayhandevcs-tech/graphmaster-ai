"use client";

// `useId` makes the gradient ids SSR-safe, and a hook means this cannot be
// rendered from a Server Component. Every path to it already runs on the
// client; the directive states that rather than leaving it to be discovered
// by whoever first imports the character into a server page.
import { useId } from "react";

import { cn } from "@/lib/utils";

/**
 * The student's character, drawn rather than fetched.
 *
 * `avatars.image_url` is a flat file, and a flat file has one expression. A
 * reward sequence needs the character to react — to cheer, to be knocked
 * dizzy, to set its jaw and get back up — so the client draws it from shapes
 * it can pose (06-frontend-architecture §8.2).
 *
 * Three consequences worth stating:
 *
 * - **Every colour is a token**, so the character themes with the rest of the
 *   product instead of being a fixed-palette image that only works on white.
 *   Volume comes from gradients whose stops are `currentColor` at different
 *   opacities — a lit side and a shadow side of *whatever* the theme's colour
 *   turns out to be, which is why this survives dark mode when a painted
 *   highlight would not.
 * - **It is stylised, not realistic.** A duotone illustration in the product's
 *   own purple has no skin tone to get wrong, which for a platform used by one
 *   cohort of students and then another is the right default rather than a
 *   compromise.
 * - **Two builds, one head.** `bust` is the 96×96 head-and-shoulders every
 *   list uses; `figure` is the full body the celebration stage and the profile
 *   use. The head, hair, face and accessories are drawn once and shared. Two
 *   separate components would drift, which is exactly how six avatar SVGs came
 *   to be referenced by a database that no file ever matched.
 */

export type Expression = "neutral" | "happy" | "cheer" | "dizzy" | "determined";

/**
 * What the arms are doing.
 *
 * The arms are what make a body read as *reacting* rather than standing there,
 * so they are a prop rather than something derived from the expression: the
 * hammer sequence needs a guarded pose while the face is still neutral, which
 * a derivation could not express.
 */
export type Pose = "rest" | "cheer" | "brace" | "guard";

/**
 * Which drawn character belongs to a profile.
 *
 * The fallback is for a profile that predates the avatar catalogue —
 * registration has assigned one since sprint 2 — and picks by gender, which is
 * what the catalogue itself is partitioned by.
 */
export function avatarCodeFor(user: { avatar?: { code: string } | null; gender?: string } | null) {
  if (user?.avatar?.code) return user.avatar.code;
  return user?.gender === "male" ? "boy_default" : "girl_default";
}

type Hair = "short" | "long";
type Accessory = "none" | "glasses" | "hat";

/** How each seeded avatar code is drawn. Unknown codes fall back to the pair
 *  of defaults, so a catalogue row added by a migration still renders. */
const LOOKS: Record<string, { hair: Hair; accessory: Accessory }> = {
  boy_default: { hair: "short", accessory: "none" },
  girl_default: { hair: "long", accessory: "none" },
  boy_scholar: { hair: "short", accessory: "glasses" },
  girl_scholar: { hair: "long", accessory: "glasses" },
  boy_explorer: { hair: "short", accessory: "hat" },
  girl_explorer: { hair: "long", accessory: "hat" },
};

/**
 * The avatar code hiding in a stored `image_url`.
 *
 * `/avatars/girl-scholar.svg` names `girl_scholar`. The file itself has never
 * existed in this repository — which is why the character is drawn rather than
 * served — but the *path* is still the only place a leaderboard entry carries
 * which avatar its student chose, so it is read as an identifier and never
 * fetched.
 */
export function avatarCodeFromUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  const file = url.split("/").pop();
  if (!file) return null;
  const code = file.replace(/\.[a-z0-9]+$/i, "").replace(/-/g, "_");
  return code in LOOKS ? code : null;
}

function lookFor(code: string): { hair: Hair; accessory: Accessory } {
  return LOOKS[code] ?? { hair: code.startsWith("girl") ? "long" : "short", accessory: "none" };
}

export function AvatarCharacter({
  code,
  expression = "neutral",
  variant = "bust",
  pose = "rest",
  className,
  title,
}: {
  /** The avatar's `code` from the catalogue — `girl_scholar`, `boy_default`. */
  code: string;
  expression?: Expression;
  /**
   * `bust` is the default and what every list wants: a full body at 32px is a
   * smudge. `figure` is for the two screens where the character is the
   * subject rather than a row label.
   */
  variant?: "bust" | "figure";
  /** Ignored by `bust`, which has no arms to pose. */
  pose?: Pose;
  className?: string;
  /** An accessible name. Omit where the character is decoration beside a label. */
  title?: string;
}) {
  const look = lookFor(code);
  // Unique per instance: two celebrations on one page sharing a gradient id
  // would both paint with whichever one mounted first.
  const uid = useId().replace(/:/g, "");

  const shared = {
    role: title ? ("img" as const) : ("presentation" as const),
    "aria-label": title,
    "aria-hidden": title ? undefined : true,
  };

  // `text-primary` goes on the SVG root rather than on the inner groups.
  // `currentColor` inside a gradient stop resolves against the element that
  // *declares* the gradient, never the shape that references it — so with the
  // colour set only on a group, the whole body painted in the page's text
  // colour (charcoal on a light theme) while the flat fills beside it were
  // purple.
  if (variant === "figure") {
    return (
      <svg viewBox="0 0 96 140" className={cn("text-primary h-32 w-auto", className)} {...shared}>
        <Shading uid={uid} />

        {/* Drawn before the body so everything stands on it. A separate
            ellipse rather than a CSS drop-shadow: the shadow has to widen on a
            jump and flatten on a landing, which a filter cannot be told to do
            — and `filter: drop-shadow` costs a repaint per frame on a phone. */}
        <ellipse cx="48" cy="133" rx="26" ry="5" className="fill-primary/20" />

        <Legs />
        <Torso uid={uid} />
        <Arms pose={pose} />

        {/* The head sits on the shoulders rather than in a disc: the circle
            behind the bust is a list affordance, and on a full figure it reads
            as a bubble the character is trapped in. */}
        <g transform="translate(0 -6) scale(0.78) translate(13.5 8)">
          <Head look={look} expression={expression} uid={uid} />
        </g>
      </svg>
    );
  }

  return (
    <svg viewBox="0 0 96 96" className={cn("text-primary size-16", className)} {...shared}>
      <Shading uid={uid} />
      <circle cx="48" cy="48" r="48" className="fill-primary/10" />

      {/* Shoulders, over the hair so long hair falls behind them. */}
      <path d="M42 56h12v16H42z" className="fill-card" />
      <path d="M14 96C14 79 29 70 48 70s34 9 34 26z" fill={`url(#${uid}-torso)`} />

      <Head look={look} expression={expression} uid={uid} />
    </svg>
  );
}

/**
 * The gradients every part shades with.
 *
 * Both stops are `currentColor`, so a gradient is a *shape* of light rather
 * than a pair of colours — which is what lets one definition work on a purple
 * character in light mode and the same character in dark mode. Declared once
 * per instance and referenced by id.
 */
function Shading({ uid }: { uid: string }) {
  return (
    <defs>
      <linearGradient id={`${uid}-torso`} x1="0" y1="0" x2="1" y2="0.6">
        <stop offset="0" stopColor="currentColor" stopOpacity="0.95" />
        <stop offset="1" stopColor="currentColor" stopOpacity="0.6" />
      </linearGradient>
      <linearGradient id={`${uid}-hair`} x1="0.15" y1="0" x2="0.9" y2="1">
        <stop offset="0" stopColor="currentColor" stopOpacity="1" />
        <stop offset="1" stopColor="currentColor" stopOpacity="0.72" />
      </linearGradient>
      {/* The face is the light plane, so its gradient runs the other way: the
          cheek away from the light picks up a wash of the hair colour. */}
      <linearGradient id={`${uid}-face`} x1="0.1" y1="0" x2="1" y2="1">
        <stop offset="0.55" stopColor="currentColor" stopOpacity="0" />
        <stop offset="1" stopColor="currentColor" stopOpacity="0.16" />
      </linearGradient>
    </defs>
  );
}

/** Head, hair, face and accessory, in the 96×96 frame both builds share. */
function Head({
  look,
  expression,
  uid,
}: {
  look: { hair: Hair; accessory: Accessory };
  expression: Expression;
  uid: string;
}) {
  return (
    <g>
      {/* Hair sits behind the face and a little higher, so what shows is a
          band around the crown rather than a shape stuck on top. */}
      {look.hair === "long" ? (
        <>
          <ellipse cx="48" cy="42" rx="26" ry="26" fill={`url(#${uid}-hair)`} />
          <path d="M23 44c-1 14 0 22 4 28l9-3c-3-8-4-16-3-25z" fill={`url(#${uid}-hair)`} />
          <path d="M73 44c1 14 0 22-4 28l-9-3c3-8 4-16 3-25z" fill={`url(#${uid}-hair)`} />
        </>
      ) : (
        <circle cx="48" cy="40" r="24" fill={`url(#${uid}-hair)`} />
      )}

      <circle cx="48" cy="45" r="21" className="fill-card" />
      {/* The shaded cheek, laid over the face and under everything on it. */}
      <circle cx="48" cy="45" r="21" fill={`url(#${uid}-face)`} />

      {/* A side-swept fringe, the one asymmetric thing on the face — without
          it the helmet reads as a hood rather than as hair. */}
      <path
        d="M28 40c2-9 10-15 20-15 7 0 12 3 15 7-7-2-18-1-24 4-4 2-8 3-11 4z"
        className="fill-primary"
      />
      {/* One highlight along the lit edge of the hair. A single stroke is the
          difference between hair and a helmet; two start to look like a wig. */}
      <path
        d="M31 33c3-6 9-10 16-11"
        className="stroke-card fill-none opacity-45"
        strokeWidth="3"
        strokeLinecap="round"
      />

      <Face expression={expression} />

      {look.accessory === "glasses" ? (
        <g className="stroke-primary fill-none" strokeWidth="2">
          <circle cx="39.5" cy="45" r="7" />
          <circle cx="56.5" cy="45" r="7" />
          <path d="M46.5 45h3" />
        </g>
      ) : null}

      {/* Flat fills plus a highlight rather than the shared gradient: the
          gradients resolve `currentColor` at the SVG root, which is primary,
          so a hat drawn with one would come out purple beside its own
          secondary brim. */}
      {look.accessory === "hat" ? (
        <g className="fill-secondary">
          <path d="M29 32c0-11 8-17 19-17s19 6 19 17z" />
          <path d="M48 15c-10 0-19 6-19 17h9c0-9 4-15 10-17z" className="fill-card opacity-25" />
          <path d="M26 32h44a3 3 0 0 1 0 6H26a3 3 0 0 1 0-6z" />
          <path d="M67 32h13a4 4 0 0 1 0 6H67z" />
        </g>
      ) : null}
    </g>
  );
}

/** Torso and neck. Shaded down the side away from the light. */
function Torso({ uid }: { uid: string }) {
  return (
    <g>
      <path d="M43 44h10v12H43z" className="fill-card" />
      {/* A rounded trapezoid rather than a rectangle: shoulders wider than the
          waist is most of what makes a body read as a body at this size. */}
      <path
        d="M48 50c11 0 20 6 21 15l3 30a6 6 0 0 1-6 7H30a6 6 0 0 1-6-7l3-30c1-9 10-15 21-15z"
        fill={`url(#${uid}-torso)`}
      />
      {/* The collar, which stops the head reading as balanced on a bag. */}
      <path
        d="M39 52c3 4 5 6 9 6s6-2 9-6"
        className="stroke-card fill-none opacity-70"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
    </g>
  );
}

/** Legs, slightly apart. A stance, not a pedestal. */
function Legs() {
  return (
    <g className="fill-primary/70">
      <path d="M38 96h8l-1 32a4 4 0 0 1-8 0z" />
      <path d="M50 96h8l1 32a4 4 0 0 1-8 0z" />
      <rect x="33" y="126" width="14" height="7" rx="3.5" className="fill-primary" />
      <rect x="49" y="126" width="14" height="7" rx="3.5" className="fill-primary" />
    </g>
  );
}

/**
 * The arms, by pose.
 *
 * Each pose is a whole pair rather than a mirrored single arm: `guard` is
 * deliberately asymmetric — one arm over the head and one still down — which
 * is what makes the hammer beat read as flinching rather than surrendering.
 */
function Arms({ pose }: { pose: Pose }) {
  const arm = "stroke-primary fill-none";
  const props = { strokeWidth: 9, strokeLinecap: "round" as const, className: arm };

  if (pose === "cheer") {
    return (
      <g {...props}>
        <path d="M28 68 18 46" />
        <path d="M68 68 78 46" />
      </g>
    );
  }

  if (pose === "brace") {
    return (
      <g {...props}>
        <path d="M28 68 18 82l12 6" />
        <path d="M68 68 78 82l-12 6" />
      </g>
    );
  }

  if (pose === "guard") {
    return (
      <g {...props}>
        <path d="M28 68 22 50l20-6" />
        <path d="M68 68 74 88" />
      </g>
    );
  }

  return (
    <g {...props}>
      <path d="M28 68 22 92" />
      <path d="M68 68 74 92" />
    </g>
  );
}

/**
 * Eyes and mouth.
 *
 * Each expression is a whole face rather than a set of overrides, because the
 * combinations that matter are few and a face assembled from independent parts
 * produces the ones that do not — dizzy eyes over a smile, which reads as
 * something other than comic.
 */
function Face({ expression }: { expression: Expression }) {
  const eye = "fill-primary";
  const line = "stroke-primary fill-none";

  if (expression === "cheer") {
    return (
      <g>
        <path
          d="M34 45c2-4 8-4 10 0M52 45c2-4 8-4 10 0"
          className={line}
          strokeWidth="2.5"
          strokeLinecap="round"
        />
        <path d="M40 53c3 6 13 6 16 0z" className={eye} />
      </g>
    );
  }

  if (expression === "dizzy") {
    return (
      <g className={line} strokeWidth="2.5" strokeLinecap="round">
        <path d="M36 42l6 6M42 42l-6 6M54 42l6 6M60 42l-6 6" />
        <path d="M41 56c2-2 4 2 6 0s4 2 6 0" strokeWidth="2" />
      </g>
    );
  }

  if (expression === "determined") {
    return (
      <g>
        {/* Brows lowered a little, not angled into a scowl: this is resolve
            after a knock, and an angry face would be the platform telling a
            student off. */}
        <g className={line} strokeWidth="2.5" strokeLinecap="round">
          <path d="M35 39h7M61 39h-7" />
        </g>
        <circle cx="40" cy="45" r="2.6" className={eye} />
        <circle cx="56" cy="45" r="2.6" className={eye} />
        {/* Set, not smiling: a grin here would read as enjoying the knock. */}
        <path d="M42 55h11" className={line} strokeWidth="2.5" strokeLinecap="round" />
      </g>
    );
  }

  const smile = expression === "happy" ? "M40 53c3 5 13 5 16 0" : "M41 55h14";

  return (
    <g>
      <circle cx="40" cy="45" r="2.8" className={eye} />
      <circle cx="56" cy="45" r="2.8" className={eye} />
      <path d={smile} className={line} strokeWidth="2.5" strokeLinecap="round" />
    </g>
  );
}
