import { CircleCheck, CircleX } from "lucide-react";

import { MetricBar } from "./metric-bar";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { ScoreOut } from "@/types/api";

/**
 * Which target words were used, and which were not.
 *
 * The missing list is the part that teaches, so it is not hidden behind a
 * disclosure. It is also the reason the target set is kept from a student
 * *before* the attempt and released after: named up front it would be a list to
 * copy, named afterwards it is the specific thing to try next time
 * (04-api-design §3.6c).
 */
export function VocabularyPanel({ score }: { score: ScoreOut }) {
  const categories = Object.entries(score.category_breakdown);
  const requiredMissing = score.missing_terms.filter((term) => term.is_required);
  const optionalMissing = score.missing_terms.filter((term) => !term.is_required);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Vocabulary</CardTitle>
        <CardDescription>
          {/* The denominator is frozen at scoring time, so a later edit to the
              graph cannot move this figure — and it can be zero, on a graph
              curated before required targets were enforced. "4 of the 0
              required target terms" is not a sentence, so a graph with no
              denominator gets one describing what was used instead of a
              ratio against nothing. */}
          {score.total_target_count > 0
            ? `You used ${score.unique_detected_count} of the ${score.total_target_count} required target terms, ${score.detected_count} times in total.`
            : score.unique_detected_count > 0
              ? `This graph has no required target terms set, so there is no vocabulary percentage to earn. You used ${score.unique_detected_count} target ${score.unique_detected_count === 1 ? "term" : "terms"} anyway.`
              : "This graph has no required target terms set, so there is no vocabulary percentage to earn."}
        </CardDescription>
      </CardHeader>

      <CardContent className="flex flex-col gap-6">
        {categories.length > 0 ? (
          <ul className="flex flex-col gap-4">
            {categories.map(([key, usage]) => (
              <li key={key}>
                <MetricBar
                  label={usage.name}
                  value={usage.percentage}
                  hint={`${usage.detected_count} of ${usage.target_count} terms`}
                />
              </li>
            ))}
          </ul>
        ) : null}

        {score.detected_terms.length > 0 ? (
          <TermList
            title="Terms you used"
            icon={<CircleCheck className="text-success size-4" aria-hidden />}
            terms={score.detected_terms.map((term) => ({
              key: term.lemma || term.term,
              label: term.term,
              count: term.count,
              required: term.is_required,
            }))}
            tone="border-success/40 bg-success/10"
          />
        ) : null}

        {requiredMissing.length > 0 ? (
          <TermList
            title="Required terms you did not use"
            icon={<CircleX className="text-muted-foreground size-4" aria-hidden />}
            terms={requiredMissing.map((term) => ({
              key: term.lemma || term.term,
              label: term.term,
              required: true,
            }))}
            tone="border-border bg-muted/60"
          />
        ) : null}

        {optionalMissing.length > 0 ? (
          <TermList
            title="Other terms that would have fitted"
            icon={<CircleX className="text-muted-foreground size-4" aria-hidden />}
            terms={optionalMissing.map((term) => ({
              key: term.lemma || term.term,
              label: term.term,
              required: false,
            }))}
            tone="border-border bg-muted/40"
          />
        ) : null}
      </CardContent>
    </Card>
  );
}

function TermList({
  title,
  icon,
  terms,
  tone,
}: {
  title: string;
  icon: React.ReactNode;
  terms: { key: string; label: string; count?: number; required: boolean }[];
  tone: string;
}) {
  return (
    <div className="flex flex-col gap-2.5">
      <h3 className="inline-flex items-center gap-2 text-sm font-medium">
        {icon}
        {title}
      </h3>
      <ul className="flex flex-wrap gap-1.5">
        {terms.map((term) => (
          <li key={term.key}>
            <span
              className={cn(
                "inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs",
                tone,
              )}
            >
              {term.label}
              {term.count && term.count > 1 ? (
                <span className="text-muted-foreground tabular-nums">×{term.count}</span>
              ) : null}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
