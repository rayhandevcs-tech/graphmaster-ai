import { formatShortDate } from "@/lib/format";
import type { ScoreTrendPoint } from "./trend";
import type { ChartData, DateString } from "@/types/api";

/**
 * A class trend, drawn against a real calendar.
 *
 * The student's own trend (`trend.ts`) spaces its points evenly and calls the
 * axis "days you practised", because there the ordering is the information.
 * A class trend is a different question — *is this cohort improving over the
 * term* — and there the interval matters: three silent days in the middle of a
 * scheme of work is something a teacher needs to see.
 *
 * `GET /analytics/trends` groups by bucket, so a day nobody submitted produces
 * **no row at all** rather than a zero. Plotting the rows as they arrive would
 * therefore draw a straight line across the silence and label it progress.
 * This module expands them onto the calendar the teacher asked for and leaves
 * `null` where nothing was marked; `spanGaps: false` in the chart config then
 * breaks the line rather than guessing across it.
 *
 * That is CLAUDE.md rule 32 at the level of a series: missing is missing, not
 * zero, and not smoothed away.
 */

export type Granularity = "day" | "week" | "month";

/** Beyond this many buckets a calendar axis is unreadable, so it is not drawn. */
export const MAX_BUCKETS = 120;

export interface TrendSeries {
  chartData: ChartData;
  /** True when the axis is a calendar; false when it is only the buckets that exist. */
  calendar: boolean;
  /** Buckets inside the range with no marked work. */
  gapCount: number;
  granularity: Granularity;
}

const DAY_MS = 86_400_000;

function parseDay(iso: string): Date | null {
  // Parsed as UTC midnight rather than through the local timezone: a
  // `YYYY-MM-DD` read in a zone behind UTC becomes the previous day, which
  // silently shifts every bucket by one.
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!match) return null;
  const at = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
  return Number.isNaN(at.getTime()) ? null : at;
}

function toKey(at: Date): DateString {
  return at.toISOString().slice(0, 10);
}

/** The bucket a day belongs to, matching PostgreSQL's `date_trunc`. */
export function truncate(at: Date, granularity: Granularity): Date {
  if (granularity === "month") {
    return new Date(Date.UTC(at.getUTCFullYear(), at.getUTCMonth(), 1));
  }
  if (granularity === "week") {
    // `date_trunc('week')` is Monday-based; `getUTCDay()` is Sunday-based.
    const offset = (at.getUTCDay() + 6) % 7;
    return new Date(at.getTime() - offset * DAY_MS);
  }
  return at;
}

function advance(at: Date, granularity: Granularity): Date {
  if (granularity === "month") {
    return new Date(Date.UTC(at.getUTCFullYear(), at.getUTCMonth() + 1, 1));
  }
  return new Date(at.getTime() + (granularity === "week" ? 7 : 1) * DAY_MS);
}

/**
 * The granularity that keeps a range readable.
 *
 * Chosen by the caller *before* requesting the trend, so the server buckets it
 * once rather than the browser re-bucketing what it was sent. A term-long range
 * at daily granularity is ninety unlabelled ticks; at weekly it is thirteen
 * points a teacher can actually compare.
 */
export function chooseGranularity(from: DateString, to: DateString): Granularity {
  const start = parseDay(from);
  const end = parseDay(to);
  if (!start || !end) return "day";

  const days = Math.round((end.getTime() - start.getTime()) / DAY_MS) + 1;
  if (days <= 45) return "day";
  if (days <= 365) return "week";
  return "month";
}

/** Every bucket between two dates, inclusive — including the empty ones. */
export function calendarBuckets(
  from: DateString,
  to: DateString,
  granularity: Granularity,
): DateString[] {
  const start = parseDay(from);
  const end = parseDay(to);
  if (!start || !end || end < start) return [];

  const buckets: DateString[] = [];
  let cursor = truncate(start, granularity);
  while (cursor <= end && buckets.length < MAX_BUCKETS) {
    buckets.push(toKey(cursor));
    cursor = advance(cursor, granularity);
  }
  return buckets;
}

/**
 * The class trend as something `ChartPanel` can draw.
 *
 * When the range is short enough to plot honestly, the axis is a calendar and
 * silent buckets are `null`. When it is not — a range wider than
 * `MAX_BUCKETS`, or one whose bounds are unknown — the buckets that exist are
 * plotted in order and `calendar` is `false`, so the surface can say which
 * axis the reader is looking at instead of leaving them to assume.
 */
export function classTrendSeries(
  points: ScoreTrendPoint[],
  options: { from?: DateString | null; to?: DateString | null; granularity?: Granularity } = {},
): TrendSeries {
  const granularity =
    options.granularity ??
    (options.from && options.to ? chooseGranularity(options.from, options.to) : "day");

  const from = options.from ?? points[0]?.date ?? null;
  const to = options.to ?? points[points.length - 1]?.date ?? null;
  const buckets = from && to ? calendarBuckets(from, to, granularity) : [];

  if (buckets.length === 0) {
    return {
      chartData: build(
        points.map((point) => formatShortDate(point.date)),
        points.map((point) => point.average_final_score),
        points.map((point) => point.average_vocabulary_percentage),
      ),
      calendar: false,
      gapCount: 0,
      granularity,
    };
  }

  const byBucket = new Map<string, ScoreTrendPoint>();
  for (const point of points) {
    const at = parseDay(point.date);
    if (at) byBucket.set(toKey(truncate(at, granularity)), point);
  }

  const scores = buckets.map((key) => byBucket.get(key)?.average_final_score ?? null);
  const vocabulary = buckets.map((key) => byBucket.get(key)?.average_vocabulary_percentage ?? null);

  return {
    chartData: build(buckets.map(formatShortDate), scores, vocabulary),
    calendar: true,
    gapCount: scores.filter((value) => value === null).length,
    granularity,
  };
}

function build(
  labels: string[],
  scores: (number | null)[],
  vocabulary: (number | null)[],
): ChartData {
  return {
    labels,
    datasets: [
      { label: "Overall score", data: scores },
      { label: "Vocabulary", data: vocabulary },
    ],
    x_axis_label: "Date",
    y_axis_label: "Percentage",
    unit: "%",
  };
}
