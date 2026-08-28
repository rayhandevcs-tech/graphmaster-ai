import Link from "next/link";
import { ArrowRight, Target } from "lucide-react";

import { Card } from "@/components/ui/card";
import { GraphThumbnail } from "./graph-thumbnail";
import { DifficultyBadge, GRAPH_TYPE_LABELS, GraphTypeIcon, targetTermsLabel } from "./graph-meta";
import type { GraphSummary } from "@/types/api";

/**
 * One graph in the library.
 *
 * **The card leads with the graph.** It used to lead with a type icon in a
 * rounded square — the same 9×9 tile the settings page uses for a category —
 * which meant choosing between four graphs was reading four titles. A student
 * picking something to practise is choosing a *shape* and a *task*, so the
 * card shows the shape, then the title, then the task. The type label stays as
 * a caption for the picture rather than as its stand-in.
 *
 * The thumbnail is drawn from `preview` in a handful of SVG paths, not by a
 * chart library — see `graph-thumbnail.tsx` for why twenty canvases is the
 * wrong answer here.
 *
 * The whole card is the link — a student on a phone should not have to find a
 * small "Practise" button. The stretched overlay keeps that to a single
 * focusable element, so tabbing through the grid is one stop per graph rather
 * than two.
 */
export function GraphCard({ graph }: { graph: GraphSummary }) {
  const targets = targetTermsLabel(graph.target_vocabulary_count);

  return (
    <Card className="group focus-within:ring-ring relative flex h-full flex-col gap-0 overflow-hidden p-0 transition-all duration-200 focus-within:ring-2 focus-within:ring-offset-2 hover:-translate-y-0.5 hover:shadow-md">
      {/* A fixed ratio rather than a fixed height, so every card in a row
          shows the same amount of picture whatever its title wraps to. */}
      <div className="bg-muted/40 relative aspect-[16/7] border-b">
        {/* Absolutely positioned rather than padded, so the drawing has a
            *definite* height to fill. A percentage height against a parent
            sized by `aspect-ratio` resolves to auto, and an SVG with an
            intrinsic square ratio then takes its width as its height — which
            grew the pie card to twice the height of every other card in the
            row, and only the pie, because it is the only square one. */}
        <div className="absolute inset-3">
          <GraphThumbnail graphType={graph.graph_type} preview={graph.preview} />
        </div>
        <div className="absolute top-2 right-2">
          <DifficultyBadge difficulty={graph.difficulty} />
        </div>
      </div>

      <div className="flex flex-1 flex-col gap-2 p-5">
        <span className="text-muted-foreground inline-flex items-center gap-1.5 text-xs font-medium">
          <GraphTypeIcon graphType={graph.graph_type} />
          {GRAPH_TYPE_LABELS[graph.graph_type]}
        </span>

        <h3 className="leading-snug font-semibold tracking-tight text-balance">
          <Link href={`/practice/${graph.id}`} className="after:absolute after:inset-0">
            {graph.title}
          </Link>
        </h3>

        {/* The task, clamped to two lines. It is what a student is actually
            choosing between — two graphs of the same rainfall data asking for
            a comparison and asking for a trend are different exercises — and
            the full text is on the practice page a tap away. */}
        <p className="text-muted-foreground line-clamp-2 text-sm text-pretty">{graph.prompt}</p>

        <div className="text-muted-foreground mt-auto flex items-center justify-between gap-3 pt-2 text-xs">
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
      </div>
    </Card>
  );
}

export function GraphCardSkeleton() {
  return (
    <Card className="flex flex-col gap-0 overflow-hidden p-0" aria-hidden>
      <div className="bg-muted aspect-[16/7] animate-pulse border-b" />
      <div className="flex flex-col gap-2 p-5">
        <div className="bg-muted h-3 w-1/3 animate-pulse rounded" />
        <div className="bg-muted h-4 w-4/5 animate-pulse rounded" />
        <div className="bg-muted h-3 w-full animate-pulse rounded" />
        <div className="bg-muted mt-2 h-3 w-1/2 animate-pulse rounded" />
      </div>
    </Card>
  );
}
