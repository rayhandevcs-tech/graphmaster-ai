"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Keyboard, PenLine } from "lucide-react";

import { AnnotatedAnswer } from "./annotated-answer";
import { IssueList } from "./issue-list";
import { StatusChip } from "./status-chip";
import { HighlightedAnswer } from "@/components/results/highlighted-answer";
import { ModelAnswer } from "@/components/results/model-answer";
import { ScoreRing } from "@/components/results/score-ring";
import { VocabularyPanel } from "@/components/results/vocabulary-panel";
import { WritingPanel } from "@/components/results/writing-panel";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ApiError, assessmentApi, errorMessage, queryKeys, submissionsApi } from "@/lib/api";
import { formatCount, formatPercent, formatWhen } from "@/lib/format";
import type { UUID } from "@/types/api";

/**
 * One attempt, read by the person who set it.
 *
 * The teacher's view of a submission is not the student's with more numbers on
 * it. A student opens their result to find out how they did; a teacher opens
 * it to find out what to teach — so the assessment's findings lead, and the
 * score summary is a strip rather than the centrepiece the reward screen makes
 * of it. No tier animation plays here, and no tier is shown: this is not that
 * student's moment.
 *
 * The assessment is loaded separately and its absence is a normal state, not
 * an error. Submissions marked before the engine existed carry none and there
 * is no backfill, so a 404 from that endpoint is reported as "not assessed"
 * rather than as a failure.
 */
export function SubmissionReview({ submissionId }: { submissionId: UUID }) {
  const submission = useQuery({
    queryKey: queryKeys.submission(submissionId),
    queryFn: () => submissionsApi.get(submissionId),
  });

  const assessment = useQuery({
    queryKey: queryKeys.assessment(submissionId),
    queryFn: () => assessmentApi.submission(submissionId),
    enabled: submission.data?.status === "scored",
    retry: false,
  });

  if (submission.isPending) return <ReviewSkeleton />;

  if (submission.isError) {
    const missing = submission.error instanceof ApiError && submission.error.isNotFound;
    return (
      <div className="flex max-w-lg flex-col items-start gap-4 py-8">
        <Alert variant="destructive">
          <AlertTitle>{missing ? "No such submission" : "Something went wrong"}</AlertTitle>
          <AlertDescription>
            {missing
              ? "This attempt does not exist, or it belongs to a class you do not teach."
              : errorMessage(submission.error)}
          </AlertDescription>
        </Alert>
        <BackLink />
      </div>
    );
  }

  const detail = submission.data;
  const score = detail.score;
  const answer = detail.answer_text ?? "";
  const handwritten = detail.input_method === "handwriting";
  const issues = assessment.data?.issues ?? [];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3">
        <BackLink />
        <div className="flex flex-col gap-2">
          <h1 className="text-2xl font-semibold tracking-tight text-balance">
            {detail.student_name ?? "Unknown student"}
          </h1>
          <p className="text-muted-foreground flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
            <span>{detail.graph_title ?? "Untitled graph"}</span>
            <StatusChip status={detail.status} />
            <span className="inline-flex items-center gap-1.5">
              {handwritten ? (
                <PenLine className="size-3.5" aria-hidden />
              ) : (
                <Keyboard className="size-3.5" aria-hidden />
              )}
              {handwritten ? "Handwritten" : "Typed"}
            </span>
            <span>{formatWhen(detail.scored_at ?? detail.submitted_at)}</span>
            <span className="tabular-nums">{formatCount(detail.word_count)} words</span>
          </p>
        </div>
      </div>

      {detail.status === "failed" ? (
        <Alert variant="info">
          <AlertTitle>The handwriting could not be read</AlertTitle>
          <AlertDescription>
            {detail.error_message ??
              "Recognition failed on the photograph. The student can still type this attempt — the record keeps that handwriting was what they tried."}
          </AlertDescription>
        </Alert>
      ) : null}

      {score ? (
        <Card>
          <CardContent className="flex flex-wrap items-center gap-6 p-6">
            <ScoreRing
              value={score.final_score}
              label={`Final score ${Math.round(score.final_score)} out of 100`}
            />
            <dl className="grid flex-1 grid-cols-2 gap-x-8 gap-y-3 sm:grid-cols-3">
              <Figure label="Vocabulary" value={formatPercent(score.vocabulary_score, 0)} />
              <Figure label="Writing quality" value={formatPercent(score.writing_score, 0)} />
              <Figure label="Target terms" value={formatPercent(score.vocabulary_percentage, 0)} />
            </dl>
          </CardContent>
        </Card>
      ) : null}

      <Tabs defaultValue="findings">
        <TabsList className="w-full justify-start overflow-x-auto sm:w-fit">
          <TabsTrigger value="findings">
            Findings{issues.length > 0 ? ` (${issues.length})` : ""}
          </TabsTrigger>
          <TabsTrigger value="vocabulary">Vocabulary</TabsTrigger>
          {score ? <TabsTrigger value="writing">Writing quality</TabsTrigger> : null}
          {detail.reference_description ? (
            <TabsTrigger value="model">Model description</TabsTrigger>
          ) : null}
        </TabsList>

        <TabsContent value="findings">
          <Card>
            <CardHeader>
              <CardTitle>What the assessment found</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-6">
              {assessment.isError ? (
                <Alert variant="info">
                  <AlertTitle>This attempt carries no assessment</AlertTitle>
                  <AlertDescription>
                    It was marked before the assessment engine ran on this server, and there is no
                    backfill. The score and vocabulary detection above are unaffected.
                  </AlertDescription>
                </Alert>
              ) : null}

              <AnnotatedAnswer text={answer} issues={issues} />

              {assessment.data ? (
                <div className="flex flex-col gap-3 border-t pt-4">
                  <p className="text-muted-foreground text-xs text-pretty">
                    {assessment.data.suppressed_count > 0
                      ? `${assessment.data.suppressed_count} further ${
                          assessment.data.suppressed_count === 1 ? "finding was" : "findings were"
                        } below this server's confidence floor and are counted but not shown.`
                      : "Every finding above this server's confidence floor is shown."}
                  </p>
                  <IssueList issues={issues} />
                  <AnalyzerNotes analyzers={assessment.data.analyzers ?? {}} />
                </div>
              ) : null}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="vocabulary">
          <Card>
            <CardHeader>
              <CardTitle>Target vocabulary in this answer</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-6">
              <HighlightedAnswer text={answer} terms={score?.detected_terms ?? []} />
              {score ? <VocabularyPanel score={score} /> : null}
            </CardContent>
          </Card>
        </TabsContent>

        {score ? (
          <TabsContent value="writing">
            <WritingPanel breakdown={score.writing_breakdown} />
          </TabsContent>
        ) : null}

        {detail.reference_description ? (
          <TabsContent value="model">
            <ModelAnswer text={detail.reference_description} />
          </TabsContent>
        ) : null}
      </Tabs>
    </div>
  );
}

