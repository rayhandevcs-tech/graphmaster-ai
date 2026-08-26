"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Keyboard, PenLine, RotateCcw } from "lucide-react";

import { FeedbackPanel } from "./feedback-panel";
import { HighlightedAnswer } from "./highlighted-answer";
import { ModelAnswer } from "./model-answer";
import { ScoreRing } from "./score-ring";
import { VocabularyPanel } from "./vocabulary-panel";
import { WritingPanel } from "./writing-panel";
import { avatarCodeFor } from "@/components/avatars/character";
import { AwardSummary } from "@/components/gamification/award-summary";
import { LevelUpBanner } from "@/components/gamification/level-up-banner";
import { TierPanel } from "@/components/gamification/tier-panel";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ApiError, errorMessage, queryKeys, submissionsApi } from "@/lib/api";
import { useAuth } from "@/lib/auth/context";
import type { SubmissionResult } from "@/types/api";

/**
 * One marked attempt.
 *
 * The screen is assembled from two sources, and the difference matters. The
 * score, the feedback and the model answer come from the submission and are
 * there whenever the page is opened. XP, the level change and any achievements
 * exist **only** in the reply to `analyze`, so they are read from the cache
 * entry that call seeded on its way here — and on a revisit that panel is
 * simply absent. Reconstructing it would imply the award happened again, and
 * the XP ledger is append-only precisely so that is never ambiguous.
 *
 * The tier animation lives inside `TierPanel`; the character it poses is
 * resolved here, because the session is already in scope on this page and a
 * celebration that reads the session itself cannot be exercised beat by beat
 * without one.
 */
