"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useReducedMotion } from "@/lib/hooks/use-reduced-motion";
import { hasReached, isAt, type Storyboard } from "./sequence";

export interface SequenceState {
  /** The beat currently showing. */
  index: number;
  beatId: string;
  /** True once the sequence has come to rest — the still card. */
  isSettled: boolean;
  /** Whether the sequence has passed a named beat. */
  reached: (id: string) => boolean;
  /** Whether a named beat is the current one. */
  at: (id: string) => boolean;
  /** Jump to the settled frame (FR-7.9). */
  skip: () => void;
  /** Start again from the first beat (FR-7.9). */
  replay: () => void;
  /** True when nothing is animating, because the reader asked for that. */
  reducedMotion: boolean;
}

/**
 * Plays a storyboard.
 *
 * One `setTimeout` per beat rather than a requestAnimationFrame loop: beats
 * are hundreds of milliseconds apart and nothing here interpolates, so a
 * per-frame tick would wake the main thread sixty times a second to compute an
 * index that changes six times in total.
 *
 * Under `prefers-reduced-motion` the sequence begins at its last beat and no
 * timer is ever scheduled — FR-7.10 asks for a still card, and a sequence that
 * runs at 0.01ms per beat is not the same thing as one that never starts.
 */
export function useSequence(storyboard: Storyboard, { play = true } = {}): SequenceState {
  const reducedMotion = useReducedMotion();
  const beats = storyboard.beats;
  const lastIndex = beats.length - 1;

  const [index, setIndex] = useState(0);
  // Bumped by `replay` so the effect below re-runs; the beat list alone does
  // not change, and a replay is not a change of storyboard.
  const [run, setRun] = useState(0);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  const clear = useCallback(() => {
    for (const timer of timers.current) clearTimeout(timer);
    timers.current = [];
  }, []);

  useEffect(() => {
    clear();

    if (reducedMotion || !play) {
      setIndex(lastIndex);
      return;
    }

    setIndex(0);
    timers.current = beats
      .map((beat, position) =>
        position === 0 ? null : setTimeout(() => setIndex(position), Math.round(beat.at * 1000)),
      )
      .filter((timer): timer is ReturnType<typeof setTimeout> => timer !== null);

    return clear;
  }, [beats, lastIndex, reducedMotion, play, run, clear]);

  const skip = useCallback(() => {
    clear();
    setIndex(lastIndex);
  }, [clear, lastIndex]);

  const replay = useCallback(() => {
    clear();
    setIndex(0);
    setRun((current) => current + 1);
  }, [clear]);

  return useMemo(
    () => ({
      index,
      beatId: beats[index]?.id ?? "",
      isSettled: index >= lastIndex,
      reached: (id: string) => hasReached(beats, index, id),
      at: (id: string) => isAt(beats, index, id),
      skip,
      replay,
      reducedMotion,
    }),
    [beats, index, lastIndex, skip, replay, reducedMotion],
  );
}
