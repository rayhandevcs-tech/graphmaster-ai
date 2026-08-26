import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * A determinate progress bar.
 *
 * Deliberately colourless by default: the fill is `primary`, and a caller that
 * needs another colour passes `barClassName`. That is how the XP bar gets its
 * gold without this file — an ordinary interface primitive — being somewhere
 * gold lives (`tests/design-tokens.test.ts` enforces the difference).
 *
 * `label` is required rather than optional. A bar with no accessible name is a
 * rectangle to a screen reader, and a percentage with nothing to attach it to
 * is worse than no bar at all.
 */
export interface ProgressProps extends Omit<React.ComponentPropsWithoutRef<"div">, "children"> {
  value: number;
  max?: number;
  /** The accessible name. Visually hidden — pair it with your own visible text. */
  label: string;
  /** Spoken instead of the bare percentage, e.g. "740 of 1,000 XP". */
  valueText?: string;
  size?: "sm" | "md" | "lg";
  barClassName?: string;
}

const TRACK_HEIGHT = { sm: "h-1.5", md: "h-2.5", lg: "h-4" } as const;

export function Progress({
  value,
  max = 100,
  label,
  valueText,
  size = "md",
  className,
  barClassName,
  ...props
}: ProgressProps) {
  // A NaN from a division by zero upstream would render a bar of width "NaN%",
  // which browsers drop silently — so the fallback is explicit.
  const safeMax = max > 0 ? max : 100;
  const clamped = Number.isFinite(value) ? Math.min(Math.max(value, 0), safeMax) : 0;
  const percent = (clamped / safeMax) * 100;

  return (
    <div
      role="progressbar"
      aria-valuenow={Math.round(clamped)}
      aria-valuemin={0}
      aria-valuemax={safeMax}
      aria-label={label}
      aria-valuetext={valueText}
      className={cn("bg-muted w-full overflow-hidden rounded-full", TRACK_HEIGHT[size], className)}
      {...props}
    >
      <div
        className={cn(
          "bg-primary h-full rounded-full transition-[width] duration-500",
          barClassName,
        )}
        style={{ width: `${percent}%` }}
      />
    </div>
  );
}
