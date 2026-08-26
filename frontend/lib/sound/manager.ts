"use client";

import { CUES, type Cue } from "./cues";

/**
 * Reward sound, muted until asked for.
 *
 * FR-7.11, and not only because the specification says so: audio that starts
 * unprompted is hostile in a shared computer lab or a library, which is
 * exactly where this platform is used. Browsers also block unprompted
 * autoplay, so an unmuted default would fail inconsistently rather than
 * loudly.
 *
 * The preference lives in `localStorage`, per browser rather than per account.
 * A student on a lab machine who turns sound on for one lesson has not asked
 * for it on every machine they ever sign in from.
 *
 * The `AudioContext` is created the first time something plays and never
 * before. An audio context constructed on page load is a suspended object the
 * browser holds open for a sound that may never come.
 */

const STORAGE_KEY = "graphmaster:sound";
const MASTER_GAIN = 0.16;

type Listener = (enabled: boolean) => void;

let context: AudioContext | null = null;
let cachedPreference: boolean | null = null;
const listeners = new Set<Listener>();

/** `localStorage` throws in a sandboxed frame and in some privacy modes. */
function readStorage(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "on";
  } catch {
    return false;
  }
}

export function isSoundEnabled(): boolean {
  if (typeof window === "undefined") return false;
  if (cachedPreference === null) cachedPreference = readStorage();
  return cachedPreference;
}

export function setSoundEnabled(enabled: boolean): void {
  cachedPreference = enabled;
  try {
    window.localStorage.setItem(STORAGE_KEY, enabled ? "on" : "off");
  } catch {
    // A browser refusing storage is not a reason to refuse the setting for
    // this page view.
  }
  for (const listener of listeners) listener(enabled);
}

export function subscribeToSound(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function audioContext(): AudioContext | null {
  if (typeof window === "undefined") return null;

  const Constructor =
    window.AudioContext ??
    (window as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Constructor) return null;

  context ??= new Constructor();
  return context;
}

/**
 * Play a cue, if sound is on.
 *
 * A no-op when it is off, when the browser has no Web Audio, or when the
 * context is still suspended because the page has had no user gesture — which
 * is the case on a hard reload of a result page, and is not worth reporting to
 * anyone. The common path arrives here by client-side navigation from the
 * submit button, so the gesture has already happened in this document.
 */
export function playCue(cue: Cue): void {
  if (!isSoundEnabled()) return;

  const ctx = audioContext();
  if (!ctx) return;

  if (ctx.state === "suspended") void ctx.resume().catch(() => {});

  const start = ctx.currentTime + 0.02;
  for (const note of CUES[cue]) {
    const oscillator = ctx.createOscillator();
    const envelope = ctx.createGain();

    oscillator.type = note.type;
    oscillator.frequency.setValueAtTime(note.frequency, start + note.at);

    // A short attack and an exponential decay: a square wave switched on and
    // off at full gain clicks, and the click is louder than the note.
    const peak = MASTER_GAIN * note.gain;
    envelope.gain.setValueAtTime(0.0001, start + note.at);
    envelope.gain.exponentialRampToValueAtTime(peak, start + note.at + 0.012);
    envelope.gain.exponentialRampToValueAtTime(0.0001, start + note.at + note.duration);

    oscillator.connect(envelope).connect(ctx.destination);
    oscillator.start(start + note.at);
    oscillator.stop(start + note.at + note.duration + 0.02);
  }
}

/** For tests: forget the cached preference and the context. */
export function resetSoundForTests(): void {
  cachedPreference = null;
  context = null;
  listeners.clear();
}
