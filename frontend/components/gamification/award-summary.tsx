"use client";

import { useQuery } from "@tanstack/react-query";
import { Flame, Sparkles, Trophy } from "lucide-react";

import { XpBar } from "./xp-bar";
import { CountUp } from "@/components/motion/count-up";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { queryKeys, usersApi } from "@/lib/api";
import type { GamificationOut, XPReason } from "@/types/api";

const REASON_LABELS: Record<XPReason, string> = {
  submission: "Completing this graph",
  high_score_bonus: "High score bonus",
  streak_bonus: "Daily streak bonus",
  achievement: "Achievement unlocked",
  manual_adjustment: "Adjustment",
};

/**
 * What this attempt earned.
 *
 * Only shown for the attempt that has just been marked. XP, the level change
 * and any achievements exist solely in the `analyze` response — re-reading the
 * submission later returns the score without them — so on a revisit this panel
 * is absent rather than reconstructed. Showing a stale "+45 XP" every time the
 * page is opened would suggest the award happened again, and the ledger is
 * append-only precisely so that never becomes ambiguous.
 */
export function AwardSummary({ awards }: { awards: GamificationOut }) {
  const level = useQuery({ queryKey: queryKeys.level(), queryFn: () => usersApi.level() });

  const xp = awards.xp_awarded ?? 0;
  const breakdown = awards.xp_breakdown ?? [];
  const achievements = awards.new_achievements ?? [];
  const streak = awards.streak_days ?? 0;

  return (
    <Card className="h-full">
      <CardHeader className="pb-3">
        <CardTitle className="text-muted-foreground text-xs font-medium tracking-wide uppercase">
          What you earned
        </CardTitle>
      </CardHeader>

      <CardContent className="flex flex-col gap-5">
        <div className="flex items-baseline gap-2">
          {/* Counts up from zero, sharing the dashboard's component so the
              number behaves the same way in both places. */}
          <span className="text-3xl font-semibold tabular-nums">
            +<CountUp value={xp} format={(value) => Math.round(value).toLocaleString()} />
          </span>
          <span className="text-muted-foreground text-sm">XP</span>
          {awards.leveled_up ? (
            <Badge className="ml-auto gap-1">
              <Sparkles className="size-3" aria-hidden />
              Level {awards.level_after}
            </Badge>
          ) : null}
        </div>

        {breakdown.length > 0 ? (
          <ul className="flex flex-col gap-1.5">
            {breakdown.map((line) => (
              <li
                key={`${line.reason}-${line.amount}`}
                className="text-muted-foreground flex items-center justify-between gap-3 text-xs"
              >
                <span>{REASON_LABELS[line.reason] ?? line.reason}</span>
                <span className="text-foreground font-medium tabular-nums">
                  +{line.amount.toLocaleString()}
                </span>
              </li>
            ))}
          </ul>
        ) : null}

        <div className="border-t pt-4">
          {level.isLoading ? (
            <Skeleton className="h-14 w-full" />
          ) : level.data ? (
            <XpBar
              level={level.data.current_level}
              xpIntoLevel={level.data.xp_into_level}
              xpForNextLevel={level.data.xp_for_next_level}
              isMaxLevel={level.data.is_max_level}
            />
          ) : null}
        </div>

        {streak > 0 ? (
          <p className="text-muted-foreground inline-flex items-center gap-2 text-sm">
            <Flame className="size-4" aria-hidden />
            {streak === 1 ? "Practice streak started today" : `${streak}-day practice streak`}
          </p>
        ) : null}

        {achievements.length > 0 ? (
          <div className="flex flex-col gap-2 border-t pt-4">
            <p className="inline-flex items-center gap-2 text-sm font-medium">
              <Trophy className="size-4" aria-hidden />
              {achievements.length === 1 ? "Achievement unlocked" : "Achievements unlocked"}
            </p>
            <ul className="flex flex-col gap-2">
              {achievements.map((achievement) => (
                <li key={achievement.code} className="flex items-start gap-2.5">
                  <span className="text-lg leading-none" aria-hidden>
                    {achievement.icon}
                  </span>
                  <span className="flex flex-col">
                    <span className="text-sm font-medium">{achievement.title}</span>
                    <span className="text-muted-foreground text-xs">{achievement.description}</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
