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
 * reward sequence needs the character to react — to be startled, to cheer, to
 * be knocked over and get back up — so the client draws it from shapes it can
 * pose (06-frontend-architecture §8.2).
 *
 * **What changed, and why the first version was wrong.** It was a duotone
 * silhouette: face, hair, shirt and shoes were all `--primary` at different
 * opacities. That themed beautifully and read as a pictogram — a shape where a
 * character should be. Three things fix that, in descending order of effect:
 *
 * 1. **Eyes with a white, an iris and a catchlight.** This is most of it. A
 *    filled dot has no gaze; a sclera with a dark iris and one off-centre
 *    highlight is the difference between a diagram of a face and something
 *    that appears to be looking at you. Every expression here is built around
 *    the eyes for that reason, and the mouth follows them.
 * 2. **Separate colour zones.** Skin, hair, shirt, trousers and shoes are five
 *    different tokens, so the figure has parts. Volume comes from each zone
 *    carrying its own shade, painted as a real shape on the side away from the
 *    light, rather than from a translucent overlay — see the note beside
 *    `--skin-light-shade` in `globals.css`.
 * 3. **Cartoon proportions.** The head is roughly two-fifths of the height.
 *    Realistic proportions at 96px produce a small head and no face, which is
 *    the one thing this illustration exists to show.
 *
 * **Six characters that look like six people.** Skin tone and hair colour vary
 * across the catalogue rather than the accessory alone — `boy_default` and
 * `boy_scholar` previously differed only by a pair of glasses. The tones are
 * illustration tones, not anyone's complexion, and a student picks their
 * character, so a tone is chosen rather than assigned.
 *
 * **Two builds, one head.** `bust` is the head-and-shoulders every list uses;
 * `figure` is the full body the celebration, the dashboard and the profile
 * use. Both draw `Head` in the same coordinate frame — the face centres on
 * (50, 46) in either — so there is no transform to keep in sync and the
 * features cannot drift between the two.
 */

export type Expression =
  | "neutral"
  | "happy"
  | "cheer"
  /** Eyes wide, brows up, mouth open. The beat a crown lands, and nothing else. */
  | "surprised"
  | "dizzy"
  | "determined";

/**
 * What the arms are doing.
 *
 * The arms are what make a body read as *reacting* rather than standing there,
 * so they are a prop rather than something derived from the expression: the
 * hammer sequence needs a guarded pose while the face is still neutral, which
 * a derivation could not express.
 */
export type Pose = "rest" | "cheer" | "brace" | "guard" | "sprawl";

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

type HairStyle = "short" | "long";
type HairColour = "dark" | "brown" | "warm";
type Tone = "light" | "mid" | "deep";
type Accessory = "none" | "glasses" | "hat";
type Look = { hair: HairStyle; colour: HairColour; tone: Tone; accessory: Accessory };

/**
 * How each seeded avatar code is drawn.
 *
 * Unknown codes fall back to one of the defaults, so a catalogue row added by
 * a later migration still renders rather than throwing.
 */
const LOOKS: Record<string, Look> = {
  boy_default: { hair: "short", colour: "brown", tone: "light", accessory: "none" },
  girl_default: { hair: "long", colour: "dark", tone: "light", accessory: "none" },
  boy_scholar: { hair: "short", colour: "dark", tone: "mid", accessory: "glasses" },
  girl_scholar: { hair: "long", colour: "warm", tone: "mid", accessory: "glasses" },
  boy_explorer: { hair: "short", colour: "dark", tone: "deep", accessory: "hat" },
  girl_explorer: { hair: "long", colour: "brown", tone: "deep", accessory: "hat" },
};

/**
 * Tailwind scans source text for complete class names, so these are written
 * out rather than composed as `fill-skin-${tone}` — which produces a correct
 * string at runtime and no matching rule in the stylesheet.
 */
