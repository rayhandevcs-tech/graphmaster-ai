import { cn } from "@/lib/utils";

export interface Finding {
  key: string;
  label: string;
  value: number;
  /** The line beneath — a category, a lemma, how many students. */
  detail?: string;
}

/**
 * A ranked list where the bar *is* the comparison.
 *
 * Used for the mistakes worth a lesson and the words a class reaches for.
 * A bare table of counts makes a reader do the ranking themselves; the fill
 * behind each row is proportional to the largest value, so the shape of the
 * list carries the finding before any number is read.
 *
 * The bar is a background rather than a chart: it reflows to any width, needs
 * no canvas, and the figures stay selectable text.
 */
export function FindingList({
  findings,
  valueLabel,
  emptyMessage,
  className,
}: {
  findings: Finding[];
  /** What the number counts — "uses", "occurrences". Announced, not printed. */
  valueLabel: string;
  emptyMessage: string;
  className?: string;
}) {
  if (findings.length === 0) {
    return <p className={cn("text-muted-foreground text-sm", className)}>{emptyMessage}</p>;
  }

  const peak = Math.max(...findings.map((finding) => finding.value), 1);

  return (
    <ol className={cn("flex flex-col gap-1", className)}>
      {findings.map((finding) => (
        <li key={finding.key} className="relative overflow-hidden rounded-md">
          <span
            className="bg-primary/10 absolute inset-y-0 left-0"
            style={{ width: `${(finding.value / peak) * 100}%` }}
            aria-hidden
          />
          <div className="relative flex items-baseline justify-between gap-3 px-3 py-2">
            <span className="flex flex-col">
              <span className="text-sm font-medium">{finding.label}</span>
              {finding.detail ? (
                <span className="text-muted-foreground text-xs">{finding.detail}</span>
              ) : null}
            </span>
            <span className="text-sm tabular-nums">
              {finding.value.toLocaleString()}
              <span className="sr-only"> {valueLabel}</span>
            </span>
          </div>
        </li>
      ))}
    </ol>
  );
}