function Figure({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-muted-foreground text-xs font-medium tracking-wide uppercase">{label}</dt>
      <dd className="text-lg font-semibold tabular-nums">{value}</dd>
    </div>
  );
}

/**
 * Which analyzers ran, and which could not.
 *
 * `unavailable` and `failed` are deliberately different in the payload: the
 * first is a deployment fact — no grammar engine is installed — and the second
 * is a fault. Collapsing them into "no results" would let a missing engine
 * look like a clean bill of health for a whole class.
 */
function AnalyzerNotes({
  analyzers,
}: {
  analyzers: Record<string, { status: string; issue_count?: number }>;
}) {
  const notable = Object.entries(analyzers).filter(([, value]) => value.status !== "ok");
  if (notable.length === 0) return null;

  return (
    <ul className="text-muted-foreground flex flex-col gap-1 text-xs">
      {notable.map(([name, value]) => (
        <li key={name}>
          <span className="font-medium capitalize">{name.replace(/[_-]+/g, " ")}</span>:{" "}
          {value.status === "unavailable"
            ? "not installed on this server, so nothing was checked"
            : value.status === "failed"
              ? "failed on this submission; the rest of the assessment still ran"
              : "skipped"}
        </li>
      ))}
    </ul>
  );
}

function BackLink() {
  return (
    <Button asChild variant="ghost" size="sm" className="text-muted-foreground -ml-2 w-fit">
      <Link href="/teacher/submissions">
        <ArrowLeft aria-hidden />
        All submissions
      </Link>
    </Button>
  );
}

function ReviewSkeleton() {
  return (
    <div className="flex flex-col gap-6" aria-busy>
      <span className="sr-only" role="status">
        Loading this submission
      </span>
      <Skeleton className="h-9 w-64" />
      <Skeleton className="h-32 rounded-xl" />
      <Skeleton className="h-96 rounded-xl" />
    </div>
  );
}
