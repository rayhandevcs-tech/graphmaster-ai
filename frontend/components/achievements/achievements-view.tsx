"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Medal, RefreshCw } from "lucide-react";

import { AchievementCard } from "./achievement-card";
import { EmptyState } from "@/components/layout/empty-state";
import { Reveal } from "@/components/motion/reveal";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { FilterChips } from "@/components/ui/filter-chips";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { errorMessage, gamificationApi, queryKeys } from "@/lib/api";

/**
 * The achievement catalogue.
 *
 * Everything, locked and unlocked together, because the locked ones are the
 * point of the page — the dashboard already shows what has been earned, and a
 * student comes here to find out what is next. The API sends progress towards
 * each locked entry for exactly that reason.
 *
 * The filter defaults to everything rather than to "in progress". A wall of
 * things you have not done is a poor first impression, but so is hiding the
 * ones you have: the summary line at the top puts the earned count first, and
 * the grid keeps them mixed in where their distance can be compared.
 */
type Filter = "unlocked" | "locked";

const FILTERS = [
  { value: "unlocked" as const, label: "Unlocked" },
  { value: "locked" as const, label: "In progress" },
];

export function AchievementsView() {
  const [filter, setFilter] = useState<Filter | null>(null);

  const achievements = useQuery({
    queryKey: queryKeys.achievements(),
    queryFn: () => gamificationApi.achievements(),
  });

  // Memoised rather than `?? []` inline: a fresh empty array on every render
  // is a new dependency for both memos below, which then recompute for a list
  // that has not changed.
  const rows = useMemo(() => achievements.data ?? [], [achievements.data]);
  const unlockedCount = useMemo(() => rows.filter((row) => row.is_unlocked).length, [rows]);

  const visible = useMemo(() => {
    if (filter === null) return rows;
    return rows.filter((row) => (filter === "unlocked" ? row.is_unlocked : !row.is_unlocked));
  }, [rows, filter]);

  if (achievements.isPending) return <AchievementsSkeleton />;

  if (achievements.isError) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Your achievements could not be loaded</AlertTitle>
        <AlertDescription className="flex flex-col items-start gap-3">
          <span>{errorMessage(achievements.error)}</span>
          <Button variant="outline" size="sm" onClick={() => void achievements.refetch()}>
            <RefreshCw aria-hidden />
            Try again
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">Achievements</h1>
        <p className="text-muted-foreground text-sm">
          Unlocked by practising. Each one adds XP the moment it is earned.
        </p>
      </div>

      <Reveal>
        <Card>
          <CardContent className="flex flex-col gap-4 p-6">
            <div className="flex items-baseline justify-between gap-4">
              <span className="text-2xl font-semibold tabular-nums">
                {unlockedCount}
                <span className="text-muted-foreground text-base font-normal">
                  {" "}
                  of {rows.length} unlocked
                </span>
              </span>
              <Button asChild size="sm">
                <Link href="/practice">Practise</Link>
              </Button>
            </div>

            <Progress
              value={unlockedCount}
              max={Math.max(rows.length, 1)}
              label="Achievements unlocked"
              valueText={`${unlockedCount} of ${rows.length} achievements unlocked`}
            />
          </CardContent>
        </Card>
      </Reveal>

      <FilterChips
        label="Show"
        options={FILTERS}
        value={filter}
        onChange={setFilter}
        allLabel="All"
      />

      {visible.length === 0 ? (
        <EmptyState
          icon={Medal}
          title={filter === "unlocked" ? "Nothing unlocked yet" : "Nothing left to unlock"}
          description={
            filter === "unlocked"
              ? "Finishing a single description unlocks your first one."
              : "You have earned every achievement in the catalogue."
          }
          action={
            filter === "unlocked" ? (
              <Button asChild size="sm">
                <Link href="/practice">Choose a graph</Link>
              </Button>
            ) : null
          }
        />
      ) : (
        <ul className="grid gap-4 md:grid-cols-2">
          {visible.map((achievement) => (
            <AchievementCard key={achievement.code} achievement={achievement} />
          ))}
        </ul>
      )}
    </div>
  );
}

function AchievementsSkeleton() {
  return (
    <div className="flex flex-col gap-6" aria-busy>
      <span className="sr-only" role="status">
        Loading your achievements
      </span>
      <Skeleton className="h-9 w-56" />
      <Skeleton className="h-28 rounded-xl" />
      <div className="grid gap-4 md:grid-cols-2">
        {[0, 1, 2, 3].map((index) => (
          <Skeleton key={index} className="h-36 rounded-xl" />
        ))}
      </div>
    </div>
  );
}
