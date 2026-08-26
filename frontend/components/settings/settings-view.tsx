"use client";

import Link from "next/link";
import { Accessibility, User } from "lucide-react";

import { useAuth } from "@/lib/auth/context";
import { isStudent } from "@/lib/auth/roles";
import { useRubric, weightingSentence, wordBandLabel } from "@/lib/hooks/use-rubric";
import { Reveal } from "@/components/motion/reveal";
import { ChangePasswordCard, SessionsCard } from "@/components/settings/security-cards";
import { ThemeChoice } from "@/components/settings/theme-choice";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * How the app behaves, and how the account is secured.
 *
 * Kept separate from the profile: identity is one question and behaviour is
 * another, and a page that answers both is the one where changing a password
 * sits under a heading about your photograph.
 *
 * There is no sound control here, and that is deliberate rather than an
 * oversight. Sound is muted by default and the reward sequences that would use
 * it are the next sprint's work; a switch that toggles nothing is worse than
 * no switch, because a student who turns it on and hears nothing concludes the
 * app is broken.
 */
export function SettingsView() {
  const { user } = useAuth();
  const { data: rubric } = useRubric();
  const weighting = weightingSentence(rubric);
  const band = wordBandLabel(rubric);

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
          <p className="text-muted-foreground text-sm">
            Appearance, accessibility and account security.
          </p>
        </div>

        <Button asChild variant="outline" size="sm">
          <Link href="/profile">
            <User aria-hidden />
            Profile
          </Link>
        </Button>
      </div>

      <Reveal>
        <Card>
          <CardHeader>
            <CardTitle>Appearance</CardTitle>
            <CardDescription>
              Every colour in GraphMaster is defined for both themes, so nothing is harder to read
              in one than the other.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ThemeChoice />
          </CardContent>
        </Card>
      </Reveal>

      <Reveal delay={0.06}>
        <Card>
          <CardHeader>
            <CardTitle>Motion</CardTitle>
            <CardDescription>
              Reward animations and chart transitions follow your device&rsquo;s reduced-motion
              setting.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-muted-foreground flex gap-3 text-sm">
              <Accessibility className="mt-0.5 size-4 shrink-0" aria-hidden />
              {/* No override switch: the operating system setting is honoured
                  already, and a second control that could disagree with it is
                  a way for the two to end up out of step. */}
              <p className="text-pretty">
                Turn on <span className="text-foreground font-medium">Reduce motion</span> in your
                device&rsquo;s accessibility settings and GraphMaster shows every result as a still
                screen instead of an animated one. Nothing is lost — the same words, scores and
                rewards appear either way.
              </p>
            </div>
          </CardContent>
        </Card>
      </Reveal>

      {isStudent(user?.role) && weighting ? (
        <Reveal delay={0.12}>
          <Card>
            <CardHeader>
              <CardTitle>How your work is marked</CardTitle>
              <CardDescription>
                Read from the server, so this is the rubric your descriptions are actually scored
                against.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-2 text-sm">
              <p className="text-pretty">{weighting}</p>
              {band ? (
                <p className="text-muted-foreground text-pretty">
                  Aim for {band}. Writing well under that loses marks for length, and padding well
                  over it loses them too.
                </p>
              ) : null}
              <p className="text-muted-foreground text-pretty">
                Which words count as target vocabulary depends on the graph, and you see the full
                list — used and missed — on your result page.
              </p>
            </CardContent>
          </Card>
        </Reveal>
      ) : null}

      <Reveal delay={0.18}>
        <ChangePasswordCard />
      </Reveal>

      <Reveal delay={0.24}>
        <SessionsCard />
      </Reveal>
    </div>
  );
}
