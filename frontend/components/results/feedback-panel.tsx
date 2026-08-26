import { ArrowRight, Lightbulb, ListChecks } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { FeedbackOut } from "@/types/api";

/**
 * What went well, what to work on, and the one thing to do next.
 *
 * Every line here is the server's wording, rendered as it arrived. The rule the
 * engine enforces — that feedback never claims something the student did not
 * do, in either direction: no praise for unused vocabulary, and no "you used no
 * comparison language" for a category they did use — only holds if the client
 * does not paraphrase, reorder into claims, or pad an empty list with a
 * cheerful default.
 */
export function FeedbackPanel({ feedback }: { feedback: FeedbackOut }) {
  const hasLists = feedback.strengths.length > 0 || feedback.improvements.length > 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Feedback</CardTitle>
      </CardHeader>

      <CardContent className="flex flex-col gap-6">
        {hasLists ? (
          <div className="grid gap-6 sm:grid-cols-2">
            {feedback.strengths.length > 0 ? (
              <Points
                title="What worked"
                icon={<ListChecks className="text-success size-4" aria-hidden />}
                points={feedback.strengths}
              />
            ) : null}
            {feedback.improvements.length > 0 ? (
              <Points
                title="What to work on"
                icon={<Lightbulb className="text-secondary size-4" aria-hidden />}
                points={feedback.improvements}
              />
            ) : null}
          </div>
        ) : null}

        {feedback.next_step ? (
          <div className="border-secondary/40 bg-secondary/10 flex gap-3 rounded-lg border p-4">
            <ArrowRight className="mt-0.5 size-4 shrink-0" aria-hidden />
            <div className="flex flex-col gap-1">
              <p className="text-sm font-medium">Try this next</p>
              <p className="text-sm leading-relaxed text-pretty">{feedback.next_step}</p>
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function Points({
  title,
  icon,
  points,
}: {
  title: string;
  icon: React.ReactNode;
  points: string[];
}) {
  return (
    <section className="flex flex-col gap-2.5">
      <h3 className="inline-flex items-center gap-2 text-sm font-medium">
        {icon}
        {title}
      </h3>
      <ul className="flex flex-col gap-2">
        {points.map((point) => (
          <li key={point} className="text-muted-foreground text-sm leading-relaxed text-pretty">
            {point}
          </li>
        ))}
      </ul>
    </section>
  );
}
