import { TIER_LABELS, TIER_ORDER, TierMark } from "./tiers";
import { cn } from "@/lib/utils";
import type { RewardTier } from "@/types/api";

/**
 * How this student's own results are spread across the four tiers.
 *
 * **Private to the student it belongs to.** FR-7.6 keeps a hammer count off
 * every shared surface — a leaderboard, a class list — because a tally of
 * someone's lowest results published beside their name is the humiliation the
 * requirement exists to prevent. On their own dashboard it is the opposite: it
 * is the shape of their progress, and the practice tier is where most students
 * start.
 *
 * The bar is never the only signal. Each tier is listed with its icon and its
 * name, so the segmentation is a summary of the list rather than the only
 * place the information exists (NFR-4.6).
 */
const TIER_FILLS: Record<RewardTier, string> = {
  crown: "bg-tier-crown",
  flower: "bg-tier-flower",
  steady: "bg-tier-steady",
  hammer: "bg-tier-hammer",
};

export function TierDistribution({
  distribution,
  className,
}: {
  distribution: Record<string, number>;
  className?: string;
}) {
  const counts = TIER_ORDER.map((tier) => ({ tier, count: distribution[tier] ?? 0 }));
  const total = counts.reduce((sum, row) => sum + row.count, 0);

  if (total === 0) {
    return (
      <p className={cn("text-muted-foreground text-sm", className)}>
        Your first marked description will appear here.
      </p>
    );
  }

  return (
    <div className={cn("flex flex-col gap-4", className)}>
      <div className="bg-muted flex h-2.5 w-full overflow-hidden rounded-full" aria-hidden>
        {counts
          .filter((row) => row.count > 0)
          .map((row) => (
            <span
              key={row.tier}
              className={TIER_FILLS[row.tier]}
              style={{ width: `${(row.count / total) * 100}%` }}
            />
          ))}
      </div>

      <ul className="flex flex-col gap-2">
        {counts.map((row) => (
          <li key={row.tier} className="flex items-center gap-3 text-sm">
            <TierMark tier={row.tier} className="size-7" iconClassName="size-3.5" />
            <span className="flex-1">{TIER_LABELS[row.tier]}</span>
            <span className="text-muted-foreground tabular-nums">
              {row.count}
              <span className="sr-only">{row.count === 1 ? " description" : " descriptions"}</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
