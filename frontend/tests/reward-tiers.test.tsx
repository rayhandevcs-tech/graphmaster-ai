/**
 * How a reward tier reaches the screen.
 *
 * Three product rules meet here, and all three are easy to break with a
 * well-meaning edit: the tier comes from the vocabulary percentage rather than
 * the final score, the lowest tier is never humiliating, and the words a
 * student reads are the engine's rather than the client's.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TierPanel } from "@/components/gamification/tier-panel";
import { VocabularyPanel } from "@/components/results/vocabulary-panel";
import { TIER_BANDS, TIER_ICONS, TIER_LABELS, TIER_ORDER } from "@/components/gamification/tiers";
import {
  HAMMER_MESSAGE,
  HAMMER_RECOVERY,
  SETTLED,
  TIER_STORYBOARDS,
} from "@/lib/motion/storyboards";
import { beatIndexAt, sequenceDuration } from "@/lib/motion/sequence";
import type { FeedbackOut, RewardTier } from "@/types/api";

const feedback = (headline: string, message: string): FeedbackOut => ({
  headline,
  message,
  strengths: [],
  improvements: [],
  missing_by_category: {},
  next_step: "",
});

describe("the tier table", () => {
  it("covers all four tiers", () => {
    expect(TIER_ORDER).toEqual(["crown", "flower", "steady", "hammer"]);
  });

  it.each(TIER_ORDER)("%s has a label, an icon and a band", (tier) => {
    expect(TIER_LABELS[tier]).toBeTruthy();
    expect(TIER_ICONS[tier]).toBeTruthy();
    expect(TIER_BANDS[tier]).toBeTruthy();
  });

  it("never labels the lowest tier with the word the database uses", () => {
    // `hammer` is a storage value. On screen it is "Practice tier": the
    // animation ends in recovery and the wording has to match (FR-7.7).
    expect(TIER_LABELS.hammer.toLowerCase()).not.toContain("hammer");
    for (const word of ["fail", "poor", "bad", "weak"]) {
      expect(TIER_LABELS.hammer.toLowerCase()).not.toContain(word);
    }
  });
});

describe("the tier panel", () => {
  it("renders the engine's headline and message untouched", () => {
    // The crown headline is gendered server-side and the lowest tier's message
    // is specified verbatim. Paraphrasing either here is the one way to break
    // a rule the backend asserts.
    const message = "Keep Practicing! You Can Improve! You used 4 of 12 target terms.";
    render(
      <TierPanel
        tier="hammer"
        feedback={feedback("Keep Practicing!", message)}
        vocabularyPercentage={33.3}
        avatarCode="girl_default"
      />,
    );

    expect(screen.getByText("Keep Practicing!")).toBeInTheDocument();
    expect(screen.getByText(message)).toBeInTheDocument();
  });

  it("says the tier came from the vocabulary percentage", () => {
    render(
      <TierPanel
        tier="flower"
        feedback={feedback("Rising Writer", "Good work.")}
        vocabularyPercentage={74}
        avatarCode="girl_default"
      />,
    );

    expect(screen.getByText(/74%/)).toBeInTheDocument();
    expect(screen.getByText(/not from your final score/i)).toBeInTheDocument();
    expect(screen.getByText(/60–89%/)).toBeInTheDocument();
  });

  it.each(TIER_ORDER)("names the tier in words for %s, not only in colour", (tier: RewardTier) => {
    render(
      <TierPanel
        tier={tier}
        feedback={feedback("A headline", "A message.")}
        vocabularyPercentage={50}
        avatarCode="boy_scholar"
      />,
    );

    // NFR-4.6: a colour-blind student still has to be able to read which tier
    // this is. The label appears twice — as the eyebrow and in the note.
    expect(screen.getAllByText(new RegExp(TIER_LABELS[tier], "i")).length).toBeGreaterThan(0);
  });
});

/**
 * The celebrations, read as data.
 *
 * This is the point of storyboards being a list rather than control flow: the
 * requirement that the hammer ends in recovery is a property of an array, and
 * asserting it needs no timers, no rendering and no waiting three seconds.
 */
