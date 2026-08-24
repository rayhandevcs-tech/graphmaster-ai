import { Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * The label is the point: a spinner with no accessible name is silence to a
 * screen reader, which is indistinguishable from a page that has stopped.
 */
export function Spinner({ className, label = "Loading" }: { className?: string; label?: string }) {
  return (
    <span role="status" className="inline-flex items-center gap-2">
      <Loader2 className={cn("size-4 animate-spin", className)} aria-hidden />
      <span className="sr-only">{label}</span>
    </span>
  );
}
