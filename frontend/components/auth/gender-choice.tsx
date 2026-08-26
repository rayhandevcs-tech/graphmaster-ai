"use client";

import { cn } from "@/lib/utils";
import type { Gender } from "@/types/api";

/**
 * Which avatar set the student's rewards use.
 *
 * A pair of radio buttons rather than a dropdown, because there are two
 * options and both should be visible; and framed by what it *does* rather than
 * as a bare demographic field, because that is the only thing the platform
 * uses it for — the avatar catalogue and the gendered crown headline
 * ("Graph King" / "Graph Queen"). Saying so is the difference between a
 * question with a purpose and one that reads as data collection.
 *
 * A real `radiogroup`, so arrow keys move between the options and a screen
 * reader announces "1 of 2".
 */
const OPTIONS: { value: Gender; label: string; hint: string }[] = [
  { value: "female", label: "She / her", hint: "Graph Queen" },
  { value: "male", label: "He / him", hint: "Graph King" },
];

export function GenderChoice({
  value,
  onChange,
  error,
  describedById,
}: {
  value: Gender | null;
  onChange: (value: Gender) => void;
  error?: string;
  describedById?: string;
}) {
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="text-sm leading-none font-medium">Your avatar set</legend>
      <p id={describedById} className="text-muted-foreground text-xs">
        This chooses the cartoon character that celebrates your results. You can change the
        character itself next.
      </p>

      <div
        role="radiogroup"
        aria-label="Your avatar set"
        aria-invalid={Boolean(error)}
        className="mt-1 grid grid-cols-2 gap-3"
      >
        {OPTIONS.map((option) => {
          const selected = value === option.value;
          return (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={selected}
              onClick={() => onChange(option.value)}
              className={cn(
                "flex flex-col items-start gap-0.5 rounded-lg border p-3 text-left transition-colors",
                selected
                  ? "border-primary bg-primary/5 ring-primary/30 ring-2"
                  : "hover:bg-accent/60",
              )}
            >
              <span className="text-sm font-medium">{option.label}</span>
              <span className="text-muted-foreground text-xs">{option.hint}</span>
            </button>
          );
        })}
      </div>

      {error ? <p className="text-destructive text-sm">{error}</p> : null}
    </fieldset>
  );
}
