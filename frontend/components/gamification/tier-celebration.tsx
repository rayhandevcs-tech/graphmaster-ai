"use client";

import { useEffect } from "react";
import { m } from "framer-motion";
import { Crown, Hammer, RotateCcw, SkipForward, Volume2, VolumeX } from "lucide-react";

import { AvatarCharacter, type Expression } from "@/components/avatars/character";
import { MotionStage } from "@/components/motion/stage";
import { BloomingFlower, Confetti, OrbitStars, Pulse, Sparkles } from "./particles";
import { Button } from "@/components/ui/button";
import { useSequence, type SequenceState } from "@/lib/motion/use-sequence";
import { HAMMER_MESSAGE, HAMMER_RECOVERY, TIER_STORYBOARDS } from "@/lib/motion/storyboards";
import { DURATION, EASE, SPRING, SPRING_SOFT } from "@/lib/motion/tokens";
import { useSound } from "@/lib/sound/use-sound";
import type { Cue } from "@/lib/sound/cues";
import { cn } from "@/lib/utils";
import type { RewardTier } from "@/types/api";

/**
 * The tier's celebration, played on the result card.
 *
 * The sequence is the storyboard in `lib/motion/storyboards.ts`; this file
 * decides what each beat looks like and nothing about what order the beats
 * come in. That separation is what makes the hammer's requirement testable
 * without rendering anything (FR-7.7).
 *
 * The **headline is the server's words**, and the message beneath this
 * component — which for the lowest tier always opens "Keep Practicing! You Can
 * Improve!" — is on the card from the first frame. The animation reveals the
 * title card; it never gates the encouragement. A student who navigates away
 * at 1.2 seconds, whose tab is throttled in the background, or who is using a
 * screen reader has been told the same thing as everyone else.
 */
export function TierCelebration({
  tier,
  headline,
  avatarCode,
  className,
}: {
  tier: RewardTier;
  /** `feedback.headline` — "Graph Queen", "Keep Practicing!". Never composed here. */
  headline: string;
  /** The student's character, resolved by the page. Passed rather than read
   *  from the session here, so the celebration is a pure function of its props
   *  and can be exercised beat by beat without a signed-in user. */
  avatarCode: string;
  className?: string;
}) {
  const sequence = useSequence(TIER_STORYBOARDS[tier]);
  const { play } = useSound();
  const { beatId } = sequence;

  // One cue per tier, fired as its beat arrives. `playCue` is a no-op while
  // sound is off, which is the default — so this runs on every celebration and
  // is silent for almost all of them.
  useEffect(() => {
    const [cue, beat] = CUES_BY_TIER[tier];
    if (beatId === beat) play(cue);
  }, [beatId, tier, play]);

  return (
    <MotionStage>
      <div className={cn("flex flex-col items-center gap-3", className)}>
        <Stage tier={tier} sequence={sequence} code={avatarCode} />
        <TitleCard tier={tier} headline={headline} sequence={sequence} />
        <Controls sequence={sequence} />
      </div>
    </MotionStage>
  );
}

/**
 * The cue each tier plays, and the beat it plays on.
 *
 * The sound lands *with* the visual event rather than at the start of the
 * sequence: the crown's fanfare on the confetti, the hammer's blip on the
 * contact. A cue that leads its picture reads as a different sound entirely.
 */
const CUES_BY_TIER: Record<RewardTier, [Cue, string]> = {
  crown: ["victory", "confetti"],
  flower: ["chime", "spin"],
  steady: ["soft", "nod"],
  hammer: ["bonk", "bonk"],
};

function Stage({
  tier,
  sequence,
  code,
}: {
  tier: RewardTier;
  sequence: SequenceState;
  code: string;
}) {
  const { at, reached, beatId } = sequence;

  return (
    // `overflow-visible` so confetti can leave the stage; the fixed height
    // means nothing below moves while the sequence plays.
    <div className="relative grid h-32 w-full place-items-center overflow-visible">
      {tier === "steady" && at("pulse") ? <Pulse /> : null}

      <m.div
        className="relative"
        initial={{ opacity: 0, y: 16 }}
        animate={avatarPose(tier, beatId)}
        transition={poseTransition(beatId)}
      >
        <AvatarCharacter
          code={code}
          expression={expressionFor(tier, reached)}
          className="size-28"
        />

        {tier === "crown" && reached("crown") ? (
          <m.span
            className="text-tier-crown absolute -top-3 left-1/2 -translate-x-1/2"
            initial={{ y: -70, opacity: 0, rotate: -12 }}
            animate={{ y: 0, opacity: 1, rotate: 0 }}
            transition={SPRING_SOFT}
          >
            <Crown className="size-10 fill-current" aria-hidden />
          </m.span>
        ) : null}

        {tier === "flower" && reached("bloom") ? (
          <m.span
            className="absolute -top-3 -right-6"
            animate={{ rotate: reached("spin") ? 22 : 0 }}
            transition={{ duration: DURATION.settle, ease: EASE.standard }}
          >
            <BloomingFlower className="size-20" />
          </m.span>
        ) : null}

        {tier === "hammer" && (at("swing") || at("bonk")) ? (
          <CartoonHammer swung={at("bonk")} />
        ) : null}

        {tier === "hammer" && (at("dizzy") || at("wobble")) ? <OrbitStars /> : null}
      </m.div>

      {tier === "crown" && reached("sparkle") && !sequence.isSettled ? <Sparkles /> : null}
      {tier === "crown" && reached("confetti") && !sequence.isSettled ? <Confetti /> : null}
    </div>
  );
}

