/**
 * Reward sound.
 *
 * The rule that matters is a default, and a default is exactly the kind of
 * thing that survives review and then quietly flips: **muted until asked for**
 * (FR-7.11). Audio that starts unprompted is hostile in a shared computer lab
 * or a library, which is where this platform is used.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

import { CUES } from "@/lib/sound/cues";
import {
  isSoundEnabled,
  playCue,
  resetSoundForTests,
  setSoundEnabled,
  subscribeToSound,
} from "@/lib/sound/manager";

beforeEach(() => {
  resetSoundForTests();
  try {
    window.localStorage.clear();
  } catch {
    // Some environments refuse storage; the manager tolerates that too.
  }
});

describe("the sound preference", () => {
  it("is off before anyone has said otherwise", () => {
    expect(isSoundEnabled()).toBe(false);
  });

  it("stays off across a reload once it has never been set", () => {
    resetSoundForTests();
    expect(isSoundEnabled()).toBe(false);
  });

  it("is remembered once turned on", () => {
    setSoundEnabled(true);
    resetSoundForTests();
    expect(isSoundEnabled()).toBe(true);
  });

  it("tells every control that shows it", () => {
    const seen: boolean[] = [];
    const stop = subscribeToSound((enabled) => seen.push(enabled));

    setSoundEnabled(true);
    setSoundEnabled(false);
    stop();
    setSoundEnabled(true);

    // The third change lands after unsubscribing and must not be delivered.
    expect(seen).toEqual([true, false]);
  });

  it("survives a browser that refuses storage", () => {
    const getItem = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("denied");
    });
    const setItem = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("denied");
    });

    resetSoundForTests();
    expect(isSoundEnabled()).toBe(false);
    expect(() => setSoundEnabled(true)).not.toThrow();
    // The setting still applies to this page view, it simply is not persisted.
    expect(isSoundEnabled()).toBe(true);

    getItem.mockRestore();
    setItem.mockRestore();
  });
});

describe("playing a cue", () => {
  it("builds no audio context while sound is off", () => {
    const construct = vi.fn();
    vi.stubGlobal(
      "AudioContext",
      class {
        constructor() {
          construct();
        }
      },
    );

    playCue("victory");

    // Not merely silent: nothing is constructed at all. A suspended context
    // held open for a sound that never comes is a resource leak with no
    // audible symptom.
    expect(construct).not.toHaveBeenCalled();
  });

  it("does nothing in a browser with no Web Audio", () => {
    setSoundEnabled(true);
    vi.stubGlobal("AudioContext", undefined);
    vi.stubGlobal("webkitAudioContext", undefined);

    expect(() => playCue("bonk")).not.toThrow();
  });
});

describe("the cues themselves", () => {
  it("carries every cue the celebrations ask for", () => {
    expect(Object.keys(CUES).sort()).toEqual(["bonk", "chime", "soft", "victory"]);
  });

  it("keeps each one short", () => {
    // These play under an animation beat, not over it. A cue still sounding
    // when the next thing happens reads as lag.
    for (const [name, notes] of Object.entries(CUES)) {
      const end = Math.max(...notes.map((note) => note.at + note.duration));
      expect(end, `${name} runs too long`).toBeLessThanOrEqual(0.8);
    }
  });

  it("keeps the hammer's cue low and brief rather than harsh", () => {
    // The joke is the timing. A sound that startles is the one thing that
    // would turn slapstick into something a student flinches at (FR-7.6).
    const bonk = CUES.bonk;
    expect(Math.max(...bonk.map((note) => note.frequency))).toBeLessThan(400);
    expect(Math.max(...bonk.map((note) => note.at + note.duration))).toBeLessThan(0.3);
  });
});
