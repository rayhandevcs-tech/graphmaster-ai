import { DistributionBar } from "@/components/insight/distribution-bar";
import { TIER_LABELS, TIER_ORDER } from "./tiers";
import type { RewardTier } from "@/types/api";

/**
 * Where a *class's* marks landed, across the four tiers.
 *
 * Deliberately not `TierDistribution`, which is the same four tiers on one
 * student's own dashboard. The difference is the whole reason both exist: that
 * one is a private summary of a person's progress, listed tier by tier with
 * counts; this one is an aggregate over attempts on a screen a teacher may
 * project.
 *
 * **It counts attempts, never students.** A tier is a per-attempt reward, and
 * a distribution presented as a count of people would be a ranking of the
 * class by their weakest work — the humiliation FR-7.6 rules out. The caption
 * beside it and the sentence beneath it both keep "attempts" as the subject,
 * and no student is named anywhere near it.
 *
 * It lives under `components/gamification/` because it paints in the tier
 * tokens, and gold is allowed only here (`tests/design-tokens.test.ts`).
 */
const TIER_FILL: Record<RewardTier, string> = {
  crown: "bg-tier-crown",
  flower: "bg-tier-flower",
  steady: "bg-tier-steady",
  hammer: "bg-tier-hammer",
};

export function ClassTierSpread({ distribution }: { distribution: Record<string, number> }) {
  return (
    <DistributionBar
      label="Reward tiers across marked attempts"
      segments={TIER_ORDER.map((tier) => ({
        key: tier,
        label: TIER_LABELS[tier],
        value: distribution[tier] ?? 0,
        className: TIER_FILL[tier],
      }))}
    />
  );
}
