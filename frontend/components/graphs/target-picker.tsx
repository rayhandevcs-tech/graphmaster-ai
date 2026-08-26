"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Search } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { errorMessage, graphsApi, queryKeys, vocabularyApi } from "@/lib/api";
import { useDebouncedValue } from "@/lib/hooks/use-debounced-value";
import type { TargetVocabularyOut, UUID } from "@/types/api";

/**
 * Which terms this graph is marked against.
 *
 * **Required terms are the denominator of the vocabulary percentage**, so this
 * is the screen that decides what a crown costs. Each term is off, required or
 * optional — three states in one control, because "on but optional" is a real
 * and common choice and a checkbox plus a second checkbox invites the
 * combination that means nothing.
 *
 * The count of required terms is shown while editing, because a graph with
 * none cannot be published (CLAUDE.md rule 12) and this is where that is
 * fixed.
 */
type State = "off" | "required" | "optional";

export function TargetPicker({
  graphId,
  open,
  onOpenChange,
  current,
}: {
  graphId: UUID;
  open: boolean;
  onOpenChange: (next: boolean) => void;
  current: TargetVocabularyOut[];
}) {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const debounced = useDebouncedValue(search, 250);

  const [chosen, setChosen] = useState<Map<UUID, State>>(
    () => new Map(current.map((row) => [row.item.id, row.is_required ? "required" : "optional"])),
  );

  const terms = useQuery({
    queryKey: queryKeys.vocabularyItems({
      search: debounced || undefined,
      is_active: true,
      page_size: 100,
    }),
    queryFn: () =>
      vocabularyApi.list({ search: debounced || undefined, is_active: true, page_size: 100 }),
  });

  const requiredCount = useMemo(
    () => [...chosen.values()].filter((state) => state === "required").length,
    [chosen],
  );

  const save = useMutation({
    mutationFn: () =>
      graphsApi.replaceTargetVocabulary(graphId, {
        items: [...chosen.entries()]
          .filter(([, state]) => state !== "off")
          .map(([id, state]) => ({ vocabulary_item_id: id, is_required: state === "required" })),
      }),
    onSuccess: async () => {
      onOpenChange(false);
      await queryClient.invalidateQueries({ queryKey: ["graphs"] });
    },
  });

  const cycle = (id: UUID) => {
    setChosen((previous) => {
      const next = new Map(previous);
      const state = next.get(id) ?? "off";
      next.set(id, state === "off" ? "required" : state === "required" ? "optional" : "off");
      return next;
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>Target vocabulary</DialogTitle>
          <DialogDescription>
            Required terms are the denominator of the vocabulary percentage. Optional terms are
            credited when a student uses them, without making the crown harder to reach.
          </DialogDescription>
        </DialogHeader>

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
          {terms.isPending ? (
            <div className="flex flex-col gap-1 p-2">
              {[0, 1, 2, 3].map((index) => (
                <Skeleton key={index} className="h-10 rounded" />
              ))}
            </div>
          ) : (
            <ul className="divide-border divide-y">
              {(terms.data?.items ?? []).map((item) => {
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
                        className={
                          state === "required"
                            ? "bg-primary text-primary-foreground rounded-full px-2 py-0.5 text-xs font-medium"
                            : state === "optional"
                              ? "bg-secondary/15 text-secondary rounded-full px-2 py-0.5 text-xs font-medium"
                              : "text-muted-foreground text-xs"
                        }
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

        {save.isError ? (
          <Alert variant="destructive">
            <AlertDescription>{errorMessage(save.error)}</AlertDescription>
          </Alert>
        ) : null}

        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="outline">
              Cancel
            </Button>
          </DialogClose>
          <Button onClick={() => save.mutate()} disabled={save.isPending}>
            {save.isPending ? "Saving…" : "Save targets"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
