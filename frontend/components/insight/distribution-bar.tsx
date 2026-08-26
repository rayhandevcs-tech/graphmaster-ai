import { cn } from "@/lib/utils";

export interface DistributionSegment {
  key: string;
  label: string;
  value: number;
  /** The fill, as a token utility supplied by the caller. */
  className: string;
}

/**
 * A whole, divided into named parts.
 *
 * One bar rather than a pie: the parts here are always compared against each
 * other and against the total, and a stacked bar does that at a glance while a
 * pie asks the eye to compare angles. It also survives a phone, which a pie
 * with four labels does not.
 *
 * **The colours come from the caller.** This file has no palette of its own,
 * which is what lets the reward-tier version live under `components/gamification/`
 * where the tier tokens are allowed to be used — the rule
 * `tests/design-tokens.test.ts` enforces.
 *
 * Every segment is named in text beneath the bar. Colour alone would make the
 * whole figure unreadable to a colour-blind teacher (NFR-4.6), and the legend
 * doubles as the place the counts are actually readable.
 */
export function DistributionBar({
  segments,
  label,
  className,
}: {
  segments: DistributionSegment[];
  /** The accessible name for the bar as a whole. */
  label: string;
  className?: string;
}) {
  const total = segments.reduce((sum, segment) => sum + segment.value, 0);

  if (total === 0) {
    return (
      <p className={cn("text-muted-foreground text-sm", className)}>
        Nothing to show for this period yet.
      </p>
    );
  }

  const share = (value: number) => (value / total) * 100;

  return (
    <div className={cn("flex flex-col gap-3", className)}>
      <div
        className="bg-muted flex h-3 w-full overflow-hidden rounded-full"
        role="img"
        aria-label={`${label}: ${segments
          .filter((segment) => segment.value > 0)
          .map((segment) => `${segment.label} ${Math.round(share(segment.value))}%`)
          .join(", ")}`}
      >
        {segments
          .filter((segment) => segment.value > 0)
          .map((segment) => (
            <span
              key={segment.key}
              className={segment.className}
              style={{ width: `${share(segment.value)}%` }}
            />
          ))}
      </div>

      <ul className="flex flex-wrap gap-x-4 gap-y-1.5">
        {segments.map((segment) => (
          <li key={segment.key} className="flex items-center gap-1.5 text-sm">
            <span className={cn("size-2.5 shrink-0 rounded-full", segment.className)} aria-hidden />
            <span>{segment.label}</span>
            <span className="text-muted-foreground tabular-nums">
              {Math.round(share(segment.value))}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
