/**
 * Locating the target vocabulary inside the student's own text.
 *
 * The offsets that arrive with a score are into the *original* answer, not a
 * cleaned copy of it: normalisation keeps an index back to every character it
 * touched precisely so a highlight lands on what the student wrote. That makes
 * these offsets trustworthy — and makes a wrong one silent, since slicing past
 * the end of a string produces an empty span rather than an error, and the
 * answer would render with a word quietly missing.
 */

import { describe, expect, it } from "vitest";

import { splitAnswer } from "@/lib/results/highlight";
import type { DetectedTermOut } from "@/types/api";

function term(name: string, positions: number[][], required = true): DetectedTermOut {
  return {
    term: name,
    lemma: name,
    category: "movement",
    category_name: "Movement",
    is_required: required,
    count: positions.length,
    matched_forms: [name],
    positions,
  };
}

/** The rendered text must always be the answer, byte for byte. */
function rejoin(segments: { text: string }[]): string {
  return segments.map((segment) => segment.text).join("");
}

describe("splitting an answer", () => {
  const answer = "Sales rose sharply, then fell in June.";

  it("marks the run the offsets point at", () => {
    const segments = splitAnswer(answer, [term("rose", [[6, 10]])]);

    expect(segments.filter((segment) => segment.term)).toHaveLength(1);
    expect(segments.find((segment) => segment.term)?.text).toBe("rose");
    expect(rejoin(segments)).toBe(answer);
  });

  it("marks every occurrence of the same term", () => {
    const repeated = "It fell, and fell again.";
    const segments = splitAnswer(repeated, [
      term("fell", [
        [3, 7],
        [13, 17],
      ]),
    ]);

    expect(segments.filter((segment) => segment.term)).toHaveLength(2);
    expect(rejoin(segments)).toBe(repeated);
  });

  it("keeps the longer of two overlapping terms", () => {
    // "rise" sits inside "sharp rise"; both are legitimate targets, and marking
    // both would nest one highlight in another and show the word twice.
    const text = "There was a sharp rise in July.";
    const segments = splitAnswer(text, [term("rise", [[18, 22]]), term("sharp rise", [[12, 22]])]);

    const marked = segments.filter((segment) => segment.term);
    expect(marked).toHaveLength(1);
    expect(marked[0]?.text).toBe("sharp rise");
    expect(rejoin(segments)).toBe(text);
  });

  it("drops an offset that runs past the end of the answer", () => {
    const segments = splitAnswer("Short.", [term("nonsense", [[3, 400]])]);

    expect(segments.filter((segment) => segment.term)).toHaveLength(0);
    expect(rejoin(segments)).toBe("Short.");
  });

  it.each([
    ["negative start", [[-2, 4]]],
    ["end before start", [[9, 4]]],
    ["empty span", [[4, 4]]],
  ])("drops an unusable span: %s", (_name, positions) => {
    const segments = splitAnswer(answer, [term("x", positions)]);

    expect(segments.filter((segment) => segment.term)).toHaveLength(0);
    expect(rejoin(segments)).toBe(answer);
  });

  it("survives a term with no positions at all", () => {
    expect(rejoin(splitAnswer(answer, [term("rose", [])]))).toBe(answer);
  });

  it("returns nothing for an empty answer", () => {
    expect(splitAnswer("", [term("rose", [[0, 4]])])).toEqual([]);
  });

  it("never loses or duplicates a character, whatever the input", () => {
    const text = "A rose by any other name would rise as sweetly.";
    const segments = splitAnswer(text, [
      term("rose", [[2, 6]]),
      term("rise", [[31, 35]]),
      term("name", [[21, 25]], false),
    ]);

    expect(rejoin(segments)).toBe(text);
    expect(segments.filter((segment) => segment.term)).toHaveLength(3);
  });

  it("carries the term through, so the legend and the mark agree", () => {
    const segments = splitAnswer(answer, [term("rose", [[6, 10]], false)]);
    const marked = segments.find((segment) => segment.term);

    expect(marked?.term?.is_required).toBe(false);
    expect(marked?.term?.category_name).toBe("Movement");
  });
});
