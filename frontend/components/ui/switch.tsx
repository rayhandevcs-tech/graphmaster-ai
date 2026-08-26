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
      className={cn(
        "focus-visible:ring-ring inline-flex h-6 w-11 shrink-0 items-center rounded-full border-2 border-transparent",
        "transition-colors focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none",
        "disabled:cursor-not-allowed disabled:opacity-50",
        checked ? "bg-primary" : "bg-muted-foreground/40",
        className,
      )}
    >
      <span
        className={cn(
          "bg-background pointer-events-none block size-5 rounded-full shadow transition-transform",
          checked ? "translate-x-5" : "translate-x-0",
        )}
      />
    </button>
  );
}
