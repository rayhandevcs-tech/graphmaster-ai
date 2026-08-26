"use client";

import Link from "next/link";
import { Settings } from "lucide-react";

import { useAuth } from "@/lib/auth/context";
import { isStudent } from "@/lib/auth/roles";
import { AvatarPicker } from "@/components/avatars/avatar-picker";
import { LevelRing } from "@/components/gamification/level-ring";
import { StreakFlame } from "@/components/gamification/streak-flame";
import { XpBar } from "@/components/gamification/xp-bar";
import { IdentityCard } from "@/components/profile/identity-card";
import { Reveal } from "@/components/motion/reveal";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatCount } from "@/lib/format";
import { useQuery } from "@tanstack/react-query";
import { queryKeys, usersApi } from "@/lib/api";

/**
 * Who you are on the platform.
 *
 * Split from settings deliberately. This page is identity — the name on the
 * leaderboard, the character that celebrates a result, the level that has been
 * reached. Settings is behaviour and security, and mixing the two produces the
 * page every admin template has, where changing your password sits under a
 * heading about your photograph.
 *
 * The progress panel is students-only. A teacher has no level, no streak and
 * no XP, and rendering three zeroes for them would invent a game they are not
 * playing.
 */
export function ProfileView() {
  const { user } = useAuth();

  if (!user) {
    return (
      <div className="flex flex-col gap-6">
        <Skeleton className="h-32 rounded-xl" />
        <Skeleton className="h-96 rounded-xl" />
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold tracking-tight">Your profile</h1>
          <p className="text-muted-foreground text-sm">
            Your name, your character and how far you have come.
          </p>
        </div>

        <Button asChild variant="outline" size="sm">
          <Link href="/settings">
            <Settings aria-hidden />
            Settings
          </Link>
        </Button>
      </div>

      {isStudent(user.role) ? (
        <Reveal>
          <ProgressCard />
        </Reveal>
      ) : null}

      <Reveal delay={0.06}>
        <IdentityCard user={user} />
      </Reveal>

      <Reveal delay={0.12}>
        <Card>
          <CardHeader>
            <CardTitle>Your character</CardTitle>
            <CardDescription>
              The avatar that celebrates your results. New ones unlock as you level up.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <AvatarPicker />
          </CardContent>
        </Card>
      </Reveal>
    </div>
  );
}

/**
 * Level, XP and streak, read from the level endpoint rather than from the
 * profile.
 *
 * `users.total_xp` on the profile is a cache the ledger is recomputed into,
 * and it is the right number — but the split of that total into "how far
 * through this level" is derived from the level curve, and the server is where
 * that curve lives. A second copy of the arithmetic here would disagree with
 * the dashboard the first time the curve is retuned.
 */
function ProgressCard() {
  const level = useQuery({
    queryKey: queryKeys.level(),
    queryFn: () => usersApi.level(),
  });

  const { user } = useAuth();

  if (level.isPending || !user) return <Skeleton className="h-36 rounded-xl" />;
  if (level.isError) return null;

  const isMaxLevel = level.data.xp_for_next_level <= 0;

  return (
    <Card>
      <CardContent className="flex flex-col gap-5 p-6 sm:flex-row sm:items-center sm:gap-8">
        <div className="flex items-center gap-4">
          <LevelRing
            level={level.data.current_level}
            progressPercent={level.data.progress_percent}
            isMaxLevel={isMaxLevel}
          />
          <div className="flex flex-col">
            <span className="text-2xl font-semibold tabular-nums">
              {formatCount(level.data.total_xp)}
            </span>
            <span className="text-muted-foreground text-sm">XP earned in total</span>
          </div>
        </div>

        <div className="flex flex-1 flex-col gap-4">
          <XpBar
            level={level.data.current_level}
            xpIntoLevel={level.data.xp_into_level}
            xpForNextLevel={level.data.xp_for_next_level}
            isMaxLevel={isMaxLevel}
          />
          <StreakFlame
            currentDays={user.current_streak_days}
            longestDays={user.longest_streak_days}
          />
        </div>
      </CardContent>
    </Card>
  );
}
