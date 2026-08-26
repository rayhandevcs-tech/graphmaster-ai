import { Target } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { targetTermsLabel } from "./graph-meta";

/**
 * The question being answered.
 *
 * Kept beside the chart rather than above the page title, because it is the
 * thing a student re-reads while writing — including the word-count
 * instruction, which lives in the prompt a teacher wrote rather than in a
 * hardcoded target here. The rubric that decides the real band is
 * configuration, and its endpoint is teacher-only.
 */
export function TaskPrompt({
  prompt,
  targetCount,
}: {
  prompt: string;
  targetCount: number | undefined;
}) {
  const targets = targetTermsLabel(targetCount);

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-muted-foreground text-xs font-medium tracking-wide uppercase">
          Your task
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <p className="text-[0.95rem] leading-relaxed text-pretty">{prompt}</p>

        {targets ? (
          <p className="text-muted-foreground flex items-center gap-2 border-t pt-4 text-xs">
            <Target className="size-3.5 shrink-0" aria-hidden />
            {/* The count, not the list: naming the words before the attempt
                would be marking a student on their copying. They see every term
                they missed once the work is marked, which is where it teaches. */}
            Marking looks for {targets} in your description.
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}
