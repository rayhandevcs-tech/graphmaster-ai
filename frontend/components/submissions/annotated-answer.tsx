import { cn } from "@/lib/utils";
import type { AssessmentIssueOut } from "@/types/api";

/**
 * The student's writing, with the assessment's findings marked in it.
 *
 * Deliberately a second component rather than a second layer on
 * `HighlightedAnswer`. Vocabulary highlights and issue spans overlap — a
 * misspelled target term is both — and merging two span sets means a
 * span-splitting algorithm whose failure mode is unreadable prose. Here the
 * teacher gets two views of the same text, one per question they are asking,
 * and the student's writing stays legible in both.
 *
 * Spans are sorted and clipped, and any that overlap the previous one is
 * dropped rather than drawn on top of it: `start_index`/`end_index` are a
 * half-open range into the answer, and two marks over the same characters
 * produce nested `<mark>` elements that read as one long highlight.
 *
 * The marks are visual. A screen reader gets the answer as continuous prose,
 * with the same findings as a list beneath — annotating two hundred words
 * inline makes them unreadable aloud.
 */
export function AnnotatedAnswer({
  text,
  issues,
  className,
}: {
  text: string;
  issues: readonly AssessmentIssueOut[];
  className?: string;
}) {
  const segments = split(text, issues);

  return (
    <p className={cn("text-[0.95rem] leading-8 whitespace-pre-wrap", className)}>
      {segments.map((segment, index) =>
        segment.issue ? (
          <mark
            key={index}
            className={cn(
              "rounded-sm bg-transparent px-0.5 underline decoration-2 underline-offset-4",
              segment.issue.severity === "info"
                ? "decoration-secondary text-foreground"
                : "decoration-destructive text-foreground",
            )}
          >
            {segment.text}
          </mark>
        ) : (
          <span key={index}>{segment.text}</span>
        ),
      )}
    </p>
  );
}

interface Segment {
  text: string;
  issue: AssessmentIssueOut | null;
}

export function split(text: string, issues: readonly AssessmentIssueOut[]): Segment[] {
  const ordered = [...issues]
    .filter((issue) => issue.end_index > issue.start_index && issue.start_index >= 0)
    .sort((a, b) => a.start_index - b.start_index);

  const segments: Segment[] = [];
  let cursor = 0;

  for (const issue of ordered) {
    // Past the end of the answer, or overlapping one already drawn.
    if (issue.start_index < cursor || issue.start_index >= text.length) continue;

    const end = Math.min(issue.end_index, text.length);
    if (issue.start_index > cursor) {
      segments.push({ text: text.slice(cursor, issue.start_index), issue: null });
    }
    segments.push({ text: text.slice(issue.start_index, end), issue });
    cursor = end;
  }

  if (cursor < text.length) segments.push({ text: text.slice(cursor), issue: null });
  return segments;
}
