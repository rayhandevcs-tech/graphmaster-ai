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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { errorMessage, vocabularyApi } from "@/lib/api";
import type { VocabularyCategoryOut, VocabularyItemOut } from "@/types/api";

/**
 * Adding or editing one term.
 *
 * Two of this product's quieter invariants live in this form.
 *
 * **`is_phrase` is derived from the term and never sent** (CLAUDE.md rule 13).
 * There is no control for it; the badge on the row is a reading of what the
 * server decided. A checkbox here would let a teacher mark "level off" as a
 * single word and silently stop it ever matching.
 *
 * **Editing a term does not re-derive a hand-set lemma** — also rule 13. So
 * the lemma is an explicit field rather than a hidden one, and when a teacher
 * changes the term while a lemma is set, the form says out loud that the lemma
 * is staying as it is. Silently re-deriving it is how a curated term stops
 * being detected without anyone touching the thing that broke.
 */
export function TermForm({
  open,
  onOpenChange,
  categories,
  editing,
}: {
  open: boolean;
  onOpenChange: (next: boolean) => void;
  categories: VocabularyCategoryOut[];
  /** `null` opens the form empty, for a new term. */
  editing: VocabularyItemOut | null;
}) {
  const queryClient = useQueryClient();
  const [term, setTerm] = useState(editing?.term ?? "");
  const [lemma, setLemma] = useState(editing?.lemma ?? "");
  const [category, setCategory] = useState(editing?.category_code ?? categories[0]?.code ?? "");
  const [weight, setWeight] = useState(String(editing?.weight ?? 1));

  const save = useMutation({
    mutationFn: async () => {
      const trimmedLemma = lemma.trim();
      if (editing) {
        return vocabularyApi.update(editing.id, {
          term: term.trim(),
          category_code: category,
          weight: Number(weight),
          // Sent only when the teacher typed one. Omitted, the server keeps
          // whatever is already stored rather than deriving a new one.
          lemma: trimmedLemma || null,
        });
      }
      return vocabularyApi.create({
        term: term.trim(),
        category_code: category,
        weight: Number(weight),
        lemma: trimmedLemma || null,
      });
    },
    onSuccess: async () => {
      onOpenChange(false);
      await queryClient.invalidateQueries({ queryKey: ["vocabulary"] });
    },
  });

  const lemmaKept = Boolean(editing && lemma.trim() && term.trim() !== editing.term);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{editing ? "Edit term" : "Add a term"}</DialogTitle>
          <DialogDescription>
            Terms are matched by lemma and by surface form, so inflections and nominalisations of
            what you type are detected too.
          </DialogDescription>
        </DialogHeader>

        <form
          className="flex flex-col gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (term.trim()) save.mutate();
          }}
        >
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="term">Term</Label>
            <Input
              id="term"
              value={term}
              autoFocus
              maxLength={100}
              placeholder="level off"
              onChange={(event) => setTerm(event.target.value)}
            />
            <p className="text-muted-foreground text-xs">
              A term with a space in it is stored as a phrase. That is worked out from what you
              type, not set here.
            </p>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="category">Category</Label>
            <Select
              id="category"
              value={category}
              onChange={(event) => setCategory(event.target.value)}
            >
              {categories.map((option) => (
                <option key={option.code} value={option.code}>
                  {option.name}
                </option>
              ))}
            </Select>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="lemma">Lemma (optional)</Label>
            <Input
              id="lemma"
              value={lemma}
              maxLength={100}
              placeholder="Left blank, the server works one out"
              onChange={(event) => setLemma(event.target.value)}
            />
            {lemmaKept ? (
              <p className="text-secondary text-xs text-pretty">
                The lemma stays as “{lemma.trim()}”. Changing the term does not work out a new one —
                clear this field if you want it derived again.
              </p>
            ) : (
              <p className="text-muted-foreground text-xs">
                Set one when the automatic lemma is wrong — “plateaued” becomes “plateaue”, for
                instance.
              </p>
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="weight">Suggestion priority</Label>
            <Input
              id="weight"
              type="number"
              min={0.1}
              max={9.99}
              step={0.1}
              value={weight}
              aria-describedby="weight-help"
              onChange={(event) => setWeight(event.target.value)}
            />
            {/* This field was labelled "Weight" and offered no explanation at
                all, which read as a score multiplier. It is not one — see the
                note in `vocabulary-manager.tsx`. */}
            <p id="weight-help" className="text-muted-foreground text-xs text-pretty">
              Lowest first: a student who missed several words is pointed at the one with the
              smallest number, so leave the basic terms low and the ambitious ones high.{" "}
              <strong className="font-medium">It does not change anyone&rsquo;s score.</strong>
            </p>
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
            <Button type="submit" disabled={!term.trim() || save.isPending}>
              {save.isPending ? "Saving…" : editing ? "Save changes" : "Add term"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
