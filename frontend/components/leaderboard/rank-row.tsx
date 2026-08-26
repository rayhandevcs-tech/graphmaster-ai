import { AvatarCharacter, avatarCodeFromUrl } from "@/components/avatars/character";
import { RankBadge } from "@/components/gamification/rank-medal";
import { cn } from "@/lib/utils";
import type { LeaderboardEntryOut } from "@/types/api";

/**
 * One place on the board, from fourth down.
 *
 * 56px tall, which is the comfortable end of the touch range rather than the
 * minimum — this is a list a student scrolls with a thumb looking for one
 * name, and rows that are merely tappable are still tiring to scan.
 *
 * The student's own row is tinted and says "you" in text as well as in colour.
 * It is the only row on the board a reader is looking for.
 */
export function RankRow({ entry }: { entry: LeaderboardEntryOut }) {
  return (
    <li
      className={cn(
        "flex min-h-14 items-center gap-3 rounded-lg px-3 py-2",
        entry.is_you ? "bg-primary/10 ring-primary/30 ring-1" : "hover:bg-muted/40",
      )}
    >
      <RankBadge rank={entry.rank} />

      <AvatarCharacter
        code={avatarCodeFromUrl(entry.avatar_url) ?? "girl_default"}
        className="size-9 shrink-0"
      />

      <span className="flex min-w-0 flex-1 flex-col">
        <span className="truncate text-sm font-medium">
          {entry.full_name}
          {entry.is_you ? <span className="text-primary font-semibold"> · you</span> : null}
        </span>
        <span className="text-muted-foreground text-xs">Level {entry.level}</span>
      </span>

      <span className="shrink-0 text-sm font-semibold tabular-nums">
        {entry.xp.toLocaleString()}
        <span className="text-muted-foreground ml-1 text-xs font-normal">XP</span>
      </span>
    </li>
  );
}