describe("the tier storyboards", () => {
  it.each(TIER_ORDER)("%s starts at zero and ends settled", (tier: RewardTier) => {
    const beats = TIER_STORYBOARDS[tier].beats;

    expect(beats[0]?.at).toBe(0);
    expect(beats[beats.length - 1]?.id).toBe(SETTLED);
  });

  it.each(TIER_ORDER)("%s runs strictly forwards", (tier: RewardTier) => {
    const times = TIER_STORYBOARDS[tier].beats.map((beat) => beat.at);
    expect([...times].sort((a, b) => a - b)).toEqual(times);
    expect(new Set(times).size).toBe(times.length);
  });

  it("ends the hammer on recovery and the encouragement, in that order (FR-7.7)", () => {
    const ids = TIER_STORYBOARDS.hammer.beats.map((beat) => beat.id);

    // The last three, in order: the character gets back up, is told it can
    // improve, and the card comes to rest. Nothing may be appended after the
    // knock without also passing through these.
    expect(ids.slice(-3)).toEqual([HAMMER_RECOVERY, HAMMER_MESSAGE, SETTLED]);
  });

  it("never leaves the hammer's character down for long", () => {
    const beats = TIER_STORYBOARDS.hammer.beats;
    const at = (id: string) => beats.find((beat) => beat.id === id)?.at ?? -1;

    // Knocked off balance, not knocked down: the wobble is under half a
    // second, and the recovery follows it immediately.
    expect(at(HAMMER_RECOVERY) - at("wobble")).toBeLessThanOrEqual(0.5);
    expect(at(HAMMER_RECOVERY)).toBeGreaterThan(at("bonk"));
  });

  it("keeps every celebration short enough to sit through", () => {
    // A student who scored badly should not be watching for longer than one
    // who scored well; three seconds is the ceiling for all of them.
    for (const tier of TIER_ORDER) {
      expect(sequenceDuration(TIER_STORYBOARDS[tier])).toBeLessThanOrEqual(3);
    }
  });

  it("resolves the beat playing at a given moment", () => {
    const beats = TIER_STORYBOARDS.hammer.beats;

    expect(beats[beatIndexAt(beats, 0)]?.id).toBe("arrive");
    expect(beats[beatIndexAt(beats, 0.6)]?.id).toBe("bonk");
    expect(beats[beatIndexAt(beats, 1.9)]?.id).toBe(HAMMER_RECOVERY);
    // Past the end it stays settled rather than running off the array.
    expect(beats[beatIndexAt(beats, 99)]?.id).toBe(SETTLED);
  });
});

describe("the vocabulary sentence", () => {
  const score = (overrides: Record<string, unknown> = {}) =>
    ({
      vocabulary_score: 67,
      writing_score: 71,
      final_score: 71,
      vocabulary_percentage: 67,
      total_target_count: 12,
      unique_detected_count: 4,
      detected_count: 4,
      detected_terms: [],
      missing_terms: [],
      category_breakdown: {},
      reward_tier: "flower",
      ...overrides,
    }) as never;

  it("states the ratio when there is a denominator", () => {
    render(<VocabularyPanel score={score()} />);
    expect(screen.getByText(/You used 4 of the 12 required target terms/)).toBeInTheDocument();
  });

  it("never writes a ratio against zero", () => {
    // "You used 4 of the 0 required target terms" is not a sentence.
    render(<VocabularyPanel score={score({ total_target_count: 0 })} />);

    expect(screen.queryByText(/of the 0 required/)).not.toBeInTheDocument();
    expect(screen.getByText(/no required target terms set/i)).toBeInTheDocument();
    expect(screen.getByText(/You used 4 target terms anyway/)).toBeInTheDocument();
  });

  it("says only what happened when there is neither a denominator nor a hit", () => {
    render(<VocabularyPanel score={score({ total_target_count: 0, unique_detected_count: 0 })} />);

    expect(screen.getByText(/no vocabulary percentage to earn\.$/i)).toBeInTheDocument();
    expect(screen.queryByText(/anyway/)).not.toBeInTheDocument();
  });
});
