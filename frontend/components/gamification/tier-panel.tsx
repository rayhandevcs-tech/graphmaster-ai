import { TIER_BANDS, TIER_LABELS, tierSurface } from "./tiers";
import { TierCelebration } from "./tier-celebration";
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
 * The celebration above animates; **the message below does not wait for it**.
 * It is rendered from the first frame, so a student whose tab is throttled,
 * who navigates away mid-sequence, or who is using a screen reader has been
 * told the same thing as everyone else. The sequence reveals the title card;
 * it never gates the words.
 *
 * The line about the vocabulary percentage is not a footnote: the tier is
 * driven by that number and *not* by the final score (FR-7.1), and a student
 * who scored 74 overall while sitting in the flower tier deserves to see why
 * rather than assume the page is wrong.
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
        "flex h-full flex-col gap-4 rounded-xl border p-6 text-center",
        tierSurface(tier),
        className,
      )}
    >
      <p className="text-xs font-medium tracking-wide uppercase opacity-80">{TIER_LABELS[tier]}</p>

      <TierCelebration tier={tier} headline={feedback.headline} />

      <p className="text-[0.95rem] leading-relaxed text-pretty">{feedback.message}</p>

      <p className="mt-auto border-t border-current/15 pt-3 text-left text-xs opacity-80">
        Your tier comes from the target vocabulary you used —{" "}
        <span className="font-medium tabular-nums">{vocabularyPercentage.toFixed(0)}%</span> of it —
        not from your final score. {TIER_LABELS[tier]} is {TIER_BANDS[tier]}.
      </p>
    </div>
  );
}
