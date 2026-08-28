"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

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
import { TargetChooser, targetEntries, type TargetState } from "./target-chooser";
import { errorMessage, graphsApi } from "@/lib/api";
import type { ChartData, GraphType, TargetVocabularyOut, UUID } from "@/types/api";

/**
 * Changing the targets on a graph that already exists.
 *
 * The list itself is `TargetChooser`, shared with the authoring flow — the two
 * screens differ only in when the choice is written: here it replaces the
 * stored set, and there it travels with the graph being created.
 *
 * The figures are passed through so this screen gets the same suggestions as
 * authoring. A teacher revisiting a graph they made before the suggestions
 * existed is exactly who needs them.
 */
export function TargetPicker({
  graphId,
  open,
  onOpenChange,
  current,
  chartData,
  graphType,
}: {
  graphId: UUID;
  open: boolean;
  onOpenChange: (next: boolean) => void;
  current: TargetVocabularyOut[];
  chartData?: ChartData | null;
  graphType?: GraphType;
}) {
  const queryClient = useQueryClient();

  const [chosen, setChosen] = useState<Map<UUID, TargetState>>(
    () => new Map(current.map((row) => [row.item.id, row.is_required ? "required" : "optional"])),
  );

  const save = useMutation({
    mutationFn: () => graphsApi.replaceTargetVocabulary(graphId, { items: targetEntries(chosen) }),
    onSuccess: async () => {
      onOpenChange(false);
      await queryClient.invalidateQueries({ queryKey: ["graphs"] });
    },
  });

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

        <TargetChooser
          chosen={chosen}
          onChange={setChosen}
          series={chartData ? chartData.datasets.map((dataset) => dataset.data) : undefined}
          graphType={graphType}
        />

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