/**
 * The hammer.
 *
 * Oversized and weightless: it arrives at an impossible angle, makes contact,
 * and rebounds past vertical. A hammer with plausible mass reads as harm; this
 * one reads as a cartoon, which is the whole difference the specification asks
 * for (FR-7.6).
 *
 * Rotated about its centre. About a corner, a 48px icon turning 60° travels
 * most of the card — a translation dressed as a rotation, which lands the
 * hammer somewhere near the heading instead of on the character.
 */
function CartoonHammer({ swung }: { swung: boolean }) {
  return (
    <m.span
      className="text-tier-hammer absolute top-1 right-0"
      initial={{ rotate: -65, x: 32, y: -26, opacity: 0 }}
      animate={
        swung ? { rotate: 20, x: -8, y: 4, opacity: 1 } : { rotate: -35, x: 16, y: -12, opacity: 1 }
      }
      transition={{ duration: DURATION.base, ease: EASE.anticipate }}
    >
      <Hammer className="size-12" aria-hidden />
    </m.span>
  );
}

function TitleCard({
  tier,
  headline,
  sequence,
}: {
  tier: RewardTier;
  headline: string;
  sequence: SequenceState;
}) {
  // The hammer's title beat is its encouragement; every other tier calls it
  // `title`. Both are the last beat before the card settles.
  const beat = tier === "hammer" ? HAMMER_MESSAGE : "title";
  const revealed = sequence.reached(beat);

  // Rendered from the first frame and revealed by opacity, not mounted at the
  // beat. The headline is content — a screen reader should reach it whether or
  // not two seconds of animation have elapsed, and the card should not change
  // height when it arrives.
  return (
    <m.h2
      className="text-xl font-semibold tracking-tight text-balance"
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: revealed ? 1 : 0, scale: revealed ? 1 : 0.9 }}
      transition={SPRING}
    >
      {headline}
    </m.h2>
  );
}

/**
 * Skip and replay (FR-7.9).
 *
 * Neither is offered to a reader who has asked for reduced motion: for them
 * the card is already in its settled frame, so "skip" would do nothing and
 * "replay" would offer to play something that does not play.
 */
function Controls({ sequence }: { sequence: SequenceState }) {
  if (sequence.reducedMotion) return null;

  return sequence.isSettled ? (
    <Button
      variant="ghost"
      size="sm"
      onClick={sequence.replay}
      className="opacity-70 hover:opacity-100"
    >
      <RotateCcw aria-hidden />
      Replay
    </Button>
  ) : (
    <Button
      variant="ghost"
      size="sm"
      onClick={sequence.skip}
      className="opacity-70 hover:opacity-100"
    >
      <SkipForward aria-hidden />
      Skip
    </Button>
  );
}

/** The face for the beat the sequence has reached. */
function expressionFor(tier: RewardTier, reached: (id: string) => boolean): Expression {
  if (tier === "hammer") {
    if (reached(HAMMER_RECOVERY)) return "determined";
    if (reached("dizzy")) return "dizzy";
    return "neutral";
  }
  if (tier === "crown") return reached("crown") ? "cheer" : "happy";
  if (tier === "flower") return reached("spin") ? "cheer" : "happy";
  return reached("nod") ? "happy" : "neutral";
}

/** How the character itself is posed on each beat. */
function avatarPose(tier: RewardTier, beatId: string): Record<string, number | number[]> {
  const rest = { opacity: 1, y: 0, rotate: 0, scale: 1, scaleY: 1 };

  if (tier === "hammer") {
    if (beatId === "bonk") return { ...rest, scaleY: [1, 0.86, 1], y: [0, 8, 2] };
    if (beatId === "wobble") return { ...rest, rotate: 12, y: 10 };
    if (beatId === HAMMER_RECOVERY) return { ...rest, scale: [1, 1.08, 1] };
    return rest;
  }

  if (tier === "crown" && beatId === "crown") return { ...rest, scaleY: [1, 0.96, 1] };
  if (tier === "flower" && beatId === "spin") return { ...rest, y: [0, -10, 0] };
  if (tier === "steady" && beatId === "nod") return { ...rest, y: [0, 7, 0] };

  return rest;
}

function poseTransition(beatId: string) {
  if (beatId === HAMMER_RECOVERY) return SPRING;
  if (beatId === "wobble") return { duration: DURATION.base, ease: EASE.standard };
  return { duration: DURATION.settle, ease: EASE.standard };
}
