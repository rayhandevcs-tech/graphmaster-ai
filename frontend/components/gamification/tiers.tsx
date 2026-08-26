import { Crown, Flower, Hammer, TrendingUp } from "lucide-react";

import { cn } from "@/lib/utils";
import type { RewardTier } from "@/types/api";

/**
 * The four reward tiers, as the interface presents them.
 *
 * This module is one of the few allowed to use gold — the crown is the only
 * place it appears, which is what makes it feel earned rather than decorative
 * (06-frontend-architecture §4, enforced by `tests/design-tokens.test.ts`).
 *
 * Two product rules are encoded here rather than left to whoever renders a
 * tier next:
 *
 * - **The tier comes from the vocabulary percentage, not the final score**
 *   (FR-7.1). Callers pass that number, and the panel says so on screen.
 * - **The lowest tier is never humiliating** (FR-7.7). It is labelled
 *   "Practice tier", not "Hammer"; the wording a student reads is the server's
 *   feedback, which always opens "Keep Practicing! You Can Improve!".
 */

export const TIER_ORDER: readonly RewardTier[] = ["crown", "flower", "steady", "hammer"];

/** Neutral names. The celebratory title is the server's `feedback.headline`. */
export const TIER_LABELS: Record<RewardTier, string> = {
  crown: "Crown tier",
  flower: "Flower tier",
  steady: "Steady tier",
  hammer: "Practice tier",
};

export const TIER_ICONS = {
  crown: Crown,
  flower: Flower,
  steady: TrendingUp,
  hammer: Hammer,
} as const;

/** The vocabulary percentage each tier starts at, for the "how it is decided" note. */
export const TIER_BANDS: Record<RewardTier, string> = {
  crown: "90% and above",
  flower: "60–89%",
  steady: "50–59%",
  hammer: "below 50%",
};

const TIER_SURFACES: Record<RewardTier, string> = {
  crown: "bg-tier-crown/15 text-tier-crown-foreground border-tier-crown/40",
  flower: "bg-tier-flower/15 border-tier-flower/40",
  steady: "bg-tier-steady/15 border-tier-steady/40",
  hammer: "bg-tier-hammer/15 border-tier-hammer/40",
};

const TIER_MARKS: Record<RewardTier, string> = {
  crown: "bg-tier-crown text-tier-crown-foreground",
  flower: "bg-tier-flower text-tier-flower-foreground",
  steady: "bg-tier-steady text-tier-steady-foreground",
  hammer: "bg-tier-hammer text-tier-hammer-foreground",
};

export function tierSurface(tier: RewardTier): string {
  return TIER_SURFACES[tier];
}

/**
 * The tier's icon on its colour.
 *
 * Always rendered beside the tier's label, never as a bare swatch: a
 * colour-blind student has to be able to read which tier this is (NFR-4.6).
 */
export function TierMark({
  tier,
  className,
  iconClassName,
}: {
  tier: RewardTier;
  className?: string;
  iconClassName?: string;
}) {
  const Icon = TIER_ICONS[tier];
  return (
    <span
      className={cn(
        "flex items-center justify-center rounded-full",
        TIER_MARKS[tier],
        className ?? "size-12",
      )}
    >
      <Icon className={cn(iconClassName ?? "size-6")} aria-hidden />
    </span>
  );
}
