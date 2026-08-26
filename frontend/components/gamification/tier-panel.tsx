import { TIER_BANDS, TIER_LABELS, TierMark, tierSurface } from "./tiers";
import { cn } from "@/lib/utils";
import type { FeedbackOut, RewardTier } from "@/types/api";

/**
 * The reward tier, and the honest account of where it came from.
 *
 * The headline and message are the server's — the crown title is gendered
 * there, and the lowest tier's message always opens "Keep Practicing! You Can
 * Improve!", which is a product requirement rather than a template's mood
 * (FR-7.7). Rewriting either here would be the one way to break that.
 *
 * The line about the vocabulary percentage is not a footnote: the tier is
 * driven by that number and *not* by the final score (FR-7.1), and a student
 * who scored 74 overall while sitting in the flower tier deserves to see why
 * rather than assume the page is wrong.
 *
 * Sprint 12 replaces the static mark with the tier animation. It slots in here;
 * everything else on this card is the still version the reduced-motion path
 * needs anyway.
 */
export function TierPanel({
  tier,
  feedback,
  vocabularyPercentage,
  className,
}: {
  tier: RewardTier;
  feedback: FeedbackOut;
  vocabularyPercentage: number;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex h-full flex-col gap-4 rounded-xl border p-6",
        tierSurface(tier),
        className,
      )}
    >
      <div className="flex items-center gap-4">
        <TierMark tier={tier} />
        <div className="flex flex-col gap-0.5">
          <p className="text-xs font-medium tracking-wide uppercase opacity-80">
            {TIER_LABELS[tier]}
          </p>
          <h2 className="text-xl font-semibold tracking-tight text-balance">{feedback.headline}</h2>
        </div>
      </div>

      <p className="text-[0.95rem] leading-relaxed text-pretty">{feedback.message}</p>

      <p className="mt-auto border-t border-current/15 pt-3 text-xs opacity-80">
        Your tier comes from the target vocabulary you used —{" "}
        <span className="font-medium tabular-nums">{vocabularyPercentage.toFixed(0)}%</span> of it —
        not from your final score. {TIER_LABELS[tier]} is {TIER_BANDS[tier]}.
      </p>
    </div>
  );
}
