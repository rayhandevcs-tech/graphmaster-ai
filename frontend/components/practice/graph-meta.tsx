import { ChartArea, ChartColumn, ChartLine, ChartPie } from "lucide-react";

import { cn } from "@/lib/utils";
import type { Difficulty, GraphType } from "@/types/api";

/**
 * How a graph's type and difficulty are presented, in one place.
 *
 * Both appear on the library card, the practice header and the result screen.
 * Three copies of the same lookup drift, and the symptom — a graph that is
 * "Intermediate" in the list and "Medium" on the page it opens — reads as two
 * different exercises.
 */

export const GRAPH_TYPE_LABELS: Record<GraphType, string> = {
  line: "Line graph",
  bar: "Bar chart",
  pie: "Pie chart",
  area: "Area chart",
};

const GRAPH_TYPE_ICONS = {
  line: ChartLine,
  bar: ChartColumn,
  pie: ChartPie,
  area: ChartArea,
} as const;

export function GraphTypeIcon({
  graphType,
  className,
}: {
  graphType: GraphType;
  className?: string;
}) {
  const Icon = GRAPH_TYPE_ICONS[graphType] ?? ChartLine;
  return <Icon className={cn("size-4", className)} aria-hidden />;
}

export const DIFFICULTY_LABELS: Record<Difficulty, string> = {
  beginner: "Beginner",
  intermediate: "Intermediate",
  advanced: "Advanced",
};

/**
 * Colour *and* the word, never colour alone (NFR-4.6). The tint is a hint for
 * someone scanning a grid; the label is what carries the level.
 */
const DIFFICULTY_TONES: Record<Difficulty, string> = {
  beginner: "border-success/40 bg-success/10 text-foreground",
  intermediate: "border-secondary/40 bg-secondary/10 text-foreground",
  advanced: "border-primary/40 bg-primary/10 text-foreground",
};

export function DifficultyBadge({
  difficulty,
  className,
}: {
  difficulty: Difficulty;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium",
        DIFFICULTY_TONES[difficulty],
        className,
      )}
    >
      {DIFFICULTY_LABELS[difficulty]}
    </span>
  );
}

/** "12 target terms", and the singular a naive template gets wrong. */
export function targetTermsLabel(count: number | undefined): string | null {
  if (count === undefined || count <= 0) return null;
  return count === 1 ? "1 target term" : `${count} target terms`;
}
