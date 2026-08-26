import Link from "next/link";
import { ArrowUp } from "lucide-react";

import { AvatarCharacter, avatarCodeFromUrl } from "@/components/avatars/character";
import { RankBadge } from "@/components/gamification/rank-medal";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { LeaderboardEntryOut, LeaderboardPosition } from "@/types/api";

/**
 * The student's own standing, pinned where they can always see it.
 *
 * This is the most important element on the screen. `GET /leaderboard/me`
 * returns the caller's rank even when it falls outside the visible page, and a
 * board that makes a student scroll to find themselves — or cannot show them
 * at all — is demotivating in exactly the way this product exists not to be.
 *
 * The distance to the next rank is the motivational payload, and it is
 * *computed from the entry above* rather than estimated. When there is no
 * entry above — rank 1 — or the student is unranked, it is omitted rather
 * than faked.
 *
 * An unranked student is invited, not shown an empty row: they have not lost
 * anything, they have not started.
 */
export function YourRank({
  position,
  above,
  className,
}: {
  position: LeaderboardPosition;
  /** The entry one rank above, when it is on the loaded page. */
  above: LeaderboardEntryOut | null;
  className?: string;
}) {
  const entry = position.entry;

  return (
    <div
      className={cn(
        "bg-card/95 supports-[backdrop-filter]:bg-card/80 sticky bottom-20 z-20 rounded-xl border p-3 shadow-lg backdrop-blur md:bottom-4",
        className,
      )}
    >
      {entry ? (
        <div className="flex items-center gap-3">
          <RankBadge rank={entry.rank} />
          <AvatarCharacter
            code={avatarCodeFromUrl(entry.avatar_url) ?? "girl_default"}
            expression="happy"
            className="size-10 shrink-0"
          />
          <div className="flex min-w-0 flex-1 flex-col">
            <span className="text-sm font-semibold">
              You · rank {entry.rank}
              <span className="text-muted-foreground font-normal">
                {" "}
                of {position.total_ranked.toLocaleString()}
              </span>
            </span>
            <span className="text-muted-foreground text-xs">
              Level {entry.level} · {entry.xp.toLocaleString()} XP this period
              {above ? ` · ${(above.xp - entry.xp).toLocaleString()} XP to rank ${above.rank}` : ""}
            </span>
          </div>
          {above ? <ArrowUp className="text-primary size-4 shrink-0" aria-hidden /> : null}
        </div>
      ) : (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-pretty">
            <span className="font-semibold">You are not on this board yet.</span>{" "}
            <span className="text-muted-foreground">
              One marked description in this period puts you on it.
            </span>
          </p>
          <Button asChild size="sm">
            <Link href="/practice">Practise</Link>
          </Button>
        </div>
      )}
    </div>
  );
}
