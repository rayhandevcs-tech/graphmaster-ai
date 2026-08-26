import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

/**
 * One 0–100 measure with its number beside it.
 *
 * The number is always shown, not only the bar: a bar communicates roughly, and
 * a student comparing this attempt with their last one needs the figure.
 */
export function MetricBar({
  label,
  value,
  hint,
  barClassName,
  className,
}: {
  label: string;
  value: number;
  hint?: string;
  barClassName?: string;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-sm">{label}</span>
        <span className="text-sm font-medium tabular-nums">{Math.round(value)}</span>
      </div>
      <Progress value={value} label={label} size="sm" barClassName={barClassName} />
      {hint ? <p className="text-muted-foreground text-xs text-pretty">{hint}</p> : null}
    </div>
  );
}
