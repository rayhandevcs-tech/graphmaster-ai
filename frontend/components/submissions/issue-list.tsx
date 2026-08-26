import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { AssessmentIssueOut } from "@/types/api";

/**
 * The findings, quoted with the words they are about.
 *
 * This is the representation that actually teaches: the fragment as written,
 * what to write instead where there is a single right answer, and why. It is
 * also the accessible form of the marks in the text above — a screen-reader
 * user reads the answer as prose and the findings as a list.
 *
 * `info` is a preference, not a mistake, and is worded and coloured as one.
 * A style note presented with the same weight as a spelling error teaches a
 * student that the two are equally wrong.
 */
export function IssueList({
  issues,
  className,
}: {
  issues: readonly AssessmentIssueOut[];
  className?: string;
}) {
  if (issues.length === 0) {
    return (
      <p className={cn("text-muted-foreground text-sm", className)}>
        The assessment found nothing to flag in this answer.
      </p>
    );
  }

  return (
    <ul className={cn("flex flex-col gap-2", className)}>
      {issues.map((issue, index) => (
        <li key={`${issue.subtype}-${issue.start_index}-${index}`}>
          <Card className="flex flex-col gap-1.5 p-4 shadow-none">
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={cn(
                  "rounded-full px-2 py-0.5 text-xs font-medium",
                  issue.severity === "info"
                    ? "bg-secondary/15 text-secondary"
                    : "bg-destructive/15 text-destructive",
                )}
              >
                {issue.severity === "info" ? "Suggestion" : readable(issue.category)}
              </span>
              <span className="text-muted-foreground text-xs">{readable(issue.subtype)}</span>
            </div>

            <p className="text-sm">
              <q className="font-medium">{issue.original_text}</q>
              {issue.suggested_text ? (
                <>
                  {" → "}
                  <q className="text-success font-medium">{issue.suggested_text}</q>
                </>
              ) : null}
            </p>

            <p className="text-muted-foreground text-sm text-pretty">{issue.explanation}</p>
          </Card>
        </li>
      ))}
    </ul>
  );
}

/** `subject_verb_agreement` → "Subject verb agreement". */
function readable(slug: string): string {
  const words = slug.replace(/[_-]+/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}
