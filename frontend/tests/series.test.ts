/**
 * A class trend drawn against a real calendar.
 *
 * `GET /analytics/trends` groups by bucket, so a day nobody submitted is an
 * *absent row*, not a zero one. Everything here exists to stop that absence
 * being drawn as a straight line through the silence.
 */

import { describe, expect, it } from "vitest";

import {
  MAX_BUCKETS,
  calendarBuckets,
  chooseGranularity,
  classTrendSeries,
  truncate,
} from "@/lib/charts/series";
import type { ScoreTrendPoint } from "@/lib/charts/trend";

const point = (date: string, score: number): ScoreTrendPoint => ({
  date,
  submission_count: 2,
  average_final_score: score,
  average_vocabulary_percentage: score - 5,
});

describe("calendar buckets", () => {
  it("covers every day between the bounds, inclusive", () => {
    expect(calendarBuckets("2026-08-01", "2026-08-05", "day")).toEqual([
      "2026-08-01",
      "2026-08-02",
      "2026-08-03",
      "2026-08-04",
      "2026-08-05",
    ]);
  });

  it("starts a week on Monday, as date_trunc does", () => {
    // 2026-08-26 is a Wednesday; its week bucket is Monday the 24th.
    expect(
      truncate(new Date(Date.UTC(2026, 7, 26)), "week")
        .toISOString()
        .slice(0, 10),
    ).toBe("2026-08-24");
    expect(calendarBuckets("2026-08-26", "2026-09-08", "week")).toEqual([
      "2026-08-24",
      "2026-08-31",
      "2026-09-07",
    ]);
  });

  it("steps months by calendar, not by 30 days", () => {
    expect(calendarBuckets("2026-01-15", "2026-04-02", "month")).toEqual([
      "2026-01-01",
      "2026-02-01",
      "2026-03-01",
      "2026-04-01",
    ]);
  });

  it("reads a date as the day it says, in any timezone", () => {
    // Parsed through the local zone, "2026-08-01" becomes 31 July anywhere
    // behind UTC, and every bucket shifts by one.
    expect(calendarBuckets("2026-08-01", "2026-08-01", "day")).toEqual(["2026-08-01"]);
  });

  it("refuses a reversed or unparseable range rather than looping", () => {
    expect(calendarBuckets("2026-08-05", "2026-08-01", "day")).toEqual([]);
    expect(calendarBuckets("not-a-date", "2026-08-01", "day")).toEqual([]);
  });

  it("stops at the readable limit", () => {
    expect(calendarBuckets("2020-01-01", "2030-01-01", "day")).toHaveLength(MAX_BUCKETS);
  });
});

describe("choosing a granularity", () => {
  it("keeps a short range daily and a long one coarser", () => {
    expect(chooseGranularity("2026-08-01", "2026-08-30")).toBe("day");
    // A month is the last daily range; past it the labels stop being readable.
    expect(chooseGranularity("2026-08-01", "2026-09-10")).toBe("week");
    expect(chooseGranularity("2026-06-01", "2026-08-30")).toBe("week");
    expect(chooseGranularity("2024-06-01", "2026-08-30")).toBe("month");
  });
});

describe("the class trend series", () => {
  it("breaks the line across a day nobody submitted", () => {
    const series = classTrendSeries([point("2026-08-01", 60), point("2026-08-04", 70)], {
      from: "2026-08-01",
      to: "2026-08-04",
    });

    expect(series.calendar).toBe(true);
    expect(series.chartData.datasets[0]?.data).toEqual([60, null, null, 70]);
    expect(series.gapCount).toBe(2);
  });

  it("never fills a silent day with a zero", () => {
    const series = classTrendSeries([point("2026-08-01", 60)], {
      from: "2026-08-01",
      to: "2026-08-03",
    });

    expect(series.chartData.datasets[0]?.data).not.toContain(0);
  });

  it("carries both series onto the same calendar", () => {
    const series = classTrendSeries([point("2026-08-02", 60)], {
      from: "2026-08-01",
      to: "2026-08-02",
    });

    expect(series.chartData.datasets.map((set) => set.label)).toEqual([
      "Overall score",
      "Vocabulary",
    ]);
    expect(series.chartData.datasets[1]?.data).toEqual([null, 55]);
  });

  it("folds days into the bucket they belong to at a coarser granularity", () => {
    const series = classTrendSeries([point("2026-08-24", 60), point("2026-09-07", 80)], {
      from: "2026-08-24",
      to: "2026-09-13",
      granularity: "week",
    });

    expect(series.chartData.labels).toHaveLength(3);
    expect(series.chartData.datasets[0]?.data).toEqual([60, null, 80]);
  });

  it("falls back to the buckets that exist when the range is unknown", () => {
    const series = classTrendSeries([]);

    expect(series.calendar).toBe(false);
    expect(series.chartData.labels).toEqual([]);
    expect(series.gapCount).toBe(0);
  });

  it("uses the points' own bounds when no range is given", () => {
    const series = classTrendSeries([point("2026-08-01", 60), point("2026-08-03", 70)]);

    expect(series.calendar).toBe(true);
    expect(series.chartData.datasets[0]?.data).toEqual([60, null, 70]);
  });
});
