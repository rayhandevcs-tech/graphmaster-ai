import { Check, CloudAlert, RefreshCw } from "lucide-react";

import { cn } from "@/lib/utils";

export type SaveState = "idle" | "saving" | "saved" | "error";

/**
 * Whether the draft is safe.
 *
 * A student writes 200 words in this box. Saying nothing about whether any of
 * it has reached the server is the difference between a closed tab costing
 * nothing and costing the whole attempt — so the state is always on screen,
 * including the failure, which is the one that matters.
 */
export function SaveStatus({ state, className }: { state: SaveState; className?: string }) {
  if (state === "idle") return null;

  const { Icon, text, tone } = {
    saving: { Icon: RefreshCw, text: "Saving…", tone: "text-muted-foreground" },
    saved: { Icon: Check, text: "Draft saved", tone: "text-muted-foreground" },
    error: {
      Icon: CloudAlert,
      text: "Not saved — check your connection",
      tone: "text-destructive",
    },
  }[state];

  return (
    <p
      // Polite: it must not interrupt someone mid-sentence, but a failed save
      // has to reach a screen-reader user without them going looking for it.
      aria-live="polite"
      className={cn("inline-flex items-center gap-1.5 text-xs", tone, className)}
    >
      <Icon className={cn("size-3.5", state === "saving" && "animate-spin")} aria-hidden />
      {text}
    </p>
  );
}
