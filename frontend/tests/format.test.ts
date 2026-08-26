/**
 * The formatting rules that carry a meaning.
 *
 * Most of `lib/format` is `Intl` with a house style over it and is not worth
 * asserting. Two things here are product rules rather than presentation, and
 * both are the kind that a well-meaning refactor undoes:
 *
 * - **A missing average is an em dash, never zero.** The API goes to some
 *   trouble to send `null` for a student who has not been marked yet; a `?? 0`
 *   anywhere between there and the screen turns "no mark" into "a mark of
 *   zero", which is a thing the student would reasonably believe.
 * - **Relative wording stops at a day.** "23 days ago" is a number nobody
 *   converts back into a date.
 */

import { describe, expect, it } from "vitest";

import { daysLabel, formatCount, formatPercent, formatWhen } from "@/lib/format";
import { trendChartData } from "@/lib/charts/trend";

describe("a figure that may be missing", () => {
  it("renders an em dash for null, and never a zero", () => {
    expect(formatPercent(null)).toBe("—");
    expect(formatPercent(undefined)).toBe("—");
    expect(formatCount(null)).toBe("—");
  });

  it("still renders a genuine zero", () => {
    // A student who scored zero is not a student with no score, and the two
    // must not look the same.
    expect(formatPercent(0)).toBe("0.0%");
    expect(formatCount(0)).toBe("0");
  });

  it("survives a non-finite number rather than printing NaN", () => {
    expect(formatPercent(Number.NaN)).toBe("—");
    expect(formatCount(Number.POSITIVE_INFINITY)).toBe("—");
  });

  it("rounds to the requested precision", () => {
    expect(formatPercent(72.349)).toBe("72.3%");
    expect(formatPercent(72.349, 0)).toBe("72%");
  });
});

describe("when something happened", () => {
  const now = Date.parse("2026-08-26T12:00:00Z");
  const ago = (ms: number) => new Date(now - ms).toISOString();

  it("uses relative wording for the first day", () => {
    expect(formatWhen(ago(30_000), now)).toBe("just now");
    expect(formatWhen(ago(60_000), now)).toBe("1 minute ago");
    expect(formatWhen(ago(5 * 60_000), now)).toBe("5 minutes ago");
    expect(formatWhen(ago(3 * 3_600_000), now)).toBe("3 hours ago");
    expect(formatWhen(ago(30 * 3_600_000), now)).toBe("yesterday");
  });

  it("switches to a date once relative wording stops helping", () => {
    expect(formatWhen(ago(9 * 86_400_000), now)).not.toMatch(/ago|yesterday/);
  });

  it("does not claim the future when a clock is a little behind", () => {
    expect(formatWhen(new Date(now + 5_000).toISOString(), now)).toBe("just now");
  });

  it("hands back an unparseable value rather than printing Invalid Date", () => {
    expect(formatWhen("not a date", now)).toBe("not a date");
  });
});

describe("counted things", () => {
  it("gets the singular right", () => {
    expect(daysLabel(1)).toBe("1 day");
    expect(daysLabel(2)).toBe("2 days");
  });
});

describe("the score trend as chart data", () => {
  const points = [
    {
      date: "2026-08-01",
      submission_count: 2,
      average_final_score: 61.5,
      average_vocabulary_percentage: 55,
    },
    {
      date: "2026-08-20",
      submission_count: 1,
      average_final_score: 74,
      average_vocabulary_percentage: 71.25,
    },
  ];

  it("plots both measures as named series", () => {
    const data = trendChartData(points);

    expect(data.datasets).toHaveLength(2);
    expect(data.datasets.map((set) => set.label)).toEqual(["Overall score", "Vocabulary"]);
    expect(data.datasets[0]?.data).toEqual([61.5, 74]);
    expect(data.datasets[1]?.data).toEqual([55, 71.25]);
  });

  it("labels the axis as practice days rather than as a calendar", () => {
    // The two points above are nineteen days apart and adjacent on the chart.
    // The axis title is the only thing stopping that being read as an
    // overnight jump, so it is asserted rather than left to a designer's
    // memory.
    const data = trendChartData(points);

    expect(data.labels).toHaveLength(2);
    expect(data.x_axis_label).toMatch(/days you practised/i);
    expect(data.unit).toBe("%");
  });

  it("has nothing to draw for a student with no marked work", () => {
    expect(trendChartData([]).labels).toEqual([]);
  });
});
