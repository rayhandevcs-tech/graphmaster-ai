"use client";

import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { GraphChart } from "@/components/charts/graph-chart";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
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
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { TargetChooser, targetEntries, type TargetState } from "./target-chooser";
import { errorMessage, graphsApi } from "@/lib/api";
import { parseTable, toTableText } from "@/lib/charts/table-text";
import type { Difficulty, GraphAuthoringDetail, GraphType, UUID } from "@/types/api";

/**
 * Authoring a practice graph, in two steps and one dialog.
 *
 * **It used to be two dialogs and a gap.** A teacher filled this in, saved,
 * found the new graph in the list, opened a second dialog and picked its
 * target vocabulary from the whole library. A graph cannot be published
 * without at least one required target (CLAUDE.md rule 12), so every graph
 * needed both halves — and the second half was a separate errand, in a
 * different place, against a list of every term the library holds.
 *
 * Now the figures and the words they will be marked on are one flow, and the
 * second step *suggests* the words by reading the figures the first step just
 * produced: a series that finishes higher offers the vocabulary of increase, a
 * series that turns four times offers fluctuation. The reasons are shown with
 * the suggestions, and nothing is chosen automatically — a required set nobody
 * looked at is a graph marked on the wrong words.
 *
 * The figures are typed as a table rather than into a grid of inputs, because
 * that is the shape they already exist in — a spreadsheet, or a table in a
 * textbook — and a paste is faster and less error-prone than forty fields. The
 * chart beside it redraws as the table is edited, which is the only check that
 * matters: a teacher sees the graph their students will describe.
 *
 * The model description is optional here and released to students only after
 * their attempt is marked. It is on this form because writing it while the
 * data is in front of you is the moment it is easiest to write.
 */
const TYPES: GraphType[] = ["line", "bar", "pie", "area"];
const DIFFICULTIES: Difficulty[] = ["beginner", "intermediate", "advanced"];

