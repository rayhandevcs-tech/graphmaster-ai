import { api } from "./client";
import type {
  AnalyticsReport,
  DateString,
  TrendReport,
  UUID,
  VocabularyUsageReport,
} from "@/types/api";

export interface DateRange {
  date_from?: DateString;
  date_to?: DateString;
}

export interface TrendParams extends DateRange {
  class_id?: UUID;
  granularity?: string;
}

export interface VocabularyUsageParams extends DateRange {
  class_id?: UUID;
  limit?: number;
}

/**
 * Computed live, never from `analytics_snapshots`: a cached figure is stale
 * exactly when a teacher wants it, in the minutes after a lesson.
 *
 * A class the caller does not teach is refused with 403, not returned empty —
 * an empty report and a forbidden one look identical, and the first is a lie
 * (FR-11.6).
 */
export const analyticsApi = {
  class: (classId: UUID, params: DateRange = {}) =>
    api.get<AnalyticsReport>(`/analytics/class/${classId}`, { query: { ...params } }),

  platform: (params: DateRange = {}) =>
    api.get<AnalyticsReport>("/analytics/platform", { query: { ...params } }),

  trends: (params: TrendParams = {}) =>
    api.get<TrendReport>("/analytics/trends", { query: { ...params } }),

  /** Counts `scores.detected_terms`, never a re-scan of the answers. */
  vocabularyUsage: (params: VocabularyUsageParams = {}) =>
    api.get<VocabularyUsageReport>("/analytics/vocabulary-usage", { query: { ...params } }),
};
