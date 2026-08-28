/**
 * Reading a graph's shape off its figures.
 *
 * The suggestions decide which words a teacher is *offered* for the set that
 * becomes the denominator of every vocabulary score on that graph, so the
 * cases that matter are the ones where a plausible rule gets it wrong: a rise
 * that is small in absolute terms but large for its series, a plateau in the
 * middle of a climb, a maximum that is simply the end of one.
 */

import { describe, expect, it } from "vitest";

import { shapesIn, suggestTargets, type ShapeCode } from "@/lib/authoring/suggest-targets";
import type { VocabularyItemOut } from "@/types/api";

const codes = (series: (number | null)[][], type: Parameters<typeof shapesIn>[1] = "line") =>
  shapesIn(series, type).map((shape) => shape.code);

describe("what the figures do", () => {
  it("calls a rise a rise", () => {
    expect(codes([[10, 20, 30, 45]])).toContain("increase");
    expect(codes([[10, 20, 30, 45]])).not.toContain("decrease");
  });

  it("measures movement against the series' own range, not against zero", () => {
    // 98 → 100 is two units and the whole story. An absolute threshold would
    // call this flat and offer the vocabulary of stability for a graph about
    // growth.
    expect(codes([[98, 99, 100]])).toContain("increase");
  });

  it("calls a series that ends where it started stable", () => {
    expect(codes([[50, 51, 50, 49, 50]])).toContain("stability");
    expect(codes([[50, 51, 50, 49, 50]])).not.toContain("increase");
  });

  it("does not count a plateau as a change of direction", () => {
    // A flat step in the middle of a climb is not a reversal, and counting it
    // as one turns every stepped rise into a fluctuation.
    expect(codes([[10, 20, 20, 30, 40]])).not.toContain("fluctuation");
  });

  it("names fluctuation only when the reversals are the story", () => {
    expect(codes([[10, 40, 12, 38, 14, 36]])).toContain("fluctuation");
    // One dip in a long rise is not a fluctuating series.
    expect(codes([[10, 20, 18, 30, 40, 50]])).not.toContain("fluctuation");
  });

  it("does not call a zigzag a rise because of where it happens to end", () => {
    // 10 → 40 → 12 → 38 → 14 → 36 finishes 26 higher than it starts, and its
    // endpoints sit near the extremes, so measured against the *range* it
    // scores 0.87 and reads as a steady climb. Measured against the distance
    // actually travelled it scores 0.2, which is what it looks like.
    expect(codes([[10, 40, 12, 38, 14, 36]])).not.toContain("increase");
    // A rise with one dip in it is still a rise.
    expect(codes([[10, 20, 18, 30, 40, 50]])).toContain("increase");
  });

  it("does not phrase two series as one contradiction", () => {
    // "The series finishes higher" directly above "The series finishes lower"
    // reads as a mistake rather than as two facts about two series.
    const reasons = shapesIn(
      [
        [1, 2, 3],
        [9, 6, 3],
      ],
      "line",
    ).map((shape) => shape.reason);

    expect(reasons.some((reason) => reason.startsWith("The series"))).toBe(false);
  });

  it("does not call the end of a rise a peak", () => {
    // The last point of a steady climb is the highest value in the series.
    // Offering "peaked at" for it would describe a graph that is still going.
    expect(codes([[10, 20, 30, 40]])).not.toContain("peak");
    expect(codes([[10, 40, 30, 20]])).toContain("peak");
  });

  it("reads a pie as proportions rather than as a trend", () => {
    const shapes = codes([[45, 25, 18, 12]], "pie");
    expect(shapes).toContain("comparison");
    expect(shapes).not.toContain("increase");
    expect(shapes).not.toContain("decrease");
  });

  it("notices a second series", () => {
    expect(
      codes([
        [1, 2, 3],
        [3, 2, 1],
      ]),
    ).toContain("comparison");
  });

  it("says nothing at all when there is nothing to read", () => {
    expect(shapesIn([], "line")).toEqual([]);
    expect(shapesIn([[42]], "line")).toEqual([]);
    expect(shapesIn([[null, null]], "line")).toEqual([]);
  });

  it("gives every suggestion a reason a teacher can disagree with", () => {
    for (const shape of shapesIn([[10, 40, 12, 38]], "line")) {
      expect(shape.reason.length).toBeGreaterThan(10);
    }
  });
});

const term = (id: string, category: ShapeCode, weight: number): VocabularyItemOut =>
  ({
    id,
    term: id,
    lemma: id,
    is_phrase: false,
    weight,
    is_active: true,
    category_id: category,
    category_code: category,
    category_name: category,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  }) as VocabularyItemOut;

describe("which terms are offered", () => {
  const library = [
    term("rose", "increase", 1),
    term("climbed", "increase", 2),
    term("surged", "increase", 3),
    term("wavered", "fluctuation", 1),
    term("oscillated", "fluctuation", 2),
    term("fell", "decrease", 1),
  ];

  const shapes = [
    { code: "increase" as const, reason: "" },
    { code: "fluctuation" as const, reason: "" },
  ];

  it("covers every shape before going deeper into any one of them", () => {
    // Taking the top by priority overall would offer three ways of saying
    // "increase" and nothing for the shape a student is most likely to miss.
    const offered = suggestTargets(library, shapes, 4).map((item) => item.term);
    expect(offered.slice(0, 2).sort()).toEqual(["rose", "wavered"]);
    expect(offered).toContain("climbed");
    expect(offered).toContain("oscillated");
  });

  it("orders within a category by priority, which is what weight is for", () => {
    const offered = suggestTargets(library, [{ code: "increase", reason: "" }], 3);
    expect(offered.map((item) => item.term)).toEqual(["rose", "climbed", "surged"]);
  });

  it("offers nothing from a category the figures did not match", () => {
    const offered = suggestTargets(library, shapes, 6).map((item) => item.term);
    expect(offered).not.toContain("fell");
  });

  it("never offers a soft-deleted term", () => {
    // Vocabulary is soft-deleted because historical scores reference it
    // (CLAUDE.md rule 10); a retired term must not come back through a
    // suggestion.
    const retired = { ...term("obsolete", "increase", 0), is_active: false };
    const offered = suggestTargets([retired, ...library], shapes, 6).map((item) => item.term);
    expect(offered).not.toContain("obsolete");
  });

  it("returns nothing when the figures said nothing", () => {
    expect(suggestTargets(library, [], 6)).toEqual([]);
  });
});