const SKIN: Record<Tone, { base: string; shade: string }> = {
  light: { base: "fill-skin-light", shade: "fill-skin-light-shade" },
  mid: { base: "fill-skin-mid", shade: "fill-skin-mid-shade" },
  deep: { base: "fill-skin-deep", shade: "fill-skin-deep-shade" },
};

const HAIR: Record<HairColour, { fill: string; stroke: string }> = {
  dark: { fill: "fill-hair-dark", stroke: "stroke-hair-dark" },
  brown: { fill: "fill-hair-brown", stroke: "stroke-hair-brown" },
  warm: { fill: "fill-hair-warm", stroke: "stroke-hair-warm" },
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

function lookFor(code: string): Look {
  const fallback = code.startsWith("girl") ? LOOKS.girl_default : LOOKS.boy_default;
  return LOOKS[code] ?? (fallback as Look);
}

export function AvatarCharacter({
  code,
  expression = "neutral",
  variant = "bust",
  pose = "rest",
  groundShadow = true,
  className,
  title,
}: {
  /** The avatar's `code` from the catalogue — `girl_scholar`, `boy_default`. */
  code: string;
  expression?: Expression;
  /**
   * `bust` is the default and what every list wants: a full body at 32px is a
   * smudge. `figure` is for the screens where the character is the subject
   * rather than a row label.
   */
  variant?: "bust" | "figure";
  /** Ignored by `bust`, which has no arms to pose. */
  pose?: Pose;
  /**
   * `figure` only. The celebration stage draws its own shadow as a *sibling*
   * of the figure, so that it can spread on an impact while the body squashes;
   * a shadow inside this SVG would inherit those transforms and travel with
   * the body, which is the one thing a shadow must not do. That stage turns
   * this off. Everywhere else the figure would otherwise float.
   */
  groundShadow?: boolean;
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
  // colour set only on a group, the shirt painted in the page's text colour
  // (charcoal on a light theme) while the flat fills beside it were purple.
  if (variant === "figure") {
    return (
      <svg viewBox="0 0 100 160" className={cn("text-primary h-32 w-auto", className)} {...shared}>
        <Shading uid={uid} />

        {groundShadow ? (
          <ellipse cx="50" cy="153" rx="30" ry="5" className="fill-primary/20" />
        ) : null}

        <Legs />
        <Torso uid={uid} look={look} />
        <Arms pose={pose} look={look} />
        <Head look={look} expression={expression} />
      </svg>
    );
  }

  return (
    <svg viewBox="0 0 100 100" className={cn("text-primary size-16", className)} {...shared}>
      <Shading uid={uid} />
      <circle cx="50" cy="50" r="50" className="fill-primary/10" />

      {/* Neck first, then shoulders over it, then the head over both. */}
      <rect x="43" y="60" width="14" height="18" rx="6" className={SKIN[look.tone].base} />
      <path d="M8 100c0-16 19-26 42-26s42 10 42 26z" fill={`url(#${uid}-shirt)`} />

      <Head look={look} expression={expression} />
    </svg>
  );
}

/**
 * The one gradient left.
 *
 * Everything else is now a flat token with its shade drawn as a real shape.
 * The shirt keeps a gradient because it is the largest unbroken area on the
 * figure and the only one where a hand-drawn shade would read as a stripe.
 * Both stops are `currentColor`, so it is a *shape of light* rather than a
 * pair of colours — which is what lets one definition work in both themes.
 */
function Shading({ uid }: { uid: string }) {
  return (
    <defs>
      <linearGradient id={`${uid}-shirt`} x1="0" y1="0" x2="1" y2="0.6">
        <stop offset="0" stopColor="currentColor" stopOpacity="1" />
        <stop offset="1" stopColor="currentColor" stopOpacity="0.68" />
      </linearGradient>
    </defs>
  );
}

/**
 * Head, hair, face and accessory.
 *
 * Drawn in the frame both builds share: the face centres on (50, 46) whether
 * this is a 100×100 bust or the top of a 100×160 figure.
 */
function Head({ look, expression }: { look: Look; expression: Expression }) {
  const skin = SKIN[look.tone];
  const hair = HAIR[look.colour];

  return (
    <g>
      {/* The hair mass sits behind the face and a little higher, so what shows
          is a hairline around the crown rather than a cap stuck on top. Long
          hair adds two falls either side, drawn from the same mass. */}
      {look.hair === "long" ? (
        <>
          <ellipse cx="50" cy="42" rx="31" ry="32" className={hair.fill} />
          <path d="M19 46c-2 16 0 26 4 34l11-4c-4-9-5-19-4-29z" className={hair.fill} />
          <path d="M81 46c2 16 0 26-4 34l-11-4c4-9 5-19 4-29z" className={hair.fill} />
        </>
      ) : (
        <ellipse cx="50" cy="40" rx="29" ry="30" className={hair.fill} />
      )}

      {/* Ears, before the face so the face edge trims them into half-discs. */}
      <ellipse cx="25" cy="49" rx="4.5" ry="6" className={skin.base} />
      <ellipse cx="75" cy="49" rx="4.5" ry="6" className={skin.base} />

      <ellipse cx="50" cy="46" rx="25" ry="25.5" className={skin.base} />
      {/* The shadow side: a crescent between the face's outer edge and an
          inner ellipse. A real shape rather than a translucent wash, so it
          stays a complexion in both themes. */}
      <path
        d="M50 20.5a25 25.5 0 0 1 0 51 17 25.5 0 0 0 0-51z"
        className={skin.shade}
        opacity="0.85"
      />

      {/* A side-swept fringe over the forehead — the one asymmetric thing on
          the face. Without it the hair mass reads as a hood. */}
      <path
        d="M25 42c1-15 12-25 25-25 9 0 16 4 20 10-9-4-23-3-31 4-6 4-11 7-14 11z"
        className={hair.fill}
      />
      {/* One highlight along the lit edge. A single stroke is the difference
          between hair and a helmet; two start to look like a wig. */}
      <path
        d="M30 33c4-7 11-11 19-12"
        className={cn(hair.stroke, "fill-none opacity-30")}
        strokeWidth="3.5"
        strokeLinecap="round"
      />

      <Face expression={expression} look={look} />

      {look.accessory === "glasses" ? (
        <g className="stroke-character-eye fill-none opacity-80" strokeWidth="2.2">
          <circle cx="41" cy="46" r="10" />
          <circle cx="59" cy="46" r="10" />
          <path d="M51 46h-2" />
          <path d="M31 44l-6-2M69 44l6-2" strokeLinecap="round" />
        </g>
      ) : null}

      {/* Flat fills plus a highlight rather than the shirt gradient: that
          gradient resolves `currentColor` at the SVG root, which is primary,
          so a hat drawn with it would come out purple beside its own
          secondary brim. */}
      {look.accessory === "hat" ? (
        <g className="fill-secondary">
          <path d="M28 25c0-14 10-23 22-23s22 9 22 23z" />
          <path d="M50 2c-12 0-22 9-22 23h10c0-12 5-20 12-23z" className="fill-card opacity-25" />
          <path d="M21 25h58a4 4 0 0 1 0 8H21a4 4 0 0 1 0-8z" />
          <path d="M79 25h9a4 4 0 0 1 0 8h-9z" className="fill-card opacity-20" />
        </g>
      ) : null}
    </g>
  );
}

/** Neck, shoulders and shirt. */
function Torso({ uid, look }: { uid: string; look: Look }) {
  const skin = SKIN[look.tone];

  return (
    <g>
      <rect x="43" y="62" width="14" height="18" rx="6" className={skin.base} />
      {/* Under the chin. Without it the head reads as balanced on a post. */}
      <path d="M39 66c4 5 7 7 11 7s7-2 11-7v6H39z" className={skin.shade} opacity="0.7" />

      {/* A rounded trapezoid: shoulders wider than the waist is most of what
          makes a body read as a body at this size. */}
      <path
        d="M50 76c12 0 21 7 22 16l2 26a6 6 0 0 1-6 7H32a6 6 0 0 1-6-7l2-26c1-9 10-16 22-16z"
        fill={`url(#${uid}-shirt)`}
      />
      <path
        d="M41 78c3 5 6 7 9 7s6-2 9-7"
        className="stroke-card fill-none opacity-60"
        strokeWidth="3"
        strokeLinecap="round"
      />
    </g>
  );
}

/** Trousers and shoes. A stance, not a pedestal. */
function Legs() {
  return (
    <g>
      <g className="fill-character-pants">
        <path d="M38 118h10v27a5 5 0 0 1-10 0z" />
        <path d="M52 118h10v27a5 5 0 0 1-10 0z" />
      </g>
      <g className="fill-character-shoe">
        <rect x="32" y="141" width="17" height="9" rx="4.5" />
        <rect x="51" y="141" width="17" height="9" rx="4.5" />
      </g>
    </g>
  );
}

/**
 * The arms, by pose.
 *
 * Each pose is a whole pair rather than a mirrored single arm: `guard` is
 * deliberately asymmetric — one arm over the head and one still down — which
 * is what makes the hammer beat read as flinching rather than surrendering.
 *
 * The sleeve is a stroke and the hand a disc in skin at its end, so an arm
 * terminates in something rather than tapering into nothing.
 */
function Arms({ pose, look }: { pose: Pose; look: Look }) {
  const POSES: Record<Pose, { arms: string[]; hands: [number, number][] }> = {
    rest: {
      arms: ["M29 86 26 116", "M71 86 74 116"],
      hands: [
        [25, 119],
        [75, 119],
      ],
    },
    cheer: {
      arms: ["M29 86 14 62", "M71 86 86 62"],
      hands: [
        [12, 58],
        [88, 58],
      ],
    },
    brace: {
      arms: ["M29 86 16 102 28 110", "M71 86 84 102 72 110"],
      hands: [
        [30, 112],
        [70, 112],
      ],
    },
    guard: {
      // Up the *side* of the head, not across it. Routed over the face, the
      // sleeve lay across one eye and the whole pose read as the character
      // covering their own eyes rather than shielding against something.
      arms: ["M29 86 12 58 20 30", "M71 86 76 114"],
      hands: [
        [19, 23],
        [77, 117],
      ],
    },
    sprawl: {
      arms: ["M29 86 8 94", "M71 86 92 94"],
      hands: [
        [6, 95],
        [94, 95],
      ],
    },
  };

  const { arms, hands } = POSES[pose];

  return (
    <g>
      <g
        className="stroke-primary fill-none"
        strokeWidth="12.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        {arms.map((d) => (
          <path key={d} d={d} />
        ))}
      </g>
      {hands.map(([cx, cy]) => (
        <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r="7.5" className={SKIN[look.tone].base} />
      ))}
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
 *
 * The brows are drawn in the hair colour and the blush sits under everything,
 * so a face keeps its structure at 32px where only the darkest shapes survive.
 */
function Face({ expression, look }: { expression: Expression; look: Look }) {
  const hair = HAIR[look.colour];
  const brow = cn(hair.stroke, "fill-none");
  const line = "stroke-character-eye fill-none";

  const blush = (
    <g className="fill-character-blush" opacity="0.3">
      <ellipse cx="30" cy="57" rx="6.5" ry="3.6" />
      <ellipse cx="70" cy="57" rx="6.5" ry="3.6" />
    </g>
  );

  if (expression === "cheer") {
    return (
      <g>
        {blush}
        {/* Arched shut — the smile that reaches the eyes. */}
        <g className={line} strokeWidth="3" strokeLinecap="round">
          <path d="M32 48c3-8 13-8 16 0M56 48c3-8 13-8 16 0" />
        </g>
        <g className={brow} strokeWidth="3" strokeLinecap="round">
          <path d="M32 31c4-4 10-4 13-1M68 31c-4-4-10-4-13-1" />
        </g>
        {/* An open mouth with a tongue. A closed curve here reads as polite,
            and this beat is not polite. */}
        <path d="M39 55h22c0 8-5 12-11 12s-11-4-11-12z" className="fill-character-eye" />
        <path d="M45 63c0-2 2-3 5-3s5 1 5 3-2 4-5 4-5-2-5-4z" className="fill-character-blush" />
      </g>
    );
  }

  if (expression === "dizzy") {
    return (
      <g>
        {blush}
        <g className={line} strokeWidth="3" strokeLinecap="round">
          <path d="M34 40l12 12M46 40l-12 12M54 40l12 12M66 40l-12 12" />
        </g>
        <g className={brow} strokeWidth="3" strokeLinecap="round">
          <path d="M31 30c4-2 10-2 13 0M69 30c-4-2-10-2-13 0" />
        </g>
        <path
          d="M42 58c2-2 3 2 5 0s3 2 5 0 3 2 5 0"
          className={line}
          strokeWidth="2.6"
          strokeLinecap="round"
        />
      </g>
    );
  }

  const brows =
    expression === "surprised" ? (
      // Lifted clear of the hairline. Raised brows are half of surprise; wide
      // eyes on their own read as a stare.
      <g className={brow} strokeWidth="3" strokeLinecap="round">
        <path d="M30 26c4-4 11-4 14 0M70 26c-4-4-11-4-14 0" />
      </g>
    ) : expression === "determined" ? (
      // Lowered a little, not angled into a scowl: this is resolve after a
      // knock, and an angry face would be the platform telling a student off.
      <g className={brow} strokeWidth="3.4" strokeLinecap="round">
        <path d="M30 33c5-3 10-3 14 1M70 33c-5-3-10-3-14 1" />
      </g>
    ) : (
      <g className={brow} strokeWidth="3" strokeLinecap="round">
        <path d="M31 32c4-3 10-3 13 0M69 32c-4-3-10-3-13 0" />
      </g>
    );

  // Big. The reference this was redrawn against carries almost all of its
  // character in the eyes, and a 6px sclera on a 25px face is a diagram's
  // eye — correct, unmemorable, and invisible at the size a list renders it.
  // Everything else on this face is deliberately plain so these can carry it.
  const wide = expression === "surprised";
  const scleraRx = wide ? 9 : 7.6;
  const scleraRy = wide ? 10.5 : 8.4;
  const irisR = wide ? 3.6 : 4.4;

  const mouth =
    expression === "surprised" ? (
      <ellipse cx="50" cy="59" rx="4.5" ry="5.5" className="fill-character-eye" />
    ) : expression === "determined" ? (
      <path d="M43 59h14" className={line} strokeWidth="3" strokeLinecap="round" />
    ) : expression === "happy" ? (
      <path d="M41 56c3 6 15 6 18 0" className={line} strokeWidth="3" strokeLinecap="round" />
    ) : (
      <path d="M44 58h12" className={line} strokeWidth="3" strokeLinecap="round" />
    );

  return (
    <g>
      {blush}
      {brows}
      {/* The white, the iris and one catchlight. The catchlight is up and to
          the left on both eyes — a highlight centred in each pupil reads as
          two lamps rather than one room. */}
      {[41, 59].map((cx) => (
        <g key={cx}>
          <ellipse cx={cx} cy="46" rx={scleraRx} ry={scleraRy} className="fill-character-sclera" />
          <circle cx={cx + 0.6} cy="47.4" r={irisR} className="fill-character-eye" />
          <circle cx={cx - 1.9} cy="43.6" r="1.9" className="fill-character-sclera" />
        </g>
      ))}
      {mouth}
    </g>
  );
}
