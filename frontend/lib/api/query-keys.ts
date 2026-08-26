/**
 * Query keys, in one place.
 *
 * TanStack Query invalidates by key prefix, so the keys have to agree across
 * the whole app: a submission that scores must invalidate the dashboard, the
 * XP history and the leaderboard, and it can only do that if those three were
 * spelled the same way when they were fetched. Ad-hoc string arrays at each
 * call site drift, and the symptom is a screen that quietly shows yesterday's
 * XP.
 */

import type { UUID } from "@/types/api";

type Params = Record<string, unknown>;

export const queryKeys = {
  currentUser: () => ["users", "me"] as const,
  dashboard: () => ["users", "me", "dashboard"] as const,
  level: () => ["users", "me", "level"] as const,
  users: (params: Params = {}) => ["users", "list", params] as const,
  publicProfile: (userId: UUID) => ["users", "public", userId] as const,

  avatars: () => ["avatars", "me"] as const,

  graphs: (params: Params = {}) => ["graphs", "list", params] as const,
  graph: (graphId: UUID) => ["graphs", "detail", graphId] as const,
  graphTargets: (graphId: UUID) => ["graphs", "detail", graphId, "targets"] as const,

  vocabularyCategories: () => ["vocabulary", "categories"] as const,
  vocabularyItems: (params: Params = {}) => ["vocabulary", "items", params] as const,

  classes: (params: Params = {}) => ["classes", "list", params] as const,
  class: (classId: UUID) => ["classes", "detail", classId] as const,
  classStudents: (classId: UUID) => ["classes", "detail", classId, "students"] as const,

  submissions: (params: Params = {}) => ["submissions", "list", params] as const,
  submission: (submissionId: UUID) => ["submissions", "detail", submissionId] as const,

  /**
   * What one submission earned, handed from the analyze call to the result
   * screen it navigates to.
   *
   * Deliberately *not* under the `submissions` prefix. XP, the level change and
   * any achievements arrive only in the `analyze` response — re-reading the
   * submission afterwards returns the score without them — so this cache entry
   * is the only copy. Filing it under `submissions` would put it inside
   * `INVALIDATED_BY_SCORING`, and scoring would evict the very payload it just
   * produced.
   */
  submissionAward: (submissionId: UUID) => ["submission-awards", submissionId] as const,

  achievements: () => ["gamification", "achievements"] as const,
  badges: () => ["gamification", "badges"] as const,
  xpHistory: (params: Params = {}) => ["gamification", "xp-history", params] as const,

  leaderboard: (params: Params = {}) => ["leaderboard", "page", params] as const,
  leaderboardPosition: (params: Params = {}) => ["leaderboard", "me", params] as const,

  analyticsClass: (classId: UUID, params: Params = {}) =>
    ["analytics", "class", classId, params] as const,
  analyticsPlatform: (params: Params = {}) => ["analytics", "platform", params] as const,
  analyticsTrends: (params: Params = {}) => ["analytics", "trends", params] as const,
  analyticsVocabulary: (params: Params = {}) => ["analytics", "vocabulary", params] as const,

  reports: (params: Params = {}) => ["reports", "list", params] as const,
  reportCapabilities: () => ["reports", "capabilities"] as const,

  ocrStatus: () => ["ocr", "status"] as const,
  engineStatus: () => ["analysis", "engine"] as const,
  rubric: () => ["analysis", "rubric"] as const,
} as const;

/**
 * What a freshly scored submission makes stale.
 *
 * Scoring writes to four places at once — the submission, the XP ledger, the
 * student's totals and the leaderboard — so a single invalidation would leave
 * three screens wrong.
 */
export const INVALIDATED_BY_SCORING = [
  ["users", "me"],
  ["submissions"],
  ["gamification"],
  ["leaderboard"],
] as const;
