"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Check } from "lucide-react";

import { DeadlineChip } from "./deadline-chip";
import { Reveal } from "@/components/motion/reveal";
import { Card } from "@/components/ui/card";
import { assignmentsApi, queryKeys } from "@/lib/api";
import { GRAPH_TYPE_LABELS } from "@/components/practice/graph-meta";
import type { AssignmentSummary } from "@/types/api";

/**
 * What your teacher asked for, above what you chose for yourself.
 *
 * Only rendered when there is something set — a permanently empty "Assignments"
 * card on every student's dashboard is furniture that teaches them to skip
 * that part of the screen.
 *
 * **A student is never shown how their classmates are doing.** The card says
 * whether *they* have started, and the API sends them no class counts at all.
 * "18 of your 30 classmates have finished" is the comparison FR-7.6 keeps off
 * the leaderboard, and it does not get in here through the dashboard either.
 *
 * Nothing says "late", before or after the deadline. The chip is a plan while
 * the date is ahead and a quiet fact once it has passed; the work is accepted
 * either way and scores the same.
 */
export function SetForYou() {
  const assignments = useQuery({
    queryKey: queryKeys.assignments({ page_size: 5 }),
    queryFn: () => assignmentsApi.list({ page_size: 5 }),
  });

  const items = assignments.data?.items ?? [];
  // Nothing at all — not an empty card, and not an empty wrapper either: the
  // dashboard is a `gap-6` column, so a rendered-but-empty child would leave a
  // visible hole between the hero panel and the figures.
  if (items.length === 0) return null;

  return (
    <Reveal delay={0.03}>
      <Card className="flex flex-col gap-4 p-5">
        <div className="flex flex-col gap-1">
          <h2 className="font-semibold tracking-tight">Set for you</h2>
          <p className="text-muted-foreground text-sm">
            Your teacher showed these in class. Describe them here in your own words.
          </p>
        </div>

        <ul className="-mx-2 flex flex-col">
          {items.map((assignment) => (
            <TaskRow key={assignment.id} assignment={assignment} />
          ))}
        </ul>
      </Card>
    </Reveal>
  );
}

function TaskRow({ assignment }: { assignment: AssignmentSummary }) {
  const done = assignment.submission_status === "scored";
  const started = Boolean(assignment.submission_id) && !done;

  return (
    <li>
      <Link
        href={
          done
            ? `/submissions/${assignment.submission_id}`
            : `/practice/${assignment.graph_id}?assignment=${assignment.id}`
        }
        className="hover:bg-muted/50 focus-visible:ring-ring flex min-h-14 items-center gap-3 rounded-lg px-2 py-2.5 transition-colors focus-visible:ring-2 focus-visible:outline-none"
      >
        <span className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span className="truncate text-sm font-medium">{assignment.title}</span>
          <span className="text-muted-foreground truncate text-xs">
            {GRAPH_TYPE_LABELS[assignment.graph_type]} · {assignment.graph_title}
          </span>
        </span>

        {done ? (
          <span className="text-muted-foreground inline-flex shrink-0 items-center gap-1 text-xs font-medium">
            <Check className="size-3.5" aria-hidden />
            Done
          </span>
        ) : (
          <span className="flex shrink-0 items-center gap-2">
            {started ? (
              <span className="text-muted-foreground text-xs font-medium">In progress</span>
            ) : null}
            <DeadlineChip dueAt={assignment.due_at ?? null} />
            <ArrowRight className="text-muted-foreground size-4" aria-hidden />
          </span>
        )}
      </Link>
    </li>
  );
}
