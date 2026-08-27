"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Pencil } from "lucide-react";

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
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { assignmentsApi, errorMessage } from "@/lib/api";
import type { AssignmentSummary } from "@/types/api";

/**
 * Change what was set, but not *what it asks*.
 *
 * The graph and the section are absent from this form on purpose, and the API
 * refuses them too: moving an assignment to a different graph would silently
 * change what the submissions already filed against it were answering.
 *
 * Closing it is a switch rather than a delete. The work stays in the teacher's
 * list with its history intact and simply stops appearing on the students'.
 */
export function EditWorkDialog({ assignment }: { assignment: AssignmentSummary }) {
  const [open, setOpen] = useState(false);
  const queryClient = useQueryClient();

  const [form, setForm] = useState({
    title: assignment.title,
    instructions: assignment.instructions ?? "",
    // `<input type="date">` wants a local YYYY-MM-DD, not an instant.
    dueAt: assignment.due_at ? toDateInput(assignment.due_at) : "",
    isActive: assignment.is_active,
  });

  const save = useMutation({
    mutationFn: () =>
      assignmentsApi.update(assignment.id, {
        title: form.title.trim(),
        instructions: form.instructions.trim() || null,
        due_at: form.dueAt ? new Date(`${form.dueAt}T23:59:59`).toISOString() : null,
        is_active: form.isActive,
      }),
    onSuccess: async () => {
      setOpen(false);
      await queryClient.invalidateQueries({ queryKey: ["assignments"] });
    },
  });

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) save.reset();
      }}
    >
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <Pencil aria-hidden />
          Edit
        </Button>
      </DialogTrigger>

      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit this assignment</DialogTitle>
          <DialogDescription>
            The graph cannot be changed — the work already handed in was written about this one.
          </DialogDescription>
        </DialogHeader>

        <form
          className="flex flex-col gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (form.title.trim()) save.mutate();
          }}
        >
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="edit-work-title">Title</Label>
            <Input
              id="edit-work-title"
              value={form.title}
              maxLength={200}
              onChange={(event) =>
                setForm((current) => ({ ...current, title: event.target.value }))
              }
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="edit-work-due">Due date</Label>
            <Input
              id="edit-work-due"
              type="date"
              value={form.dueAt}
              onChange={(event) =>
                setForm((current) => ({ ...current, dueAt: event.target.value }))
              }
            />
            <p className="text-muted-foreground text-xs">
              Clear the field for work with no deadline.
            </p>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="edit-work-instructions">Instructions</Label>
            <Textarea
              id="edit-work-instructions"
              value={form.instructions}
              rows={3}
              maxLength={4000}
              onChange={(event) =>
                setForm((current) => ({ ...current, instructions: event.target.value }))
              }
            />
          </div>

          <div className="flex items-start justify-between gap-4 rounded-lg border p-3">
            <div className="flex flex-col gap-0.5">
              <span className="text-sm font-medium">Open to students</span>
              <p className="text-muted-foreground text-xs text-pretty">
                Closing it hides the task from your students. Everything they already submitted
                stays exactly as it is.
              </p>
            </div>
            <Switch
              label="Open to students"
              checked={form.isActive}
              onCheckedChange={(next) => setForm((current) => ({ ...current, isActive: next }))}
            />
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
            <Button type="submit" disabled={!form.title.trim() || save.isPending}>
              {save.isPending ? "Saving…" : "Save"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/** An instant to the `YYYY-MM-DD` a date input wants, in the reader's zone. */
function toDateInput(iso: string): string {
  const when = new Date(iso);
  if (Number.isNaN(when.getTime())) return "";
  const month = `${when.getMonth() + 1}`.padStart(2, "0");
  const day = `${when.getDate()}`.padStart(2, "0");
  return `${when.getFullYear()}-${month}-${day}`;
}
