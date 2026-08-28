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
    { id: "crown", at: 0.3 },
    { id: CROWN_LANDING, at: 0.7 },
    { id: CROWN_DELIGHT, at: 1.2 },
    { id: "confetti", at: 1.5 },
    { id: "title", at: 1.9 },
    { id: SETTLED, at: 2.9 },
  ],
};

const FLOWER: Storyboard = {
  id: "flower",
  beats: [
    { id: "arrive", at: 0 },
    { id: "bloom", at: 0.3 },
    { id: "spin", at: 0.8 },
    { id: "title", at: 1.2 },
    { id: SETTLED, at: 1.9 },
  ],
};

const STEADY: Storyboard = {
  id: "steady",
  beats: [
    { id: "arrive", at: 0 },
    { id: "pulse", at: 0.3 },
    { id: "nod", at: 0.7 },
    { id: "title", at: 1.1 },
    { id: SETTLED, at: 1.6 },
  ],
};

/**
 * Bonk, over, and back up.
 *
 * The order is the requirement (FR-7.7), and the shape of it changed. The
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
 * `dazed` is half a second. Long enough to land the joke, short enough that
 * nobody watches a student's avatar lie on the floor — and the whole sequence
 * still fits the three-second ceiling every tier is held to, because a student
 * who scored badly must not be made to watch for longer than one who did well.
 *
 * `message` reveals the server's own encouragement, which is on the card from
 * the first frame regardless; nothing here composes text.
 */
const HAMMER: Storyboard = {
  id: "hammer",
  beats: [
    { id: "arrive", at: 0 },
    { id: "swing", at: 0.2 },
    { id: "bonk", at: 0.5 },
    { id: HAMMER_FALL, at: 0.8 },
    { id: "dazed", at: 1.3 },
    { id: HAMMER_RECOVERY, at: 1.8 },
    { id: HAMMER_MESSAGE, at: 2.3 },
    { id: SETTLED, at: 3 },
  ],
};

export const TIER_STORYBOARDS: Record<RewardTier, Storyboard> = {
  crown: CROWN,
  flower: FLOWER,
  steady: STEADY,
  hammer: HAMMER,
};
