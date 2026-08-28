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
import {
  CROWN_DELIGHT,
  CROWN_LANDING,
  HAMMER_FALL,
  HAMMER_MESSAGE,
  HAMMER_RECOVERY,
  TIER_STORYBOARDS,
} from "@/lib/motion/storyboards";
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
 * **The two moments this exists for.**
 *
 * *The crown lands before it is believed.* A crown that appears over a face
 * already cheering has skipped the interesting half-second — the one between
 * the thing happening and the person realising it has. So the head takes the
 * weight, the eyes go wide, and only then does the delight arrive. Surprise is
 * what makes a reward feel given rather than displayed.
 *
 * *The hammer knocks the character over, and the getting up is the point.* The
 * first version kept them upright, on the reasoning that a fall would read as
 * humiliating. It doesn't; it reads as the platform handling a student with
 * tongs, and it left the lowest tier with nothing to watch. What keeps
 * slapstick kind is that the character is the comedian rather than the target
 * and that the recovery is the biggest movement on screen — which is what
 * `rise` is here, and why the encouragement follows it immediately.
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

  // Cues fire as their beat arrives. `play` is a no-op while sound is off,
  // which is the default — so this runs on every celebration and is silent for
  // almost all of them.
  useEffect(() => {
    for (const [cue, beat] of CUES_BY_TIER[tier]) {
      if (beatId === beat) play(cue);
    }
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
 * The cues each tier plays, and the beats they play on.
 *
 * A sound lands *with* its visual event rather than at the start of the
 * sequence: the crown's fanfare on the confetti, the hammer's blip on the
 * contact. A cue that leads its picture reads as a different sound entirely.
 *
 * The hammer has two, and the gap between them is doing real work. `bonk` is
 * the contact; `wah` is three-tenths of a second later, as the character goes
 * over. Played together they read as the platform's verdict on the score.
 * Separated, the second one is the character's own reaction to falling — which
 * is the difference between slapstick and a scolding.
 */
const CUES_BY_TIER: Record<RewardTier, [Cue, string][]> = {
  crown: [["victory", "confetti"]],
  flower: [["chime", "spin"]],
  steady: [["soft", "nod"]],
  hammer: [
    ["bonk", "bonk"],
    ["wah", HAMMER_FALL],
  ],
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
  const floored = tier === "hammer" && (beatId === HAMMER_FALL || beatId === "dazed");

  return (
    // `overflow-visible` so confetti can leave the stage; the fixed height
    // means nothing below moves while the sequence plays.
    <div className="relative grid h-48 w-full place-items-end justify-items-center overflow-visible pb-1">
      {tier === "steady" && at("pulse") ? <Pulse /> : null}

      {/* The ground shadow is a sibling of the figure, not a child of it, so
          it does not inherit the figure's squash, rise or rotation. A body
          that jumps takes its shadow with it; a body whose shadow stays on the
          floor and spreads is the one that reads as having left the ground.
          The character's own shadow is turned off for the same reason. */}
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

      {tier === "hammer" && at(HAMMER_FALL) ? <DustPuff /> : null}

      <m.div
        className="relative"
        initial={{ opacity: 0, y: 16 }}
        animate={avatarPose(tier, beatId)}
        transition={poseTransition(beatId)}
        // The pivot is the feet. A figure that falls about its centre
        // translates as much as it rotates and ends up somewhere near the
        // heading; about the feet it goes over, which is what falling is.
        style={{ transformOrigin: "50% 100%" }}
      >
        <AvatarCharacter
          code={code}
          variant="figure"
          expression={expressionFor(tier, reached, floored)}
          pose={poseFor(tier, reached, floored)}
          groundShadow={false}
          className="h-44"
        />

        {tier === "crown" && reached("crown") ? (
          <m.span
            // Worked out from the two frames rather than guessed, because
            // guessing has now been wrong in both directions. The figure is
            // h-44 over a 160-unit box, so a unit is 1.1px and the hair
            // crowns at y≈10 → 11px down. The crown is size-14 over a
            // 60-unit box, so its band starts 38px below its own top. Putting
            // the band a little below the hairline gives -20px. The first
            // attempt at this used the obvious offset and sat the band across
            // the eyes; the second over-corrected and floated it clear of the
            // head entirely.
            className="text-tier-crown absolute -top-5 left-1/2 -translate-x-1/2"
            initial={{ y: -80, opacity: 0, rotate: -14 }}
            animate={
              reached(CROWN_LANDING)
                ? { y: 0, opacity: 1, rotate: 0 }
                : { y: -30, opacity: 1, rotate: -6 }
            }
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

        {tier === "hammer" && at("dazed") ? <OrbitStars /> : null}
      </m.div>

      {tier === "crown" && reached(CROWN_DELIGHT) && !sequence.isSettled ? <Sparkles /> : null}
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
 * Rotated about its centre. About a corner, a 64px prop turning 80° travels
 * most of the card — a translation dressed as a rotation, which lands the
 * hammer somewhere near the heading instead of on the character.
 */
function CartoonHammer({ swung }: { swung: boolean }) {
  return (
    <m.span
      className="text-tier-hammer absolute top-0 right-0"
      initial={{ rotate: -70, x: 38, y: -34, opacity: 0 }}
      animate={
        swung ? { rotate: 20, x: -6, y: 4, opacity: 1 } : { rotate: -38, x: 20, y: -16, opacity: 1 }
      }
      transition={{ duration: DURATION.base, ease: EASE.anticipate }}
      style={{ transformOrigin: "50% 85%" }}
    >
      <TierMallet className="size-16" />
    </m.span>
  );
}

/**
 * The dust the landing kicks up.
 *
 * Three puffs that expand and fade outward along the floor. It is the cheapest
 * possible impact cue and it does something no amount of easing on the body
 * can: it tells you the floor is there. Without it a rotating figure reads as
 * tipping over in a vacuum.
 */
function DustPuff() {
  const puffs = [
    { x: -34, delay: 0 },
    { x: -6, delay: 0.04 },
    { x: 26, delay: 0.08 },
  ];

  return (
    <div className="pointer-events-none absolute bottom-1 left-1/2 -translate-x-1/2" aria-hidden>
      {puffs.map(({ x, delay }) => (
        <m.span
          key={x}
          className="bg-primary/30 absolute bottom-0 size-4 rounded-full blur-[2px]"
          style={{ left: x }}
          initial={{ scale: 0.3, opacity: 0.75, y: 0 }}
          animate={{ scale: 1.9, opacity: 0, y: -14 }}
          transition={{ duration: DURATION.settle, delay, ease: EASE.standard }}
        />
      ))}
    </div>
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
  // not three seconds of animation have elapsed, and the card should not
  // change height when it arrives.
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

/**
 * The face for the beat the sequence has reached.
 *
 * `floored` is passed rather than derived from `reached`, because the two
 * beats on the floor are the only ones in the whole system that are *left*
 * again — `reached` is monotonic and would keep the character dizzy after it
 * stood up.
 */
function expressionFor(
  tier: RewardTier,
  reached: (id: string) => boolean,
  floored: boolean,
): Expression {
  if (tier === "hammer") {
    if (reached(HAMMER_RECOVERY)) return "determined";
    if (floored) return "dizzy";
    return "neutral";
  }
  if (tier === "crown") {
    if (reached(CROWN_DELIGHT)) return "cheer";
    if (reached(CROWN_LANDING)) return "surprised";
    return "happy";
  }
  if (tier === "flower") return reached("spin") ? "cheer" : "happy";
  return reached("nod") ? "happy" : "neutral";
}

/**
 * What the arms are doing at the beat the sequence has reached.
 *
 * Separate from the face because they move at different moments: the hammer
 * character throws an arm up to guard *before* the mallet lands, while its
 * expression is still neutral. Deriving one from the other would lose that —
 * and a body that reacts only after contact reads as a doll being hit.
 */
function poseFor(tier: RewardTier, reached: (id: string) => boolean, floored: boolean): Pose {
  if (tier === "hammer") {
    if (reached(HAMMER_RECOVERY)) return "brace";
    if (floored) return "sprawl";
    if (reached("swing")) return "guard";
    return "rest";
  }
  if (tier === "crown") return reached(CROWN_DELIGHT) ? "cheer" : "rest";
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
    if (beatId === "bonk") return { width: [56, 74, 62], opacity: 1 };
    // A body lying down casts a long shadow, not a round one, and it has to
    // be long enough to sit under the whole figure — a 56px ellipse under a
    // 170px body reads as a second object on the floor.
    if (beatId === HAMMER_FALL) return { width: [62, 150, 140], opacity: 0.9 };
    if (beatId === "dazed") return { width: 140, opacity: 0.85 };
    // Pulled back in as the figure comes upright and momentarily leaves the
    // floor at the top of the bounce.
    if (beatId === HAMMER_RECOVERY) return { width: [140, 42, 56], opacity: 1 };
    return rest;
  }

  if (tier === "crown" && beatId === CROWN_LANDING) return { width: [56, 68, 56], opacity: 1 };
  if (tier === "crown" && beatId === CROWN_DELIGHT) return { width: [56, 44, 56], opacity: 0.85 };
  // The only other beat where a figure genuinely leaves the ground, so the
  // only other one where the shadow shrinks and fades rather than spreading.
  if (tier === "flower" && beatId === "spin") return { width: [56, 40, 56], opacity: 0.75 };
  if (tier === "steady" && beatId === "nod") return { width: [56, 62, 56], opacity: 1 };

  return rest;
}

/** How the character itself is posed on each beat. */
function avatarPose(tier: RewardTier, beatId: string): Record<string, number | number[]> {
  const rest = { opacity: 1, y: 0, x: 0, rotate: 0, scale: 1, scaleY: 1 };

  if (tier === "hammer") {
    // The blow: compressed onto the floor, not yet moving sideways.
    if (beatId === "bonk") return { ...rest, scaleY: [1, 0.84, 0.94], y: [0, 10, 4] };
    // Over. About the feet, so the body swings rather than slides — and a
    // little short of horizontal, because a figure flat on its back reads as
    // unconscious and this one is about to get up.
    //
    // The x is not decoration. Rotating a 176px figure 78° about its feet puts
    // the head 172px to the right of the pivot, so the body ends up entirely
    // in the right half of the stage — hanging out of the card, with the
    // ground shadow left behind under nothing. Shifting the pivot half a body
    // to the left lands the lying figure across the centre, where its shadow
    // is. It also reads better: a body that falls travels.
    if (beatId === HAMMER_FALL) return { ...rest, rotate: [8, 88, 78], x: [0, -70, -80], y: 6 };
    if (beatId === "dazed") return { ...rest, rotate: 78, x: -80, y: 6 };
    // The largest movement in the sequence, and deliberately so: it overshoots
    // upright, lifts off the floor and comes back down. This is the beat
    // FR-7.7 exists for, and it should be the one a student remembers.
    if (beatId === HAMMER_RECOVERY) {
      return { ...rest, rotate: [78, -6, 0], x: [-80, 0, 0], y: [6, -12, 0], scale: [1, 1.06, 1] };
    }
    return rest;
  }

  if (tier === "crown") {
    // The crown has weight: the head takes it and the whole figure gives.
    if (beatId === CROWN_LANDING) return { ...rest, scaleY: [1, 0.93, 1], y: [0, 7, 0] };
    if (beatId === CROWN_DELIGHT) return { ...rest, y: [0, -14, 0], scale: [1, 1.05, 1] };
    return rest;
  }

  if (tier === "flower" && beatId === "spin") return { ...rest, y: [0, -10, 0] };
  if (tier === "steady" && beatId === "nod") return { ...rest, y: [0, 7, 0] };

  return rest;
}

/**
 * Springs take exactly two keyframes.
 *
 * Every beat below is a three-part move — out, over, back — so a spring here
 * throws at runtime and animates nothing at all, which is how the recovery
 * beat FR-7.7 hinges on came to play as a jump cut for an entire sprint
 * without anybody noticing. `anticipate` is the curve the motion tokens
 * reserve for exactly this, and it overshoots on its own.
 */
function poseTransition(beatId: string) {
  if (beatId === HAMMER_RECOVERY) return { duration: DURATION.beat, ease: EASE.anticipate };
  if (beatId === HAMMER_FALL) return { duration: DURATION.base, ease: EASE.anticipate };
  if (beatId === CROWN_LANDING) return { duration: DURATION.base, ease: EASE.anticipate };
  if (beatId === CROWN_DELIGHT) return { duration: DURATION.beat, ease: EASE.anticipate };
  return { duration: DURATION.settle, ease: EASE.standard };
}
