"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AreaChart,
  BarChart3,
  LineChart,
  Pencil,
  PieChart,
  Plus,
  RefreshCw,
  Tags,
  TriangleAlert,
} from "lucide-react";

import { GraphForm } from "./graph-form";
import { TargetPicker } from "./target-picker";
import { EmptyState } from "@/components/layout/empty-state";
import { Pager } from "@/components/layout/pager";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { FilterChips } from "@/components/ui/filter-chips";
import { Skeleton } from "@/components/ui/skeleton";
import { errorMessage, graphsApi, isAuthoringDetail, queryKeys } from "@/lib/api";
import { formatCount } from "@/lib/format";
import type { GraphAuthoringDetail, GraphSummary } from "@/types/api";

/**
 * The practice graphs, as pictures.
 *
 * Cards rather than rows, because a graph *is* a picture and the preview is
 * the fastest way to recognise one — the existing `GraphChart` renders it with
 * the theme, the lazy Chart.js import and the accessible description already
 * handled.
 *
 * **A graph cannot be published without at least one required target term**
 * (CLAUDE.md rule 12): required terms are the denominator of the vocabulary
 * percentage, so an empty set makes the exercise unscoreable. The publish
 * control is therefore disabled *with the reason attached to the card*, rather
 * than enabled and then refused with a 409. The fix is one tap away on the
 * same card.
 */
const FILTERS = [
  { value: "published" as const, label: "Published" },
  { value: "draft" as const, label: "Draft" },
];

const PAGE_SIZE = 12;

export function GraphsManager() {
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<"published" | "draft" | null>(null);
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<GraphAuthoringDetail | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [targetsFor, setTargetsFor] = useState<GraphAuthoringDetail | null>(null);

  const query = { include_unpublished: true, page, page_size: PAGE_SIZE };

  const graphs = useQuery({
    queryKey: queryKeys.graphs(query),
    queryFn: () => graphsApi.list(query),
    placeholderData: (previous) => previous,
  });

  const publish = useMutation({
    mutationFn: (graph: GraphSummary) =>
      graphsApi.setPublished(graph.id, { is_published: !graph.is_published }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["graphs"] });
    },
  });

  const openEditor = async (id: string) => {
    const graph = await queryClient.fetchQuery({
      queryKey: queryKeys.graph(id),
      queryFn: () => graphsApi.get(id),
    });
    if (isAuthoringDetail(graph)) {
      setEditing(graph);
      setFormOpen(true);
    }
  };

  const openTargets = async (id: string) => {
    const graph = await queryClient.fetchQuery({
      queryKey: queryKeys.graph(id),
      queryFn: () => graphsApi.get(id),
    });
    if (isAuthoringDetail(graph)) setTargetsFor(graph);
  };

  const items = (graphs.data?.items ?? []).filter((graph) =>
    filter === null ? true : filter === "published" ? graph.is_published : !graph.is_published,
  );

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold tracking-tight">Graphs</h1>
          <p className="text-muted-foreground text-sm text-pretty">
            The charts your students describe, and the vocabulary each one is marked against.
          </p>
        </div>
        <Button
          size="sm"
          onClick={() => {
            setEditing(null);
            setFormOpen(true);
          }}
        >
          <Plus aria-hidden />
          New graph
        </Button>
      </div>

      <FilterChips
        label="Status"
        options={FILTERS}
        value={filter}
        onChange={(next) => {
          setFilter(next);
          setPage(1);
        }}
      />

      {publish.isError ? (
        <Alert variant="destructive">
          <AlertTitle>That graph could not be published</AlertTitle>
          <AlertDescription>{errorMessage(publish.error)}</AlertDescription>
        </Alert>
      ) : null}

      {graphs.isPending ? (
        <GraphsSkeleton />
      ) : graphs.isError ? (
        <Alert variant="destructive">
          <AlertTitle>The graphs could not be loaded</AlertTitle>
          <AlertDescription className="flex flex-col items-start gap-3">
            <span>{errorMessage(graphs.error)}</span>
            <Button variant="outline" size="sm" onClick={() => void graphs.refetch()}>
              <RefreshCw aria-hidden />
              Try again
            </Button>
          </AlertDescription>
        </Alert>
      ) : items.length === 0 ? (
        <EmptyState
          icon={LineChart}
          title={filter === "draft" ? "No drafts" : "No graphs yet"}
          description="A graph carries the figures, the prompt, and the vocabulary it is marked against."
          action={
            <Button
              size="sm"
              onClick={() => {
                setEditing(null);
                setFormOpen(true);
              }}
            >
              <Plus aria-hidden />
              New graph
            </Button>
          }
        />
      ) : (
        <>
          <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {items.map((graph) => (
              <GraphCard
                key={graph.id}
                graph={graph}
                busy={publish.isPending}
                onPublish={() => publish.mutate(graph)}
                onEdit={() => void openEditor(graph.id)}
                onTargets={() => void openTargets(graph.id)}
              />
            ))}
          </ul>

          {graphs.data && graphs.data.total_pages > 1 ? (
            <Pager
              page={graphs.data.page}
              totalPages={graphs.data.total_pages}
              total={graphs.data.total}
              onPageChange={setPage}
              itemNoun="graphs"
            />
          ) : null}
        </>
      )}

      {formOpen ? (
        <GraphForm
          key={editing?.id ?? "new"}
          open={formOpen}
          onOpenChange={setFormOpen}
          editing={editing}
        />
      ) : null}

      {targetsFor ? (
        <TargetPicker
          key={targetsFor.id}
          graphId={targetsFor.id}
          open
          onOpenChange={(next) => {
            if (!next) setTargetsFor(null);
          }}
          current={targetsFor.target_vocabulary ?? []}
        />
      ) : null}
    </div>
  );
}

