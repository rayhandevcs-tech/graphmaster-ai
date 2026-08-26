import type { EngagementOut, VocabularyUsageReport } from "@/types/api";
import type { ScoreTrendPoint } from "@/lib/charts/trend";

/**
 * The sentence under each figure.
 *
 * Every analytics card states a question, an answer and an interpretation, and
 * the interpretation is *derived* here rather than written into the component.
 * That is the same discipline `app/nlp/feedback.py` applies to a student:
 * never claim something that did not happen, in either direction. A caption
 * reading "scores are improving" beside a flat line is worse than no caption,
 * and a hand-written one goes stale the first time the data does something
 * else.
 *
 * Where the data cannot support a claim these functions say so in those words.
 * They never return an empty string to be hidden by the caller — an absent
 * interpretation is itself a finding, and it is worded.
 */

/** Points, either side of which a change is worth calling a direction. */
export const STEADY_BAND = 2;

/** Buckets of marked work needed before a direction is claimed at all. */
export const MIN_POINTS_FOR_DIRECTION = 4;

export type TrendDirection = "rising" | "falling" | "steady" | "unknown";

export interface TrendReading {
  direction: TrendDirection;
  /** Signed change between the first and last halves, or `null` when unknown. */
  delta: number | null;
  sentence: string;
}

type TrendField = "average_final_score" | "average_vocabulary_percentage";

const FIELD_NOUN: Record<TrendField, string> = {
  average_final_score: "Scores",
  average_vocabulary_percentage: "Vocabulary use",
};

function mean(values: number[]): number {
  return values.reduce((total, value) => total + value, 0) / values.length;
}

/**
 * Whether the class is moving, and which way.
 *
 * Compared as first half against second half rather than first point against
 * last: a single unusually good or bad day at either end would otherwise
 * decide the sentence for the whole period.
 *
 * Only buckets with marked work count. The API returns no bucket at all for a
 * day nobody submitted, so a filter here is belt and braces — but a defensive
 * one, because a zero-count bucket averaged in would read as a day the class
 * scored nothing.
 */
export function readTrend(
  points: ScoreTrendPoint[],
  field: TrendField = "average_final_score",
): TrendReading {
  const values = points
    .filter((point) => point.submission_count > 0)
    .map((point) => point[field])
    .filter((value): value is number => typeof value === "number" && Number.isFinite(value));

  if (values.length < MIN_POINTS_FOR_DIRECTION) {
    return {
      direction: "unknown",
      delta: null,
      sentence: "Not enough marked work yet to show a direction.",
    };
  }

  const half = Math.floor(values.length / 2);
  const delta = mean(values.slice(values.length - half)) - mean(values.slice(0, half));
  const rounded = Math.round(delta * 10) / 10;
  const size = Math.abs(rounded).toLocaleString(undefined, {
    maximumFractionDigits: 1,
  });
  const noun = FIELD_NOUN[field];

  if (Math.abs(rounded) < STEADY_BAND) {
    return {
      direction: "steady",
      delta: rounded,
      sentence: `${noun} have held steady across this period.`,
    };
  }

  return rounded > 0
    ? {
        direction: "rising",
        delta: rounded,
        sentence: `${noun} are up ${size} points from the start of this period to the end.`,
      }
    : {
        direction: "falling",
        delta: rounded,
        sentence: `${noun} are down ${size} points from the start of this period to the end.`,
      };
}

/**
 * How many of the enrolled students actually practised.
 *
 * Measured against enrolment, never against whoever happened to submit
 * (CLAUDE.md rule 35) — so "half the class never started" cannot hide behind
 * "everyone who practised, practised a lot". Both halves of that sentence are
 * here, in that order.
 */
export function describeParticipation(engagement: EngagementOut): string {
  const { enrolled_student_count: enrolled, active_student_count: active } = engagement;
  const inactive = engagement.inactive_student_count;

  if (enrolled === 0) return "Nobody is enrolled in this class yet.";
  if (active === 0)
    return `None of the ${enrolled} enrolled students has practised in this period.`;

  const each = engagement.submissions_per_active_student.toLocaleString(undefined, {
    maximumFractionDigits: 1,
  });
  const practised = `Those who did practise averaged ${each} ${
    engagement.submissions_per_active_student === 1 ? "attempt" : "attempts"
  } each.`;

  if (inactive === 0) {
    return `Every enrolled student has marked work in this period. ${practised}`;
  }

  return `${inactive} enrolled ${
    inactive === 1 ? "student has" : "students have"
  } no marked work in this period. ${practised}`;
}

/**
 * The curated terms nobody reached for.
 *
 * This is the finding that no report built from what students *did* write can
 * produce, which is why it gets its own card rather than a row in a table.
 */
export function describeVocabularyReach(report: VocabularyUsageReport): string {
  const { term_count: total, unused_term_count: unused } = report;

  if (total === 0) return "No target vocabulary has been curated yet.";
  if (unused === 0) return "Every curated term was used at least once in this period.";

  return `${unused} of ${total} target ${
    total === 1 ? "term" : "terms"
  } went unused — no student reached for ${unused === 1 ? "it" : "them"} once.`;
}

const TIER_WORDS: Record<string, string> = {
  crown: "the crown band",
  flower: "the flower band",
  steady: "the steady band",
  hammer: "the practice band",
};

/**
 * Where the marks landed, as a sentence about attempts.
 *
 * Deliberately never about students. A tier distribution is the one figure on
 * a shared screen that could be read as a ranking of people, and FR-7.6 rules
 * that out; the caption beside it says "attempts, not students" and this
 * sentence keeps the same subject.
 */
export function describeTierSpread(distribution: Record<string, number>): string {
  const entries = Object.entries(distribution).filter(([, count]) => count > 0);
  const total = entries.reduce((sum, [, count]) => sum + count, 0);

  if (total === 0) return "No attempts have been marked in this period.";

  const [tier, count] = entries.reduce((best, entry) => (entry[1] > best[1] ? entry : best));
  const share = Math.round((count / total) * 100);

  return `Most attempts landed in ${TIER_WORDS[tier] ?? tier} — ${share}% of ${total.toLocaleString()}.`;
}
