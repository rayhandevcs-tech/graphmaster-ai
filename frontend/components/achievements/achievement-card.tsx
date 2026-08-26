import { Check, Lock } from "lucide-react";

import { Progress } from "@/components/ui/progress";
import { formatLongDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { AchievementOut } from "@/types/api";

/**
 * One achievement, unlocked or not.
 *
 * A locked one shows its distance — "7 of 10" — rather than being greyed out
 * and left at that. A visible distance is what makes a catalogue motivating
 * instead of decorative, and it is the reason the API sends progress for
 * locked entries at all.
 *
 * The gendered crown pair never appears here locked: the server omits the one
 * that can never apply to this student, so nobody is shown a permanently
 * unreachable row (FR-7.2).
 */
export function AchievementCard({ achievement }: { achievement: AchievementOut }) {
  const unlocked = achievement.is_unlocked;
  const target = Math.max(achievement.target, 1);

  return (
    <li
      className={cn(
        "flex flex-col gap-3 rounded-xl border p-5 transition-colors",
        unlocked ? "bg-card" : "bg-muted/30",
      )}
    >
      <div className="flex items-start gap-3">
        <span
          className={cn(
            "flex size-12 shrink-0 items-center justify-center rounded-full border text-xl",
            unlocked ? "bg-card shadow-sm" : "bg-muted text-muted-foreground",
          )}
        >
          {unlocked ? (
            <span aria-hidden>{achievement.icon}</span>
          ) : (
            <Lock className="size-4" aria-hidden />
          )}
        </span>

        <div className="flex min-w-0 flex-col gap-0.5">
          <h3 className={cn("font-semibold tracking-tight", !unlocked && "text-muted-foreground")}>
            {achievement.title}
          </h3>
          <p className="text-muted-foreground text-sm text-pretty">{achievement.description}</p>
        </div>

        <span className="text-muted-foreground ml-auto shrink-0 text-xs tabular-nums">
          +{achievement.xp_reward} XP
        </span>
      </div>

      {unlocked ? (
        <p className="text-success inline-flex items-center gap-1.5 text-xs">
          <Check className="size-3.5" aria-hidden />
          {achievement.unlocked_at
            ? `Unlocked ${formatLongDate(achievement.unlocked_at)}`
            : "Unlocked"}
        </p>
      ) : (
        <div className="flex flex-col gap-1.5">
          <Progress
            value={Math.min(achievement.progress, target)}
            max={target}
            size="sm"
            label={`Progress towards ${achievement.title}`}
            valueText={`${achievement.progress} of ${target}`}
          />
          <p className="text-muted-foreground text-xs tabular-nums">
            {achievement.progress} of {target}
          </p>
        </div>
      )}
    </li>
  );
}
