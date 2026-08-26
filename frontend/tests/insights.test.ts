/**
 * The two derived readings a teacher acts on.
 *
 * Both are pure functions on purpose. The triage decides which names appear at
 * the top of a teacher's screen and the narration puts a sentence under every
 * figure — neither should be reachable only by rendering a page and reading it.
 */

import { describe, expect, it } from "vitest";

import {
  HARD_BELOW_SCORE,
  QUIET_AFTER_DAYS,
  attentionCount,
  classify,
  triage,
} from "@/lib/insights/attention";
import {
  describeParticipation,
  describeTierSpread,
  describeVocabularyReach,
  readTrend,
} from "@/lib/insights/narrate";
import type { EngagementOut, StudentRow, VocabularyUsageReport } from "@/types/api";
import type { ScoreTrendPoint } from "@/lib/charts/trend";

const NOW = Date.parse("2026-08-26T10:00:00Z");
const daysAgo = (days: number) => new Date(NOW - days * 86_400_000).toISOString();

function student(overrides: Partial<StudentRow> = {}): StudentRow {
  return {
    user_id: overrides.user_id ?? "00000000-0000-0000-0000-000000000001",
    full_name: "Amina Yusuf",
    email: "amina@university.edu",
    total_xp: 0,
    current_level: 1,
    current_streak_days: 0,
    longest_streak_days: 0,
    submission_count: 4,
    average_final_score: 72,
    average_vocabulary_percentage: 66,
    highest_final_score: 81,
    last_submission_at: daysAgo(1),
    ...overrides,
  };
}

describe("who needs the teacher", () => {
  it("files a student with no marked work under not started", () => {
    const row = student({
      submission_count: 0,
      average_final_score: null,
      last_submission_at: null,
    });
    expect(classify(row, NOW)).toBe("never-started");
  });

  it("never calls a student with no average one who is finding it hard", () => {
    // `null < 50` is true in JavaScript, so a comparison without the explicit
    // guard files everyone who has not started under a sentence about work
    // they did not do (CLAUDE.md rule 32).
    const row = student({
      submission_count: 0,
      average_final_score: null,
      last_submission_at: null,
    });
    expect(classify(row, NOW)).not.toBe("finding-it-hard");
  });

  it("uses the platform's own practice-tier boundary, not a second one", () => {
    expect(HARD_BELOW_SCORE).toBe(50);
    expect(classify(student({ average_final_score: 49.9 }), NOW)).toBe("finding-it-hard");
    // 50 is the bottom of the steady band, so it is not "finding it hard".
    expect(classify(student({ average_final_score: 50 }), NOW)).toBeNull();
  });

  it("surfaces silence only once it has lasted", () => {
    const quiet = (days: number) =>
      classify(student({ last_submission_at: daysAgo(days), average_final_score: 70 }), NOW);

    expect(quiet(QUIET_AFTER_DAYS - 1)).toBeNull();
    expect(quiet(QUIET_AFTER_DAYS)).toBe("gone-quiet");
    expect(quiet(30)).toBe("gone-quiet");
  });

  it("puts a student in exactly one group", () => {
    // Struggling *and* silent for a month: they appear once, under the group
    // the teacher can act on with evidence in hand.
    const row = student({ average_final_score: 31, last_submission_at: daysAgo(40) });
    const groups = triage([row], NOW);

    expect(attentionCount(groups)).toBe(1);
    expect(groups.map((group) => group.id)).toEqual(["finding-it-hard"]);
  });

  it("drops groups nobody is in", () => {
    const groups = triage([student(), student({ average_final_score: 22 })], NOW);
    expect(groups.map((group) => group.id)).toEqual(["finding-it-hard"]);
  });

  it("orders the groups by what the evidence supports acting on", () => {
    const groups = triage(
      [
        student({ user_id: "a", last_submission_at: daysAgo(20), average_final_score: 80 }),
        student({ user_id: "b", average_final_score: 30 }),
        student({ user_id: "c", submission_count: 0, average_final_score: null }),
      ],
      NOW,
    );

    expect(groups.map((group) => group.id)).toEqual([
      "never-started",
      "finding-it-hard",
      "gone-quiet",
    ]);
  });

  it("puts the student who needs it most at the top of each group", () => {
    const groups = triage(
      [
        student({ user_id: "a", full_name: "Higher", average_final_score: 46 }),
        student({ user_id: "b", full_name: "Lower", average_final_score: 12 }),
      ],
      NOW,
    );

    expect(groups[0]?.entries.map((entry) => entry.student.full_name)).toEqual(["Lower", "Higher"]);
  });

  it("never labels the lowest group with a word said in front of a class", () => {
    const groups = triage([student({ average_final_score: 20 })], NOW);
    const label = groups[0]?.label.toLowerCase() ?? "";

    for (const word of ["risk", "fail", "weak", "poor", "bottom"]) {
      expect(label).not.toContain(word);
    }
  });
});

