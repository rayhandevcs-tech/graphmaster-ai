import { Flame } from "lucide-react";

import { daysLabel } from "@/lib/format";
import { cn } from "@/lib/utils";

/**
 * The practice streak.
 *
 * Purple rather than the obvious flame orange, and that is not timidity: the
 * only warm colours in the palette are gold, which means a crown, and the
 * hammer tier's amber, which means the lowest result. A flame in either would
 * borrow a meaning it does not have. The icon carries "streak" on its own.
 *
 * A streak of zero is stated plainly rather than hidden. A student who has
 * just broken one needs to see that it is at zero to have a reason to start
 * another, and the copy names the way back rather than the loss.
 */
export function StreakFlame({
  currentDays,
  longestDays,
  className,
}: {
  currentDays: number;
  longestDays: number;
  className?: string;
}) {
  const running = currentDays > 0;

  return (
    <div className={cn("flex items-center gap-3", className)}>
      <span
        className={cn(
          "flex size-11 shrink-0 items-center justify-center rounded-full",
          running ? "bg-primary/12 text-primary" : "bg-muted text-muted-foreground",
        )}
      >
        <Flame className="size-5" aria-hidden />
      </span>

      <div className="flex flex-col">
        <span className="text-sm font-semibold">
          {running ? `${daysLabel(currentDays)} in a row` : "No streak yet"}
        </span>
        <span className="text-muted-foreground text-xs">
          {longestDays > 0
            ? `Your best is ${daysLabel(longestDays)}`
            : "Practise today to start one"}
        </span>
      </div>
    </div>
  );
}
