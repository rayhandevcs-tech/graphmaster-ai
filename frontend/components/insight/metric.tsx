import { cn } from "@/lib/utils";

/**
 * One figure, with the absence of one handled properly.
 *
 * `value` is already formatted — `formatPercent` and `formatCount` render a
 * missing number as an em dash, and this component is where that dash is made
 * legible to a screen reader. Several readers announce a bare "—"
 * inconsistently and some skip it entirely, so a student or teacher listening
 * to the page would hear a label with no value and reasonably assume the page
 * had failed to load.
 */
export function Metric({
  label,
  value,
  detail,
  emphasis = "md",
  className,
}: {
  label: string;
  /** Pre-formatted. "—" is a first-class value here, not a placeholder. */
  value: string;
  /** The line under the figure — a count, a comparison, a unit. */
  detail?: string;
  emphasis?: "sm" | "md" | "lg";
  className?: string;
}) {
  const missing = value === "—";

  return (
    <div className={cn("flex flex-col gap-0.5", className)}>
      <span
        className={cn(
          "font-semibold tabular-nums",
          emphasis === "lg" && "text-3xl",
          emphasis === "md" && "text-2xl",
          emphasis === "sm" && "text-lg",
          missing && "text-muted-foreground",
        )}
      >
        {value}
        {missing ? <span className="sr-only">no marked work yet</span> : null}
      </span>
      <span className="text-muted-foreground text-xs font-medium tracking-wide uppercase">
        {label}
      </span>
      {detail ? <span className="text-muted-foreground text-sm">{detail}</span> : null}
    </div>
  );
}
