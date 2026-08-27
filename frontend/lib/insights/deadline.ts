/**
 * How a due date reads, and how firmly.
 *
 * A pure function with its own tests rather than a ternary inside a card,
 * because the wording carries a product rule that is easy to lose: **a passed
 * deadline is not a failure state.** The platform never refuses work over a
 * due date and never changes a mark for lateness (sprint-22-assignments §4),
 * so "Due date passed" is a fact a teacher acts on, not an alarm — which is
 * why nothing here returns a destructive tone.
 *
 * Everything is computed against an injected `now` so the tests do not depend
 * on the day they run.
 */

export type DeadlineTone = "none" | "later" | "soon" | "passed";

export interface Deadline {
  /** What the chip says. */
  label: string;
  tone: DeadlineTone;
  /** The full sentence a screen reader gets, since the chip is an abbreviation. */
  description: string;
}

const DAY = 24 * 60 * 60 * 1000;

/** Calendar days between two instants, in the reader's own timezone. */
function daysApart(from: Date, to: Date): number {
  const a = new Date(from.getFullYear(), from.getMonth(), from.getDate());
  const b = new Date(to.getFullYear(), to.getMonth(), to.getDate());
  return Math.round((b.getTime() - a.getTime()) / DAY);
}

export function describeDeadline(
  dueAt: string | null | undefined,
  now: number = Date.now(),
): Deadline {
  if (!dueAt) {
    // Not the same thing as overdue, and the wording has to keep them apart:
    // work with no deadline is open indefinitely, not late forever.
    return {
      label: "No deadline",
      tone: "none",
      description: "This work has no deadline.",
    };
  }

  const when = new Date(dueAt);
  if (Number.isNaN(when.getTime())) {
    return { label: "No deadline", tone: "none", description: "This work has no deadline." };
  }

  const today = new Date(now);
  const days = daysApart(today, when);

  if (when.getTime() < now) {
    const dateText = formatDeadline(dueAt);
    return {
      label: days === 0 ? "Due today" : "Due date passed",
      tone: days === 0 ? "soon" : "passed",
      description:
        days === 0
          ? `Due today, ${dateText}. Work submitted after the deadline is still accepted.`
          : `The deadline passed on ${dateText}. Work is still accepted and the score is unaffected.`,
    };
  }

  if (days === 0) {
    return {
      label: "Due today",
      tone: "soon",
      description: `Due today, ${formatDeadline(dueAt)}.`,
    };
  }
  if (days === 1) {
    return {
      label: "Due tomorrow",
      tone: "soon",
      description: `Due tomorrow, ${formatDeadline(dueAt)}.`,
    };
  }
  if (days <= 6) {
    // A weekday name inside the week is what a teacher plans against; a date
    // is something they have to convert.
    const weekday = when.toLocaleDateString(undefined, { weekday: "long" });
    return {
      label: `Due ${weekday}`,
      tone: days <= 2 ? "soon" : "later",
      description: `Due on ${formatDeadline(dueAt)}.`,
    };
  }

  return {
    label: `Due ${when.toLocaleDateString(undefined, { day: "numeric", month: "short" })}`,
    tone: "later",
    description: `Due on ${formatDeadline(dueAt)}.`,
  };
}

/** "Friday 3 October", the long form used in headings and descriptions. */
export function formatDeadline(dueAt: string): string {
  const when = new Date(dueAt);
  if (Number.isNaN(when.getTime())) return dueAt;
  return when.toLocaleDateString(undefined, {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
}

/**
 * "12 of 30 have submitted" — and what to do about the rest.
 *
 * Counted against enrolment, never against whoever submitted (CLAUDE.md rule
 * 35). The second sentence names the students who have *not* started, because
 * those are the only ones the teacher can act on; the ones who have submitted
 * need nothing from this screen.
 */
export function describeSubmissionProgress(
  submitted: number,
  enrolled: number,
): { headline: string; action: string } {
  if (enrolled === 0) {
    return {
      headline: "Nobody is enrolled yet",
      action: "Share the class join code and this will start filling in.",
    };
  }
  const outstanding = enrolled - submitted;
  return {
    headline: `${submitted} of ${enrolled} have submitted`,
    action:
      outstanding === 0
        ? "Everyone has submitted."
        : `${outstanding} ${outstanding === 1 ? "has" : "have"} not started`,
  };
}
