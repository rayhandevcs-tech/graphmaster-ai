"use client";

import { Chip } from "./chip";
import { cn } from "@/lib/utils";

export interface ChipOption<T extends string> {
  value: T;
  label: string;
}

/**
 * A single-select filter row.
 *
 * Buttons with `aria-pressed` rather than a `<select>`: the options are worth
 * showing rather than hiding behind a picker, and the whole set is three or
 * four items. `null` is "no filter" and it is an option in the row — a student
 * should undo a filter with the same gesture that set it, not hunt for a clear
 * button.
 *
 * The chip itself is `ui/chip.tsx`, shared with the leaderboard's scope row so
 * the two cannot drift apart on touch size again.
 */
export function FilterChips<T extends string>({
  label,
  options,
  value,
  onChange,
  allLabel = "All",
  className,
}: {
  label: string;
  options: readonly ChipOption<T>[];
  value: T | null;
  onChange: (next: T | null) => void;
  allLabel?: string;
  className?: string;
}) {
  const entries: { value: T | null; label: string }[] = [
    { value: null, label: allLabel },
    ...options,
  ];

  return (
    <div
      role="group"
      aria-label={label}
      className={cn("flex flex-wrap items-center gap-1.5", className)}
    >
      {entries.map((entry) => (
        <Chip
          key={entry.value ?? "__all"}
          pressed={entry.value === value}
          onPress={() => onChange(entry.value)}
        >
          {entry.label}
        </Chip>
      ))}
    </div>
  );
}
