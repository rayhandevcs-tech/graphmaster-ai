import Link from "next/link";
import { ChevronRight } from "lucide-react";

import { CompletionBar } from "./completion-bar";
import { DeadlineChip } from "./deadline-chip";
import { Card } from "@/components/ui/card";
import { describeSubmissionProgress } from "@/lib/insights/deadline";
import type { AssignmentSummary } from "@/types/api";

/**
 * One piece of set work, as a teacher reads it.
 *
 * The loudest thing on the card is the bar and the count under it, because
 * the question a teacher opens this page with is "who has not done it" — not
 * "what did I set". The title is the label for that figure, not the point.
 *
 * The whole card is one link rather than a card containing a link: one tab
 * stop, one target well past 44px, and nothing for a screen reader to
 * announce twice.
 */
export function AssignmentCard({ assignment }: { assignment: AssignmentSummary }) {
  const submitted = assignment.submitted_count ?? 0;
  const enrolled = assignment.enrolled_count ?? 0;
  const progress = describeSubmissionProgress(submitted, enrolled);

  return (
    <Card className="hover:border-primary/40 focus-within:border-primary/40 transition-colors">
      <Link
        href={`/teacher/assignments/${assignment.id}`}
        className="focus-visible:ring-ring flex flex-col gap-4 rounded-xl p-5 focus-visible:ring-2 focus-visible:outline-none"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 flex-col gap-1">
            <h3 className="truncate font-semibold tracking-tight">{assignment.title}</h3>
            <p className="text-muted-foreground truncate text-sm">
              {assignment.graph_title} · {assignment.class_name}
            </p>
          </div>
          <DeadlineChip dueAt={assignment.due_at ?? null} />
        </div>

        <div className="flex flex-col gap-2">
          <CompletionBar submitted={submitted} enrolled={enrolled} />
          <p className="text-sm font-medium tabular-nums">{progress.headline}</p>
        </div>

        <p className="text-muted-foreground flex items-center gap-1 text-sm">
          {progress.action}
          <ChevronRight className="size-4" aria-hidden />
        </p>

        {assignment.is_active ? null : (
          <p className="text-muted-foreground text-xs">
            Closed — students no longer see this on their list.
          </p>
        )}
      </Link>
    </Card>
  );
}
