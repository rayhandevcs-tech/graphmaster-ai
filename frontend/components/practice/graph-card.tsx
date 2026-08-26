import Link from "next/link";
import { ArrowRight, Target } from "lucide-react";

import { Card } from "@/components/ui/card";
import { DifficultyBadge, GRAPH_TYPE_LABELS, GraphTypeIcon, targetTermsLabel } from "./graph-meta";
import type { GraphSummary } from "@/types/api";

/**
 * One graph in the library.
 *
 * The whole card is the link — a student on a phone should not have to find a
 * small "Practise" button. The stretched overlay keeps that to a single
 * focusable element, so tabbing through the grid is one stop per graph rather
 * than two.
 */
export function GraphCard({ graph }: { graph: GraphSummary }) {
  const targets = targetTermsLabel(graph.target_vocabulary_count);

  return (
    <Card className="group focus-within:ring-ring relative flex h-full flex-col gap-4 p-5 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md focus-within:ring-2 focus-within:ring-offset-2">
      <div className="flex items-start justify-between gap-3">
        <span className="bg-muted text-muted-foreground group-hover:bg-accent group-hover:text-accent-foreground flex size-9 items-center justify-center rounded-lg transition-colors">
          <GraphTypeIcon graphType={graph.graph_type} />
        </span>
        <DifficultyBadge difficulty={graph.difficulty} />
      </div>

      <div className="flex flex-col gap-1.5">
        <h3 className="leading-snug font-semibold tracking-tight text-balance">
          <Link href={`/practice/${graph.id}`} className="after:absolute after:inset-0">
            {graph.title}
          </Link>
        </h3>
        <p className="text-muted-foreground text-sm">{GRAPH_TYPE_LABELS[graph.graph_type]}</p>
      </div>

      <div className="text-muted-foreground mt-auto flex items-center justify-between gap-3 text-xs">
        {targets ? (
          <span className="inline-flex items-center gap-1.5">
            <Target className="size-3.5" aria-hidden />
            {targets}
          </span>
        ) : (
          <span />
        )}
        <span className="text-foreground inline-flex items-center gap-1 font-medium opacity-0 transition-opacity group-hover:opacity-100">
          Practise
          <ArrowRight className="size-3.5" aria-hidden />
        </span>
      </div>
    </Card>
  );
}

export function GraphCardSkeleton() {
  return (
    <Card className="flex flex-col gap-4 p-5" aria-hidden>
      <div className="flex items-start justify-between">
        <div className="bg-muted size-9 animate-pulse rounded-lg" />
        <div className="bg-muted h-5 w-20 animate-pulse rounded-full" />
      </div>
      <div className="flex flex-col gap-2">
        <div className="bg-muted h-4 w-4/5 animate-pulse rounded" />
        <div className="bg-muted h-3 w-1/3 animate-pulse rounded" />
      </div>
      <div className="bg-muted h-3 w-1/2 animate-pulse rounded" />
    </Card>
  );
}
