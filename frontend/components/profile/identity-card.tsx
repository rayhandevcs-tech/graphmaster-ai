"use client";

import { useState } from "react";
import { Check, Pencil, X } from "lucide-react";

import { errorMessage, queryKeys, usersApi } from "@/lib/api";
import { useAuth } from "@/lib/auth/context";
import { NAME_MAX, NAME_MIN } from "@/lib/auth/validation";
import { ROLE_LABELS } from "@/lib/auth/roles";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { formatLongDate } from "@/lib/format";
import type { UserProfile } from "@/types/api";

/**
 * Name, email, role and when the account was created.
 *
 * Only the name is editable, and the card says why the others are not rather
 * than rendering disabled inputs. A greyed-out field invites a student to
 * click it and work out for themselves that nothing happens; a line of text
 * saying an administrator changes your class is an answer.
 *
 * Editing is a mode rather than an always-live field. An input that saves as
 * you type has no moment at which the change is committed, which is precisely
 * what you want for a draft answer and precisely what you do not want for the
 * name that appears on a leaderboard.
 */
export function IdentityCard({ user }: { user: UserProfile }) {
  const { applyUser } = useAuth();
  const queryClient = useQueryClient();

  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(user.full_name);
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: (fullName: string) => usersApi.updateMe({ full_name: fullName }),
    onSuccess: (profile) => {
      applyUser(profile);
      queryClient.setQueryData(queryKeys.currentUser(), profile);
      setEditing(false);
      setError(null);
    },
  });

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = name.trim();

    if (trimmed.length < NAME_MIN || trimmed.length > NAME_MAX) {
      setError(`Your name needs between ${NAME_MIN} and ${NAME_MAX} characters.`);
      return;
    }
    setError(null);
    save.mutate(trimmed);
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Your details</CardTitle>
        <CardDescription>
          Your name is what appears on the leaderboard and in your teacher&rsquo;s reports.
        </CardDescription>
      </CardHeader>

      <CardContent className="flex flex-col gap-6">
        {save.isError ? (
          <Alert variant="destructive">
            <AlertTitle>Your name was not saved</AlertTitle>
            <AlertDescription>{errorMessage(save.error)}</AlertDescription>
          </Alert>
        ) : null}

        {editing ? (
          <form onSubmit={submit} className="flex flex-col gap-3">
            <div className="flex flex-col gap-2">
              <Label htmlFor="full_name">Full name</Label>
              <Input
                id="full_name"
                name="full_name"
                autoComplete="name"
                autoFocus
                value={name}
                onChange={(event) => setName(event.target.value)}
                aria-invalid={Boolean(error)}
                aria-describedby={error ? "full_name-error" : undefined}
              />
              {error ? (
                <p id="full_name-error" className="text-destructive text-sm">
                  {error}
                </p>
              ) : null}
            </div>

            <div className="flex gap-2">
              <Button type="submit" size="sm" disabled={save.isPending}>
                {save.isPending ? <Spinner label="Saving" /> : <Check aria-hidden />}
                Save
              </Button>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={() => {
                  setName(user.full_name);
                  setError(null);
                  setEditing(false);
                }}
              >
                <X aria-hidden />
                Cancel
              </Button>
            </div>
          </form>
        ) : (
          <Row label="Full name" value={user.full_name}>
            <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
              <Pencil aria-hidden />
              Edit
            </Button>
          </Row>
        )}

        <dl className="flex flex-col gap-4">
          <Detail term="Email" description={user.email} note="Contact your teacher to change it." />
          <Detail term="Role" description={ROLE_LABELS[user.role]} />
          <Detail
            term="Class"
            description={user.class_id ? "Enrolled" : "Not enrolled"}
            note={
              user.class_id
                ? "An administrator manages class membership."
                : "Ask your teacher for a class code."
            }
          />
          <Detail term="Member since" description={formatLongDate(user.created_at)} />
        </dl>
      </CardContent>
    </Card>
  );
}

function Row({
  label,
  value,
  children,
}: {
  label: string;
  value: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div className="flex min-w-0 flex-col">
        <span className="text-muted-foreground text-xs tracking-wide uppercase">{label}</span>
        <span className="truncate font-medium">{value}</span>
      </div>
      {children}
    </div>
  );
}

function Detail({ term, description, note }: { term: string; description: string; note?: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-muted-foreground text-xs tracking-wide uppercase">{term}</dt>
      <dd className="flex flex-wrap items-baseline gap-x-2">
        <span className="font-medium break-all">{description}</span>
        {note ? <span className="text-muted-foreground text-xs">{note}</span> : null}
      </dd>
    </div>
  );
}
