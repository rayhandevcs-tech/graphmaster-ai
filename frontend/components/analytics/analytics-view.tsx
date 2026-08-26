"use client";

import { useQuery } from "@tanstack/react-query";
import { RefreshCw, Users } from "lucide-react";

import { ExportMenu } from "./export-menu";
import { CreateClassDialog } from "@/components/teaching/create-class-dialog";
import { ScopeBar } from "@/components/teaching/scope-bar";
import { ChartPanel } from "@/components/charts/chart-panel";
import { ClassTierSpread } from "@/components/gamification/class-tier-spread";
import { EmptyState } from "@/components/layout/empty-state";
import { FindingList } from "@/components/insight/finding-list";
import { InsightCard } from "@/components/insight/insight-card";
import { Metric } from "@/components/insight/metric";
import { Reveal } from "@/components/motion/reveal";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { analyticsApi, errorMessage, queryKeys } from "@/lib/api";
import { classTrendSeries } from "@/lib/charts/series";
import { formatCount } from "@/lib/format";
import { useClassScope } from "@/lib/hooks/use-class-scope";
import {
  describeParticipation,
  describeTierSpread,
  describeVocabularyReach,
  readTrend,
} from "@/lib/insights/narrate";
import { chooseGranularity } from "@/lib/charts/series";

/**
 * Analytics as a set of answers, not a set of charts.
 *
 * Every card here states a question a teacher came with, answers it, and says
 * what the answer means — and the meaning is derived in
 * `lib/insights/narrate.ts` rather than written, so it cannot congratulate a
 * class on a rise that did not happen.
 *
 * The order is the argument: are they practising, are they improving, which
 * words are landing, which words are not, and where the marks are falling.
 * Participation comes first because every other figure on the screen is
 * conditional on it — an average over the third of the class who bothered is a
 * different number from an average over the class.
 *
 * **Computed live** (CLAUDE.md rule 36). `analytics_snapshots` is unused on
 * purpose: a cached figure is stale exactly when a teacher wants it, in the
 * minutes after a lesson.
 */
