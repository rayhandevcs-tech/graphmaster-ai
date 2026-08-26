"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Lock } from "lucide-react";

import { avatarsApi, errorMessage, queryKeys } from "@/lib/api";
import { useAuth } from "@/lib/auth/context";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { AvatarWithLock, UUID } from "@/types/api";

/**
 * Choosing the character that celebrates your results.
 *
 * The catalogue is the caller's own — `GET /avatars` returns their gender's
 * set with each entry marked locked or unlocked against their level — so a
 * locked avatar is shown, not hidden. Something to work towards is the point
 * of a level gate; a catalogue that silently omits what you have not earned
 * gives a student no reason to earn it.
 *
 * A locked tile is a disabled button rather than an unlabelled dimmed image.
 * It says which level unlocks it, and a screen reader is told the same thing
 * the tint says to everyone else.
 */
export function AvatarPicker({
  onSelected,
  className,
}: {
  /** Called after the server has confirmed the change. */
  onSelected?: (avatarId: UUID) => void;
  className?: string;
}) {
  const { applyUser } = useAuth();
  const queryClient = useQueryClient();
  const [pendingId, setPendingId] = useState<UUID | null>(null);

  const avatars = useQuery({
    queryKey: queryKeys.avatars(),
    queryFn: () => avatarsApi.forMe(),
  });

  const select = useMutation({
    mutationFn: (avatarId: UUID) => avatarsApi.select({ avatar_id: avatarId }),
    onSuccess: async (profile, avatarId) => {
      // The response is a fresh profile, so the header's avatar and the
      // catalogue's `is_selected` both update from one round trip.
      applyUser(profile);
      queryClient.setQueryData(queryKeys.currentUser(), profile);
      await queryClient.invalidateQueries({ queryKey: queryKeys.avatars() });
      onSelected?.(avatarId);
    },
    onSettled: () => setPendingId(null),
  });

  if (avatars.isPending) {
    return (
      <div className={cn("grid grid-cols-3 gap-3 sm:grid-cols-4", className)}>
        {[0, 1, 2, 3, 4, 5].map((index) => (
          <Skeleton key={index} className="aspect-square rounded-xl" />
        ))}
      </div>
    );
  }

  if (avatars.isError) {
    return (
      <Alert variant="destructive">
        <AlertTitle>The avatars could not be loaded</AlertTitle>
        <AlertDescription>{errorMessage(avatars.error)}</AlertDescription>
      </Alert>
    );
  }

  return (
    <div className={cn("flex flex-col gap-3", className)}>
      {select.isError ? (
        <Alert variant="destructive">
          <AlertTitle>That avatar could not be saved</AlertTitle>
          <AlertDescription>{errorMessage(select.error)}</AlertDescription>
        </Alert>
      ) : null}

      <ul className="grid grid-cols-3 gap-3 sm:grid-cols-4">
        {avatars.data.map((avatar) => (
          <li key={avatar.id}>
            <AvatarTile
              avatar={avatar}
              busy={pendingId === avatar.id}
              onChoose={() => {
                setPendingId(avatar.id);
                select.mutate(avatar.id);
              }}
            />
          </li>
        ))}
      </ul>
    </div>
  );
}

function AvatarTile({
  avatar,
  busy,
  onChoose,
}: {
  avatar: AvatarWithLock;
  busy: boolean;
  onChoose: () => void;
}) {
  const locked = !avatar.is_unlocked;

  return (
    <button
      type="button"
      disabled={locked || busy}
      aria-pressed={avatar.is_selected}
      onClick={onChoose}
      className={cn(
        "group relative flex w-full flex-col items-center gap-2 rounded-xl border p-3 transition-all",
        locked
          ? "cursor-not-allowed opacity-60"
          : "hover:border-primary/50 hover:shadow-sm active:scale-[0.98]",
        avatar.is_selected && "border-primary bg-primary/5 ring-primary/30 ring-2",
        busy && "opacity-70",
      )}
    >
      <Avatar className="size-14">
        <AvatarImage src={avatar.image_url} alt="" />
        <AvatarFallback>{avatar.name.slice(0, 2).toUpperCase()}</AvatarFallback>
      </Avatar>

      <span className="text-xs leading-tight font-medium text-balance">{avatar.name}</span>

      {locked ? (
        <span className="text-muted-foreground flex items-center gap-1 text-[0.6875rem]">
          <Lock className="size-3" aria-hidden />
          Level {avatar.unlock_level}
        </span>
      ) : null}

      {avatar.is_selected ? (
        <span className="bg-primary text-primary-foreground absolute -top-1.5 -right-1.5 flex size-5 items-center justify-center rounded-full">
          <Check className="size-3" aria-hidden />
        </span>
      ) : null}

      <span className="sr-only">
        {avatar.is_selected
          ? " — your current avatar"
          : locked
            ? ` — locked until level ${avatar.unlock_level}`
            : ""}
      </span>
    </button>
  );
}
