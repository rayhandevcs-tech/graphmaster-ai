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
export const HAMMER_RECOVERY = "recover";
export const HAMMER_MESSAGE = "message";

const CROWN: Storyboard = {
  id: "crown",
  beats: [
    { id: "arrive", at: 0 },
    { id: "crown", at: 0.35 },
    { id: "sparkle", at: 0.85 },
    { id: "confetti", at: 1.25 },
    { id: "title", at: 1.6 },
    { id: SETTLED, at: 2.6 },
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
 * Bonk, and back up.
 *
 * The order is the requirement (FR-7.7). `wobble` is short and small on
 * purpose — the character is knocked off balance, never knocked down — and it
 * exists only so that `recover` has something to answer. `message` reveals the
 * server's own encouragement, which is on the card from the first frame
 * regardless; nothing here composes text.
 */
const HAMMER: Storyboard = {
  id: "hammer",
  beats: [
    { id: "arrive", at: 0 },
    { id: "swing", at: 0.25 },
    { id: "bonk", at: 0.55 },
    { id: "dizzy", at: 0.75 },
    { id: "wobble", at: 1.3 },
    { id: HAMMER_RECOVERY, at: 1.7 },
    { id: HAMMER_MESSAGE, at: 2.2 },
    { id: SETTLED, at: 3.0 },
  ],
};

export const TIER_STORYBOARDS: Record<RewardTier, Storyboard> = {
  crown: CROWN,
  flower: FLOWER,
  steady: STEADY,
  hammer: HAMMER,
};
