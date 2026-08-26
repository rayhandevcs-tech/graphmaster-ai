/**
 * Formatting a student reads, in one place.
 *
 * Two rules are encoded here rather than repeated at each call site:
 *
 * 1. **A missing average is `—`, never `0`.** A student who has not started is
 *    not one scoring nothing, and a zero on a dashboard is a figure they will
 *    read as their mark. The API is careful to send `null` (FR-11.x); this is
 *    where that care survives contact with the interface.
 * 2. **Dates are formatted in the reader's locale**, not written out by hand.
 *    `Intl` is in every browser and it knows about the ordering, the
 *    separators and the month names; a template literal knows about none of
 *    them.
 */

/** A score or percentage, to one decimal place. `null` becomes an em dash. */
export function formatPercent(value: number | null | undefined, fractionDigits = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return `${value.toLocaleString(undefined, {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  })}%`;
}

/** A whole number with thousands separators. `null` becomes an em dash. */
export function formatCount(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return Math.round(value).toLocaleString();
}

/** "3 Sep" — the day and month, which is what a dense chart axis has room for. */
export function formatShortDate(iso: string): string {
  const when = new Date(iso);
  if (Number.isNaN(when.getTime())) return iso;
  return when.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

/** "3 September 2026", for a caption where the year matters. */
export function formatLongDate(iso: string): string {
  const when = new Date(iso);
  if (Number.isNaN(when.getTime())) return iso;
  return when.toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" });
}

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

/**
 * "12 minutes ago", "yesterday", "3 Sep".
 *
 * Relative wording is used only for the first day, where it is the more useful
 * reading; past that a date is clearer than "23 days ago", which nobody
 * converts back into a day of the week.
 */
export function formatWhen(iso: string, now: number = Date.now()): string {
  const when = new Date(iso);
  if (Number.isNaN(when.getTime())) return iso;

  const elapsed = now - when.getTime();
  // A clock a little behind the server's is ordinary; "in 3 seconds" is not.
  if (elapsed < MINUTE) return "just now";
  if (elapsed < HOUR) {
    const minutes = Math.floor(elapsed / MINUTE);
    return minutes === 1 ? "1 minute ago" : `${minutes} minutes ago`;
  }
  if (elapsed < DAY) {
    const hours = Math.floor(elapsed / HOUR);
    return hours === 1 ? "1 hour ago" : `${hours} hours ago`;
  }
  if (elapsed < 2 * DAY) return "yesterday";
  return formatShortDate(iso);
}

/** "1 day" / "5 days" — the singular a naive template gets wrong. */
export function daysLabel(count: number): string {
  return count === 1 ? "1 day" : `${count} days`;
}
