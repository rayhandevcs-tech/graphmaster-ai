import { api, type PageParams } from "./client";
import type {
  LeaderboardPage,
  LeaderboardPosition,
  LeaderboardRefreshOut,
  LeaderboardScope,
  UUID,
} from "@/types/api";

export interface LeaderboardParams extends PageParams {
  scope?: LeaderboardScope;
  /** Required for the `class` scope, meaningless for the other three. */
  class_id?: UUID;
}

/**
 * Boards rank students only, and never publish a reward tier: a hammer count
 * belongs on one student's own results screen, not beside their name in front
 * of the cohort (FR-7.6).
 */
export const leaderboardApi = {
  page: (params: LeaderboardParams = {}) =>
    api.get<LeaderboardPage>("/leaderboard", { query: { ...params } }),

  /** The caller's own rank, including when they fall outside the visible page. */
  me: (params: Omit<LeaderboardParams, keyof PageParams> = {}) =>
    api.get<LeaderboardPosition>("/leaderboard/me", { query: { ...params } }),

  /** Rematerialises every scope. Administrators only. */
  refresh: () => api.post<LeaderboardRefreshOut>("/leaderboard/refresh"),
};
