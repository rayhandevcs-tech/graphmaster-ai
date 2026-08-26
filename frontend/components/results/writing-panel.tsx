import { MetricBar } from "./metric-bar";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { WritingBreakdownOut } from "@/types/api";

/**
 * The writing-quality half of the score, and what it measured.
 *
 * The measures are shown rather than hidden because the score is a heuristic:
 * "your sentences average 11 words" is something a student can act on, where
 * "sentence structure: 62" alone is not. The API exposes them for the same
 * reason — a teacher disputing a score deserves to see what produced it.
 */
export function WritingPanel({ breakdown }: { breakdown: WritingBreakdownOut }) {
  const { components, measures } = breakdown;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Writing quality</CardTitle>
        <CardDescription>
          Four equally weighted parts, measured over {breakdown.word_count.toLocaleString()} words
          in {breakdown.sentence_count} {breakdown.sentence_count === 1 ? "sentence" : "sentences"}.
        </CardDescription>
      </CardHeader>

      <CardContent className="flex flex-col gap-5">
        <MetricBar
          label="Length"
          value={components.word_count}
          hint={`${breakdown.word_count.toLocaleString()} words written`}
          barClassName="bg-secondary"
        />
        <MetricBar
          label="Range of vocabulary"
          value={components.lexical_diversity}
          hint={`Measured across the whole answer, not just the target terms`}
          barClassName="bg-secondary"
        />
        <MetricBar
          label="Sentence structure"
          value={components.sentence_structure}
          hint={`Sentences average ${measures.mean_sentence_length.toFixed(1)} words`}
          barClassName="bg-secondary"
        />
        <MetricBar
          label="Overview"
          value={components.overview}
          hint={
            measures.has_overview
              ? overviewHint(measures.overview_sentence_index)
              : "No sentence summarised the overall trend. Open with one — it is what a marker looks for first."
          }
          barClassName="bg-secondary"
        />
      </CardContent>
    </Card>
  );
}

function overviewHint(index: number | null | undefined): string {
  if (typeof index !== "number") return "You summarised the overall trend.";
  return index === 0
    ? "You opened with an overview of the overall trend."
    : `You summarised the overall trend in sentence ${index + 1}. Earlier is stronger.`;
}
