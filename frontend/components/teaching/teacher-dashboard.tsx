"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { BarChart3, BookOpen, RefreshCw, Users } from "lucide-react";

import { AttentionPanel } from "./attention-panel";
import { CreateClassDialog } from "./create-class-dialog";
import { ScopeBar } from "./scope-bar";
import { EmptyState } from "@/components/layout/empty-state";
import { FindingList } from "@/components/insight/finding-list";
import { InsightCard } from "@/components/insight/insight-card";
import { Metric } from "@/components/insight/metric";
import { Sparkline } from "@/components/insight/sparkline";
import { Reveal } from "@/components/motion/reveal";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { analyticsApi, assessmentApi, errorMessage, queryKeys } from "@/lib/api";
import { useClassScope } from "@/lib/hooks/use-class-scope";
import { formatCount, formatPercent } from "@/lib/format";
import { describeParticipation, describeVocabularyReach, readTrend } from "@/lib/insights/narrate";
import { rangeLabel } from "@/lib/insights/scope";
import type { AnalyticsReport } from "@/types/api";

/**
 * What is happening, why it matters, and what to do next — in that order.
 *
 * The order is the design. Names first, because a teacher between lessons is
 * deciding who to talk to; the class figures sit beside them as the context
 * that explains the names, quiet and small; and the two findings underneath
 * are the ones that turn into a lesson rather than a conversation.
 *
 * Nothing here is a table. Everything a table would have carried is either a
 * tappable row that leads to that student's work, or a figure with a sentence
 * saying what it means.
 */
export function TeacherDashboard() {
  const scope = useClassScope();

  const report = useQuery({
    queryKey: queryKeys.analyticsClass(scope.classId ?? "none", scope.dates),
    queryFn: () => analyticsApi.class(scope.classId as string, scope.dates),
    enabled: Boolean(scope.classId),
    // The previous figures stay on screen while a new range loads, dimmed,
    // rather than collapsing the whole page back to skeletons on every change.
    placeholderData: (previous) => previous,
  });

  const issues = useQuery({
    queryKey: queryKeys.assessmentIssues({ class_id: scope.classId, ...scope.dates, limit: 5 }),
    queryFn: () =>
      assessmentApi.issues({ class_id: scope.classId as string, ...scope.dates, limit: 5 }),
    enabled: Boolean(scope.classId),
    placeholderData: (previous) => previous,
  });

  const vocabulary = useQuery({
    queryKey: queryKeys.analyticsVocabulary({ class_id: scope.classId, ...scope.dates }),
    queryFn: () =>
      analyticsApi.vocabularyUsage({ class_id: scope.classId as string, ...scope.dates }),
    enabled: Boolean(scope.classId),
    placeholderData: (previous) => previous,
  });

  if (scope.isLoading) return <DashboardSkeleton />;

  if (scope.isEmpty) {
    return (
      <div className="flex flex-col gap-6">
        <Heading />
        <EmptyState
          icon={Users}
          title="No classes yet"
          description="Every teaching screen is scoped to a class. Create one, and the join code it generates is what your students enrol with."
          action={<CreateClassDialog />}
        />
      </div>
    );
  }

  const data = report.data;
  const stale = report.isFetching && report.isPlaceholderData;

  return (
    <div className="flex flex-col gap-6">
      <Heading />

      <ScopeBar
        scope={scope}
        summary={
          data
            ? summarise(
                data.active_student_count,
                data.enrolled_student_count,
                data.submission_count,
              )
            : undefined
        }
      />

      {report.isError ? (
        <Alert variant="destructive">
          <AlertTitle>This class could not be loaded</AlertTitle>
          <AlertDescription className="flex flex-col items-start gap-3">
            <span>{errorMessage(report.error)}</span>
            <Button variant="outline" size="sm" onClick={() => void report.refetch()}>
              <RefreshCw aria-hidden />
              Try again
            </Button>
          </AlertDescription>
        </Alert>
      ) : !data ? (
        <DashboardSkeleton />
      ) : (
        <div className={stale ? "opacity-60 transition-opacity" : "transition-opacity"}>
          <div className="flex flex-col gap-6">
            <section className="grid items-start gap-4 lg:grid-cols-3">
              <Reveal className="lg:col-span-2">
                <AttentionPanel students={data.students ?? []} />
              </Reveal>

              <Reveal delay={0.06}>
                <ClassFigures report={data} range={rangeLabel(scope.range)} />
              </Reveal>
            </section>

            <section className="grid items-start gap-4 md:grid-cols-2">
              <Reveal delay={0.1}>
                <InsightCard
                  question="What is worth a lesson?"
                  interpretation={
                    issues.data
                      ? `Counted across ${formatCount(issues.data.assessed_count)} of ${formatCount(
                          issues.data.submission_count,
                        )} submissions — the rest were marked before the assessment engine existed.`
                      : "Loading the commonest mistakes."
                  }
                  action={
                    <Button asChild variant="ghost" size="sm">
                      <Link href="/teacher/analytics">
                        <BarChart3 aria-hidden />
                        Analytics
                      </Link>
                    </Button>
                  }
                >
                  <FindingList
                    findings={(issues.data?.entries ?? []).map((entry) => ({
                      key: entry.subtype,
                      label: readableSubtype(entry.subtype),
                      value: entry.occurrences,
                    }))}
                    valueLabel="occurrences"
                    emptyMessage="No issues have been recorded for this class in this period."
                  />
                </InsightCard>
              </Reveal>

              <Reveal delay={0.14}>
                <InsightCard
                  question="Which words is nobody using?"
                  interpretation={
                    vocabulary.data
                      ? describeVocabularyReach(vocabulary.data)
                      : "Loading vocabulary coverage."
                  }
                  action={
                    <Button asChild variant="ghost" size="sm">
                      <Link href="/teacher/vocabulary">
                        <BookOpen aria-hidden />
                        Vocabulary
                      </Link>
                    </Button>
                  }
                >
                  <FindingList
                    findings={(vocabulary.data?.least_used ?? []).slice(0, 5).map((row) => ({
                      key: row.term,
                      label: row.term,
                      value: row.uses,
                      detail: row.category_name,
                    }))}
                    valueLabel="uses"
                    emptyMessage="No target vocabulary has been curated for these graphs yet."
                  />
                </InsightCard>
              </Reveal>
            </section>
          </div>
        </div>
      )}
    </div>
  );
}

