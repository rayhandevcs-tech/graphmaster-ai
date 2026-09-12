import type { Storyboard } from "./sequence";
import type { RewardTier } from "@/types/api";

/**
 * The four tier celebrations, beat by beat.
 *
 * Documented in 06-frontend-architecture.md §8.3, and this file is the
 * authority — the doc describes what is here rather than the other way round.
 *
 * Every sequence ends on `settled`, whose frame is the still card. That is
 * what "skip" arrives at and what a student who has asked for reduced motion
 * sees from the outset.
 */

/** The beat every sequence ends on: the card at rest. */
export const SETTLED = "settled";

/**
 * The hammer's last two beats before it settles.
 *
 * Named here rather than written as strings in the tests, so that renaming a
 * beat cannot quietly make the assertion vacuous — the test imports these and
 * checks their position, which fails if either is removed.
 */
/** The mallet, wound back in front of the character before it swings in. */
export const HAMMER_RAISE = "raise";
/**
 * Squashed, not felled.
 *
 * The character concertinas straight down under the blow and springs back.
 * This replaced a beat that put them on the floor: a fall is a longer, more
 * elaborate thing to animate and it reads as *defeat*, where a squash is the
 * oldest joke in animation and reads as an indignity the character is about
 * to object to. FR-7.6 wants the second.
 */
export const HAMMER_SQUASH = "squash";
/** And the objection: brows down, shouting, before anything else happens. */
export const HAMMER_ANGRY = "angry";
export const HAMMER_RECOVERY = "recover";
export const HAMMER_MESSAGE = "message";

/**
 * The crown's two halves: the weight arriving, and the student believing it.
 *
 * Named for the same reason as the hammer's beats — a test that asserts
 * surprise comes before delight should fail if either is renamed away, rather
 * than passing vacuously against a string that no longer exists.
 */
export const CROWN_LANDING = "land";
export const CROWN_DELIGHT = "delight";

/**
 * Landed on, then believed.
 *
 * The crown used to appear and the character was already cheering, which
 * skipped the only interesting moment in it: the beat between the thing
 * happening and the person realising. `land` is the impact — the crown's
 * weight arrives, the head takes it, and the face is *startled*, not pleased.
 * `delight` is a third of a second later, and it is where the joy is.
 *
 * A celebration that opens on its own punchline has nowhere to go.
 */
const CROWN: Storyboard = {
  id: "crown",
  beats: [
    { id: "arrive", at: 0 },
    { id: "crown", at: 0.7 },
    { id: CROWN_LANDING, at: 1.6 },
    { id: CROWN_DELIGHT, at: 2.5 },
    { id: "confetti", at: 3 },
    { id: "title", at: 3.6 },
    { id: SETTLED, at: 5 },
  ],
};

const FLOWER: Storyboard = {
  id: "flower",
  beats: [
    { id: "arrive", at: 0 },
    { id: "bloom", at: 0.7 },
    { id: "spin", at: 1.6 },
    { id: "title", at: 2.4 },
    { id: SETTLED, at: 3.8 },
  ],
};

const STEADY: Storyboard = {
  id: "steady",
  beats: [
    { id: "arrive", at: 0 },
    { id: "pulse", at: 0.6 },
    { id: "nod", at: 1.4 },
    { id: "title", at: 2.2 },
    { id: SETTLED, at: 3.4 },
  ],
};

/**
 * Bonk, squash, object, and straighten up.
 *
 * The order is the requirement (FR-7.7), and the shape of it has changed
 * three times. The first version kept the character upright — "knocked off
 * balance, never knocked down" — which read as the platform handling a
 * student with tongs and left the lowest tier with nothing to watch. The
 * second put them on the floor, which watched better and read as defeat.
 *
 * This one squashes them. It is the oldest joke in animation and it is a
 * *different* joke: a body that concertinas and springs back has not lost
 * anything, and the beat that follows is theirs — brows down, shouting at the
 * mallet. A character with a grievance has agency; one lying dazed on the
 * floor is only a victim. That is the line FR-7.6 actually draws, and it is
 * why the angry beat belongs here rather than being the thing to avoid.
 *
 * `recover` then puts the face and the body back to normal before the
 * encouragement arrives, so the last thing on screen is a student's own
 * character standing up straight.
 *
 * **It is played slowly, but the strike is not.** Kept from the fix this
 * merged with: the wind-up used to be held for over a second and the blow
 * itself was eased *backwards* before it fell, so it read as hovering rather
 * than hitting. The raise is a short beat now and the contact accelerates
 * into the head. The beats that follow it are the slow ones, because the
 * reaction is the part worth watching.
 *
 * The mallet arrives **from the front** rather than from overhead: wound back
 * at the right of frame, close to the camera and oversized, then swinging in
 * along an arc and shrinking to scene size as it lands. Coming straight down
 * it read as a hand reaching in from off-stage; coming at you, it is a swing.
 *
 * The reaction beats are about a second each, on a screen of their own, with
 * `Skip` in view throughout — which is what makes the length affordable at
 * all.
 */
const HAMMER: Storyboard = {
  id: "hammer",
  beats: [
    { id: "arrive", at: 0 },
    { id: HAMMER_RAISE, at: 0.5 },
    { id: "swing", at: 1.3 },
    { id: "bonk", at: 2.1 },
    { id: HAMMER_SQUASH, at: 2.4 },
    { id: HAMMER_ANGRY, at: 3.5 },
    { id: HAMMER_RECOVERY, at: 4.8 },
    { id: HAMMER_MESSAGE, at: 5.6 },
    { id: SETTLED, at: 6.6 },
  ],
};

export const TIER_STORYBOARDS: Record<RewardTier, Storyboard> = {
  crown: CROWN,
  flower: FLOWER,
  steady: STEADY,
  hammer: HAMMER,
};
