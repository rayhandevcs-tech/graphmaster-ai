"use client";

import { useCallback, useEffect, useState } from "react";

import type { Cue } from "./cues";
import { isSoundEnabled, playCue, setSoundEnabled, subscribeToSound } from "./manager";

/**
 * The sound preference, shared by every control that shows it.
 *
 * Starts `false` on the server and on the first client render — the preference
 * is in `localStorage`, which the server cannot read, and asserting the stored
 * value before hydration is a mismatch. The effect corrects it immediately,
 * and the only cost is that a muted icon appears for one frame to a student
 * who has sound on.
 */
export function useSound() {
  const [enabled, setEnabledState] = useState(false);

  useEffect(() => {
    setEnabledState(isSoundEnabled());
    return subscribeToSound(setEnabledState);
  }, []);

  const toggle = useCallback(() => setSoundEnabled(!isSoundEnabled()), []);
  const play = useCallback((cue: Cue) => playCue(cue), []);

  return { enabled, toggle, setEnabled: setSoundEnabled, play };
}
