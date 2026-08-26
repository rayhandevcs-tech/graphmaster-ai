import { BookOpen } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * The teacher's own description of the graph.
 *
 * Released only now. It is absent from the student's graph payload entirely —
 * not merely omitted by the handler — so that a student who could fetch it
 * before submitting would have been scored on their copying (04-api-design
 * §3.5). Reading it after the attempt is the point of having it.
 */
export function ModelAnswer({ text }: { text: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="inline-flex items-center gap-2">
          <BookOpen className="size-4" aria-hidden />A model description
        </CardTitle>
        <CardDescription>
          One good answer, not the only one. Compare the structure and the word choices with yours.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <p className="text-[0.95rem] leading-7 whitespace-pre-wrap">{text}</p>
      </CardContent>
    </Card>
  );
}
