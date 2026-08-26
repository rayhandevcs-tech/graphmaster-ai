import { cn } from "@/lib/utils";

const RADIUS = 52;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

/**
 * The final score, as a ring.
 *
 * Deliberately `primary` rather than the tier's colour. The tier is decided by
 * the vocabulary percentage and the final score is a different number
 * (FR-7.1) — colouring this ring by tier would quietly assert that the two
 * move together, which is exactly the misreading the tier panel exists to
 * correct.
 */
export function ScoreRing({
  value,
  label,
  className,
}: {
  value: number;
  label: string;
  className?: string;
}) {
  const clamped = Math.min(Math.max(Number.isFinite(value) ? value : 0, 0), 100);

  return (
    <div className={cn("relative grid size-32 place-items-center", className)}>
      <svg viewBox="0 0 120 120" className="size-full -rotate-90" aria-hidden>
        <circle cx="60" cy="60" r={RADIUS} className="stroke-muted fill-none" strokeWidth="9" />
        <circle
          cx="60"
          cy="60"
          r={RADIUS}
          className="stroke-primary fill-none transition-[stroke-dashoffset] duration-700"
          strokeWidth="9"
          strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={CIRCUMFERENCE * (1 - clamped / 100)}
        />
      </svg>

      <div className="absolute flex flex-col items-center">
        <span className="text-3xl font-semibold tabular-nums">{Math.round(clamped)}</span>
        <span className="text-muted-foreground text-xs">out of 100</span>
      </div>
      <span className="sr-only">{label}</span>
    </div>
  );
}
