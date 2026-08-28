import type { GraphType, VocabularyItemOut } from "@/types/api";

/**
 * Which vocabulary a graph is likely to need, read off the figures.
 *
 * **The problem this solves.** A teacher who has just typed in a chart is then
 * shown a searchable list of every term in the library and asked to pick the
 * ones it should be marked on. That is the step where authoring stalls: the
 * answer is obvious from the numbers they just entered, and the interface
 * makes them go and find it. A graph with no required targets cannot be
 * published at all (CLAUDE.md rule 12), so the stall is not cosmetic.
 *
 * **It suggests, and never decides.** Every suggestion arrives switched off
 * with the reason it was made — "the direction changes four times" — so a
 * teacher accepts, edits or ignores it. Required targets are the denominator
 * of the vocabulary percentage: a set assembled without anyone looking at it
 * is a graph marked on the wrong words.
 *
 * **The shapes are the seeded categories**, not a vocabulary of their own.
 * `increase`, `decrease`, `fluctuation`, `stability`, `comparison`, `peak` and
 * `lowest` are the codes in `db/seed/data.py`, which is what lets a match be a
 * lookup rather than a mapping table that drifts from the seed.
 */

/** A seeded vocabulary category code. */
export type ShapeCode =
  "increase" | "decrease" | "fluctuation" | "stability" | "comparison" | "peak" | "lowest";

export interface Shape {
  code: ShapeCode;
  /** Shown beside the suggestion, so it can be judged rather than trusted. */
  reason: string;
}

const isNumber = (value: number | null): value is number => typeof value === "number";

/**
 * What the figures do.
 *
 * Everything here is measured against the series' own range rather than
 * against absolute values, so a rise from 98 to 100 in a series that never
 * moves more than two counts as a rise. An absolute threshold would call it
 * flat and suggest the vocabulary of stability for a graph about growth.
 */
export function shapesIn(series: (number | null)[][], graphType: GraphType): Shape[] {
  const found = new Map<ShapeCode, string>();
  const add = (code: ShapeCode, reason: string) => {
    if (!found.has(code)) found.set(code, reason);
  };

  const usable = series.map((points) => points.filter(isNumber)).filter((p) => p.length >= 2);
  if (usable.length === 0) return [];

  if (graphType === "pie") {
    // A pie has no direction, so none of the trend shapes apply to it. What it
    // has is parts of a whole, and the two ends of that.
    add("comparison", "A pie chart is read as proportions of a whole.");

    const points = usable[0] as number[];
    const total = points.reduce((sum, value) => sum + Math.max(value, 0), 0);
    if (total > 0) {
      const share = (value: number) => Math.round((value / total) * 100);
      const largest = Math.max(...points);
      const smallest = Math.min(...points);
      if (share(largest) >= 30) {
        add("peak", `The largest slice is ${share(largest)}% of the whole.`);
      }
      if (share(smallest) <= 12) {
        add("lowest", `The smallest slice is ${share(smallest)}% of the whole.`);
      }
    }
    return ordered(found);
  }

  if (usable.length > 1) {
    add("comparison", `${usable.length} series are plotted together.`);
  }

  const subject = usable.length > 1 ? "One of the series" : "The series";

  for (const points of usable) {
    const first = points[0] as number;
    const last = points[points.length - 1] as number;
    const highest = Math.max(...points);
    const lowest = Math.min(...points);
    const span = highest - lowest;
    const net = last - first;

    // How often the direction reverses. Flat steps are skipped rather than
    // counted as a change, or a plateau in the middle of a rise would read as
    // two reversals.
    let turns = 0;
    let previous = 0;
    for (let index = 1; index < points.length; index += 1) {
      const step = (points[index] as number) - (points[index - 1] as number);
      const direction = step > 0 ? 1 : step < 0 ? -1 : 0;
      if (direction !== 0 && previous !== 0 && direction !== previous) turns += 1;
      if (direction !== 0) previous = direction;
    }

    // Two independent measures, because one of them alone gets a real case
    // wrong every time.
    //
    // `quiet` compares the movement to the size of the numbers. 50 → 51 → 50
    // is a wobble on a base of fifty; the same two units between 2 and 4 is a
    // doubling. Without this, only a perfectly flat line is ever stable, and
    // "levelled off" and "remained steady" are never suggested for anything.
    //
    // `directed` compares the net movement to the distance actually travelled.
    // Against the *range* instead, a zigzag from 10 to 40 to 12 to 38 to 14 to
    // 36 scores 0.87 and gets described as a steady rise, because its two
    // endpoints happen to sit near the extremes. Against the travelled
    // distance it scores 0.2, which is what it looks like.
    const scale = points.reduce((sum, value) => sum + Math.abs(value), 0) / points.length;
    const quiet = scale > 0 ? span / scale < 0.1 : span === 0;

    let travelled = 0;
    for (let index = 1; index < points.length; index += 1) {
      travelled += Math.abs((points[index] as number) - (points[index - 1] as number));
    }
    const directed = travelled > 0 && Math.abs(net) / travelled >= 0.5;

    if (span === 0 || (quiet && !directed)) {
      add("stability", `${subject} barely moves next to the size of its own figures.`);
    }
    if (directed && net > 0) {
      add("increase", `${subject} finishes higher than it starts, and mostly climbs to get there.`);
    }
    if (directed && net < 0) {
      add("decrease", `${subject} finishes lower than it starts, and mostly falls to get there.`);
    }

    // Three reversals, not two. A single dip in a long rise produces exactly
    // two direction changes — down, then up again — so a threshold of two
    // calls every stepped climb a fluctuation. And a series whose whole range
    // is a rounding error on its own values is not fluctuating either.
    if (!quiet && turns >= Math.max(3, Math.floor((points.length - 1) / 2.5))) {
      add("fluctuation", `${subject} changes direction ${turns} times.`);
    }

    // A peak worth naming is an interior one. The last point of a steady rise
    // is the highest value in the series and is not a peak — calling it one
    // would suggest "peaked at" for a graph that is still climbing.
    if (span > 0) {
      const at = points.indexOf(highest);
      if (at > 0 && at < points.length - 1) {
        add("peak", "The highest value falls inside the period, not at either end.");
      }
      const bottom = points.indexOf(lowest);
      if (bottom > 0 && bottom < points.length - 1) {
        add("lowest", "The lowest value falls inside the period, not at either end.");
      }
    }
  }

  return ordered(found);
}

