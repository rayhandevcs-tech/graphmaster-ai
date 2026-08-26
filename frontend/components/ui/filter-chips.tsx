"use client";

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
      {entries.map((entry) => {
        const active = entry.value === value;
        return (
          <button
            key={entry.value ?? "__all"}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(entry.value)}
            className={cn(
              "focus-visible:ring-ring rounded-full border px-3 py-1.5 text-xs font-medium",
              "transition-colors focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none",
              active
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border text-muted-foreground hover:border-input hover:text-foreground",
            )}
          >
            {entry.label}
          </button>
        );
      })}
    </div>
  );
}
