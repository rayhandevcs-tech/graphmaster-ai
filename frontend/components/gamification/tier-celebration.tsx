"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
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
  HAMMER_RAISE,
  HAMMER_RECOVERY,
  TIER_STORYBOARDS,
} from "@/lib/motion/storyboards";
import { DURATION, EASE, SPRING, SPRING_SOFT } from "@/lib/motion/tokens";
import { useSound } from "@/lib/sound/use-sound";
import type { Cue } from "@/lib/sound/cues";
import { cn } from "@/lib/utils";
import type { RewardTier } from "@/types/api";

/**
 * The tier's celebration — played full screen, then left on the card.
 *
 * The sequence is the storyboard in `lib/motion/storyboards.ts`; this file
 * decides what each beat looks like and nothing about what order the beats
 * come in. That separation is what makes the hammer's requirement testable
 * without rendering anything (FR-7.7).
 *
 * **Why it takes over the screen.** It used to play inside a 176px panel in
 * the middle column of a three-column result, between a score ring and an XP
 * ledger, at interface speed. Everything about that framing said *widget*. A
 * reward is the one moment in the product that is supposed to interrupt, and
 * a thing competing with two neighbours for attention cannot. It now plays on
 * its own, at roughly twice the size and half the speed, and hands the page
 * back when it settles — the card underneath keeps the still frame, so
 * nothing appears or disappears when the overlay goes.
 *
 * That is affordable only because leaving is free. `Skip` is on screen the
 * whole time, Escape closes it, so does a click anywhere, and a reader who
 * has asked for reduced motion never sees it at all — for them the card is
 * already in its settled frame, which is the same frame the overlay ends on.
 *
 * **The two moments it exists for.**
 *
 * *The crown lands before it is believed.* A crown that appears over a face
 * already cheering has skipped the interesting half-second — the one between
 * the thing happening and the person realising it has. So the head takes the
 * weight, the eyes go wide, and only then does the delight arrive.
 *
 * *The hammer knocks the character over, and getting up is the point.* The
 * mallet is raised in front of them and held there, comes down slowly, and
 * the fall and the recovery each get a beat of their own. What keeps
 * slapstick kind is that the character is the comedian rather than the
 * target, and that the recovery is the biggest movement on screen.
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

  // The portal needs a document. Rendering it on the first client pass
  // instead would mismatch the server's HTML, and this is a celebration —
  // there is nothing here worth an SSR pass.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  // Cues fire as their beat arrives. `play` is a no-op while sound is off,
  // which is the default — so this runs on every celebration and is silent for
  // almost all of them.
  useEffect(() => {
    for (const [cue, beat] of CUES_BY_TIER[tier]) {
      if (beatId === beat) play(cue);
    }
  }, [beatId, tier, play]);

  const onStage = !sequence.reducedMotion && !sequence.isSettled;

  return (
    <MotionStage>
      {mounted && onStage
        ? createPortal(
            <FullScreen tier={tier} headline={headline} code={avatarCode} sequence={sequence} />,
            document.body,
          )
        : null}

      <div className={cn("flex flex-col items-center gap-3", className)}>
        {/* While the overlay has the sequence, the card holds its place with
            an empty box of the same height. Running a second copy of the
            animation behind a backdrop nobody can see through is work for
            nothing, and on a phone it is the work that drops the frames. */}
        {onStage ? (
          <div className="h-52 w-full" aria-hidden />
        ) : (
          <Stage tier={tier} sequence={sequence} code={avatarCode} />
        )}
        <TitleCard tier={tier} headline={headline} sequence={sequence} />
        <Controls sequence={sequence} />
      </div>
    </MotionStage>
  );
}

/**
 * The celebration with the screen to itself.
 *
 * `role="dialog"` and a focused Skip button, because it covers the page: a
 * full-screen layer a keyboard cannot reach or leave is a trap, whatever it
 * is showing. It is not `aria-modal`, and nothing is announced as an alert —
 * the result behind it is the content, and a screen-reader user has already
 * been read the headline and the feedback from the card.
 */
