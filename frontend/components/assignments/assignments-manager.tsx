"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ClipboardList, RefreshCw } from "lucide-react";

import { AssignmentCard } from "./assignment-card";
import { SetWorkDialog } from "./set-work-dialog";
import { EmptyState } from "@/components/layout/empty-state";
import { Pager } from "@/components/layout/pager";
import { Reveal } from "@/components/motion/reveal";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { Skeleton } from "@/components/ui/skeleton";
import { assignmentsApi, classesApi, errorMessage, queryKeys } from "@/lib/api";

const PAGE_SIZE = 12;

/**
 * Work you set, ordered by what is closest to being due.
 *
 * The ordering is the server's — soonest deadline first, undated work last —
 * because a task with no deadline is never the most urgent thing on a list.
 *
 * The section filter is a `radiogroup`: it is one choice out of a set, not a
 * row of buttons that happen to look pressed. It only appears for a teacher
 * with more than one section, since a filter with a single option is furniture.
 */
export function AssignmentsManager() {
  const [classId, setClassId] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  const classes = useQuery({
    queryKey: queryKeys.classes({ page_size: 100, is_active: true }),
    queryFn: () => classesApi.list({ page_size: 100, is_active: true }),
  });

  const params = { page, page_size: PAGE_SIZE, ...(classId ? { class_id: classId } : {}) };
  const assignments = useQuery({
    queryKey: queryKeys.assignments(params),
    queryFn: () => assignmentsApi.list(params),
    placeholderData: (previous) => previous,
  });

  const sections = classes.data?.items ?? [];
  const items = assignments.data?.items ?? [];
  const stale = assignments.isFetching && assignments.isPlaceholderData;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold tracking-tight">Work you set</h1>
          <p className="text-muted-foreground max-w-prose text-sm text-pretty">
            Show the graph in your lesson. Students describe it here, in their own words, and the
            system marks the description against the target vocabulary.
          </p>
        </div>
        <SetWorkDialog />
      </div>

      {sections.length > 1 ? (
        <div
          role="radiogroup"
          aria-label="Section"
          className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1"
        >
          <Chip
            pressed={classId === null}
            onPress={() => {
              setClassId(null);
              setPage(1);
            }}
          >
            All sections
          </Chip>
          {sections.map((section) => (
            <Chip
              key={section.id}
              pressed={classId === section.id}
              onPress={() => {
                setClassId(section.id);
                setPage(1);
              }}
              className="whitespace-nowrap"
            >
              {section.name}
            </Chip>
          ))}
        </div>
      ) : null}

      {assignments.isError ? (
        <Alert variant="destructive">
          <AlertTitle>This list could not be loaded</AlertTitle>
          <AlertDescription className="flex flex-col items-start gap-3">
            <span>{errorMessage(assignments.error)}</span>
            <Button variant="outline" size="sm" onClick={() => void assignments.refetch()}>
              <RefreshCw aria-hidden />
              Try again
            </Button>
          </AlertDescription>
        </Alert>
      ) : assignments.isPending ? (
        <ListSkeleton />
      ) : items.length === 0 ? (
        <EmptyState
          icon={ClipboardList}
          title={classId ? "Nothing set for this section" : "No work set yet"}
          description="Set a graph you have already shown in class. Your students see it on their dashboard, describe it, and you get back who has done it and who has not."
          action={<SetWorkDialog classId={classId ?? undefined} />}
        />
      ) : (
        <div className={stale ? "opacity-60 transition-opacity" : "transition-opacity"}>
          <ul className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {items.map((assignment, index) => (
              <li key={assignment.id}>
                <Reveal delay={Math.min(index, 5) * 0.04}>
                  <AssignmentCard assignment={assignment} />
                </Reveal>
              </li>
            ))}
          </ul>

          <Pager
            page={page}
            totalPages={assignments.data?.total_pages ?? 1}
            total={assignments.data?.total ?? 0}
            onPageChange={setPage}
            itemNoun="assignments"
          />
        </div>
      )}
    </div>
  );
}

function ListSkeleton() {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {Array.from({ length: 3 }).map((_, index) => (
        <Skeleton key={index} className="h-40 rounded-xl" />
      ))}
    </div>
  );
}
