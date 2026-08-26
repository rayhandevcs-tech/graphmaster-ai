"use client";

import { useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ClipboardList, RefreshCw } from "lucide-react";

import { QueueCard, QueueRow } from "./queue-row";
import { ExportMenu } from "@/components/analytics/export-menu";
import { CreateClassDialog } from "@/components/teaching/create-class-dialog";
import { ScopeBar } from "@/components/teaching/scope-bar";
import { EmptyState } from "@/components/layout/empty-state";
import { Pager } from "@/components/layout/pager";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { FilterChips } from "@/components/ui/filter-chips";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { errorMessage, queryKeys, submissionsApi } from "@/lib/api";
import { useClassScope } from "@/lib/hooks/use-class-scope";
import { formatCount } from "@/lib/format";
import type { SubmissionStatus } from "@/types/api";

/**
 * What the class has written, most recent first.
 *
 * Two presentations of the same list rather than one responsive compromise: a
 * stack of cards below `md`, a table at `md` and above. Squeezing seven
 * columns onto a 390px screen produces the horizontal scroll the design
 * directive rules out; stacking cards on a wide monitor throws away the
 * column-to-column comparison a teacher opened the screen to make.
 *
 * The status filter is single-select on purpose. Multi-status filtering was
 * deferred out of Sprint 11 and stays deferred: the four states are few enough
 * that a teacher looking for unmarked work wants exactly one of them.
 */
const STATUSES: { value: SubmissionStatus; label: string }[] = [
  { value: "scored", label: "Marked" },
  { value: "extracted", label: "Ready to mark" },
  { value: "failed", label: "Not recognised" },
  { value: "draft", label: "Draft" },
];

const PAGE_SIZE = 20;

export function SubmissionQueue() {
  const scope = useClassScope();
  const params = useSearchParams();
  const studentId = params.get("student");

  const [status, setStatus] = useState<SubmissionStatus | null>(null);
  const [page, setPage] = useState(1);

  const query = {
    class_id: scope.classId ?? undefined,
    student_id: studentId ?? undefined,
    status: status ?? undefined,
    page,
    page_size: PAGE_SIZE,
  };

  const submissions = useQuery({
    queryKey: queryKeys.submissions(query),
    queryFn: () => submissionsApi.list(query),
    enabled: Boolean(scope.classId),
    placeholderData: (previous) => previous,
  });

  if (scope.isLoading) return <QueueSkeleton />;

  if (scope.isEmpty) {
    return (
      <div className="flex flex-col gap-6">
        <Heading />
        <EmptyState
          icon={ClipboardList}
          title="No classes yet"
          description="Submissions are listed per class. Create one, and your students' work appears here as they practise."
          action={<CreateClassDialog />}
        />
      </div>
    );
  }

  const items = submissions.data?.items ?? [];
  const total = submissions.data?.total ?? 0;

  return (
    <div className="flex flex-col gap-6">
      <Heading />

      <ScopeBar
        scope={scope}
        summary={
          submissions.data
            ? `${formatCount(total)} ${total === 1 ? "attempt" : "attempts"}${
                studentId ? " from this student" : ""
              }${status ? `, ${STATUSES.find((s) => s.value === status)?.label.toLowerCase()}` : ""}.`
            : undefined
        }
        actions={
          <ExportMenu classId={scope.classId} dates={scope.dates} defaultType="submission_export" />
        }
      />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <FilterChips
          label="Status"
          options={STATUSES}
          value={status}
          onChange={(next) => {
            setStatus(next);
            setPage(1);
          }}
        />
        {studentId ? (
          <Button asChild variant="ghost" size="sm">
            <Link href="/teacher/submissions">Clear student filter</Link>
          </Button>
        ) : null}
      </div>

      {submissions.isPending ? (
        <QueueSkeleton />
      ) : submissions.isError ? (
        <Alert variant="destructive">
          <AlertTitle>These submissions could not be loaded</AlertTitle>
          <AlertDescription className="flex flex-col items-start gap-3">
            <span>{errorMessage(submissions.error)}</span>
            <Button variant="outline" size="sm" onClick={() => void submissions.refetch()}>
              <RefreshCw aria-hidden />
              Try again
            </Button>
          </AlertDescription>
        </Alert>
      ) : items.length === 0 ? (
        <EmptyState
          icon={ClipboardList}
          title="Nothing here yet"
          description={
            status
              ? "No attempts in this class match that status for the selected period."
              : "No attempts have been made in this class for the selected period."
          }
        />
      ) : (
        <>
          <ul className="flex flex-col gap-2 md:hidden">
            {items.map((summary) => (
              <QueueCard key={summary.id} summary={summary} />
            ))}
          </ul>

          <div className="hidden md:block">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Student</TableHead>
                  <TableHead>Graph</TableHead>
                  <TableHead>Written</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Score</TableHead>
                  <TableHead className="text-right">When</TableHead>
                  <TableHead className="sr-only">Open</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((summary) => (
                  <QueueRow key={summary.id} summary={summary} />
                ))}
              </TableBody>
            </Table>
          </div>

          {submissions.data && submissions.data.total_pages > 1 ? (
            <Pager
              page={submissions.data.page}
              totalPages={submissions.data.total_pages}
              total={total}
              onPageChange={setPage}
              itemNoun="attempts"
            />
          ) : null}
        </>
      )}
    </div>
  );
}

function Heading() {
  return (
    <div className="flex flex-col gap-1">
      <h1 className="text-2xl font-semibold tracking-tight">Submissions</h1>
      <p className="text-muted-foreground text-sm">
        What your students wrote, what the marker detected, and what it did not.
      </p>
    </div>
  );
}

function QueueSkeleton() {
  return (
    <div className="flex flex-col gap-3" aria-busy>
      <span className="sr-only" role="status">
        Loading submissions
      </span>
      <Skeleton className="h-9 w-40" />
      {[0, 1, 2, 3, 4].map((index) => (
        <Skeleton key={index} className="h-16 rounded-lg" />
      ))}
    </div>
  );
}