export function GraphForm({
  open,
  onOpenChange,
  editing,
}: {
  open: boolean;
  onOpenChange: (next: boolean) => void;
  editing: GraphAuthoringDetail | null;
}) {
  const queryClient = useQueryClient();

  const [title, setTitle] = useState(editing?.title ?? "");
  const [prompt, setPrompt] = useState(editing?.prompt ?? "");
  const [graphType, setGraphType] = useState<GraphType>(editing?.graph_type ?? "line");
  const [difficulty, setDifficulty] = useState<Difficulty>(editing?.difficulty ?? "beginner");
  const [reference, setReference] = useState(editing?.reference_description ?? "");
  const [table, setTable] = useState(() => toTableText(editing?.chart_data));
  const [xAxis, setXAxis] = useState(editing?.chart_data?.x_axis_label ?? "");
  const [yAxis, setYAxis] = useState(editing?.chart_data?.y_axis_label ?? "");
  const [unit, setUnit] = useState(editing?.chart_data?.unit ?? "");

  const [step, setStep] = useState<"figures" | "targets">("figures");
  const [chosen, setChosen] = useState<Map<UUID, TargetState>>(
    () =>
      new Map(
        (editing?.target_vocabulary ?? []).map((row) => [
          row.item.id,
          row.is_required ? "required" : "optional",
        ]),
      ),
  );

  const parsed = useMemo(
    () =>
      parseTable(table, { x: xAxis || undefined, y: yAxis || undefined, unit: unit || undefined }),
    [table, xAxis, yAxis, unit],
  );

  const save = useMutation({
    mutationFn: async () => {
      const payload = {
        title: title.trim(),
        prompt: prompt.trim(),
        graph_type: graphType,
        difficulty,
        chart_data: parsed.chartData,
        reference_description: reference.trim() || null,
      };
      const items = targetEntries(chosen);

      if (editing) {
        // Two calls, because the targets are a separate resource — replacing
        // them is idempotent, so a retry after a failed first call cannot
        // duplicate anything.
        await graphsApi.update(editing.id, payload);
        await graphsApi.replaceTargetVocabulary(editing.id, { items });
        return;
      }

      // One call. `GraphCreate` carries the targets, so a new graph is never
      // briefly stored in the state that cannot be published.
      await graphsApi.create({ ...payload, target_vocabulary: items });
    },
    onSuccess: async () => {
      onOpenChange(false);
      await queryClient.invalidateQueries({ queryKey: ["graphs"] });
    },
  });

  const ready = title.trim() && prompt.trim() && parsed.problems.length === 0;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>{editing ? "Edit graph" : "New graph"}</DialogTitle>
          <DialogDescription>
            {step === "figures"
              ? "Step 1 of 2 — the chart your students will describe."
              : "Step 2 of 2 — the words it is marked on. A graph is published only once it has at least one required target term."}
          </DialogDescription>
        </DialogHeader>

        <form
          className="flex flex-col gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            // Enter in a text field submits a form. On the first step that
            // would create the graph with no targets and no chance to add
            // any, so the first step advances instead.
            if (!ready) return;
            if (step === "figures") setStep("targets");
            else save.mutate();
          }}
        >
          {step === "figures" ? (
            <>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="flex flex-col gap-1.5 sm:col-span-2">
                  <Label htmlFor="graph-title">Title</Label>
                  <Input
                    id="graph-title"
                    value={title}
                    maxLength={200}
                    placeholder="Rainfall by month"
                    onChange={(event) => setTitle(event.target.value)}
                  />
                </div>

                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="graph-type">Chart type</Label>
                  <Select
                    id="graph-type"
                    value={graphType}
                    onChange={(event) => setGraphType(event.target.value as GraphType)}
                  >
                    {TYPES.map((type) => (
                      <option key={type} value={type}>
                        {type.charAt(0).toUpperCase() + type.slice(1)}
                      </option>
                    ))}
                  </Select>
                </div>

                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="graph-difficulty">Difficulty</Label>
                  <Select
                    id="graph-difficulty"
                    value={difficulty}
                    onChange={(event) => setDifficulty(event.target.value as Difficulty)}
                  >
                    {DIFFICULTIES.map((level) => (
                      <option key={level} value={level}>
                        {level.charAt(0).toUpperCase() + level.slice(1)}
                      </option>
                    ))}
                  </Select>
                </div>
              </div>

              <div className="flex flex-col gap-1.5">
                <Label htmlFor="graph-prompt">What the student is asked to do</Label>
                <Textarea
                  id="graph-prompt"
                  value={prompt}
                  rows={2}
                  maxLength={1000}
                  placeholder="Describe the changes in rainfall over the year."
                  onChange={(event) => setPrompt(event.target.value)}
                />
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="graph-table">The figures</Label>
                  <Textarea
                    id="graph-table"
                    value={table}
                    rows={9}
                    className="font-mono text-xs"
                    placeholder={"Label, Rainfall\nJan, 42\nFeb, 51"}
                    onChange={(event) => setTable(event.target.value)}
                  />
                  <p className="text-muted-foreground text-xs text-pretty">
                    Paste straight from a spreadsheet, or type it: the first line names the series,
                    then one line per point. A blank cell stays blank rather than becoming zero.
                  </p>
                </div>

                <div className="flex flex-col gap-3">
                  <span className="text-sm font-medium">Preview</span>
                  <div className="h-56 rounded-lg border p-3">
                    <GraphChart
                      chartData={parsed.chartData}
                      graphType={graphType}
                      title={title || "Preview"}
                    />
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    <Input
                      value={xAxis}
                      aria-label="Horizontal axis label"
                      placeholder="X axis"
                      onChange={(event) => setXAxis(event.target.value)}
                    />
                    <Input
                      value={yAxis}
                      aria-label="Vertical axis label"
                      placeholder="Y axis"
                      onChange={(event) => setYAxis(event.target.value)}
                    />
                    <Input
                      value={unit}
                      aria-label="Unit"
                      placeholder="Unit"
                      onChange={(event) => setUnit(event.target.value)}
                    />
                  </div>
                </div>
              </div>

              {parsed.problems.length > 0 && table.trim() ? (
                <Alert variant="info">
                  <AlertTitle>The table is not usable yet</AlertTitle>
                  <AlertDescription>
                    <ul className="list-inside list-disc">
                      {parsed.problems.map((problem) => (
                        <li key={problem}>{problem}</li>
                      ))}
                    </ul>
                  </AlertDescription>
                </Alert>
              ) : null}

              <div className="flex flex-col gap-1.5">
                <Label htmlFor="graph-reference">Model description (optional)</Label>
                <Textarea
                  id="graph-reference"
                  value={reference}
                  rows={3}
                  maxLength={5000}
                  placeholder="Released to a student only after their attempt is marked."
                  onChange={(event) => setReference(event.target.value)}
                />
              </div>
            </>
          ) : (
            <TargetChooser
              chosen={chosen}
              onChange={setChosen}
              // The figures as they stand in the textarea, not as they were
              // last saved — the suggestions are about the graph being made.
              series={parsed.chartData.datasets.map((dataset) => dataset.data)}
              graphType={graphType}
            />
          )}

          {save.isError ? (
            <Alert variant="destructive">
              <AlertDescription>{errorMessage(save.error)}</AlertDescription>
            </Alert>
          ) : null}

          <DialogFooter>
            {step === "figures" ? (
              <>
                <DialogClose asChild>
                  <Button type="button" variant="outline">
                    Cancel
                  </Button>
                </DialogClose>
                <Button type="button" disabled={!ready} onClick={() => setStep("targets")}>
                  Next: target words
                </Button>
              </>
            ) : (
              <>
                <Button type="button" variant="outline" onClick={() => setStep("figures")}>
                  Back
                </Button>
                <Button type="submit" disabled={!ready || save.isPending}>
                  {save.isPending ? "Saving…" : editing ? "Save changes" : "Create graph"}
                </Button>
              </>
            )}
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
