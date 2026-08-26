"use client";

import { useQuery } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";

import { queryKeys, usersApi, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth/context";
import { Reveal } from "@/components/motion/reveal";
import { TierDistribution } from "@/components/gamification/tier-distribution";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { AchievementStrip } from "./achievement-strip";
import { FirstRun } from "./first-run";
import { HeroPanel } from "./hero-panel";
import { RecentActivity } from "./recent-activity";
import { StatTiles } from "./stat-tiles";
import { TrendCard } from "./trend-card";

/**
 * The student's home screen.
 *
 * One request paints all of it. `GET /users/me/dashboard` is an aggregate for
 * exactly this reason — six requests would show the XP bar, the streak, the
 * chart and the activity list arriving at different moments, which reads as a
 * page that is failing rather than one that is loading.
 *
 * The sections are staggered by a few hundredths of a second on arrival, which
 * gives the eye an order to read them in: who you are, then the numbers, then
 * the detail behind them. Under `prefers-reduced-motion` they simply appear.
 *
 * A student with no marked work does not get the same screen with zeroes in
 * it. Zeroes are a mark, and they have not been given one.
 */
export function DashboardView() {
  const { user } = useAuth();

  const dashboard = useQuery({
    queryKey: queryKeys.dashboard(),
    queryFn: () => usersApi.dashboard(),
  });

  if (dashboard.isPending || !user) return <DashboardSkeleton />;

  if (dashboard.isError) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Your dashboard could not be loaded</AlertTitle>
        <AlertDescription className="flex flex-col items-start gap-3">
          <span>{errorMessage(dashboard.error)}</span>
          <Button variant="outline" size="sm" onClick={() => void dashboard.refetch()}>
            <RefreshCw aria-hidden />
            Try again
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  const data = dashboard.data;
  const started = data.total_attempts > 0;

  return (
    <div className="flex flex-col gap-6">
      <Reveal>
        <HeroPanel user={user} dashboard={data} />
      </Reveal>

      {!started ? (
        <Reveal delay={0.06}>
          <FirstRun />
        </Reveal>
      ) : (
        <>
          <Reveal delay={0.06}>
            <StatTiles dashboard={data} />
          </Reveal>

          <Reveal delay={0.12}>
            <div className="grid gap-4 lg:grid-cols-3">
              <div className="lg:col-span-2">
                <TrendCard points={data.score_trend} />
              </div>

              <Card className="flex h-full flex-col">
                <CardHeader>
                  <CardTitle>Your results</CardTitle>
                  <CardDescription>
                    Which tier each marked description earned. The tier comes from the share of
                    target words you used.
                  </CardDescription>
                </CardHeader>
                <CardContent className="flex-1">
                  <TierDistribution distribution={data.reward_tier_distribution} />
                </CardContent>
              </Card>
            </div>
          </Reveal>

          <Reveal delay={0.18}>
            <AchievementStrip achievements={data.achievements} />
          </Reveal>

          <Reveal delay={0.24}>
            <RecentActivity items={data.recent_activity} />
          </Reveal>
        </>
      )}
    </div>
  );
}

/**
 * The shape of the page, not a spinner.
 *
 * A centred spinner reflows the whole screen when the data lands. These blocks
 * occupy the same space the real cards will, so arriving changes the text and
 * nothing else.
 */
function DashboardSkeleton() {
  return (
    <div className="flex flex-col gap-6" aria-busy>
      <span className="sr-only" role="status">
        Loading your dashboard
      </span>
      <Skeleton className="h-64 rounded-2xl sm:h-56" />
      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
        {[0, 1, 2, 3].map((index) => (
          <Skeleton key={index} className="h-28 rounded-xl" />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Skeleton className="h-80 rounded-xl lg:col-span-2" />
        <Skeleton className="h-80 rounded-xl" />
      </div>
    </div>
  );
}