function GraphCard({
  graph,
  busy,
  onPublish,
  onEdit,
  onTargets,
}: {
  graph: GraphSummary;
  busy: boolean;
  onPublish: () => void;
  onEdit: () => void;
  onTargets: () => void;
}) {
  const required = graph.target_vocabulary_count ?? 0;
  const publishable = required > 0;

  return (
    <li>
      <Card className="flex h-full flex-col gap-3 p-4">
        {/* A type glyph, not a preview. The list endpoint carries no
            `chart_data` — a chart drawn from nothing would be an empty box
            claiming to be this graph, and fetching twelve details to fill a
            grid is a lot of requests for a thumbnail. The type is what
            distinguishes cards at a glance anyway. */}
        <div className="bg-muted/40 text-muted-foreground flex h-24 items-center justify-center gap-2 rounded-lg">
          <TypeGlyph type={graph.graph_type} />
          <span className="text-xs font-medium capitalize">{graph.graph_type} chart</span>
        </div>

        <div className="flex flex-col gap-1">
          <h2 className="text-sm font-semibold text-balance">{graph.title}</h2>
          <p className="text-muted-foreground text-xs">
            {graph.is_published ? "Published" : "Draft"} · {graph.difficulty} ·{" "}
            {formatCount(required)} required {required === 1 ? "term" : "terms"}
          </p>
        </div>

        {publishable ? null : (
          <p className="text-destructive flex items-start gap-1.5 text-xs text-pretty">
            <TriangleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden />
            Add at least one required target term before publishing — they are the denominator of
            the vocabulary score.
          </p>
        )}

        <div className="mt-auto flex flex-wrap gap-1 pt-1">
          <Button variant="outline" size="sm" onClick={onEdit}>
            <Pencil aria-hidden />
            Edit
          </Button>
          <Button variant="outline" size="sm" onClick={onTargets}>
            <Tags aria-hidden />
            Targets
          </Button>
          <Button
            variant={graph.is_published ? "ghost" : "primary"}
            size="sm"
            disabled={busy || (!graph.is_published && !publishable)}
            title={
              !graph.is_published && !publishable
                ? "A graph needs at least one required target term"
                : undefined
            }
            onClick={onPublish}
          >
            {graph.is_published ? "Unpublish" : "Publish"}
          </Button>
        </div>
      </Card>
    </li>
  );
}

const TYPE_GLYPH = {
  line: LineChart,
  bar: BarChart3,
  pie: PieChart,
  area: AreaChart,
} as const;

function TypeGlyph({ type }: { type: GraphSummary["graph_type"] }) {
  const Icon = TYPE_GLYPH[type] ?? LineChart;
  return <Icon className="size-6" aria-hidden />;
}

function GraphsSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3" aria-busy>
      <span className="sr-only" role="status">
        Loading the graphs
      </span>
      {[0, 1, 2, 3, 4, 5].map((index) => (
        <Skeleton key={index} className="h-64 rounded-xl" />
      ))}
    </div>
  );
}
