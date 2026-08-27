"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, CircleSlash, RefreshCw } from "lucide-react";

import { CompletionBar } from "./completion-bar";
import { DeadlineChip } from "./deadline-chip";
import { EditWorkDialog } from "./edit-work-dialog";
import { Metric } from "@/components/insight/metric";
import { Reveal } from "@/components/motion/reveal";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { assignmentsApi, errorMessage, queryKeys } from "@/lib/api";
import { formatCount, formatPercent, formatWhen, initials } from "@/lib/format";
import { describeSubmissionProgress, formatDeadline } from "@/lib/insights/deadline";
import type { AssignmentStudentProgress } from "@/types/api";

/**
 * Who has done this piece of work, and who has not.
 *
 * **Not started comes first**, above the submitted list and above the figures.
 * The submitted list is a record; the not-started list is a task, and it is
 * the only thing on this screen a teacher can act on today.
 *
 * Everything is counted against enrolment (CLAUDE.md rule 35). A screen that
 * counted against "everyone who submitted" would read as a full class every
 * time and would let half a cohort disappear.
 */
export function AssignmentProgressView({ assignmentId }: { assignmentId: string }) {
  const progress = useQuery({
    queryKey: queryKeys.assignmentProgress(assignmentId),
    queryFn: () => assignmentsApi.progress(assignmentId),
  });

  if (progress.isError) {
    return (
      <div className="flex flex-col gap-6">
        <BackLink />
        <Alert variant="destructive">
          <AlertTitle>This assignment could not be loaded</AlertTitle>
          <AlertDescription className="flex flex-col items-start gap-3">
            <span>{errorMessage(progress.error)}</span>
            <Button variant="outline" size="sm" onClick={() => void progress.refetch()}>
              <RefreshCw aria-hidden />
              Try again
            </Button>
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  if (progress.isPending) {
    return (
      <div className="flex flex-col gap-6">
        <BackLink />
        <Skeleton className="h-24 rounded-xl" />
        <div className="grid gap-4 lg:grid-cols-3">
          <Skeleton className="h-64 rounded-xl lg:col-span-2" />
          <Skeleton className="h-64 rounded-xl" />
        </div>
      </div>
    );
  }

  const data = progress.data;
  const assignment = data.assignment;
  const notStarted = data.students.filter((student) => student.submission_id === null);
  const submitted = data.students.filter((student) => student.submission_id !== null);
  const summary = describeSubmissionProgress(data.submitted_count, data.enrolled_count);

  return (
    <div className="flex flex-col gap-6">
      <BackLink />

      <header className="flex flex-col gap-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex flex-col gap-1">
            <h1 className="text-2xl font-semibold tracking-tight text-balance">
              {assignment.title}
            </h1>
            <p className="text-muted-foreground text-sm">
              {assignment.graph_title} · {assignment.class_name}
              {assignment.due_at ? ` · Due ${formatDeadline(assignment.due_at)}` : ""}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <DeadlineChip dueAt={assignment.due_at ?? null} />
            <EditWorkDialog assignment={assignment} />
          </div>
        </div>

        {assignment.instructions ? (
          <p className="text-muted-foreground max-w-prose text-sm text-pretty">
            {assignment.instructions}
          </p>
        ) : null}
      </header>

      <div className="grid items-start gap-4 lg:grid-cols-3">
        <div className="flex flex-col gap-4 lg:col-span-2">
          <Reveal>
            <Card className="flex flex-col gap-3 p-5">
              <h2 className="flex items-baseline gap-2 text-sm font-semibold tracking-tight">
                Not started
                <span className="text-muted-foreground text-xs font-medium tabular-nums">
                  {formatCount(notStarted.length)}
                </span>
              </h2>
              {notStarted.length === 0 ? (
                <p className="text-muted-foreground text-sm">
                  Everyone enrolled has submitted something.
                </p>
              ) : (
                <ul className="-mx-2 flex flex-col">
                  {notStarted.map((student) => (
                    <li
                      key={student.user_id}
                      className="flex min-h-14 items-center gap-3 rounded-lg px-2 py-2"
                    >
                      <Avatar className="size-9 shrink-0">
                        <AvatarFallback className="text-xs">
                          {initials(student.full_name)}
                        </AvatarFallback>
                      </Avatar>
                      <span className="min-w-0 flex-1 truncate text-sm font-medium">
                        {student.full_name}
                      </span>
                      <CircleSlash className="text-muted-foreground size-4 shrink-0" aria-hidden />
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </Reveal>

          <Reveal delay={0.06}>
            <Card className="flex flex-col gap-3 p-5">
              <h2 className="flex items-baseline gap-2 text-sm font-semibold tracking-tight">
                Submitted
                <span className="text-muted-foreground text-xs font-medium tabular-nums">
                  {formatCount(submitted.length)}
                </span>
              </h2>
              {submitted.length === 0 ? (
                <p className="text-muted-foreground text-sm">
                  Nothing has been handed in for this yet.
                </p>
              ) : (
                <ul className="-mx-2 flex flex-col">
                  {submitted.map((student) => (
                    <SubmittedRow key={student.user_id} student={student} />
                  ))}
                </ul>
              )}
            </Card>
          </Reveal>
        </div>

        <Reveal delay={0.1}>
          <Card className="flex flex-col gap-5 p-6">
            <h2 className="text-muted-foreground text-xs font-medium tracking-wide uppercase">
              This assignment
            </h2>

            <div className="flex flex-col gap-2">
              <Metric
                label="Submitted"
                value={`${data.submitted_count} of ${data.enrolled_count}`}
                emphasis="lg"
              />
              <CompletionBar submitted={data.submitted_count} enrolled={data.enrolled_count} />
              <p className="text-muted-foreground text-xs text-pretty">{summary.action}</p>
            </div>

            <div className="flex flex-col gap-3 border-t pt-4">
              <Metric label="Marked" value={formatCount(data.scored_count)} emphasis="sm" />
              <Metric
                label="Average score"
                value={formatPercent(data.average_score, 0)}
                emphasis="sm"
              />
              <Metric
                label="After the deadline"
                value={formatCount(data.late_count)}
                emphasis="sm"
              />
            </div>

            <p className="text-muted-foreground border-t pt-4 text-xs text-pretty">
              Work handed in after the deadline is accepted and scores exactly the same. Lateness is
              recorded here for you, and nowhere the student sees it.
            </p>
          </Card>
        </Reveal>
      </div>
    </div>
  );
}

/**
 * One student who has handed something in.
 *
 * The score is `—` until the attempt is marked, never `0`: a draft mid-flight
 * is not a student who scored nothing, and a zero would sort them below
 * someone genuinely struggling (CLAUDE.md rule 32).
 */
function SubmittedRow({ student }: { student: AssignmentStudentProgress }) {
  return (
    <li>
      <Link
        href={`/teacher/submissions/${student.submission_id}`}
        className="hover:bg-muted/50 focus-visible:ring-ring flex min-h-14 items-center gap-3 rounded-lg px-2 py-2 transition-colors focus-visible:ring-2 focus-visible:outline-none"
      >
        <Avatar className="size-9 shrink-0">
          <AvatarFallback className="text-xs">{initials(student.full_name)}</AvatarFallback>
        </Avatar>

        <span className="flex min-w-0 flex-1 flex-col">
          <span className="truncate text-sm font-medium">{student.full_name}</span>
          <span className="text-muted-foreground truncate text-xs">
            {student.submitted_at ? formatWhen(student.submitted_at) : ""}
            {student.is_late ? " · after the deadline" : ""}
          </span>
        </span>

        <span className="shrink-0 text-sm font-semibold tabular-nums">
          {student.final_score === null || student.final_score === undefined ? (
            <span className="text-muted-foreground">
              —<span className="sr-only">not marked yet</span>
            </span>
          ) : (
            formatPercent(student.final_score, 0)
          )}
        </span>
      </Link>
    </li>
  );
}

function BackLink() {
  return (
    <Link
      href="/teacher/assignments"
      className="text-muted-foreground hover:text-foreground focus-visible:ring-ring inline-flex min-h-11 w-fit items-center gap-1.5 rounded-md text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none sm:min-h-8"
    >
      <ArrowLeft className="size-4" aria-hidden />
      Work you set
    </Link>
  );
}
