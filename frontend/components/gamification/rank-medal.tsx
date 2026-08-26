import { cn } from "@/lib/utils";

/**
 * First, second and third, as a ring around a character.
 *
 * Lives under `components/gamification/` because it paints in gold, which is
 * reserved (`tests/design-tokens.test.ts`). That reservation is the reason
 * first place *is* gold: the top of the board and the top reward tier are the
 * same colour on purpose, so a student who has seen a crown recognises what a
 * gold ring means without being told.
 *
 * The rank is always written out beside the ring. A medal colour alone tells a
 * colour-blind student nothing, and a screen reader nothing at all.
 */
const RING: Record<number, string> = {
  1: "ring-gold",
  2: "ring-silver",
  3: "ring-bronze",
};

export function medalRing(rank: number): string {
  return RING[rank] ?? "ring-border";
}

export function RankBadge({ rank, className }: { rank: number; className?: string }) {
  const medal = rank <= 3;

  return (
    <span
      className={cn(
        "inline-flex min-w-8 items-center justify-center rounded-full px-2 py-0.5 text-xs font-semibold tabular-nums",
        medal ? "text-background" : "bg-muted text-muted-foreground",
        rank === 1 && "bg-gold",
        rank === 2 && "bg-silver",
        rank === 3 && "bg-bronze",
        className,
      )}
    >
      <span aria-hidden>{rank}</span>
      <span className="sr-only">Rank {rank}</span>
    </span>
  );
}
