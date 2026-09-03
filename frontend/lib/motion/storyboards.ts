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
/** The mallet, raised in front of the character before it comes down. */
export const HAMMER_RAISE = "raise";
export const HAMMER_FALL = "fall";
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
 * Bonk, over, and back up.
 *
 * The order is the requirement (FR-7.7), and the shape of it has changed
 * twice. The
 * first version kept the character on its feet — "knocked off balance, never
 * knocked down" — on the reasoning that a fall would read as humiliating.
 * Watching it, the opposite is true. A small wobble reads as *the platform
 * being careful with you*, which a student notices, and it makes the low tier
 * the one moment in the product with nothing to watch.
 *
 * What makes slapstick kind is not the size of the fall. It is that the
 * character is the comedian rather than the target, and that getting up is the
 * biggest movement in the sequence. So: `fall` puts them on the floor, `dazed`
 * holds it long enough to be funny — and `rise` is the longest, largest beat
 * here, followed immediately by the encouragement.
 *
 * **It is played slowly, but the strike is not.** The whole thing used to take
 * three seconds: a swing and a fall in well under one each. Legible, but not
 * watchable — the joke had no time to land and the recovery went past before
 * it registered. The celebration is now the only thing on screen while it
 * plays, so the fall and the getting-up each get a beat of their own. The
 * wind-up is the exception: an earlier pass held the raised mallet for over a
 * second and eased the blow itself *backwards* before it fell, so it read as
 * hovering rather than hitting. The raise is now a short beat and the contact
 * accelerates into the head.
 *
 * `dazed` is over a second now. Long enough to be funny, short enough that
 * nobody sits watching a student's avatar lie on the floor — and `Skip` is on
 * screen the entire time, which is what makes the length affordable at all.
 *
 * `message` reveals the server's own encouragement, which is on the card from
 * the first frame regardless; nothing here composes text.
 */
const HAMMER: Storyboard = {
  id: "hammer",
  beats: [
    { id: "arrive", at: 0 },
    { id: HAMMER_RAISE, at: 0.5 },
    { id: "swing", at: 1.15 },
    { id: "bonk", at: 1.95 },
    { id: HAMMER_FALL, at: 2.95 },
    { id: "dazed", at: 3.95 },
    { id: HAMMER_RECOVERY, at: 5.0 },
    { id: HAMMER_MESSAGE, at: 6.0 },
    { id: SETTLED, at: 7.1 },
  ],
};

export const TIER_STORYBOARDS: Record<RewardTier, Storyboard> = {
  crown: CROWN,
  flower: FLOWER,
  steady: STEADY,
  hammer: HAMMER,
};
