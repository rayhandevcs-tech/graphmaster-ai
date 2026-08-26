/**
 * A celebration as data.
 *
 * A storyboard is an ordered list of beats and the times they start. Nothing
 * here runs anything; `useSequence` advances an index against the clock and
 * the components read it. That shape is deliberate, and three requirements
 * fall out of it rather than having to be implemented and then remembered:
 *
 * - **Skip** (FR-7.9) sets the index to the last beat, which *is* the settled
 *   state.
 * - **Replay** (FR-7.9) sets it back to zero.
 * - **Reduced motion** (FR-7.10) starts at the last beat, so what a student
 *   sees is this same component in its final frame — not a separate static
 *   card that can drift out of step with the animated one.
 *
 * It also makes FR-7.7 provable. The hammer sequence must end in recovery and
 * must carry the encouragement; a test reads the list and asserts it. There is
 * no branch that could end the sequence early, because there is no branch.
 */

export interface Beat {
  /** Stable identifier the components switch on. */
  id: string;
  /** Seconds from the start of the sequence. The first beat is always 0. */
  at: number;
}

export interface Storyboard {
  id: string;
  beats: readonly Beat[];
}

/** Where the sequence has reached at `seconds`. */
export function beatIndexAt(beats: readonly Beat[], seconds: number): number {
  let index = 0;
  for (let i = 0; i < beats.length; i += 1) {
    const beat = beats[i];
    if (beat && beat.at <= seconds) index = i;
    else break;
  }
  return index;
}

/** True once the sequence has reached `id` — "has the crown landed yet". */
export function hasReached(beats: readonly Beat[], index: number, id: string): boolean {
  const target = beats.findIndex((beat) => beat.id === id);
  return target >= 0 && index >= target;
}

/** True only while `id` is the current beat. */
export function isAt(beats: readonly Beat[], index: number, id: string): boolean {
  return beats[index]?.id === id;
}

/** How long the whole sequence runs, in seconds. */
export function sequenceDuration(storyboard: Storyboard): number {
  return storyboard.beats[storyboard.beats.length - 1]?.at ?? 0;
}