/** Stable order, so the same figures always suggest the same terms. */
const ORDER: ShapeCode[] = [
  "increase",
  "decrease",
  "fluctuation",
  "stability",
  "peak",
  "lowest",
  "comparison",
];

function ordered(found: Map<ShapeCode, string>): Shape[] {
  return ORDER.filter((code) => found.has(code)).map((code) => ({
    code,
    reason: found.get(code) as string,
  }));
}

/**
 * The terms to offer, given what the figures do.
 *
 * Two rules, and both matter:
 *
 * - **Priority order within a category.** `weight` is the suggestion order and
 *   nothing else — it has no effect on any score (CLAUDE.md rule 41) — so this
 *   is the one place in the product it is actually for.
 * - **Round-robin across categories.** A graph that both rises and fluctuates
 *   gets terms for both. Taking the top six by priority overall would offer
 *   six ways of saying "increase" and nothing for the shape a student is most
 *   likely to miss.
 */
export function suggestTargets(
  items: VocabularyItemOut[],
  shapes: Shape[],
  limit = 6,
): VocabularyItemOut[] {
  const codes = shapes.map((shape) => shape.code);
  if (codes.length === 0) return [];

  const byCategory = new Map<string, VocabularyItemOut[]>();
  for (const item of items) {
    if (!item.is_active || !codes.includes(item.category_code as ShapeCode)) continue;
    const list = byCategory.get(item.category_code) ?? [];
    list.push(item);
    byCategory.set(item.category_code, list);
  }
  for (const list of byCategory.values()) {
    list.sort((a, b) => a.weight - b.weight || a.term.localeCompare(b.term));
  }

  const present = codes.filter((code) => byCategory.has(code));
  const picked: VocabularyItemOut[] = [];

  for (let round = 0; picked.length < limit; round += 1) {
    let took = false;
    for (const code of present) {
      const item = byCategory.get(code)?.[round];
      if (!item) continue;
      picked.push(item);
      took = true;
      if (picked.length >= limit) break;
    }
    if (!took) break;
  }

  return picked;
}
