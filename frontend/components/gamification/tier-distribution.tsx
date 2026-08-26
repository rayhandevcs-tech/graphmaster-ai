import { DistributionBar } from "@/components/insight/distribution-bar";
import { TIER_LABELS, TIER_ORDER } from "./tiers";
import type { RewardTier } from "@/types/api";

/**
 * Where a period's marks landed, across the four tiers.
 *
 * This lives under `components/gamification/` because it is the one place on a
 * teacher's screen that paints in the tier colours, and gold is allowed only
 * here (`tests/design-tokens.test.ts`).
 *
 * **It counts attempts, never students.** A tier is a per-attempt reward, and
 * a distribution presented as a count of *people* would be a ranking of the
 * class by their weakest work — the humiliation FR-7.6 rules out. The caption
 * beside it and the sentence beneath it both keep "attempts" as the subject.
 */
const TIER_FILL: Record<RewardTier, string> = {
  crown: "bg-tier-crown",
  flower: "bg-tier-flower",
  steady: "bg-tier-steady",
  hammer: "bg-tier-hammer",
};

export function TierDistribution({ distribution }: { distribution: Record<string, number> }) {
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
