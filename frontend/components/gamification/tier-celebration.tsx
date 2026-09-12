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
  HAMMER_ANGRY,
  HAMMER_MESSAGE,
  HAMMER_RAISE,
  HAMMER_RECOVERY,
  HAMMER_SQUASH,
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
 * the contact; `wah` lands three-tenths of a second later, as the character
 * concertinas. Played together they read as the platform's verdict on the
 * score. Separated, the second one is the character's own reaction to being
 * squashed — which is the difference between slapstick and a scolding.
 */
const CUES_BY_TIER: Record<RewardTier, [Cue, string][]> = {
  crown: [["victory", "confetti"]],
  flower: [["chime", "spin"]],
  steady: [["soft", "nod"]],
  hammer: [
    ["bonk", "bonk"],
    ["wah", HAMMER_SQUASH],
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
  // The only beats in the whole system that are *left* again — everything
  // else is monotonic — so they are passed down rather than derived from
  // `reached`, which would keep the character squashed after it stood up.
  const squashed = tier === "hammer" && beatId === HAMMER_SQUASH;
  const cross = tier === "hammer" && (beatId === "bonk" || beatId === HAMMER_SQUASH);

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

      {tier === "hammer" && at(HAMMER_SQUASH) ? <DustPuff big={big} /> : null}

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
          expression={expressionFor(tier, reached, squashed)}
          pose={poseFor(tier, reached, squashed)}
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

        {cross ? (
          // Inside the figure's transform, so the stars follow the head as it
          // is driven down — and carrying the exact inverse of the squash, so
          // they stay a round orbit while the body flattens. Left to inherit
          // it, the formation stretched to half again its width and threw one
          // star clear of the character altogether.
          <m.div
            className="absolute inset-0"
            animate={unsquash(beatId)}
            transition={poseTransition(beatId)}
          >
            <OrbitStars scale={big ? 2.4 : 1} />
          </m.div>
        ) : null}
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
    // Wound back at the right of frame, close to the camera and oversized,
    // then swinging in along an arc and shrinking to scene size as it lands.
    // Straight down the centre line it read as a hand reaching in from
    // off-stage; arriving from the front, it is a swing.
    //
    // The `x` on the contact frame is not a stagger: the transform origin
    // sits 11% of the width left of the box's centre, so without it the
    // striking face lands that far to the left of the character.
    //
    // The `y` values are measured rather than guessed. Against the crown of
    // the hair the face sits about 25px clear at the top of the swing and
    // 9px into the head on contact — which is the bug the fix this merged
    // with was also chasing: an earlier pass stopped the mallet a head short
    // on every beat, so the blow landed in the air above the character.
    //
    // That fix corrected an *overhead* drop, and these numbers replace it
    // because the swing now comes from the front. The two things it found
    // that are independent of direction are kept: the shorter travels below,
    // and `EASE.out` on the contact.
    //
    // Its remaining change — rotating to 194° so the head points straight
    // down — is not carried over. It was tuned against a vertical drop; on an
    // arc the mallet arriving a few degrees off vertical is what an arc looks
    // like, and 182° is the angle the contact was actually measured at.
    [HAMMER_RAISE]: { x: "78%", y: "-34%", rotate: 96, scale: 1.55, opacity: 1 },
    swing: { x: "42%", y: "-40%", rotate: 140, scale: 1.28, opacity: 1 },
    bonk: { x: "11%", y: "-18%", rotate: 182, scale: 1, opacity: 1 },
  };

  // Each frame has to *arrive* before the next beat starts, with time to spare
  // so the pose is held rather than glimpsed in passing. The raise beat is
  // ~0.65s and the swing ~0.8s, so the travels are shorter than that. The
  // contact is the fastest and accelerates in: it is the one movement that
  // should land rather than be watched.
  const travel: Record<string, number> = {
    [HAMMER_RAISE]: 0.5,
    swing: 0.45,
    bonk: 0.24,
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
      initial={{ x: "125%", y: "-14%", rotate: 58, scale: 2.1, opacity: 0 }}
      animate={frames[beatId] ?? frames[HAMMER_RAISE]}
      transition={{
        duration: travel[beatId] ?? DURATION.slow,
        // The contact accelerates in (`out`); everything before it uses the
        // standard curve. `anticipate` here wound the blow *backwards* before
        // it fell, which is what made it read as hovering rather than hitting.
        ease: beatId === "bonk" ? EASE.out : EASE.standard,
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
  squashed: boolean,
): Expression {
  if (tier === "hammer") {
    // Read newest-first: the sequence walks forward through these and the
    // last matching clause wins for any beat it has not reached yet.
    if (reached(HAMMER_RECOVERY)) return "neutral";
    if (reached(HAMMER_ANGRY)) return "angry";
    if (squashed) return "dizzy";
    // Wound back in front of them, the mallet is something the character can
    // see arriving.
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
function poseFor(tier: RewardTier, reached: (id: string) => boolean, squashed: boolean): Pose {
  if (tier === "hammer") {
    if (reached(HAMMER_RECOVERY)) return "rest";
    if (reached(HAMMER_ANGRY)) return "fists";
    if (squashed) return "sprawl";
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
    // A squashed body is pressed onto its own shadow, so the shadow spreads
    // with it rather than travelling. This is most of what sells the squash —
    // more than any amount of easing on the body.
    if (beatId === HAMMER_SQUASH) return { width: [w(62), w(104), w(96)], opacity: 1 };
    // Pulled back in as the figure springs upright and momentarily leaves the
    // floor at the top of the bounce.
    if (beatId === HAMMER_ANGRY) return { width: [w(96), w(46), w(58)], opacity: 1 };
    if (beatId === HAMMER_RECOVERY) return rest;
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

/**
 * How far the body concertinas, in one place.
 *
 * Written once because two things need it and they must not drift: the body
 * squashes by it, and anything drawn *on top of* the body — the orbiting
 * stars — has to carry its exact inverse or it stretches with it.
 */
const SQUASH: { scaleY: number[]; scaleX: number[] } = {
  scaleY: [0.92, 0.46, 0.54],
  scaleX: [1, 1.42, 1.3],
};

/** The inverse, keyframe for keyframe. */
function unsquash(beatId: string): Frame {
  if (beatId === HAMMER_SQUASH) {
    return {
      scaleY: SQUASH.scaleY.map((v) => 1 / v),
      scaleX: SQUASH.scaleX.map((v) => 1 / v),
    };
  }
  if (beatId === "bonk") return { scaleY: [1, 1 / 0.86, 1 / 0.92], scaleX: 1 };
  return { scaleX: 1, scaleY: 1 };
}

function avatarPose(tier: RewardTier, beatId: string): Frame {
  const rest = { opacity: 1, y: 0, x: "0%", rotate: 0, scale: 1, scaleY: 1, scaleX: 1 };

  if (tier === "hammer") {
    // Flinching away from something they can see coming.
    if (beatId === HAMMER_RAISE) return { ...rest, rotate: -3, scaleY: 0.98 };
    // The contact itself: a first, shallow compression, so the deep one has
    // something to come from.
    if (beatId === "bonk") return { ...rest, scaleY: [1, 0.86, 0.92], y: [0, 8, 4] };
    // The squash. Volume is conserved the way it is in every cartoon: down to
    // about half height and half again as wide, about the feet, so the head
    // comes down and the shoes stay planted.
    if (beatId === HAMMER_SQUASH)
      return { ...rest, scaleY: [...SQUASH.scaleY], scaleX: [...SQUASH.scaleX] };
    // And back — overshooting past full height, with a shake in it. The
    // largest movement in the sequence, and deliberately so: this is the beat
    // FR-7.7 exists for, and it should be the one a student remembers.
    if (beatId === HAMMER_ANGRY) {
      return {
        ...rest,
        scaleY: [SQUASH.scaleY[2] as number, 1.12, 1],
        scaleX: [SQUASH.scaleX[2] as number, 0.92, 1],
        rotate: [0, -4, 4, 0],
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
  // Fast in, slow out. A squash that takes as long as the recovery reads as
  // the character sinking rather than being hit.
  if (beatId === HAMMER_SQUASH) return { duration: DURATION.base, ease: EASE.anticipate };
  if (beatId === HAMMER_ANGRY) return { duration: DURATION.slow, ease: EASE.anticipate };
  if (beatId === HAMMER_RECOVERY) return { duration: DURATION.settle, ease: EASE.standard };
  if (beatId === HAMMER_RAISE) return { duration: DURATION.settle, ease: EASE.standard };
  if (beatId === CROWN_LANDING) return { duration: DURATION.base, ease: EASE.anticipate };
  if (beatId === CROWN_DELIGHT) return { duration: DURATION.beat, ease: EASE.anticipate };
  return { duration: DURATION.settle, ease: EASE.standard };
}