function FullScreen({
  tier,
  headline,
  code,
  sequence,
}: {
  tier: RewardTier;
  headline: string;
  code: string;
  sequence: SequenceState;
}) {
  const { skip } = sequence;

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") skip();
    };
    const { overflow } = document.body.style;
    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = overflow;
      document.removeEventListener("keydown", onKey);
    };
  }, [skip]);

  return (
    <m.div
      role="dialog"
      aria-label="Your reward"
      className="bg-background/95 fixed inset-0 z-50 flex flex-col items-center justify-center gap-6 p-6 backdrop-blur-sm"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: DURATION.base }}
      // A click anywhere ends it. The one thing a reader wants from a layer
      // over the page they were reading is a way back to it, and hunting for
      // a button is not it.
      onClick={skip}
    >
      <Stage tier={tier} sequence={sequence} code={code} big />

      <m.h2
        // The card behind carries this same headline, and carries it whether
        // or not the animation ever runs. Announcing it twice is the cost of
        // showing it twice, and the overlay is the copy that is decoration.
        aria-hidden
        className="max-w-xl text-center text-3xl font-semibold tracking-tight text-balance sm:text-4xl"
        initial={{ opacity: 0, scale: 0.92 }}
        animate={
          sequence.reached(tier === "hammer" ? HAMMER_MESSAGE : "title")
            ? { opacity: 1, scale: 1 }
            : { opacity: 0, scale: 0.92 }
        }
        transition={SPRING}
      >
        {headline}
      </m.h2>

      <Button
        size="lg"
        variant="secondary"
        autoFocus
        // Stops the backdrop's handler running twice for one press.
        onClick={(event) => {
          event.stopPropagation();
          skip();
        }}
      >
        <SkipForward aria-hidden />
        Skip
      </Button>
    </m.div>
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
 * the contact; `wah` is six-tenths of a second later, as the character goes
 * over. Played together they read as the platform's verdict on the score.
 * Separated, the second one is the character's own reaction to falling —
 * which is the difference between slapstick and a scolding.
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
  big = false,
}: {
  tier: RewardTier;
  sequence: SequenceState;
  code: string;
  /** Full screen rather than in the card. Everything scales from this. */
  big?: boolean;
}) {
  const { at, reached, beatId } = sequence;
  const floored = tier === "hammer" && (beatId === HAMMER_FALL || beatId === "dazed");

  return (
    // `overflow-visible` so confetti can leave the stage; the fixed height
    // means nothing below moves while the sequence plays.
    <div
      className={cn(
        "relative grid w-full place-items-end justify-items-center overflow-visible pb-1",
        big ? "h-[min(62vh,540px)]" : "h-64",
      )}
    >
      {tier === "steady" && at("pulse") ? <Pulse /> : null}

      {/* The ground shadow is a sibling of the figure, not a child of it, so
          it does not inherit the figure's squash, rise or rotation. A body
          that jumps takes its shadow with it; a body whose shadow stays on the
          floor and spreads is the one that reads as having left the ground.
          The character's own shadow is turned off for the same reason. */}
      <m.span
        className="bg-primary/25 absolute bottom-1 left-1/2 h-2.5 -translate-x-1/2 rounded-[50%] blur-[1px]"
        initial={{ width: 40, opacity: 0 }}
        animate={groundShadow(tier, beatId, big ? 2.2 : 1)}
        // Never a spring, unlike the figure above it. Springs take exactly two
        // keyframes, and every interesting shadow beat is a three-part
        // squash — out, in, back — so sharing the figure's transition made the
        // recovery beat throw and animate nothing at all.
        transition={{ duration: DURATION.settle, ease: EASE.standard }}
      />

      {tier === "hammer" && at(HAMMER_FALL) ? <DustPuff big={big} /> : null}

      <m.div
        // Just under three-quarters of the stage. The quarter above the
        // character's head is where the mallet is held up and where the crown
        // falls from: with the figure filling the stage, both started off the
        // top of the screen and the raised mallet was cut in half by the
        // viewport edge. A fifth was not enough — the mallet could either be
        // raised high enough for the swing to read as a descent, or stay
        // inside the frame, but not both.
        className="relative h-[72%]"
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
          className="h-full w-auto"
        />

        {/* Every prop is sized and offset as a *percentage of the figure*, so
            one set of numbers works at both sizes. In pixels, the crown that
            sat on the hairline in the card floated a hand's width above the
            head on the full-screen stage. */}
        {tier === "crown" && reached("crown") ? (
          <m.span
            className="text-tier-crown absolute left-1/2 h-[33%] -translate-x-1/2"
            style={{ top: "-14%" }}
            initial={{ y: "-160%", opacity: 0, rotate: -14 }}
            animate={
              reached(CROWN_LANDING)
                ? { y: 0, opacity: 1, rotate: 0 }
                : { y: "-60%", opacity: 1, rotate: -6 }
            }
            transition={SPRING_SOFT}
          >
            <TierCrown className="h-full w-auto" />
          </m.span>
        ) : null}

        {tier === "flower" && reached("bloom") ? (
          <m.span
            className="text-tier-flower absolute h-[42%]"
            style={{ top: "-4%", right: "-18%" }}
            animate={{ rotate: reached("spin") ? 22 : 0 }}
            transition={{ duration: DURATION.settle, ease: EASE.standard }}
          >
            <TierFlower className="h-full w-auto" />
          </m.span>
        ) : null}

        {tier === "hammer" && (at(HAMMER_RAISE) || at("swing") || at("bonk")) ? (
          <CartoonHammer beatId={beatId} />
        ) : null}

        {tier === "hammer" && at("dazed") ? <OrbitStars scale={big ? 2.6 : 1} /> : null}
      </m.div>

      {tier === "crown" && reached(CROWN_DELIGHT) && !sequence.isSettled ? <Sparkles /> : null}
      {tier === "crown" && reached("confetti") && !sequence.isSettled ? <Confetti /> : null}
    </div>
  );
}

