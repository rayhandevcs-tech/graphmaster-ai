/**
 * The teacher's view of one attempt.
 *
 * Three things go wrong here quietly: an unmarked attempt rendered as a zero,
 * two annotation spans drawn on top of each other until the answer is one long
 * highlight, and a missing analyzer reported as a clean bill of health.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AnnotatedAnswer, split } from "@/components/submissions/annotated-answer";
import { IssueList } from "@/components/submissions/issue-list";
import { StatusChip } from "@/components/submissions/status-chip";
import { QueueCard } from "@/components/submissions/queue-row";
import type { AssessmentIssueOut, SubmissionSummary } from "@/types/api";

const issue = (overrides: Partial<AssessmentIssueOut> = {}): AssessmentIssueOut => ({
  category: "spelling",
  subtype: "misspelling",
  severity: "error",
  original_text: "perid",
  suggested_text: "period",
  explanation: "This looks like a misspelling of “period”.",
  start_index: 10,
  end_index: 15,
  confidence: 0.92,
  analyzer: "spelling",
  ...overrides,
});

describe("marking findings in the answer", () => {
  it("marks only the span the finding is about", () => {
    const segments = split("The rain perid rose", [issue({ start_index: 9, end_index: 14 })]);

    expect(segments.map((segment) => segment.text)).toEqual(["The rain ", "perid", " rose"]);
    expect(segments[1]?.issue?.subtype).toBe("misspelling");
  });

  it("drops a span that overlaps one already drawn", () => {
    // A misspelled target term is both a spelling issue and a vocabulary hit;
    // nested marks read as one long highlight rather than two findings.
    const segments = split("The rain perid rose", [
      issue({ start_index: 9, end_index: 14 }),
      issue({ start_index: 11, end_index: 18, subtype: "second" }),
    ]);

    expect(segments.filter((segment) => segment.issue !== null)).toHaveLength(1);
  });

  it("ignores a span that runs past the end of the answer", () => {
    const segments = split("Short", [issue({ start_index: 2, end_index: 99 })]);

    expect(segments.map((segment) => segment.text).join("")).toBe("Short");
  });

  it("leaves the answer intact when there is nothing to mark", () => {
    render(<AnnotatedAnswer text="The rainfall rose steadily." issues={[]} />);

    expect(screen.getByText("The rainfall rose steadily.")).toBeInTheDocument();
  });
});

describe("the findings list", () => {
  it("quotes the words and what to write instead", () => {
    render(<IssueList issues={[issue()]} />);

    expect(screen.getByText("perid")).toBeInTheDocument();
    expect(screen.getByText("period")).toBeInTheDocument();
    expect(screen.getByText(/looks like a misspelling/)).toBeInTheDocument();
  });

  it("calls a preference a suggestion, not a mistake", () => {
    render(<IssueList issues={[issue({ severity: "info", suggested_text: null })]} />);

    expect(screen.getByText("Suggestion")).toBeInTheDocument();
  });

  it("says nothing was flagged rather than showing an empty list", () => {
    render(<IssueList issues={[]} />);

    expect(screen.getByText(/found nothing to flag/i)).toBeInTheDocument();
  });
});

describe("the queue", () => {
  const summary = (overrides: Partial<SubmissionSummary> = {}): SubmissionSummary => ({
    id: "00000000-0000-0000-0000-000000000001",
    graph_id: "00000000-0000-0000-0000-0000000000aa",
    graph_title: "Rainfall by month",
    graph_type: "line",
    user_id: "00000000-0000-0000-0000-0000000000bb",
    student_name: "Priya Nair",
    input_method: "handwriting",
    status: "scored",
    word_count: 148,
    final_score: 41,
    vocabulary_percentage: 33,
    reward_tier: "hammer",
    submitted_at: "2026-08-24T09:00:00Z",
    scored_at: "2026-08-24T09:04:00Z",
    ...overrides,
  });

  it("shows an unmarked attempt as unmarked, not as zero", () => {
    render(
      <ul>
        <QueueCard summary={summary({ status: "failed", final_score: null, scored_at: null })} />
      </ul>,
    );

    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.getByText("not marked")).toBeInTheDocument();
    expect(screen.queryByText("0%")).not.toBeInTheDocument();
  });

  it("keeps showing handwriting after recognition failed", () => {
    // `input_method` never flips: the record is that handwriting was attempted
    // and did not read, even once the student typed the answer instead.
    render(
      <ul>
        <QueueCard summary={summary({ status: "failed", final_score: null })} />
      </ul>,
    );

    expect(screen.getByText("Handwritten")).toBeInTheDocument();
    expect(screen.getByText("Not recognised")).toBeInTheDocument();
  });

  it("never says the student failed", () => {
    render(<StatusChip status="failed" />);

    const label = screen.getByText(/not recognised/i).textContent ?? "";
    expect(label.toLowerCase()).not.toContain("fail");
  });
});
