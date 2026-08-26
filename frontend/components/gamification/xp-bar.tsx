import { Progress } from "@/components/ui/progress";

/**
 * Progress through the current level.
 *
 * The gold is the point: it is used by the crown tier, this bar and the
 * level-up moment, and nowhere else in the product. A gold button anywhere
 * would spend the colour that makes those three feel like rewards.
 */
export function XpBar({
  level,
  xpIntoLevel,
  xpForNextLevel,
  isMaxLevel,
}: {
  level: number;
  xpIntoLevel: number;
  xpForNextLevel: number;
  isMaxLevel: boolean;
}) {
  const remaining = Math.max(xpForNextLevel - xpIntoLevel, 0);

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-sm font-medium">Level {level}</span>
        <span className="text-muted-foreground text-xs tabular-nums">
          {isMaxLevel
            ? "Top level reached"
            : `${xpIntoLevel.toLocaleString()} / ${xpForNextLevel.toLocaleString()} XP`}
        </span>
      </div>

      <Progress
        // At the cap there is no next level to fill towards, and a bar frozen
        // part-way would read as progress that has stalled.
        value={isMaxLevel ? 1 : xpIntoLevel}
        max={isMaxLevel ? 1 : xpForNextLevel}
        label={`Progress through level ${level}`}
        valueText={
          isMaxLevel
            ? "Top level reached"
            : `${xpIntoLevel.toLocaleString()} of ${xpForNextLevel.toLocaleString()} XP into level ${level}`
        }
        barClassName="bg-gold"
      />

      {isMaxLevel ? null : (
        <p className="text-muted-foreground text-xs">
          {remaining.toLocaleString()} XP to level {level + 1}
        </p>
      )}
    </div>
  );
}
