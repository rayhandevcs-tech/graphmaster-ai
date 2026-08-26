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
import { TIER_BANDS, TIER_ICONS, TIER_LABELS, TIER_ORDER } from "@/components/gamification/tiers";
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
      />,
    );

    // NFR-4.6: a colour-blind student still has to be able to read which tier
    // this is. The label appears twice — as the eyebrow and in the note.
    expect(screen.getAllByText(new RegExp(TIER_LABELS[tier], "i")).length).toBeGreaterThan(0);
  });
});
