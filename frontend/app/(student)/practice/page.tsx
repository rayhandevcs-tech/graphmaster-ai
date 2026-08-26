"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import { Search, Shuffle, SlidersHorizontal, Telescope } from "lucide-react";

import { Protected } from "@/components/auth/protected";
import { EmptyState } from "@/components/layout/empty-state";
import { Pager } from "@/components/layout/pager";
import { GraphCard, GraphCardSkeleton } from "@/components/practice/graph-card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { FilterChips } from "@/components/ui/filter-chips";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { useDebouncedValue } from "@/lib/hooks/use-debounced-value";
import { errorMessage, graphsApi, queryKeys } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { Difficulty, GraphType } from "@/types/api";

const PAGE_SIZE = 12;

const TYPE_OPTIONS = [
  { value: "line", label: "Line" },
  { value: "bar", label: "Bar" },
  { value: "pie", label: "Pie" },
  { value: "area", label: "Area" },
] as const satisfies readonly { value: GraphType; label: string }[];

const DIFFICULTY_OPTIONS = [
  { value: "beginner", label: "Beginner" },
  { value: "intermediate", label: "Intermediate" },
  { value: "advanced", label: "Advanced" },
] as const satisfies readonly { value: Difficulty; label: string }[];

export default function PracticePage() {
  return (
    <Protected roles={["student"]}>
      <GraphLibrary />
    </Protected>
  );
}

function GraphLibrary() {
  const router = useRouter();

  const [search, setSearch] = useState("");
  const [graphType, setGraphType] = useState<GraphType | null>(null);
  const [difficulty, setDifficulty] = useState<Difficulty | null>(null);
  const [page, setPage] = useState(1);

  const settledSearch = useDebouncedValue(search.trim());

  const params = {
    page,
    page_size: PAGE_SIZE,
    search: settledSearch || undefined,
    graph_type: graphType ?? undefined,
    difficulty: difficulty ?? undefined,
  };

  const graphs = useQuery({
    queryKey: queryKeys.graphs(params),
    queryFn: () => graphsApi.list(params),
    // Keeps the previous page on screen while the next one loads, so paging
    // does not blink the grid away and jump the scroll position.
    placeholderData: keepPreviousData,
  });

  const random = useMutation({
    mutationFn: () => graphsApi.random({ graph_type: graphType ?? undefined }),
    onSuccess: (graph) => router.push(`/practice/${graph.id}`),
  });

  const clearFilters = () => {
    setSearch("");
    setGraphType(null);
    setDifficulty(null);
    setPage(1);
  };

  const items = graphs.data?.items ?? [];
  const hasFilters = Boolean(settledSearch || graphType || difficulty);

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex flex-col gap-2">
          <h1 className="text-3xl font-semibold tracking-tight">Practice</h1>
          <p className="text-muted-foreground max-w-xl text-sm text-pretty">
            Pick a graph, read what it shows, and describe it in academic English. You are marked on
            the vocabulary you use and on how the writing is put together.
          </p>
        </div>

        <Button
          type="button"
          size="lg"
          onClick={() => random.mutate()}
          disabled={random.isPending}
          className="shrink-0"
        >
          {random.isPending ? <Spinner label="Finding a graph" /> : <Shuffle aria-hidden />}
          Surprise me
        </Button>
      </header>

      {random.isError ? (
        <Alert variant="destructive">
          <AlertTitle>Could not start a random graph</AlertTitle>
          <AlertDescription>{errorMessage(random.error)}</AlertDescription>
        </Alert>
      ) : null}

      <Card className="flex flex-col gap-4 p-4 sm:p-5">
        <div className="relative">
          <Search
            className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2"
            aria-hidden
          />
          <Input
            type="search"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
            placeholder="Search graphs by title"
            aria-label="Search graphs by title"
            className="pl-9"
          />
        </div>

        <div className="flex flex-col gap-3 border-t pt-4 sm:flex-row sm:flex-wrap sm:items-center sm:gap-6">
          <span className="text-muted-foreground inline-flex items-center gap-1.5 text-xs font-medium tracking-wide uppercase">
            <SlidersHorizontal className="size-3.5" aria-hidden />
            Filter
          </span>
          <FilterChips
            label="Chart type"
            options={TYPE_OPTIONS}
            value={graphType}
            onChange={(next) => {
              setGraphType(next);
              setPage(1);
            }}
            allLabel="Any type"
          />
          <FilterChips
            label="Difficulty"
            options={DIFFICULTY_OPTIONS}
            value={difficulty}
            onChange={(next) => {
              setDifficulty(next);
              setPage(1);
            }}
            allLabel="Any level"
          />
        </div>
      </Card>

      <section aria-busy={graphs.isLoading} className="flex flex-col gap-6">
        {graphs.isError ? (
          <Alert variant="destructive">
            <AlertTitle>The graph library could not be loaded</AlertTitle>
            <AlertDescription className="flex flex-col items-start gap-3">
              {errorMessage(graphs.error)}
              <Button type="button" variant="outline" size="sm" onClick={() => graphs.refetch()}>
                Try again
              </Button>
            </AlertDescription>
          </Alert>
        ) : graphs.isLoading ? (
          <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }, (_, index) => (
              <li key={index}>
                <GraphCardSkeleton />
              </li>
            ))}
          </ul>
        ) : items.length === 0 ? (
          <EmptyState
            icon={Telescope}
            title={hasFilters ? "No graphs match those filters" : "No graphs are published yet"}
            description={
              hasFilters
                ? "Try a different chart type or level, or clear the search box."
                : "Your teacher publishes graphs for the class to practise on. Check back shortly."
            }
            action={
              hasFilters ? (
                <Button type="button" variant="outline" onClick={clearFilters}>
                  Clear filters
                </Button>
              ) : null
            }
          />
        ) : (
          <>
            <ul
              className={cn(
                "grid gap-4 sm:grid-cols-2 lg:grid-cols-3",
                graphs.isPlaceholderData && "opacity-60 transition-opacity",
              )}
            >
              {items.map((graph) => (
                <li key={graph.id}>
                  <GraphCard graph={graph} />
                </li>
              ))}
            </ul>

            <Pager
              page={graphs.data?.page ?? 1}
              totalPages={graphs.data?.total_pages ?? 1}
              total={graphs.data?.total ?? 0}
              onPageChange={setPage}
            />
          </>
        )}
      </section>
    </div>
  );
}
