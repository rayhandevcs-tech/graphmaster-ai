import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

/**
 * A question, its answer, and what the answer means.
 *
 * Every analytics section is one of these, and the shape is the point. A chart
 * titled "Average score" displays a number; a card titled "Are scores
 * improving?" answers something a teacher actually asked, and is visibly
 * incomplete until the interpretation slot is filled. That is what stops the
 * contract eroding by the fourth screen.
 *
 * `interpretation` is required and is never an empty string. Where the data
 * cannot support a claim, the sentence says so — `lib/insights/narrate.ts`
 * returns "Not enough marked work yet to show a direction" rather than
 * nothing, because an absent interpretation is itself a finding.
 *
 * Grids of these use `items-start` rather than the default stretch. A card
 * whose answer is one sentence, sat beside one holding a list of eight, would
 * otherwise be a sentence and six hundred pixels of nothing — the emptier the
 * finding, the larger the hole. Tops align; bottoms fall where the content
 * ends.
 */
export function InsightCard({
  question,
  interpretation,
  children,
  action,
  className,
}: {
  /** Phrased as the question a teacher came with, not as a column heading. */
  question: string;
  /** Derived from the data, never written by hand. */
  interpretation: string;
  /** The answer: a figure, a chart, a bar, a list. */
  children: React.ReactNode;
  /** An optional link onward, to where something can be done about it. */
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <Card className={cn("flex flex-col gap-4 p-6", className)}>
      <h3 className="text-base font-semibold tracking-tight text-balance">{question}</h3>

      <div className="flex flex-1 flex-col justify-center gap-3">{children}</div>

      <div className="mt-auto flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <p className="text-muted-foreground max-w-prose text-sm text-pretty">{interpretation}</p>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
    </Card>
  );
}
