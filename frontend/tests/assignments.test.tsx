/**
 * Setting work, and reading who has done it.
 *
 * Three product rules run through these tests, and each one is a sentence the
 * interface could quietly stop saying:
 *
 * 1. A passed deadline is a fact, not a failure. Nothing here may render it
 *    as an alarm, because the platform accepts late work and never changes
 *    the mark for it.
 * 2. Counts are against enrolment, never against whoever submitted
 *    (CLAUDE.md rule 35).
 * 3. An unmarked attempt scores `—`, never `0` (rule 32).
 */

import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AssignmentCard } from "@/components/assignments/assignment-card";
import { CompletionBar } from "@/components/assignments/completion-bar";
import { DeadlineChip } from "@/components/assignments/deadline-chip";
import { describeDeadline, describeSubmissionProgress } from "@/lib/insights/deadline";
import { linksFor } from "@/lib/nav";
import type { AssignmentSummary } from "@/types/api";

const NOW = new Date("2026-09-01T09:00:00Z").getTime();
const inDays = (days: number) => new Date(NOW + days * 86_400_000).toISOString();

function assignment(overrides: Partial<AssignmentSummary> = {}): AssignmentSummary {
  return {
    id: "00000000-0000-0000-0000-0000000000a1",
    class_id: "00000000-0000-0000-0000-0000000000c1",
    graph_id: "00000000-0000-0000-0000-0000000000g1",
    title: "Week 3 · rainfall",
    instructions: null,
    due_at: inDays(3),
    is_active: true,
    created_at: new Date(NOW).toISOString(),
    graph_title: "Rainfall by month",
    graph_type: "line",
    class_name: "English 201, Section A",
    submitted_count: 12,
    enrolled_count: 30,
    ...overrides,
  };
}

describe("how a deadline reads", () => {
  it("keeps 'no deadline' apart from 'overdue'", () => {
    const none = describeDeadline(null, NOW);
    expect(none.label).toBe("No deadline");
    // Work with no deadline is open indefinitely. Wording it as anything
    // near "late" would make an untimed task look like a missed one.
    expect(none.tone).toBe("none");
  });

  it("names the weekday inside the week and a date beyond it", () => {
    // A weekday is what a teacher plans against; past a week it is a date
    // they have to look up either way. The ordering of that date is the
    // reader's locale's business, so the assertion only checks which of the
    // two forms was chosen.
    expect(describeDeadline(inDays(3), NOW).label).toBe("Due Friday");
    expect(describeDeadline(inDays(30), NOW).label).toMatch(/\d/);
    expect(describeDeadline(inDays(30), NOW).label).not.toMatch(/day$/);
  });

  it("says today and tomorrow rather than counting days", () => {
    expect(describeDeadline(new Date(NOW + 6 * 3_600_000).toISOString(), NOW).label).toBe(
      "Due today",
    );
    expect(describeDeadline(inDays(1), NOW).label).toBe("Due tomorrow");
  });

  it("never returns an alarming tone for a passed deadline", () => {
    const passed = describeDeadline(inDays(-4), NOW);
    expect(passed.label).toBe("Due date passed");
    // The whole vocabulary of tones is checked, not just this one: adding a
    // "destructive" tone later is exactly the regression this guards.
    expect(["none", "later", "soon", "passed"]).toContain(passed.tone);
    expect(passed.description).toMatch(/still accepted/i);
  });
});

describe("progress wording", () => {
  it("counts against enrolment and names who has not started", () => {
    const progress = describeSubmissionProgress(12, 30);
    expect(progress.headline).toBe("12 of 30 have submitted");
    // The twelve need nothing; the eighteen are why the page was opened.
    expect(progress.action).toBe("18 have not started");
  });

  it("says so plainly when everyone has done it", () => {
    expect(describeSubmissionProgress(30, 30).action).toBe("Everyone has submitted.");
  });

  it("does not divide by an empty class", () => {
    const progress = describeSubmissionProgress(0, 0);
    expect(progress.headline).toMatch(/nobody is enrolled/i);
    expect(progress.action).toMatch(/join code/i);
  });

  it("uses a singular verb for one outstanding student", () => {
    expect(describeSubmissionProgress(29, 30).action).toBe("1 has not started");
  });
});

describe("the completion bar", () => {
  it("announces people rather than a percentage", () => {
    render(<CompletionBar submitted={12} enrolled={30} />);
    const bar = screen.getByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "12");
    expect(bar).toHaveAttribute("aria-valuemax", "30");
    expect(bar).toHaveAccessibleName("12 of 30 students have submitted");
  });

  it("survives a class nobody has joined", () => {
    render(<CompletionBar submitted={0} enrolled={0} />);
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuemax", "0");
  });
});

describe("the deadline chip", () => {
  it("never carries its meaning in colour alone", () => {
    render(<DeadlineChip dueAt={null} />);
    expect(screen.getByText("No deadline")).toBeInTheDocument();
  });

  it("explains that a passed deadline changes nothing", () => {
    render(<DeadlineChip dueAt={new Date(Date.now() - 5 * 86_400_000).toISOString()} />);
    expect(screen.getByTitle(/score is unaffected/i)).toBeInTheDocument();
  });
});

describe("an assignment card", () => {
  it("leads with how many have done it, not with what was set", () => {
    render(<AssignmentCard assignment={assignment()} />);
    expect(screen.getByText("12 of 30 have submitted")).toBeInTheDocument();
    expect(screen.getByText(/18 have not started/)).toBeInTheDocument();
  });

  it("is one link over the whole card, not a card with links inside it", () => {
    render(<AssignmentCard assignment={assignment()} />);
    const links = screen.getAllByRole("link");
    expect(links).toHaveLength(1);
    expect(links[0]).toHaveAttribute(
      "href",
      "/teacher/assignments/00000000-0000-0000-0000-0000000000a1",
    );
    // The heading and the figure both live inside that one target.
    expect(within(links[0]!).getByText("Week 3 · rainfall")).toBeInTheDocument();
  });

  it("says when work has been closed rather than hiding it from the teacher", () => {
    render(<AssignmentCard assignment={assignment({ is_active: false })} />);
    expect(screen.getByText(/closed/i)).toBeInTheDocument();
  });

  it("does not read as complete when the counts have not arrived", () => {
    render(
      <AssignmentCard assignment={assignment({ submitted_count: null, enrolled_count: null })} />,
    );
    // A missing denominator must not render as "0 of 0 have submitted" in a
    // way that looks like a finished task.
    expect(screen.getByText(/nobody is enrolled/i)).toBeInTheDocument();
  });
});

describe("the teacher's navigation", () => {
  it("carries assignments, with a label that cannot be confused for submissions", () => {
    const labels = linksFor("teacher").map((link) => link.shortLabel ?? link.label);
    expect(labels).toContain("Assign");
    expect(labels).toContain("Work");
    // Six across a 390px bar is 65px each — above the 44px floor — and only
    // because every label is short enough not to wrap.
    expect(labels.every((label) => label.length <= 7)).toBe(true);
  });

  it("shows a student none of it", () => {
    expect(linksFor("student").map((link) => link.href)).not.toContain("/teacher/assignments");
  });
});
