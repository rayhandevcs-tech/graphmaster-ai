"use client";

import { useEffect } from "react";
import { m } from "framer-motion";
import { RotateCcw, SkipForward, Volume2, VolumeX } from "lucide-react";

import { AvatarCharacter, type Expression, type Pose } from "@/components/avatars/character";
import { MotionStage } from "@/components/motion/stage";
import { Confetti, OrbitStars, Pulse, Sparkles } from "./particles";
import { TierCrown, TierFlower, TierMallet } from "./tier-props";
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
    <div className="relative grid h-44 w-full place-items-end justify-items-center overflow-visible pb-1">
      {tier === "steady" && at("pulse") ? <Pulse /> : null}

      {/* The ground shadow is a sibling of the figure, not a child of it, so
          it does not inherit the figure's squash and rise. A body that jumps
          takes its shadow with it; a body whose shadow stays on the floor and
          spreads is the one that reads as having left the ground. */}
      <m.span
        className="bg-primary/25 absolute bottom-1 left-1/2 h-2.5 -translate-x-1/2 rounded-[50%] blur-[1px]"
        initial={{ width: 40, opacity: 0 }}
        animate={groundShadow(tier, beatId)}
        // Never a spring, unlike the figure above it. Springs take exactly two
        // keyframes, and every interesting shadow beat is a three-part
        // squash — out, in, back — so sharing the figure's transition made the
        // recovery beat throw and animate nothing at all.
        transition={{ duration: DURATION.settle, ease: EASE.standard }}
      />

      <m.div
        className="relative"
        initial={{ opacity: 0, y: 16 }}
        animate={avatarPose(tier, beatId)}
        transition={poseTransition(beatId)}
        style={{ transformOrigin: "50% 100%" }}
      >
        <AvatarCharacter
          code={code}
          variant="figure"
          expression={expressionFor(tier, reached)}
          pose={poseFor(tier, reached)}
          className="h-40"
        />

        {tier === "crown" && reached("crown") ? (
          <m.span
            // -top-6, not -top-2. The head sits high in the figure's frame and
            // the crown's band is three-quarters of the way down its own box,
            // so the obvious offset landed the band across the eyes.
            className="text-tier-crown absolute -top-6 left-1/2 -translate-x-1/2"
            initial={{ y: -70, opacity: 0, rotate: -12 }}
            animate={{ y: 0, opacity: 1, rotate: 0 }}
            transition={SPRING_SOFT}
          >
            <TierCrown className="size-14" />
          </m.span>
        ) : null}

        {tier === "flower" && reached("bloom") ? (
          <m.span
            className="text-tier-flower absolute -top-2 -right-8"
            animate={{ rotate: reached("spin") ? 22 : 0 }}
            transition={{ duration: DURATION.settle, ease: EASE.standard }}
          >
            <TierFlower className="size-20" />
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
      className="text-tier-hammer absolute top-0 right-0"
      initial={{ rotate: -65, x: 34, y: -30, opacity: 0 }}
      animate={
        swung ? { rotate: 18, x: -6, y: 2, opacity: 1 } : { rotate: -35, x: 18, y: -14, opacity: 1 }
      }
      transition={{ duration: DURATION.base, ease: EASE.anticipate }}
      style={{ transformOrigin: "50% 85%" }}
    >
      <TierMallet className="size-16" />
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
  const { enabled, toggle } = useSound();

  return (
    <div className="flex items-center gap-1">
      {sequence.reducedMotion ? null : sequence.isSettled ? (
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
      )}

      {/* Sound is off until asked for (FR-7.11), and the asking should be
          possible here rather than only three screens away in settings — this
          is the moment a student discovers there could have been a sound. */}
      <Button
        variant="ghost"
        size="icon"
        onClick={toggle}
        aria-pressed={enabled}
        aria-label={enabled ? "Turn reward sounds off" : "Turn reward sounds on"}
        className="size-8 opacity-70 hover:opacity-100"
      >
        {enabled ? <Volume2 aria-hidden /> : <VolumeX aria-hidden />}
      </Button>
    </div>
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

/**
 * What the arms are doing at the beat the sequence has reached.
 *
 * Separate from the face because they move at different moments: the hammer
 * character throws its arm up to guard *before* the mallet lands, while its
 * expression is still neutral. Deriving one from the other would lose that —
 * and a body that reacts only after contact reads as a doll being hit.
 */
function poseFor(tier: RewardTier, reached: (id: string) => boolean): Pose {
  if (tier === "hammer") {
    if (reached(HAMMER_RECOVERY)) return "brace";
    if (reached("swing")) return "guard";
    return "rest";
  }
  if (tier === "crown") return reached("crown") ? "cheer" : "rest";
  if (tier === "flower") return reached("bloom") ? "cheer" : "rest";
  return reached("nod") ? "brace" : "rest";
}

/**
 * The shadow on the floor.
 *
 * It widens and fades as the figure rises and tightens as it lands, which is
 * most of what sells weight — more than any amount of shading on the figure
 * itself. Width in pixels rather than a scale so it stays centred without a
 * transform fighting the `-translate-x-1/2` that centres it.
 */
function groundShadow(tier: RewardTier, beatId: string): Record<string, number | number[]> {
  const rest = { width: 56, opacity: 1 };

  if (tier === "hammer") {
    // Flattened wide on the impact, because the figure is compressed onto it.
    if (beatId === "bonk") return { width: [56, 70, 60], opacity: 1 };
    if (beatId === "wobble") return { width: 62, opacity: 0.9 };
    if (beatId === HAMMER_RECOVERY) return { width: [60, 44, 56], opacity: 1 };
    return rest;
  }

  if (tier === "crown" && beatId === "crown") return { width: [56, 64, 56], opacity: 1 };
  // The only beat where the figure genuinely leaves the ground, so the only
  // one where the shadow shrinks and fades rather than spreading.
  if (tier === "flower" && beatId === "spin") return { width: [56, 40, 56], opacity: 0.75 };
  if (tier === "steady" && beatId === "nod") return { width: [56, 62, 56], opacity: 1 };

  return rest;
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
  // The recovery is a three-keyframe bounce — up, over, back — and a spring
  // takes exactly two, so this used to throw at runtime and the beat FR-7.7
  // hinges on played as a jump cut. `anticipate` is the curve the motion
  // tokens reserve for precisely this movement, and it overshoots on its own.
  if (beatId === HAMMER_RECOVERY) return { duration: DURATION.beat, ease: EASE.anticipate };
  if (beatId === "wobble") return { duration: DURATION.base, ease: EASE.standard };
  return { duration: DURATION.settle, ease: EASE.standard };
}