export function AnalyticsView() {
  const scope = useClassScope();

  const report = useQuery({
    queryKey: queryKeys.analyticsClass(scope.classId ?? "none", scope.dates),
    queryFn: () => analyticsApi.class(scope.classId as string, scope.dates),
    enabled: Boolean(scope.classId),
    placeholderData: (previous) => previous,
  });

  const granularity =
    scope.dates.date_from && scope.dates.date_to
      ? chooseGranularity(scope.dates.date_from, scope.dates.date_to)
      : "day";

  const trends = useQuery({
    queryKey: queryKeys.analyticsTrends({ class_id: scope.classId, ...scope.dates, granularity }),
    queryFn: () =>
      analyticsApi.trends({ class_id: scope.classId as string, ...scope.dates, granularity }),
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

  if (scope.isLoading) return <AnalyticsSkeleton />;

  if (scope.isEmpty) {
    return (
      <div className="flex flex-col gap-6">
        <Heading />
        <EmptyState
          icon={Users}
          title="No classes yet"
          description="Analytics are always about a class. Create one and the figures appear as your students practise."
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
            ? `${formatCount(data.active_student_count)} of ${formatCount(
                data.enrolled_student_count,
              )} students practising, ${formatCount(data.submission_count)} marked ${
                data.submission_count === 1 ? "attempt" : "attempts"
              }.`
            : undefined
        }
        actions={<ExportMenu classId={scope.classId} dates={scope.dates} />}
      />

      {report.isError ? (
        <Alert variant="destructive">
          <AlertTitle>These figures could not be loaded</AlertTitle>
          <AlertDescription className="flex flex-col items-start gap-3">
            <span>{errorMessage(report.error)}</span>
            <Button variant="outline" size="sm" onClick={() => void report.refetch()}>
              <RefreshCw aria-hidden />
              Try again
            </Button>
          </AlertDescription>
        </Alert>
      ) : !data ? (
        <AnalyticsSkeleton />
      ) : (
        <div className={stale ? "flex flex-col gap-4 opacity-60" : "flex flex-col gap-4"}>
          <Reveal>
            <InsightCard
              question="Is the class practising?"
              interpretation={describeParticipation(data.engagement)}
            >
              <div className="flex flex-col gap-3">
                <Metric
                  label="Students with marked work"
                  value={`${formatCount(data.active_student_count)} of ${formatCount(
                    data.enrolled_student_count,
                  )}`}
                  emphasis="lg"
                />
                <Progress
                  value={data.active_student_count}
                  max={Math.max(data.enrolled_student_count, 1)}
                  label="Students practising"
                  valueText={`${data.active_student_count} of ${data.enrolled_student_count} students have marked work`}
                />
              </div>
            </InsightCard>
          </Reveal>

          <Reveal delay={0.05}>
            <ScoreTrendCard
              points={trends.data?.points ?? data.trend}
              from={scope.dates.date_from ?? null}
              to={scope.dates.date_to ?? null}
              granularity={granularity}
            />
          </Reveal>

          <div className="grid items-start gap-4 md:grid-cols-2">
            <Reveal delay={0.1}>
              <InsightCard
                question="Which words are they reaching for?"
                interpretation="Counted from the terms the marker detected, never from a re-scan of the answers — a second detector that disagreed with the first would make these figures unusable as evidence."
              >
                <FindingList
                  findings={(vocabulary.data?.most_used ?? []).slice(0, 8).map((row) => ({
                    key: row.term,
                    label: row.term,
                    value: row.uses,
                    detail: `${row.category_name} · ${row.student_count} ${
                      row.student_count === 1 ? "student" : "students"
                    }`,
                  }))}
                  valueLabel="uses"
                  emptyMessage="No target vocabulary has been detected in this period."
                />
              </InsightCard>
            </Reveal>

            <Reveal delay={0.15}>
              <InsightCard
                question="And which are they never using?"
                interpretation={
                  vocabulary.data
                    ? describeVocabularyReach(vocabulary.data)
                    : "Loading vocabulary coverage."
                }
              >
                <FindingList
                  findings={(vocabulary.data?.least_used ?? []).slice(0, 8).map((row) => ({
                    key: row.term,
                    label: row.term,
                    value: row.uses,
                    detail: row.category_name,
                  }))}
                  valueLabel="uses"
                  emptyMessage="Every curated term has been used at least once."
                />
              </InsightCard>
            </Reveal>
          </div>

          <Reveal delay={0.2}>
            <InsightCard
              question="Where are the marks landing?"
              interpretation={describeTierSpread(data.reward_tier_distribution)}
            >
              <ClassTierSpread distribution={data.reward_tier_distribution} />
              <p className="text-muted-foreground text-xs text-pretty">
                Across marked attempts, not across students. A tier is what one piece of work
                earned.
              </p>
            </InsightCard>
          </Reveal>
        </div>
      )}
    </div>
  );
}

/**
 * The trend, on a real calendar.
 *
 * The gap sentence is not decoration. `GET /analytics/trends` returns no
 * bucket at all for a period nobody submitted in, so the line breaks — and a
 * reader who assumes an unbroken calendar would read the break as a bug. It is
 * named instead.
 */
function ScoreTrendCard({
  points,
  from,
  to,
  granularity,
}: {
  points: Parameters<typeof classTrendSeries>[0];
  from: string | null;
  to: string | null;
  granularity: ReturnType<typeof chooseGranularity>;
}) {
  const series = classTrendSeries(points, { from, to, granularity });
  const reading = readTrend(points);

  const bucketNoun = granularity === "day" ? "days" : granularity === "week" ? "weeks" : "months";
  const gaps =
    series.gapCount > 0
      ? ` ${series.gapCount} ${series.gapCount === 1 ? bucketNoun.slice(0, -1) : bucketNoun} had no marked work; the line breaks there rather than drawing through it.`
      : "";

  return (
    <InsightCard question="Are scores improving?" interpretation={`${reading.sentence}${gaps}`}>
      <ChartPanel
        chartData={series.chartData}
        graphType="line"
        title="Average score and vocabulary use over time"
        height="h-[14rem] sm:h-[18rem]"
      />
    </InsightCard>
  );
}

function Heading() {
  return (
    <div className="flex flex-col gap-1">
      <h1 className="text-2xl font-semibold tracking-tight">Analytics</h1>
      <p className="text-muted-foreground text-sm">
        Computed now, from the work marked in this period. Nothing here is cached.
      </p>
    </div>
  );
}

function AnalyticsSkeleton() {
  return (
    <div className="flex flex-col gap-4" aria-busy>
      <span className="sr-only" role="status">
        Loading your analytics
      </span>
      <Skeleton className="h-9 w-40" />
      <Skeleton className="h-40 rounded-xl" />
      <Skeleton className="h-80 rounded-xl" />
      <div className="grid items-start gap-4 md:grid-cols-2">
        <Skeleton className="h-64 rounded-xl" />
        <Skeleton className="h-64 rounded-xl" />
      </div>
    </div>
  );
}