const point = (overrides: Partial<ScoreTrendPoint>): ScoreTrendPoint => ({
  date: "2026-08-01",
  submission_count: 3,
  average_final_score: 60,
  average_vocabulary_percentage: 55,
  ...overrides,
});

describe("the sentence under a figure", () => {
  it("refuses a direction it cannot evidence", () => {
    const reading = readTrend([point({}), point({ average_final_score: 90 })]);

    expect(reading.direction).toBe("unknown");
    expect(reading.delta).toBeNull();
    expect(reading.sentence).toMatch(/not enough marked work/i);
  });

  it("reads a rise as a rise and a fall as a fall", () => {
    const rising = readTrend(
      [40, 45, 70, 75].map((score) => point({ average_final_score: score })),
    );
    const falling = readTrend(
      [75, 70, 45, 40].map((score) => point({ average_final_score: score })),
    );

    expect(rising.direction).toBe("rising");
    expect(rising.sentence).toMatch(/up 30 points/);
    expect(falling.direction).toBe("falling");
    expect(falling.sentence).toMatch(/down 30 points/);
  });

  it("calls a small movement steady rather than a trend", () => {
    const reading = readTrend(
      [60, 61, 60, 61].map((score) => point({ average_final_score: score })),
    );

    expect(reading.direction).toBe("steady");
    expect(reading.sentence).toMatch(/held steady/i);
  });

  it("ignores a bucket with no marked work", () => {
    // Defensive: the API sends no row for a silent day, but a zero-count bucket
    // averaged in would read as a day the class scored nothing.
    const reading = readTrend([
      point({ average_final_score: 70 }),
      point({ average_final_score: 0, submission_count: 0 }),
      point({ average_final_score: 71 }),
      point({ average_final_score: 72 }),
    ]);

    expect(reading.direction).toBe("unknown");
  });

  const engagement = (overrides: Partial<EngagementOut> = {}): EngagementOut => ({
    enrolled_student_count: 31,
    active_student_count: 18,
    inactive_student_count: 13,
    submissions_per_active_student: 11.9,
    participation_rate: 58,
    streak_holders: 6,
    average_streak_days: 2.4,
    longest_streak_days: 9,
    ...overrides,
  });

  it("measures participation against enrolment, and says the harder half first", () => {
    const sentence = describeParticipation(engagement());

    expect(sentence).toMatch(/^13 enrolled students have no marked work/);
    expect(sentence).toMatch(/11\.9 attempts each/);
  });

  it("says so when everybody has practised", () => {
    expect(describeParticipation(engagement({ inactive_student_count: 0 }))).toMatch(
      /every enrolled student has marked work/i,
    );
  });

  it("distinguishes an empty class from an idle one", () => {
    expect(describeParticipation(engagement({ enrolled_student_count: 0 }))).toMatch(
      /nobody is enrolled/i,
    );
    expect(describeParticipation(engagement({ active_student_count: 0 }))).toMatch(
      /none of the 31 enrolled students/i,
    );
  });

  const usage = (overrides: Partial<VocabularyUsageReport> = {}): VocabularyUsageReport => ({
    scope: "class",
    term_count: 34,
    used_term_count: 27,
    unused_term_count: 7,
    most_used: [],
    least_used: [],
    ...overrides,
  });

  it("names the terms nobody reached for", () => {
    expect(describeVocabularyReach(usage())).toMatch(/7 of 34 target terms went unused/);
  });

  it("does not congratulate a class on coverage it did not have", () => {
    expect(describeVocabularyReach(usage())).not.toMatch(/every curated term/i);
    expect(describeVocabularyReach(usage({ unused_term_count: 0 }))).toMatch(/every curated term/i);
  });

  it("describes the tier spread as attempts, never as students", () => {
    const sentence = describeTierSpread({ crown: 31, flower: 44, steady: 15, hammer: 10 });

    expect(sentence).toMatch(/flower band/);
    expect(sentence).toMatch(/attempts/);
    expect(sentence).not.toMatch(/students?/i);
  });

  it("says nothing was marked rather than picking a winner from zeros", () => {
    expect(describeTierSpread({ crown: 0, flower: 0, steady: 0, hammer: 0 })).toMatch(
      /no attempts have been marked/i,
    );
  });
});
