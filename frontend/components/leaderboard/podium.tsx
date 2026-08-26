import { AvatarCharacter, avatarCodeFromUrl } from "@/components/avatars/character";
import { medalRing } from "@/components/gamification/rank-medal";
import { Reveal } from "@/components/motion/reveal";
import { cn } from "@/lib/utils";
import type { LeaderboardEntryOut } from "@/types/api";

/**
 * The top three, arranged the way a podium is.
 *
 * **The DOM order is 1, 2, 3 and the visual order is 2, 1, 3.** First place is
 * centred and raised with CSS `order`, so a screen reader and the tab sequence
 * still receive the ranking in rank order. Building the podium in visual order
 * is the classic bug here: it reads aloud as "second, first, third" and every
 * keyboard user meets the runner-up first.
 *
 * The characters are the drawn ones, resolved from each entry's stored avatar
 * path. Those SVG files have never existed, so a board built on `<img>` would
 * be twenty sets of initials — which is exactly what this screen must not be.
 *
 * No reward tier appears here, and none ever will (FR-7.6). What a board
 * publishes is rank, level and the XP earned in the period.
 */
export function Podium({ entries }: { entries: LeaderboardEntryOut[] }) {
  const top = entries.slice(0, 3);
  if (top.length === 0) return null;

  // Second, first, third — the visual arrangement, applied as CSS order only.
  const VISUAL_ORDER = ["order-2 sm:order-1", "order-1 sm:order-2", "order-3"];
  const HEIGHT = ["pt-6", "pt-0", "pt-8"];

  return (
    <ol className="flex items-end justify-center gap-2 sm:gap-6">
      {top.map((entry, index) => (
        <li
          key={entry.user_id}
          className={cn(
            "flex min-w-0 flex-1 justify-center sm:flex-none",
            VISUAL_ORDER[entry.rank - 1] ?? "order-3",
            HEIGHT[entry.rank - 1] ?? "pt-8",
          )}
        >
          <Reveal delay={0.06 * index}>
            <Step entry={entry} />
          </Reveal>
        </li>
      ))}
    </ol>
  );
}

function Step({ entry }: { entry: LeaderboardEntryOut }) {
  const first = entry.rank === 1;

  return (
    <div className="flex w-24 flex-col items-center gap-2 text-center sm:w-32">
      <div className="relative">
        <AvatarCharacter
          code={avatarCodeFromUrl(entry.avatar_url) ?? "girl_default"}
          expression={first ? "cheer" : "happy"}
          className={cn(
            "ring-offset-background rounded-full ring-4 ring-offset-2",
            first ? "size-20 sm:size-24" : "size-16 sm:size-20",
            medalRing(entry.rank),
          )}
        />
        <span
          className={cn(
            "bg-card absolute -bottom-1 left-1/2 -translate-x-1/2 rounded-full border px-2 py-0.5",
            "text-xs font-semibold tabular-nums",
          )}
        >
          <span aria-hidden>{entry.rank}</span>
          <span className="sr-only">Rank {entry.rank}</span>
        </span>
      </div>

      <div className="flex min-w-0 flex-col gap-0.5">
        <span
          className={cn("truncate text-sm font-semibold", entry.is_you && "text-primary")}
          title={entry.full_name}
        >
          {entry.full_name}
          {entry.is_you ? <span className="sr-only"> (you)</span> : null}
        </span>
        <span className="text-muted-foreground text-xs tabular-nums">
          {entry.xp.toLocaleString()} XP
        </span>
        <span className="text-muted-foreground text-xs">Level {entry.level}</span>
      </div>
    </div>
  );
}
