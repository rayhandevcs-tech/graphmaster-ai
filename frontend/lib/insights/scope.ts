import type { DateString } from "@/types/api";

/**
 * The period a teaching screen is looking at.
 *
 * Kept separate from the hook that stores it so the arithmetic can be tested
 * without React, and so the analytics screen and the dashboard cannot drift
 * into meaning different things by "last 30 days".
 *
 * **The dates are the browser's calendar, not the platform's.** The server
 * buckets in `PLATFORM_TIMEZONE` (CLAUDE.md rule 30); a range chosen here is a
 * filter on which days to include, so a reader in another zone may see a
 * boundary day shift. That is acceptable for a range a teacher picked in words
 * — "last 30 days" — and is the reason the label says the words rather than
 * printing the two dates as though they were exact.
 */
export type RangeKey = "7d" | "30d" | "90d" | "all";

export interface RangeOption {
  value: RangeKey;
  label: string;
}

export const RANGE_OPTIONS: readonly RangeOption[] = [
  { value: "7d", label: "Last 7 days" },
  { value: "30d", label: "Last 30 days" },
  { value: "90d", label: "Last 90 days" },
  { value: "all", label: "All time" },
];

const DAYS: Record<Exclude<RangeKey, "all">, number> = { "7d": 7, "30d": 30, "90d": 90 };

export interface RangeDates {
  date_from?: DateString;
  date_to?: DateString;
}

function toDateString(at: Date): DateString {
  const year = at.getFullYear();
  const month = `${at.getMonth() + 1}`.padStart(2, "0");
  const day = `${at.getDate()}`.padStart(2, "0");
  return `${year}-${month}-${day}`;
}

/**
 * A range as the two query parameters the analytics endpoints take.
 *
 * "All time" sends neither, rather than sending an arbitrarily early date: the
 * server's own default is the whole history, and inventing `1970-01-01` here
 * would put a decade of empty buckets on a calendar axis.
 */
export function rangeDates(range: RangeKey, now: Date = new Date()): RangeDates {
  if (range === "all") return {};

  const to = new Date(now);
  const from = new Date(now);
  // Inclusive of today, so "last 7 days" is seven days including this one.
  from.setDate(from.getDate() - (DAYS[range] - 1));

  return { date_from: toDateString(from), date_to: toDateString(to) };
}

export function rangeLabel(range: RangeKey): string {
  return RANGE_OPTIONS.find((option) => option.value === range)?.label ?? "Last 30 days";
}
