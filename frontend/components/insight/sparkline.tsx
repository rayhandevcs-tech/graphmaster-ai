import { cn } from "@/lib/utils";

/**
 * A trend small enough to sit beside a number.
 *
 * Hand-drawn SVG rather than a chart. Chart.js on a dashboard tile costs a
 * lazy import, a canvas, a resize observer and a data-table toggle for a
 * 40-pixel line whose only job is to say "roughly this shape" — the readable
 * version lives on the analytics screen, one tap away, and is a chart there.
 *
 * **It breaks where the data does.** `null` is a bucket with no marked work,
 * and the polyline restarts after one rather than running through it. A
 * sparkline that bridges its gaps is the smallest possible version of the lie
 * this project keeps refusing to tell.
 */
export function Sparkline({
  values,
  label,
  className,
}: {
  /** In order. `null` is a bucket with nothing marked. */
  values: (number | null)[];
  /** What a screen reader hears instead of the shape. */
  label: string;
  className?: string;
}) {
  const known = values.filter((value): value is number => value !== null);

  if (known.length < 2) {
    return (
      <p className={cn("text-muted-foreground text-xs", className)}>
        Not enough marked work to draw a line yet.
      </p>
    );
  }

  const width = 100;
  const height = 28;
  const low = Math.min(...known);
  const high = Math.max(...known);
  const span = high - low || 1;

  const x = (index: number) => (index / (values.length - 1)) * width;
  const y = (value: number) => height - ((value - low) / span) * (height - 4) - 2;

  // One `M` per run of known values: a gap starts a new subpath instead of
  // joining across it.
  let path = "";
  let pen = false;
  values.forEach((value, index) => {
    if (value === null) {
      pen = false;
      return;
    }
    path += `${pen ? "L" : "M"}${x(index).toFixed(2)} ${y(value).toFixed(2)} `;
    pen = true;
  });

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      role="img"
      aria-label={label}
      className={cn("text-primary h-8 w-full", className)}
    >
      <path
        d={path.trim()}
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
