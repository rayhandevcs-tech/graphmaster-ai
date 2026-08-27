"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, Plus } from "lucide-react";

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
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { assignmentsApi, classesApi, errorMessage, graphsApi, queryKeys } from "@/lib/api";

/**
 * Set a graph as work for one section.
 *
 * Four fields, two of them prefilled, because this is the thing a teacher does
 * between lessons and every extra decision is a reason to do it later. The
 * title follows the chosen graph until the teacher types something of their
 * own, at which point it stops — the common path is *pick, pick, done* and the
 * custom path is never fought.
 *
 * Instructions are collapsed. Most set work needs none, and an open textarea
 * reads as a field that has to be filled.
 *
 * Only published graphs are offered. The server refuses a draft — a student
 * cannot open one — and a picker that lists something the server will reject
 * is a trap rather than a convenience.
 */
export function SetWorkDialog({
  classId,
  graphId,
  trigger,
}: {
  /** Preselected when the dialog is opened from inside one section. */
  classId?: string;
  /** Preselected when it is opened from a graph. */
  graphId?: string;
  trigger?: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const queryClient = useQueryClient();

  const classes = useQuery({
    queryKey: queryKeys.classes({ page_size: 100, is_active: true }),
    queryFn: () => classesApi.list({ page_size: 100, is_active: true }),
    enabled: open,
  });

  const graphs = useQuery({
    queryKey: queryKeys.graphs({ page_size: 100 }),
    queryFn: () => graphsApi.list({ page_size: 100 }),
    enabled: open,
  });

  const [form, setForm] = useState({
    classId: classId ?? "",
    graphId: graphId ?? "",
    title: "",
    dueAt: "",
    instructions: "",
  });
  // Whether the teacher has taken the title over. Tracked separately so
  // changing the graph keeps updating a prefilled title but never overwrites
  // one they wrote.
  const [titleTouched, setTitleTouched] = useState(false);
  const [showInstructions, setShowInstructions] = useState(false);

  const classOptions = classes.data?.items ?? [];
  const graphOptions = (graphs.data?.items ?? []).filter((graph) => graph.is_published);
  const selectedClass = (classId ?? form.classId) || classOptions[0]?.id || "";

  function chooseGraph(nextId: string) {
    const graph = graphOptions.find((candidate) => candidate.id === nextId);
    setForm((current) => ({
      ...current,
      graphId: nextId,
      title: titleTouched ? current.title : (graph?.title ?? current.title),
    }));
  }

  const create = useMutation({
    mutationFn: () =>
      assignmentsApi.create({
        class_id: selectedClass,
        graph_id: form.graphId,
        title: form.title.trim(),
        // A blank textarea is "no instructions", not an empty string sitting
        // in the database waiting to render as a stray blank line.
        instructions: form.instructions.trim() || null,
        // The input gives a local date; the API stores an instant. End of day
        // is what "due Friday" means to everyone who is not a computer.
        due_at: form.dueAt ? new Date(`${form.dueAt}T23:59:59`).toISOString() : null,
      }),
    onSuccess: async () => {
      setOpen(false);
      setForm({
        classId: classId ?? "",
        graphId: graphId ?? "",
        title: "",
        dueAt: "",
        instructions: "",
      });
      setTitleTouched(false);
      setShowInstructions(false);
      await queryClient.invalidateQueries({ queryKey: ["assignments"] });
    },
  });

  const ready = Boolean(selectedClass && form.graphId && form.title.trim());

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) create.reset();
      }}
    >
      <DialogTrigger asChild>
        {trigger ?? (
          <Button size="sm">
            <Plus aria-hidden />
            Set work
          </Button>
        )}
      </DialogTrigger>

      <DialogContent>
        <DialogHeader>
          <DialogTitle>Set work</DialogTitle>
          <DialogDescription>
            Show the graph in your lesson. Students describe it here, in their own words, and the
            system marks the description.
          </DialogDescription>
        </DialogHeader>

        <form
          className="flex flex-col gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (ready) create.mutate();
          }}
        >
          {classId ? null : (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="work-class">Section</Label>
              <Select
                id="work-class"
                value={selectedClass}
                onChange={(event) =>
                  setForm((current) => ({ ...current, classId: event.target.value }))
                }
              >
                {classOptions.length === 0 ? <option value="">No classes yet</option> : null}
                {classOptions.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.name}
                  </option>
                ))}
              </Select>
            </div>
          )}

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="work-graph">Graph</Label>
            <Select
              id="work-graph"
              value={form.graphId}
              onChange={(event) => chooseGraph(event.target.value)}
            >
              <option value="">Choose a graph…</option>
              {graphOptions.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.title}
                </option>
              ))}
            </Select>
            {graphs.isSuccess && graphOptions.length === 0 ? (
              <p className="text-muted-foreground text-xs">
                No published graphs yet. A draft cannot be set as work — students cannot open one.
              </p>
            ) : null}
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="work-title">Title</Label>
            <Input
              id="work-title"
              value={form.title}
              maxLength={200}
              placeholder="Week 3 · rainfall"
              onChange={(event) => {
                setTitleTouched(true);
                setForm((current) => ({ ...current, title: event.target.value }));
              }}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="work-due">Due date (optional)</Label>
            <Input
              id="work-due"
              type="date"
              value={form.dueAt}
              onChange={(event) =>
                setForm((current) => ({ ...current, dueAt: event.target.value }))
              }
            />
            <p className="text-muted-foreground text-xs">
              A deadline is a plan, not a lock. Work handed in afterwards is still accepted and
              still scores the same.
            </p>
          </div>

          <div className="flex flex-col gap-2">
            <button
              type="button"
              aria-expanded={showInstructions}
              aria-controls="work-instructions-panel"
              onClick={() => setShowInstructions((current) => !current)}
              className="text-muted-foreground hover:text-foreground focus-visible:ring-ring inline-flex min-h-11 items-center gap-1.5 self-start rounded-md text-sm font-medium focus-visible:ring-2 focus-visible:outline-none sm:min-h-8"
            >
              <ChevronDown
                className={
                  showInstructions
                    ? "size-4 rotate-180 transition-transform"
                    : "size-4 transition-transform"
                }
                aria-hidden
              />
              Add instructions
            </button>
            <div id="work-instructions-panel" hidden={!showInstructions}>
              <Textarea
                value={form.instructions}
                rows={3}
                maxLength={4000}
                aria-label="Instructions"
                placeholder="What you said in the lesson — the slide, the handout, the caveat."
                onChange={(event) =>
                  setForm((current) => ({ ...current, instructions: event.target.value }))
                }
              />
            </div>
          </div>

          {create.isError ? (
            <Alert variant="destructive">
              <AlertDescription>{errorMessage(create.error)}</AlertDescription>
            </Alert>
          ) : null}

          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="outline">
                Cancel
              </Button>
            </DialogClose>
            <Button type="submit" disabled={!ready || create.isPending}>
              {create.isPending ? "Setting…" : "Set work"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
