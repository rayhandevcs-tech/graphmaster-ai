"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";

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
import { Alert, AlertDescription } from "@/components/ui/alert";
import { classesApi, errorMessage } from "@/lib/api";

/**
 * A class, created where a teacher first needs one.
 *
 * Every teaching screen is scoped to a class, so a teacher with none has
 * nowhere to stand. Rather than send them to a settings page they have not
 * found yet, the empty state on the dashboard creates one.
 *
 * The join code is left to the server. A teacher inventing one picks something
 * memorable and therefore guessable, and the field would be a decision to make
 * before the first useful thing happens.
 */
export function CreateClassDialog({ trigger }: { trigger?: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const queryClient = useQueryClient();

  const create = useMutation({
    mutationFn: () => classesApi.create({ name: name.trim() }),
    onSuccess: async () => {
      setOpen(false);
      setName("");
      await queryClient.invalidateQueries({ queryKey: ["classes"] });
    },
  });

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
            New class
          </Button>
        )}
      </DialogTrigger>

      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create a class</DialogTitle>
          <DialogDescription>
            Students join with a code, which is generated for you once the class exists.
          </DialogDescription>
        </DialogHeader>

        <form
          className="flex flex-col gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (name.trim()) create.mutate();
          }}
        >
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="class-name">Class name</Label>
            <Input
              id="class-name"
              value={name}
              autoFocus
              maxLength={100}
              placeholder="Year 10 English"
              onChange={(event) => setName(event.target.value)}
            />
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
            <Button type="submit" disabled={!name.trim() || create.isPending}>
              {create.isPending ? "Creating…" : "Create class"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
