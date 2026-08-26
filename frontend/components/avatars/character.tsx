import { cn } from "@/lib/utils";

/**
 * The student's character, drawn rather than fetched.
 *
 * `avatars.image_url` is a flat file, and a flat file has one expression. A
 * reward sequence needs the character to react — to cheer, to be knocked
 * dizzy, to set its jaw and get back up — so the client draws it from shapes
 * it can pose (06-frontend-architecture §8.2).
 *
 * Two consequences worth stating:
 *
 * - **Every colour is a token**, so the character themes with the rest of the
 *   product instead of being a fixed-palette image that only works on white.
 * - **It is stylised, not realistic.** A duotone illustration in the product's
 *   own purple has no skin tone to get wrong, which for a platform used by one
 *   cohort of students and then another is the right default rather than a
 *   compromise.
 */

export type Expression = "neutral" | "happy" | "cheer" | "dizzy" | "determined";

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

function lookFor(code: string): { hair: Hair; accessory: Accessory } {
  return LOOKS[code] ?? { hair: code.startsWith("girl") ? "long" : "short", accessory: "none" };
}

export function AvatarCharacter({
  code,
  expression = "neutral",
  className,
  title,
}: {
  /** The avatar's `code` from the catalogue — `girl_scholar`, `boy_default`. */
  code: string;
  expression?: Expression;
  className?: string;
  /** An accessible name. Omit where the character is decoration beside a label. */
  title?: string;
}) {
  const look = lookFor(code);

  return (
    <svg
      viewBox="0 0 96 96"
      className={cn("size-16", className)}
      role={title ? "img" : "presentation"}
      aria-label={title}
      aria-hidden={title ? undefined : true}
    >
      <circle cx="48" cy="48" r="48" className="fill-primary/10" />

      {/* Hair sits behind the face and a little higher, so what shows is a
          band around the crown rather than a shape stuck on top. */}
      {look.hair === "long" ? (
        <>
          <ellipse cx="48" cy="42" rx="26" ry="26" className="fill-primary" />
          <path d="M23 44c-1 14 0 22 4 28l9-3c-3-8-4-16-3-25z" className="fill-primary" />
          <path d="M73 44c1 14 0 22-4 28l-9-3c3-8 4-16 3-25z" className="fill-primary" />
        </>
      ) : (
        <circle cx="48" cy="40" r="24" className="fill-primary" />
      )}

      {/* Shoulders, over the hair so long hair falls behind them. */}
      <path d="M42 56h12v16H42z" className="fill-card" />
      <path d="M14 96C14 79 29 70 48 70s34 9 34 26z" className="fill-primary/85" />

      <circle cx="48" cy="45" r="21" className="fill-card" />

      {/* A side-swept fringe, the one asymmetric thing on the face — without
          it the helmet reads as a hood rather than as hair. */}
      <path
        d="M28 40c2-9 10-15 20-15 7 0 12 3 15 7-7-2-18-1-24 4-4 2-8 3-11 4z"
        className="fill-primary"
      />

      <Face expression={expression} />

      {look.accessory === "glasses" ? (
        <g className="stroke-primary fill-none" strokeWidth="2">
          <circle cx="39.5" cy="45" r="7" />
          <circle cx="56.5" cy="45" r="7" />
          <path d="M46.5 45h3" />
        </g>
      ) : null}

      {look.accessory === "hat" ? (
        <g className="fill-secondary">
          <path d="M29 32c0-11 8-17 19-17s19 6 19 17z" />
          <path d="M26 32h44a3 3 0 0 1 0 6H26a3 3 0 0 1 0-6z" />
          <path d="M67 32h13a4 4 0 0 1 0 6H67z" />
        </g>
      ) : null}
    </svg>
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