function Heading() {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">Teaching</h1>
        <p className="text-muted-foreground text-sm">
          Computed now, from the work your students have had marked.
        </p>
      </div>
      <CreateClassDialog />
    </div>
  );
}

/**
 * The class in three numbers, deliberately quiet.
 *
 * No card borders competing with the list beside it, one figure each, and a
 * sparkline instead of a chart. These answer "is this normal?" — they are not
 * the thing that greets a teacher.
 */
function ClassFigures({ report, range }: { report: AnalyticsReport; range: string }) {
  const trend = readTrend(report.trend);

  return (
    <Card className="flex flex-col gap-5 p-6">
      <h2 className="text-muted-foreground text-xs font-medium tracking-wide uppercase">{range}</h2>

      <div className="flex flex-col gap-2">
        <Metric
          label="Practising"
          value={`${Math.round(report.engagement.participation_rate)}%`}
          detail={`${formatCount(report.active_student_count)} of ${formatCount(
            report.enrolled_student_count,
          )} enrolled`}
          emphasis="lg"
        />
        {/* Beside the figure it explains rather than orphaned at the foot of
            the card, where a stretched column left it floating. */}
        <p className="text-muted-foreground text-xs text-pretty">
          {describeParticipation(report.engagement)}
        </p>
      </div>

      <div className="flex flex-col gap-2 border-t pt-4">
        <Metric
          label="Average score"
          value={report.submission_count === 0 ? "—" : formatPercent(report.average_final_score, 0)}
          emphasis="md"
        />
        <Sparkline
          values={report.trend.map((point) => point.average_final_score)}
          label={`Score trend: ${trend.sentence}`}
        />
        <p className="text-muted-foreground text-xs text-pretty">{trend.sentence}</p>
      </div>

      <div className="border-t pt-4">
        <Metric
          label="Target vocabulary"
          value={
            report.submission_count === 0
              ? "—"
              : formatPercent(report.average_vocabulary_percentage, 0)
          }
          detail="of the curated terms, per attempt"
          emphasis="md"
        />
      </div>
    </Card>
  );
}

function summarise(active: number, enrolled: number, submissions: number): string {
  return `${formatCount(active)} of ${formatCount(enrolled)} students practising, ${formatCount(
    submissions,
  )} marked ${submissions === 1 ? "attempt" : "attempts"}.`;
}

/**
 * `subject_verb_agreement` → "Subject verb agreement".
 *
 * The API groups by a stable slug on purpose, so the display wording can be
 * rewritten between releases without invalidating a year of reports. This is
 * that wording, and it stays here rather than in the payload.
 */
function readableSubtype(subtype: string): string {
  const words = subtype.replace(/[_-]+/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function DashboardSkeleton() {
  return (
    <div className="flex flex-col gap-6" aria-busy>
      <span className="sr-only" role="status">
        Loading your class
      </span>
      <Skeleton className="h-9 w-40" />
      <div className="grid gap-4 lg:grid-cols-3">
        <Skeleton className="h-96 rounded-xl lg:col-span-2" />
        <Skeleton className="h-96 rounded-xl" />
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <Skeleton className="h-56 rounded-xl" />
        <Skeleton className="h-56 rounded-xl" />
      </div>
    </div>
  );
}
