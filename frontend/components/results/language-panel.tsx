"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2 } from "lucide-react";

import { AnnotatedAnswer } from "@/components/submissions/annotated-answer";
import { IssueList } from "@/components/submissions/issue-list";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, assessmentApi, queryKeys } from "@/lib/api";
import type { AssessmentIssueOut, AssessmentResponse } from "@/types/api";

/**
 * Grammar and sentence feedback, for the student who wrote it.
 *
 * The engine has produced this since sprint 19 and defaults these analyzers to
 * the student audience, but nothing had ever rendered it outside the teacher's
 * review screen. The filtering, the confidence floor and the per-category caps
 * were all already in place; what was missing was the page.
 *
 * **It cannot move the score, and it says so first.** Grammar is diagnostic:
 * a student with fifteen slips and a student with none get the same
 * `final_score` for the same vocabulary and the same writing quality, the same
 * XP and the same place on the leaderboard. That is asserted in
 * `tests/unit/test_assessment_isolation.py` rather than left to intention. The
 * sentence is at the top rather than in a footnote because a student who
 * thinks a correction cost them marks reads the list as a punishment and
 * stops reading it.
 *
 * **Corrections before notes.** An issue with a `suggested_text` tells a
 * student exactly what to write instead; one without it describes something to
 * look at. Interleaving them buries the actionable half. Within each group the
 * server's order is kept — it is by position in the answer, which is the order
 * the student will reread their own writing in.
 *
 * **What it does not do.** No count of mistakes as a headline figure, no
 * grade, no comparison with anyone else. The writing-consistency analyzer
 * never reaches this component at all: the server refuses to promote it to a
 * student audience whatever the environment says, which is the right place for
 * that rule to live.
 */
export function LanguagePanel({ submissionId, answer }: { submissionId: string; answer: string }) {
  const assessment = useQuery({
    queryKey: queryKeys.assessment(submissionId),
    queryFn: () => assessmentApi.submission(submissionId),
    // A submission marked before the engine existed has no assessment and
    // never will. Retrying a 404 four times only delays the honest message.
    retry: (count, error) => !(error instanceof ApiError && error.status === 404) && count < 2,
  });

  if (assessment.isPending) return <LanguageLoading />;
  if (assessment.isError) {
    // 404 is the ordinary case, not a failure: this attempt predates the
    // language check. Anything else is a real fault and says so plainly
    // rather than pretending the answer was clean.
    const missing = assessment.error instanceof ApiError && assessment.error.status === 404;
    return <LanguageUnavailable missing={missing} />;
  }

  return <LanguageFeedback assessment={assessment.data} answer={answer} />;
}

/**
 * The three states below are separate exports on purpose.
 *
 * Every interesting question about this screen is about wording — does it
 * promise the score is untouched, does it claim a clean answer that was never
 * fully checked, does it present an old attempt as a failure — and none of
 * them is a question about fetching. Split this way they are asserted against
 * props rather than against a query whose rejection the test runner reports as
 * an unhandled error before the component has rendered anything.
 */
function LanguageLoading() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Grammar and sentences</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <Skeleton className="h-4 w-2/3" />
        <Skeleton className="h-24 w-full" />
      </CardContent>
    </Card>
  );
}

export function LanguageUnavailable({ missing }: { missing: boolean }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Grammar and sentences</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-muted-foreground text-sm text-pretty">
          {missing
            ? "This attempt was marked before the language check was available, so there is nothing to show for it. Your next one will have it."
            : "The language check could not be loaded just now. Your score and XP are unaffected — try reloading the page."}
        </p>
      </CardContent>
    </Card>
  );
}

export function LanguageFeedback({
  assessment,
  answer,
}: {
  assessment: AssessmentResponse;
  answer: string;
}) {
  const { status, issues = [], suppressed_count: suppressed } = assessment;
  const corrections = issues.filter((issue) => issue.suggested_text);
  const notes = issues.filter((issue) => !issue.suggested_text);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Grammar and sentences</CardTitle>
      </CardHeader>

      <CardContent className="flex flex-col gap-5">
        <p className="text-muted-foreground text-sm text-pretty">
          These notes are here to help you write the next one.{" "}
          <strong>They do not affect your score, your XP or your place on the leaderboard</strong> —
          those come from the vocabulary you used and how the writing is put together.
        </p>

        {status === "pending" ? (
          <Alert variant="info">
            <AlertDescription>
              The language check is still running for this answer. Come back in a moment.
            </AlertDescription>
          </Alert>
        ) : null}

        {status === "partial" ? (
          // Never claim a clean answer that was not fully checked.
          <Alert variant="info">
            <AlertDescription>
              One of the language checks could not finish on this answer, so this list may be
              incomplete.
            </AlertDescription>
          </Alert>
        ) : null}

        {issues.length === 0 ? (
          <div className="text-success flex items-start gap-2.5 text-sm">
            <CheckCircle2 className="mt-0.5 size-5 shrink-0" aria-hidden />
            <p className="text-pretty">
              <span className="font-medium">Nothing flagged in this one.</span>{" "}
              <span className="text-muted-foreground">
                The check looks at spelling, grammar and sentence structure — it does not judge
                whether you described the graph well. That part is in the feedback above.
              </span>
            </p>
          </div>
        ) : (
          <>
            <div>
              <h3 className="mb-2 text-sm font-medium">Where they are</h3>
              <AnnotatedAnswer text={answer} issues={issues} />
            </div>

            {corrections.length > 0 ? (
              <Group
                title="Worth correcting"
                caption="Each of these has a suggested replacement."
                issues={corrections}
              />
            ) : null}

            {notes.length > 0 ? (
              <Group
                title="Worth a second look"
                caption="No single right answer here — read the sentence again and decide."
                issues={notes}
              />
            ) : null}
          </>
        )}

        {suppressed > 0 ? (
          // Counted rather than hidden. A student told nothing was found, when
          // something was found and held back, has been misled.
          <p className="text-muted-foreground text-xs text-pretty">
            {suppressed} further {suppressed === 1 ? "possibility was" : "possibilities were"} found
            but not shown, because the check was not confident enough about{" "}
            {suppressed === 1 ? "it" : "them"}.
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

function Group({
  title,
  caption,
  issues,
}: {
  title: string;
  caption: string;
  issues: readonly AssessmentIssueOut[];
}) {
  return (
    <div>
      <h3 className="text-sm font-medium">{title}</h3>
      <p className="text-muted-foreground mb-2 text-xs">{caption}</p>
      <IssueList issues={issues} />
    </div>
  );
}