export function ResultView({ submissionId }: { submissionId: string }) {
  const queryClient = useQueryClient();
  const { user } = useAuth();

  // Frozen on first render: the cache entry is a one-shot handoff, and a later
  // invalidation elsewhere must not make the panel vanish mid-read.
  const [awards] = useState(() =>
    queryClient.getQueryData<SubmissionResult>(queryKeys.submissionAward(submissionId)),
  );

  const submission = useQuery({
    queryKey: queryKeys.submission(submissionId),
    queryFn: () => submissionsApi.get(submissionId),
    initialData: awards?.submission,
  });

  if (submission.isLoading) return <ResultSkeleton />;

  if (submission.isError) {
    const missing = submission.error instanceof ApiError && submission.error.isNotFound;
    return (
      <div className="mx-auto flex max-w-lg flex-col items-start gap-4 py-12">
        <Alert variant="destructive">
          <AlertTitle>
            {missing ? "That result is not available" : "Something went wrong"}
          </AlertTitle>
          <AlertDescription>
            {missing
              ? "This submission does not exist, or it belongs to another student."
              : errorMessage(submission.error)}
          </AlertDescription>
        </Alert>
        <BackToPractice />
      </div>
    );
  }

  const detail = submission.data;
  if (!detail) return null;

  const score = detail.score;

  if (!score) {
    return (
      <div className="mx-auto flex max-w-lg flex-col items-start gap-4 py-12">
        <Alert variant="info">
          <AlertTitle>This attempt has not been marked yet</AlertTitle>
          <AlertDescription>
            Finish writing your description and submit it for marking.
          </AlertDescription>
        </Alert>
        <Button asChild>
          <Link href={`/practice/${detail.graph_id}`}>Back to this graph</Link>
        </Button>
      </div>
    );
  }

  const reference = awards?.reference_description ?? detail.reference_description ?? null;
  const answer = detail.answer_text ?? "";
  const handwritten = detail.input_method === "handwriting";

  return (
    <div className="flex flex-col gap-8">
      {/* NFR-4.5: the outcome reaches a screen reader without the animation. */}
      <p role="status" className="sr-only">
        {`${detail.graph_title ?? "Your submission"} marked. ${score.feedback.headline}. Final score ${Math.round(score.final_score)} out of 100, with ${Math.round(score.vocabulary_percentage)}% of the target vocabulary.`}
      </p>

      <div className="flex flex-col gap-3">
        <Button asChild variant="ghost" size="sm" className="text-muted-foreground -ml-2 w-fit">
          <Link href="/practice">
            <ArrowLeft aria-hidden />
            All graphs
          </Link>
        </Button>

        <div className="flex flex-col gap-2">
          <h1 className="text-2xl font-semibold tracking-tight text-balance sm:text-3xl">
            {detail.graph_title ?? "Your result"}
          </h1>
          <p className="text-muted-foreground flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
            <span className="inline-flex items-center gap-1.5">
              {handwritten ? (
                <PenLine className="size-3.5" aria-hidden />
              ) : (
                <Keyboard className="size-3.5" aria-hidden />
              )}
              {handwritten ? "Handwritten" : "Typed"}
            </span>
            {detail.scored_at ? <span>Marked {formatWhen(detail.scored_at)}</span> : null}
            <span className="tabular-nums">{detail.word_count.toLocaleString()} words</span>
          </p>
        </div>
      </div>

      {awards?.gamification?.leveled_up ? (
        // The two level fields are optional on the wire, and a banner that
        // reads "level undefined" is worse than no banner; the fallbacks make
        // it degrade to "you have reached level 1" rather than to a crash.
        <LevelUpBanner
          from={awards.gamification.level_before ?? 1}
          to={awards.gamification.level_after ?? 1}
        />
      ) : null}

      <section className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-muted-foreground text-xs font-medium tracking-wide uppercase">
              Final score
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col items-center gap-5 pb-6">
            <ScoreRing
              value={score.final_score}
              label={`Final score ${Math.round(score.final_score)} out of 100`}
            />
            <div className="grid w-full grid-cols-2 gap-3 border-t pt-4">
              <Component label="Vocabulary" value={score.vocabulary_score} />
              <Component label="Writing quality" value={score.writing_score} />
            </div>
            <p className="text-muted-foreground text-center text-xs text-pretty">
              {/* The weighting is deployment configuration and its endpoint is
                  teacher-only, so it is described rather than asserted — a
                  hardcoded "70/30" here would go stale silently if it were
                  retuned. */}
              These two are combined into the final score using the weighting your course has set.
            </p>
          </CardContent>
        </Card>

        <TierPanel
          tier={score.reward_tier}
          feedback={score.feedback}
          vocabularyPercentage={score.vocabulary_percentage}
          avatarCode={avatarCodeFor(user)}
        />

        {awards?.gamification ? (
          <AwardSummary awards={awards.gamification} />
        ) : (
          <Card className="flex items-center justify-center p-6">
            <p className="text-muted-foreground max-w-[16rem] text-center text-sm text-pretty">
              The XP for this attempt was awarded when it was marked. Your totals are on your
              dashboard.
            </p>
          </Card>
        )}
      </section>

      <FeedbackPanel feedback={score.feedback} />

      <Tabs defaultValue="vocabulary">
        <TabsList className="w-full justify-start overflow-x-auto sm:w-fit">
          <TabsTrigger value="vocabulary">Vocabulary</TabsTrigger>
          <TabsTrigger value="writing">Writing quality</TabsTrigger>
          <TabsTrigger value="answer">Your answer</TabsTrigger>
          {reference ? <TabsTrigger value="model">Model description</TabsTrigger> : null}
        </TabsList>

        <TabsContent value="vocabulary">
          <VocabularyPanel score={score} />
        </TabsContent>

        <TabsContent value="writing">
          <WritingPanel breakdown={score.writing_breakdown} />
        </TabsContent>

        <TabsContent value="answer">
          <Card>
            <CardHeader>
              <CardTitle>Your answer</CardTitle>
            </CardHeader>
            <CardContent>
              <HighlightedAnswer text={answer} terms={score.detected_terms} />
            </CardContent>
          </Card>
        </TabsContent>

        {reference ? (
          <TabsContent value="model">
            <ModelAnswer text={reference} />
          </TabsContent>
        ) : null}
      </Tabs>

      <div className="flex flex-wrap gap-3 border-t pt-6">
        <Button asChild size="lg">
          <Link href={`/practice/${detail.graph_id}`}>
            <RotateCcw aria-hidden />
            Practise this graph again
          </Link>
        </Button>
        <Button asChild variant="outline" size="lg">
          <Link href="/practice">Choose another graph</Link>
        </Button>
      </div>
    </div>
  );
}

function Component({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex flex-col items-center gap-0.5">
      <span className="text-lg font-semibold tabular-nums">{Math.round(value)}</span>
      <span className="text-muted-foreground text-center text-xs">{label}</span>
    </div>
  );
}

function BackToPractice() {
  return (
    <Button asChild variant="outline">
      <Link href="/practice">
        <ArrowLeft aria-hidden />
        Back to the graph library
      </Link>
    </Button>
  );
}

/** "today at 14:05" reads better than a full timestamp on a screen just reached. */
function formatWhen(iso: string): string {
  const when = new Date(iso);
  if (Number.isNaN(when.getTime())) return "";

  const time = when.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  const isToday = new Date().toDateString() === when.toDateString();

  return isToday
    ? `today at ${time}`
    : `${when.toLocaleDateString(undefined, { day: "numeric", month: "short" })} at ${time}`;
}

function ResultSkeleton() {
  return (
    <div className="flex flex-col gap-8" aria-busy>
      <Skeleton className="h-9 w-2/3 max-w-md" />
      <div className="grid gap-4 lg:grid-cols-3">
        <Skeleton className="h-72 rounded-xl" />
        <Skeleton className="h-72 rounded-xl" />
        <Skeleton className="h-72 rounded-xl" />
      </div>
      <Skeleton className="h-56 rounded-xl" />
      <Skeleton className="h-80 rounded-xl" />
    </div>
  );
}
