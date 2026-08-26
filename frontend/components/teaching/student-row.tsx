import Link from "next/link";
import { ChevronRight } from "lucide-react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { formatPercent, formatWhen, initials } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { StudentRow as Student } from "@/types/api";

/**
 * One student, as a row a teacher taps.
 *
 * The whole row is the target, not the chevron: 56px tall on a phone, which is
 * inside the comfortable band the design directive asks for and well above the
 * 44px minimum. A chevron sized for a thumb would dominate the row; a chevron
 * sized for the row would be too small to hit.
 *
 * `detail` is passed in rather than derived here because it differs by
 * context — a student who has not started needs no figures, one who is finding
 * it hard needs their average and their attempt count, one who has gone quiet
 * needs the date. Wording the evidence at the call site keeps this component
 * from growing a `variant` prop that decides what a teacher reads.
 */
export function StudentRowLink({
  student,
  detail,
  className,
}: {
  student: Student;
  detail: React.ReactNode;
  className?: string;
}) {
  return (
    <li>
      <Link
        href={`/teacher/submissions?student=${student.user_id}`}
        className={cn(
          "hover:bg-muted/50 focus-visible:ring-ring flex min-h-14 items-center gap-3 rounded-lg px-3 py-2",
          "scroll-mt-32 transition-colors focus-visible:ring-2 focus-visible:outline-none",
          className,
        )}
      >
        <Avatar className="size-9 shrink-0">
          <AvatarFallback className="text-xs">{initials(student.full_name)}</AvatarFallback>
        </Avatar>

        <span className="flex min-w-0 flex-1 flex-col">
          <span className="truncate text-sm font-medium">{student.full_name}</span>
          <span className="text-muted-foreground truncate text-xs">{detail}</span>
        </span>

        <ChevronRight className="text-muted-foreground size-4 shrink-0" aria-hidden />
      </Link>
    </li>
  );
}

/** The evidence line for a student who is finding the work hard. */
export function hardDetail(student: Student): string {
  const attempts =
    student.submission_count === 1 ? "1 attempt" : `${student.submission_count} attempts`;
  return `Averaging ${formatPercent(student.average_final_score, 0)} over ${attempts}`;
}

/** The evidence line for a student who has stopped. */
export function quietDetail(student: Student): string {
  if (!student.last_submission_at) return "No marked work";
  return `Last worked ${formatWhen(student.last_submission_at)}`;
}
