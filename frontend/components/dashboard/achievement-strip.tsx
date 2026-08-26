import Link from "next/link";
import { ArrowUpRight, Medal } from "lucide-react";

import { EmptyState } from "@/components/layout/empty-state";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatLongDate } from "@/lib/format";
import type { AchievementOut } from "@/types/api";

/**
 * Achievements this student has unlocked.
 *
 * Unlocked ones only — the dashboard payload carries no others, and that is
 * the right shape for this screen. A wall of locked achievements is a list of
 * things you have not done, which is the opposite of what a home screen is
 * for; the full catalogue with its progress bars lives one link away, where a
 * student goes deliberately to see what is next.
 *
 * The row scrolls sideways rather than wrapping. On a phone that keeps the
 * card a fixed height whether a student has two of these or twenty, so the
 * work below it does not move down the page as they earn more.
 */
export function AchievementStrip({ achievements }: { achievements: AchievementOut[] }) {
  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between gap-4 space-y-0">
        <div className="flex flex-col gap-1.5">
          <CardTitle>Achievements</CardTitle>
          <CardDescription>
            {achievements.length === 0
              ? "Unlocked by practising — none yet."
              : `${achievements.length} unlocked.`}
          </CardDescription>
        </div>
        <Button asChild variant="ghost" size="sm" className="shrink-0">
          <Link href="/achievements">
            See all
            <ArrowUpRight aria-hidden />
          </Link>
        </Button>
      </CardHeader>

      <CardContent>
        {achievements.length === 0 ? (
          <EmptyState
            icon={Medal}
            title="Your first one is close"
            description="Finishing a single description unlocks one. The catalogue shows how far you are from each of the others."
            className="py-10"
          />
        ) : (
          // `-mx-1 px-1` so the focus ring on the first and last item is not
          // clipped by the scroll container.
          <ul className="-mx-1 flex gap-3 overflow-x-auto px-1 pb-2">
            {achievements.map((achievement) => (
              <li key={achievement.code} className="w-32 shrink-0">
                <div className="bg-muted/50 flex h-full flex-col items-center gap-2 rounded-xl border p-3 text-center">
                  <span className="bg-card flex size-11 items-center justify-center rounded-full border text-xl shadow-sm">
                    <span aria-hidden>{achievement.icon}</span>
                  </span>
                  <span className="text-xs leading-tight font-semibold text-balance">
                    {achievement.title}
                  </span>
                  <span className="text-muted-foreground mt-auto text-[0.6875rem]">
                    {achievement.unlocked_at ? formatLongDate(achievement.unlocked_at) : "Unlocked"}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
