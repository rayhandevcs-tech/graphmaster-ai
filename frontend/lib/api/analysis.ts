import { api } from "./client";
import type {
  AnalysisRequest,
  AnalysisResponse,
  EngineStatusResponse,
  TargetSummaryResponse,
  UUID,
} from "@/types/api";

/**
 * The marking engine's own surface — **teachers and administrators only**.
 *
 * Not a security boundary but a product one: `preview` would let a student
 * iterate a draft against the marker until it scored 100, and `targets` hands
 * back the exact word list the percentage is computed against. Students see
 * every term they missed after scoring, which is where the list teaches
 * something. See 04-api-design.md §3.6c.
 */
export const analysisApi = {
  /**
   * The deployed rubric and language-model state. Render the marking criteria
   * from this rather than hardcoding a copy — the weights and thresholds are
   * configuration, and a retuned rubric must not leave the UI describing rules
   * the server no longer applies.
   */
  engine: () => api.get<EngineStatusResponse>("/analysis/engine"),

  targets: (graphId: UUID) => api.get<TargetSummaryResponse>(`/analysis/graphs/${graphId}/targets`),

  /** Scores arbitrary text and stores nothing: no submission, no score, no XP. */
  preview: (graphId: UUID, payload: AnalysisRequest) =>
    api.post<AnalysisResponse>(`/analysis/graphs/${graphId}/preview`, payload),
};
