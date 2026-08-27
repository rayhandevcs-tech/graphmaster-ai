import { describeDeadline } from "@/lib/insights/deadline";
import { cn } from "@/lib/utils";

/**
 * When the work is due, worded so a passed deadline is not an alarm.
 *
 * There is deliberately no destructive variant. The platform accepts work
 * after the deadline and never changes the mark for it, so a red chip would
 * tell a teacher at a glance to treat lateness as a penalty the product does
 * not implement.
 *
 * The colour never carries the meaning on its own: the label already says
 * "Due today" or "Due date passed", and the `title` carries the full sentence
 * for anyone who wants it.
 */
export function DeadlineChip({ dueAt, className }: { dueAt: string | null; className?: string }) {
  const deadline = describeDeadline(dueAt);

  return (
    <span
      title={deadline.description}
      className={cn(
        "inline-flex shrink-0 items-center rounded-full border px-2.5 py-1 text-xs font-medium",
        deadline.tone === "soon" && "border-primary/40 bg-primary/10 text-primary",
        deadline.tone === "later" && "border-border text-muted-foreground",
        deadline.tone === "passed" && "border-border bg-muted text-muted-foreground",
        deadline.tone === "none" && "border-border text-muted-foreground border-dashed",
        className,
      )}
    >
      {deadline.label}
      <span className="sr-only">. {deadline.description}</span>
    </span>
  );
}