/**
 * The mallet, brought down from the front.
 *
 * It used to arrive from the top right, which reads as a hand reaching in
 * from off-stage. Straight down the centre line, starting large and shrinking
 * as it lands, reads as coming *towards* the character — the cartoon framing,
 * where the thing about to happen is held up where you can see it first.
 *
 * That hold is `raise`, and it is a whole beat: the mallet appears, waits, and
 * only then swings. Weightless, oversized and slow. A hammer with plausible
 * mass reads as harm; this one reads as a cartoon, which is the difference
 * FR-7.6 asks for.
 *
 * Rotated about its own head, so the striking face stays over the character
 * while the handle swings behind it. About the handle's end — which is where
 * this started — the same rotation walks the head halfway across the stage,
 * a translation wearing a rotation's clothes.
 */
function CartoonHammer({ beatId }: { beatId: string }) {
  // Upside down, and that is the fix rather than a quirk. The prop is drawn
  // head-up, handle-down — a mallet at rest. Brought in at that angle the
  // handle hangs across the character's face and the head hovers somewhere
  // above the hair, which reads as a mallet being *shown* rather than swung.
  // Turned past 180° the head leads and the handle trails up behind it, which
  // is what a swing looks like from the front.
  //
  // The pivot moves with it: about the head rather than the handle's end, so
  // the rotation swings the handle around a striking face that stays put over
  // the character. About the foot, the same rotation walks the head halfway
  // across the stage.
  const frames: Record<string, Record<string, number | string>> = {
    // `x` is the same on every frame and is not a stagger: the transform
    // origin sits 11% of the width left of the box's centre, so without it
    // the striking face lands that far to the left of the character on every
    // beat — the blow arrived beside the head rather than on it.
    //
    // The `y` values are measured rather than guessed. Against the crown of
    // the hair the face sits roughly 70px clear when raised, 25px clear at
    // the top of the swing, and 8px into the head on contact.
    [HAMMER_RAISE]: { x: "13%", y: "-72%", rotate: 152, scale: 1.2, opacity: 1 },
    swing: { x: "12%", y: "-42%", rotate: 172, scale: 1.1, opacity: 1 },
    bonk: { x: "11%", y: "-18%", rotate: 182, scale: 1, opacity: 1 },
  };

  // Each frame has to *arrive* before the next beat starts. The raise lasts
  // 1.1s and the swing 0.9s, so a 1.3s transition on either means the mallet
  // is still travelling when it is told somewhere else — it never reaches the
  // raised pose at all, and the hold that makes the swing read as a swing
  // never happens. The contact stays fast, because that is the one movement
  // that should not be watchable.
  const travel: Record<string, number> = {
    [HAMMER_RAISE]: 0.55,
    swing: 0.7,
    bonk: DURATION.base,
  };

  return (
    <m.span
      className="text-tier-hammer absolute left-1/2 h-[52%] -translate-x-1/2"
      // The origin is the striking face, and it is not the middle of the box.
      // The drawing carries its own 18° tilt about (36,47), which walks the
      // head from (36,22) to (28,23) — 39% across, not 50%. Pivoting at 50%
      // swung the head off to one side of the character on every frame, and
      // the blow landed beside the head rather than on it.
      style={{ top: "-6%", transformOrigin: "39% 25%" }}
      // Enters from above the frame at nearly twice the size and shrinks as
      // it comes down. That change of scale is what reads as *towards you*;
      // a prop that arrives at its final size has simply appeared.
      initial={{ x: "11%", y: "-150%", rotate: 116, scale: 1.9, opacity: 0 }}
      animate={frames[beatId] ?? frames[HAMMER_RAISE]}
      transition={{
        duration: travel[beatId] ?? DURATION.slow,
        ease: beatId === "bonk" ? EASE.anticipate : EASE.standard,
      }}
    >
      <TierMallet className="h-full w-auto" />
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
function DustPuff({ big }: { big: boolean }) {
  const spread = big ? 2.2 : 1;
  const puffs = [
    { x: -34 * spread, delay: 0 },
    { x: -6 * spread, delay: 0.06 },
    { x: 26 * spread, delay: 0.12 },
  ];

  return (
    <div className="pointer-events-none absolute bottom-1 left-1/2 -translate-x-1/2" aria-hidden>
      {puffs.map(({ x, delay }) => (
        <m.span
          key={x}
          className="bg-primary/30 absolute bottom-0 size-4 rounded-full blur-[2px]"
          style={{ left: x }}
          initial={{ scale: 0.3, opacity: 0.75, y: 0 }}
          animate={{ scale: 2.2 * spread, opacity: 0, y: -18 * spread }}
          transition={{ duration: DURATION.beat, delay, ease: EASE.standard }}
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
  // not seven seconds of animation have elapsed, and the card should not
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
    // Held up in front of them and coming down slowly, the mallet is
    // something the character can see arriving.
    if (reached(HAMMER_RAISE)) return "surprised";
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
    if (reached(HAMMER_RAISE)) return "guard";
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
 * transform fighting the `-translate-x-1/2` that centres it; `spread` carries
 * the stage size, because a 56px ellipse under a 460px figure is a coin.
 */
function groundShadow(
  tier: RewardTier,
  beatId: string,
  spread: number,
): Record<string, number | number[]> {
  const w = (value: number) => value * spread;
  const rest = { width: w(56), opacity: 1 };

  if (tier === "hammer") {
    // Flattened wide on the impact, because the figure is compressed onto it.
    if (beatId === "bonk") return { width: [w(56), w(74), w(62)], opacity: 1 };
    // A body lying down casts a long shadow, not a round one, and it has to
    // be long enough to sit under the whole figure.
    if (beatId === HAMMER_FALL) return { width: [w(62), w(150), w(140)], opacity: 0.9 };
    if (beatId === "dazed") return { width: w(140), opacity: 0.85 };
    // Pulled back in as the figure comes upright and momentarily leaves the
    // floor at the top of the bounce.
    if (beatId === HAMMER_RECOVERY) return { width: [w(140), w(42), w(56)], opacity: 1 };
    return rest;
  }

  if (tier === "crown" && beatId === CROWN_LANDING) {
    return { width: [w(56), w(68), w(56)], opacity: 1 };
  }
  if (tier === "crown" && beatId === CROWN_DELIGHT) {
    return { width: [w(56), w(44), w(56)], opacity: 0.85 };
  }
  // The only other beat where a figure genuinely leaves the ground, so the
  // only other one where the shadow shrinks and fades rather than spreading.
  if (tier === "flower" && beatId === "spin") {
    return { width: [w(56), w(40), w(56)], opacity: 0.75 };
  }
  if (tier === "steady" && beatId === "nod") return { width: [w(56), w(62), w(56)], opacity: 1 };

  return rest;
}

/** How the character itself is posed on each beat. */
/** A framer-motion target: a value, or keyframes through several. */
type Frame = Record<string, number | string | (number | string)[]>;

function avatarPose(tier: RewardTier, beatId: string): Frame {
  const rest = { opacity: 1, y: 0, x: "0%", rotate: 0, scale: 1, scaleY: 1 };

  if (tier === "hammer") {
    // Flinching away from something they can see coming.
    if (beatId === HAMMER_RAISE) return { ...rest, rotate: -3, scaleY: 0.98 };
    // The blow: compressed onto the floor, not yet moving sideways.
    if (beatId === "bonk") return { ...rest, scaleY: [1, 0.84, 0.94], y: [0, 10, 4] };
    // Over. About the feet, so the body swings rather than slides — and a
    // little short of horizontal, because a figure flat on its back reads as
    // unconscious and this one is about to get up.
    //
    // The x is not decoration. Rotating a figure 78° about its feet puts the
    // head a whole body-length to the right of the pivot, so it ends up
    // wholly in the right half of the stage with the ground shadow left
    // behind under nothing. Shifting the pivot half a body left lands the
    // lying figure across the centre. In percent, so it holds at both sizes.
    if (beatId === HAMMER_FALL) {
      return { ...rest, rotate: [8, 88, 78], x: ["0%", "-62%", "-72%"], y: -14 };
    }
    // Slightly *above* the standing baseline rather than below it. A body
    // rotated three-quarters of a turn about its feet is widest at the
    // bottom of its own box, and at the stage's full height that reached
    // past the floor and into the Skip button underneath.
    if (beatId === "dazed") return { ...rest, rotate: 78, x: "-72%", y: -14 };
    // The largest movement in the sequence, and deliberately so: it overshoots
    // upright, lifts off the floor and comes back down. This is the beat
    // FR-7.7 exists for, and it should be the one a student remembers.
    if (beatId === HAMMER_RECOVERY) {
      return {
        ...rest,
        rotate: [78, -6, 0],
        x: ["-72%", "0%", "0%"],
        y: [-14, -28, 0],
        scale: [1, 1.06, 1],
      };
    }
    return rest;
  }

  if (tier === "crown") {
    // The crown has weight: the head takes it and the whole figure gives.
    if (beatId === CROWN_LANDING) return { ...rest, scaleY: [1, 0.93, 1], y: [0, 7, 0] };
    if (beatId === CROWN_DELIGHT) return { ...rest, y: [0, -16, 0], scale: [1, 1.05, 1] };
    return rest;
  }

  if (tier === "flower" && beatId === "spin") return { ...rest, y: [0, -12, 0] };
  if (tier === "steady" && beatId === "nod") return { ...rest, y: [0, 8, 0] };

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
 *
 * The fall and the recovery use `slow`, which exists for this sequence and
 * nothing else: they are the two beats a student is meant to watch rather
 * than register.
 */
function poseTransition(beatId: string) {
  if (beatId === HAMMER_RECOVERY) return { duration: DURATION.slow, ease: EASE.anticipate };
  if (beatId === HAMMER_FALL) return { duration: DURATION.slow, ease: EASE.anticipate };
  if (beatId === HAMMER_RAISE) return { duration: DURATION.settle, ease: EASE.standard };
  if (beatId === CROWN_LANDING) return { duration: DURATION.base, ease: EASE.anticipate };
  if (beatId === CROWN_DELIGHT) return { duration: DURATION.beat, ease: EASE.anticipate };
  return { duration: DURATION.settle, ease: EASE.standard };
}
