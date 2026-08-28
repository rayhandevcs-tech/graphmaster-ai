/**
 * Grammar feedback, as a student reads it.
 *
 * The engine has produced this since sprint 19; only the teacher's screen ever
 * rendered it. The risks in showing it to the person who wrote the answer are
 * different from the risks in showing it to their teacher, and these are the
 * ones worth a test: implying the corrections cost marks, reporting a clean
 * answer that was never fully checked, and presenting an attempt that predates
 * the engine as a failure.
 *
 * These render the presentational halves directly rather than driving the
 * query. Every question here is about wording, none of them is about fetching,
 * and a rejected query reaches the runner as an unhandled error before the
 * component has rendered anything to assert on.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LanguageFeedback, LanguageUnavailable } from "@/components/results/language-panel";
import type { AssessmentIssueOut, AssessmentResponse } from "@/types/api";

const ANSWER = "The chart show a rise in rainfall over the perid.";

const issue = (overrides: Partial<AssessmentIssueOut> = {}): AssessmentIssueOut =>
  ({
    category: "spelling",
    subtype: "misspelling",
    severity: "error",
    original_text: "perid",
    suggested_text: "period",
    explanation: "This looks like a misspelling of \u201cperiod\u201d.",
    start_index: 43,
    end_index: 48,
    confidence: 0.92,
    analyzer: "spelling",
    ...overrides,
  }) as AssessmentIssueOut;

const response = (overrides: Partial<AssessmentResponse> = {}): AssessmentResponse =>
  ({
    submission_id: "00000000-0000-0000-0000-00000000000a",
    assessment_version: "1.0.0",
    status: "complete",
    issue_count: 0,
    error_count: 0,
    suppressed_count: 0,
    issues: [],
    assessed_at: "2026-08-28T08:00:00Z",
    ...overrides,
  }) as AssessmentResponse;

const show = (overrides: Partial<AssessmentResponse> = {}) =>
  render(<LanguageFeedback assessment={response(overrides)} answer={ANSWER} />);

describe("what the panel promises", () => {
  it("says the corrections cannot move the score", () => {
    // A student who thinks a correction cost them marks reads the list as a
    // punishment and stops reading it. Grammar is diagnostic — the same score,
    // the same XP, the same place on the board.
    show({ issues: [issue()], issue_count: 1, error_count: 1 });
    expect(screen.getByText(/do not affect your score/i)).toBeInTheDocument();
  });

  it("puts the corrections before the things to think about", () => {
    // An issue with a replacement tells a student what to write instead; one
    // without describes something to look at. Interleaving buries the
    // actionable half.
    show({
      issue_count: 2,
      error_count: 1,
      issues: [
        issue({ subtype: "long_sentence", suggested_text: null, severity: "info" }),
        issue(),
      ],
    });

    const titles = screen
      .getAllByRole("heading", { level: 3 })
      .map((heading) => heading.textContent);
    expect(titles.indexOf("Worth correcting")).toBeLessThan(titles.indexOf("Worth a second look"));
  });

  it("shows a group only when it has something in it", () => {
    show({ issues: [issue()], issue_count: 1, error_count: 1 });
    expect(screen.queryByText("Worth a second look")).not.toBeInTheDocument();
  });
});

describe("what it must not claim", () => {
  it("does not report a clean answer when a check did not finish", () => {
    show({ status: "partial" });
    expect(screen.getByText(/could not finish/i)).toBeInTheDocument();
  });

  it("says the check is still running rather than that it found nothing", () => {
    show({ status: "pending" });
    expect(screen.getByText(/still running/i)).toBeInTheDocument();
  });

  it("discloses findings held back below the confidence floor", () => {
    // "Nothing flagged" while something was found and withheld is a lie by
    // omission, and the count is already in the payload.
    show({ suppressed_count: 3 });
    expect(screen.getByText(/3 further possibilities were found/i)).toBeInTheDocument();
  });

  it("says nothing was flagged when nothing was", () => {
    show();
    expect(screen.getByText(/Nothing flagged in this one/i)).toBeInTheDocument();
  });

  it("does not say it once there is something to show", () => {
    // A separate test rather than a second `show()` in the one above:
    // cleanup runs per test, so the first render is still mounted and a
    // negative assertion would match its text.
    show({ issues: [issue()], issue_count: 1, error_count: 1 });
    expect(screen.queryByText(/Nothing flagged in this one/i)).not.toBeInTheDocument();
  });
});

describe("an attempt with no assessment", () => {
  it("explains it rather than reporting a failure", () => {
    // A submission marked before the engine existed 404s, and there is no
    // backfill. That is an ordinary fact about an old attempt, not an error
    // the student should be asked to do anything about.
    render(<LanguageUnavailable missing />);
    expect(screen.getByText(/marked before the language check/i)).toBeInTheDocument();
    expect(screen.queryByText(/try reloading/i)).not.toBeInTheDocument();
  });

  it("distinguishes a real failure, and says the score is untouched", () => {
    render(<LanguageUnavailable missing={false} />);
    expect(screen.getByText(/score and XP are unaffected/i)).toBeInTheDocument();
  });
});
