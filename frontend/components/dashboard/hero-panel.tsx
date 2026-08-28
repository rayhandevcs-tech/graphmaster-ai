"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, Sparkles } from "lucide-react";

import { LevelRing } from "@/components/gamification/level-ring";
import { StreakFlame } from "@/components/gamification/streak-flame";
import { XpBar } from "@/components/gamification/xp-bar";
import { AvatarCharacter, avatarCodeFor } from "@/components/avatars/character";
import { Button } from "@/components/ui/button";
import { formatCount } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { StudentDashboard, UserProfile } from "@/types/api";

/**
 * The first screen a student sees, and the one that has to make practising
 * feel like the obvious next thing.
 *
 * It answers four questions in the order they are asked — who am I, how far
 * along am I, what am I working towards, and what do I do now — and the
 * primary action is the largest thing on it. Everything else on the dashboard
 * is a record of work already done; this is the only part pointing forwards.
 */
export function HeroPanel({ user, dashboard }: { user: UserProfile; dashboard: StudentDashboard }) {
  const isMaxLevel = dashboard.xp_for_next_level <= 0;
  const remaining = Math.max(dashboard.xp_for_next_level - dashboard.xp_into_level, 0);

  return (
    <section
      className={cn(
        // `rounded-xl`, like every other card. The hero is already distinct by
        // its gradient; a second radius made it distinct by accident too.
        "from-primary/10 via-primary/5 to-secondary/10 relative overflow-hidden rounded-xl",
        "border bg-gradient-to-br p-6 sm:p-8",
      )}
    >
      <div className="flex flex-col gap-8 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-col gap-6">
          <div className="flex items-center gap-4">
            {/* The character the student chose, drawn — not the initials that
                stood here while `image_url` pointed at files this repository
                has never contained.

                The full figure rather than the bust: this is the one place on
                the dashboard where the character is a greeting rather than a
                row label, and a body standing beside its own name is what the
                screen is for. Hidden below `sm`, where the height would push
                the XP figures off the first screen. */}
            <AvatarCharacter
              code={avatarCodeFor(user)}
              variant="figure"
              expression="happy"
              className="hidden h-24 shrink-0 sm:block"
            />
            <AvatarCharacter
              code={avatarCodeFor(user)}
              expression="happy"
              className="ring-background/70 size-14 shrink-0 rounded-full shadow-sm ring-2 sm:hidden"
            />

            <div className="min-w-0">
              {/* The whole name, and wrapping rather than truncating.
                  Greeting a student by the first word of `full_name` was a
                  guess about which word they answer to, and it is wrong for
                  most of this cohort: in Bengali names the given name is
                  routinely not the first word, so "Good morning, Md" greeted a
                  title. The server stores one name; the greeting uses it. Two
                  lines on a narrow phone is the acceptable cost — "Good
                  morning, Am…" is not. */}
              <h1 className="text-2xl font-semibold tracking-tight text-balance sm:text-3xl">
                <Greeting name={user.full_name} />
              </h1>
              <p className="text-muted-foreground text-sm">
                {formatCount(dashboard.total_xp)} XP earned so far
              </p>
            </div>
          </div>

          <p className="text-foreground/80 max-w-md text-sm text-pretty sm:text-base">
            {isMaxLevel
              ? "You have reached the top level. Keep your streak going and see how high you can push your vocabulary."
              : `${formatCount(remaining)} XP to level ${dashboard.current_level + 1}.`}{" "}
            {goalHint(dashboard)}
          </p>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            {/* Full width on a phone: the primary action should be reachable
                with a thumb without aiming. */}
            <Button asChild size="lg" className="w-full sm:w-auto">
              <Link href="/practice">
                Start practising
                <ArrowRight aria-hidden />
              </Link>
            </Button>
            <Button asChild variant="ghost" size="lg" className="w-full sm:w-auto">
              <Link href="/achievements">
                <Sparkles aria-hidden />
                Your achievements
              </Link>
            </Button>
          </div>
        </div>

        <div className="bg-card/80 flex flex-col gap-5 rounded-xl border p-5 shadow-sm backdrop-blur-sm lg:w-80">
          <div className="flex items-center gap-4">
            <LevelRing
              level={dashboard.current_level}
              progressPercent={dashboard.level_progress_percent}
              isMaxLevel={isMaxLevel}
            />
            <div className="min-w-0 flex-1">
              <XpBar
                level={dashboard.current_level}
                xpIntoLevel={dashboard.xp_into_level}
                xpForNextLevel={dashboard.xp_for_next_level}
                isMaxLevel={isMaxLevel}
              />
            </div>
          </div>

          <div className="border-t pt-4">
            <StreakFlame
              currentDays={dashboard.current_streak_days}
              longestDays={dashboard.longest_streak_days}
            />
          </div>
        </div>
      </div>
    </section>
  );
}

/**
 * "Good morning" needs the reader's clock, and the server does not have it.
 *
 * Rendering the time-aware form on the server would produce a greeting from
 * the data centre's timezone and then correct itself on hydration — visible,
 * and wrong for exactly the students furthest from the server. The neutral
 * form is rendered first and replaced once the browser can be asked.
 */
function Greeting({ name }: { name: string }) {
  const [greeting, setGreeting] = useState("Welcome back");

  useEffect(() => {
    const hour = new Date().getHours();
    if (hour < 12) setGreeting("Good morning");
    else if (hour < 18) setGreeting("Good afternoon");
    else setGreeting("Good evening");
  }, []);

  return (
    <>
      {greeting}, {name}
    </>
  );
}

/** One sentence of encouragement, and never one the data does not support. */
function goalHint(dashboard: StudentDashboard): string {
  if (dashboard.current_streak_days >= 2) {
    return "Another description today keeps your streak alive.";
  }
  if (dashboard.current_streak_days === 1) {
    return "Practise again tomorrow to turn today into a streak.";
  }
  return "One description is all it takes to get moving again.";
}
