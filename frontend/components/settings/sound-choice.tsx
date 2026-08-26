"use client";

import { Volume2, VolumeX } from "lucide-react";

import { useSound } from "@/lib/sound/use-sound";
import { cn } from "@/lib/utils";

/**
 * Reward sounds, off unless asked for.
 *
 * FR-7.11, and not only because the specification says so: audio that starts
 * unprompted is hostile in a shared computer lab or a library, which is
 * exactly where this platform is used.
 *
 * The setting is stored per browser rather than per account. A student who
 * turns sound on for one lesson on a lab machine has not asked for it on every
 * machine they will ever sign in from — and the account is the wrong place to
 * record a fact about the room someone is sitting in.
 *
 * Kept apart from Motion above it: a student who has asked their system to
 * stop animating has not asked it to be quiet, and the reverse is at least as
 * common.
 */
const OPTIONS = [
  { value: false, label: "Muted", icon: VolumeX, hint: "The default, on every device" },
  { value: true, label: "On", icon: Volume2, hint: "A short cue with each result" },
] as const;

export function SoundChoice() {
  const { enabled, setEnabled } = useSound();

  return (
    <div role="radiogroup" aria-label="Reward sounds" className="grid gap-3 sm:grid-cols-2">
      {OPTIONS.map((option) => {
        const selected = enabled === option.value;
        return (
          <button
            key={option.label}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => setEnabled(option.value)}
            className={cn(
              "flex flex-col items-start gap-1.5 rounded-lg border p-4 text-left transition-colors",
              selected
                ? "border-primary bg-primary/5 ring-primary/30 ring-2"
                : "hover:bg-accent/60",
            )}
          >
            <option.icon className="text-muted-foreground size-4" aria-hidden />
            <span className="text-sm font-medium">{option.label}</span>
            <span className="text-muted-foreground text-xs">{option.hint}</span>
          </button>
        );
      })}
    </div>
  );
}
