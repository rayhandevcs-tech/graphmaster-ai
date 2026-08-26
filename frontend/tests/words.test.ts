/**
 * Counting words the way the server counts them.
 *
 * The composer shows a running count and the score's length component is
 * derived from the server's own count. If the two disagree a student sees 214
 * words and is marked over 209, which reads as the marking being wrong rather
 * than as two regexes differing.
 */

import { describe, expect, it } from "vitest";

import { countWords, wordsLabel } from "@/lib/text/words";

describe("counting words", () => {
  it("counts plain prose", () => {
    expect(countWords("Sales rose sharply in June.")).toBe(5);
  });

  it("treats a hyphenated compound as one word, as the server does", () => {
    expect(countWords("a well-known upward trend")).toBe(4);
  });

  it("does not split a contraction", () => {
    expect(countWords("it doesn't fall")).toBe(3);
  });

  it("counts numerals", () => {
    expect(countWords("rose to 45 percent")).toBe(4);
  });

  it("ignores punctuation and whitespace", () => {
    expect(countWords("  Rising —  and   falling ...  ")).toBe(3);
  });

  it("is zero for nothing written", () => {
    expect(countWords("")).toBe(0);
    expect(countWords("   \n  ")).toBe(0);
  });

  it("gets the singular right", () => {
    expect(wordsLabel(1)).toBe("1 word");
    expect(wordsLabel(0)).toBe("0 words");
    expect(wordsLabel(1200)).toBe("1,200 words");
  });
});
