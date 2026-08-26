import { api } from "./client";
import type {
  AnalyzerScoreReport,
  AnalyzerTrendReport,
  AssessmentResponse,
  ConsistencyResponse,
  DateString,
  IssueFrequencyReport,
  UUID,
} from "@/types/api";

export interface AssessmentScope {
  class_id?: UUID;
  date_from?: DateString;
  date_to?: DateString;
}

/**
 * What went wrong, where, and why.
 *
 * The scoring endpoints answer *what was this worth*; these answer what to
 * teach next. Two properties of the payloads shape every surface built on
 * them, and both are the same rule the rest of the platform follows:
 *
 * - **`assessed_count` travels with every figure.** Submissions marked before
 *   the assessment engine existed carry none and there is no backfill, so
 *   every mean here is over a subset and the surface must say so.
 * - **A period with nothing assessed is absent, not zero.** Trend consumers
 *   draw a gap; interpolating would put a step change on the day the engine
 *   was switched on and render it as a sudden improvement in the class.
 *
 * A class the caller does not teach is refused with 403 rather than returned
 * empty (FR-11.6).
 */
export const assessmentApi = {
  /** One submission's issues, filtered to what this caller may see. */
  submission: (submissionId: UUID) =>
    api.get<AssessmentResponse>(`/assessment/submissions/${submissionId}`),

  /** The commonest mistakes across a class, grouped by stable subtype slug. */
  issues: (params: AssessmentScope & { limit?: number } = {}) =>
    api.get<IssueFrequencyReport>("/assessment/issues", { query: { ...params } }),

  /** Every analyzer's mean, with the count behind each. */
  scores: (params: AssessmentScope = {}) =>
    api.get<AnalyzerScoreReport>("/assessment/scores", { query: { ...params } }),

  trend: (analyzer: string, params: AssessmentScope & { interval?: string } = {}) =>
    api.get<AnalyzerTrendReport>(`/assessment/trend/${analyzer}`, { query: { ...params } }),

  /** Teacher-facing writing consistency. Nothing about a comparison is stored. */
  consistency: (submissionId: UUID) =>
    api.get<ConsistencyResponse>(`/assessment/submissions/${submissionId}/consistency`),
};
