import { cn } from "@/lib/utils";

/**
 * How much of a class has done the work.
 *
 * A real `progressbar`, and its accessible name is *"12 of 30 students have
 * submitted"* — the same figure the sighted reader gets. Announcing "40%"
 * instead would hand a screen-reader user a number they have to convert back
 * into people, which is the conversion this component exists to avoid.
 *
 * The track is always the full enrolment (CLAUDE.md rule 35). A bar drawn
 * against "everyone who submitted" would be full every time and would say
 * nothing.
 */
export function CompletionBar({
  submitted,
  enrolled,
  className,
}: {
  submitted: number;
  enrolled: number;
  className?: string;
}) {
  const share = enrolled === 0 ? 0 : Math.min(100, (submitted / enrolled) * 100);

  return (
    <div
      role="progressbar"
      aria-valuenow={submitted}
      aria-valuemin={0}
      aria-valuemax={enrolled}
      aria-label={`${submitted} of ${enrolled} ${
        enrolled === 1 ? "student has" : "students have"
      } submitted`}
      className={cn("bg-muted h-2 w-full overflow-hidden rounded-full", className)}
    >
      <span
        className="bg-primary block h-full rounded-full transition-[width] duration-500"
        style={{ width: `${share}%` }}
      />
    </div>
  );
}
