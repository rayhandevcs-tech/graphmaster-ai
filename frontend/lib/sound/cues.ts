/**
 * The reward cues, as notes rather than as files.
 *
 * Nothing here downloads. A celebration that has to fetch an asset before it
 * can play arrives after the moment it was for, and a reward system whose
 * sounds can 404 is worse than a silent one — the two Sprint 12 defects that
 * would have been hardest to notice in review both came from assets that were
 * never actually served.
 *
 * Frequencies are equal-temperament, written as notes so the intervals are
 * legible: the crown is a major arpeggio resolving upward, the flower a rising
 * fifth, the steady tier a single settled tone. The hammer's two are the only
 * ones that are not musical — a short square blip on the contact, and a
 * descending brass figure as the character goes over. Both are the sounds a
 * cartoon makes, which is the point: they are what stop a low score reading as
 * a reprimand.
 */

export type Cue = "victory" | "chime" | "soft" | "bonk" | "wah";

export interface Note {
  /** Hertz. */
  frequency: number;
  /** Seconds from the start of the cue. */
  at: number;
  duration: number;
  type: OscillatorType;
  /** Peak gain for this note, before the master level. */
  gain: number;
}

const C5 = 523.25;
const E5 = 659.25;
const G5 = 783.99;
const C6 = 1046.5;
const B5 = 987.77;
const A4 = 440;

export const CUES: Record<Cue, Note[]> = {
  /** Crown: a major arpeggio, arriving. */
  victory: [
    { frequency: C5, at: 0, duration: 0.14, type: "triangle", gain: 0.9 },
    { frequency: E5, at: 0.1, duration: 0.14, type: "triangle", gain: 0.9 },
    { frequency: G5, at: 0.2, duration: 0.16, type: "triangle", gain: 0.9 },
    { frequency: C6, at: 0.32, duration: 0.42, type: "triangle", gain: 1 },
  ],

  /** Flower: a rising fifth. Pleased, not triumphant. */
  chime: [
    { frequency: E5, at: 0, duration: 0.16, type: "sine", gain: 0.9 },
    { frequency: B5, at: 0.12, duration: 0.34, type: "sine", gain: 0.8 },
  ],

  /** Steady: one tone, settling. */
  soft: [{ frequency: A4, at: 0, duration: 0.4, type: "sine", gain: 0.7 }],

  /**
   * Hammer: a comic blip.
   *
   * Deliberately short and low rather than harsh. The joke is the timing, and
   * a sound that startles is the one thing that would turn slapstick into
   * something a student flinches at.
   */
  bonk: [
    { frequency: 196, at: 0, duration: 0.09, type: "square", gain: 0.55 },
    { frequency: 110, at: 0.06, duration: 0.14, type: "square", gain: 0.4 },
  ],

  /**
   * The fall: four semitones down, the last one held.
   *
   * The cartoon "wah-wah-waaah". It plays as the character goes over, not on
   * the contact — a descending figure that lands with the blow reads as the
   * platform's verdict on the score, and a beat later it reads as the
   * character's own reaction to falling over. That gap is the entire
   * difference between slapstick and a scolding, and it is the reason this is
   * a separate cue rather than four more notes on the end of `bonk`.
   *
   * A sawtooth, quietly. It is the only voice here with enough harmonics to
   * read as brass, and at this gain — under the 0.16 master — it stays comic
   * rather than blaring in a shared computer lab.
   */
  wah: [
    { frequency: 233.08, at: 0, duration: 0.14, type: "sawtooth", gain: 0.34 },
    { frequency: 220, at: 0.13, duration: 0.14, type: "sawtooth", gain: 0.32 },
    { frequency: 207.65, at: 0.26, duration: 0.14, type: "sawtooth", gain: 0.3 },
    { frequency: 196, at: 0.39, duration: 0.34, type: "sawtooth", gain: 0.28 },
  ],
};
