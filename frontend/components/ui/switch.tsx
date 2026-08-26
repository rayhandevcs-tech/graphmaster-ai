"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * An on/off control, built on `role="switch"` rather than a checkbox.
 *
 * The distinction matters to a screen reader: a checkbox is one of several
 * things you are selecting, and a switch takes effect the moment it moves.
 * Everything this control does — showing deactivated terms, turning a filter
 * on — takes effect immediately, so "switch" is the honest role and "on"/"off"
 * the honest announcement.
 */
export function Switch({
  checked,
  onCheckedChange,
  label,
  disabled,
  className,
}: {
  checked: boolean;
  onCheckedChange: (next: boolean) => void;
  /** Always required: an unlabelled switch announces only its state. */
  label: string;
  disabled?: boolean;
  className?: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onCheckedChange(!checked)}
      // The track is 24px because that is what a switch looks like. The
      // *button* is 44px, with the track centred inside it — a control this
      // small is otherwise a quarter of the area a thumb needs.
      className={cn(
        "focus-visible:ring-ring inline-flex min-h-11 shrink-0 items-center rounded-md px-0.5",
        "focus-visible:ring-2 focus-visible:outline-none",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
    >
      <span
        className={cn(
          "inline-flex h-6 w-11 items-center rounded-full border-2 border-transparent transition-colors",
          checked ? "bg-primary" : "bg-muted-foreground/40",
        )}
      >
        <span
          className={cn(
            "bg-background pointer-events-none block size-5 rounded-full shadow transition-transform",
            checked ? "translate-x-5" : "translate-x-0",
          )}
        />
      </span>
    </button>
  );
}
