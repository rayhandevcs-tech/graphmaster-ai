"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { queryKeys, vocabularyApi } from "@/lib/api";
import { useDebouncedValue } from "@/lib/hooks/use-debounced-value";
import { shapesIn, suggestTargets } from "@/lib/authoring/suggest-targets";
import { cn } from "@/lib/utils";
import type { GraphType, UUID, VocabularyItemOut } from "@/types/api";

/**
 * Which terms a graph is marked against.
 *
 * **Required terms are the denominator of the vocabulary percentage**, so this
 * is the control that decides what a crown costs. Each term is off, required
 * or optional — three states in one button, because "on but optional" is a
 * real and common choice and a checkbox plus a second checkbox invites the
 * combination that means nothing.
 *
 * **Suggestions are the point of this rewrite.** Given the figures, it offers
 * the terms the graph is likely to need and says why — "the direction changes
 * four times". They arrive switched off. A teacher accepts, edits or ignores
 * them, because a required set nobody looked at is a graph marked on the wrong
 * words.
 *
 * Extracted from the two dialogs that both needed it: authoring a new graph,
 * where the targets are submitted with the graph, and editing an existing one,
 * where they are replaced separately.
 */

export type TargetState = "off" | "required" | "optional";

export function TargetChooser({
  chosen,
  onChange,
  series,
  graphType,
}: {
  chosen: Map<UUID, TargetState>;
  onChange: (next: Map<UUID, TargetState>) => void;
  /** The parsed figures. Omit to hide the suggestions entirely. */
  series?: (number | null)[][];
  graphType?: GraphType;
}) {
  const [search, setSearch] = useState("");
  const debounced = useDebouncedValue(search, 250);

  // Two queries that collapse into one while the box is empty, which is the
  // common case. The suggestions need the unfiltered library — they would
  // otherwise disappear the moment a teacher typed in the search box.
  const listed = useQuery({
    queryKey: queryKeys.vocabularyItems({
      search: debounced || undefined,
      is_active: true,
      page_size: 100,
    }),
    queryFn: () =>
      vocabularyApi.list({ search: debounced || undefined, is_active: true, page_size: 100 }),
  });
  const library = useQuery({
    queryKey: queryKeys.vocabularyItems({ is_active: true, page_size: 100 }),
    queryFn: () => vocabularyApi.list({ is_active: true, page_size: 100 }),
    enabled: series !== undefined,
  });

  const shapes = useMemo(
    () => (series && graphType ? shapesIn(series, graphType) : []),
    [series, graphType],
  );
  const suggested = useMemo(
    () => suggestTargets(library.data?.items ?? [], shapes),
    [library.data, shapes],
  );
  const unusedSuggestions = suggested.filter((item) => (chosen.get(item.id) ?? "off") === "off");

  const requiredCount = [...chosen.values()].filter((state) => state === "required").length;

  const set = (updates: Iterable<[UUID, TargetState]>) => {
    const next = new Map(chosen);
    for (const [id, state] of updates) next.set(id, state);
    onChange(next);
  };

  const cycle = (id: UUID) => {
    const state = chosen.get(id) ?? "off";
    set([[id, state === "off" ? "required" : state === "required" ? "optional" : "off"]]);
  };

  return (
    <div className="flex flex-col gap-3">
      {shapes.length > 0 && unusedSuggestions.length > 0 ? (
        <div className="bg-accent/40 flex flex-col gap-2.5 rounded-lg border p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="inline-flex items-center gap-1.5 text-sm font-medium">
              <Sparkles className="text-primary size-4" aria-hidden />
              Suggested for these figures
            </span>
            <Button
              type="button"
              size="sm"
              variant="secondary"
              onClick={() => set(unusedSuggestions.map((item) => [item.id, "required"] as const))}
            >
              Add all {unusedSuggestions.length} as required
            </Button>
          </div>

          {/* The reasons, not just the words. A teacher who can see why a term
              was offered can disagree with it. */}
          <ul className="text-muted-foreground flex flex-col gap-0.5 text-xs">
            {shapes.map((shape) => (
              <li key={shape.code}>{shape.reason}</li>
            ))}
          </ul>

          <div className="flex flex-wrap gap-1.5">
            {unusedSuggestions.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => set([[item.id, "required"]])}
                className="bg-card hover:border-primary focus-visible:ring-ring min-h-9 rounded-full border px-3 py-1.5 text-sm transition-colors focus-visible:ring-2 focus-visible:outline-none"
              >
                + {item.term}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      <div className="relative">
        <Search
          className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2"
          aria-hidden
        />
        <Input
          value={search}
          placeholder="Search the vocabulary"
          aria-label="Search the vocabulary"
          className="pl-9"
          onChange={(event) => setSearch(event.target.value)}
        />
      </div>

      <p role="status" className="text-sm">
        {requiredCount === 0 ? (
          <span className="text-destructive">
            No required terms yet — a graph cannot be published without at least one.
          </span>
        ) : (
          <span className="text-muted-foreground">
            {requiredCount} required {requiredCount === 1 ? "term" : "terms"}
          </span>
        )}
      </p>

      <div className="max-h-72 overflow-y-auto rounded-lg border">
        {listed.isPending ? (
          <div className="flex flex-col gap-1 p-2">
            {[0, 1, 2, 3].map((index) => (
              <Skeleton key={index} className="h-10 rounded" />
            ))}
          </div>
        ) : (
          <ul className="divide-border divide-y">
            {(listed.data?.items ?? []).map((item: VocabularyItemOut) => {
              const state = chosen.get(item.id) ?? "off";
              return (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => cycle(item.id)}
                    className="hover:bg-muted/50 focus-visible:ring-ring flex min-h-12 w-full items-center justify-between gap-3 px-3 py-2 text-left transition-colors focus-visible:ring-2 focus-visible:-outline-offset-2 focus-visible:outline-none"
                  >
                    <span className="flex min-w-0 flex-col">
                      <span className="truncate text-sm font-medium">{item.term}</span>
                      <span className="text-muted-foreground truncate text-xs">
                        {item.category_name}
                      </span>
                    </span>
                    <span
                      className={cn(
                        "rounded-full px-2 py-0.5 text-xs font-medium",
                        state === "required"
                          ? "bg-primary text-primary-foreground"
                          : state === "optional"
                            ? "bg-secondary/15 text-secondary"
                            : "text-muted-foreground",
                      )}
                    >
                      {state === "off"
                        ? "Not used"
                        : state === "required"
                          ? "Required"
                          : "Optional"}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}

/** The chosen map as the API's list, dropping everything switched off. */
export function targetEntries(chosen: Map<UUID, TargetState>) {
  return [...chosen.entries()]
    .filter(([, state]) => state !== "off")
    .map(([id, state]) => ({ vocabulary_item_id: id, is_required: state === "required" }));
}
