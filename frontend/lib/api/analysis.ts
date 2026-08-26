import { api } from "./client";
import type {
  AnalysisRequest,
  AnalysisResponse,
  EngineStatusResponse,
  StudentRubricOut,
  TargetSummaryResponse,
  UUID,
} from "@/types/api";

/**
 * The marking engine's own surface.
 *
 * `rubric` is open to everyone signed in. The rest is **teachers and
 * administrators only** — not a security boundary but a product one: `preview`
 * would let a student iterate a draft against the marker until it scored 100,
 * and `targets` hands back the exact word list the percentage is computed
 * against. Students see every term they missed after scoring, which is where
 * the list teaches something. See 04-api-design.md §3.6c.
 */
export const analysisApi = {
  /**
   * The deployed rubric and language-model state. Render the marking criteria
   * from this rather than hardcoding a copy — the weights and thresholds are
   * configuration, and a retuned rubric must not leave the UI describing rules
   * the server no longer applies.
   */
  engine: () => api.get<EngineStatusResponse>("/analysis/engine"),

  /**
   * The marking criteria a student may see: the two weights and the word-count
   * band, and deliberately nothing else — no tier thresholds, no engine
   * version, no target vocabulary.
   *
   * Read it rather than writing "70% vocabulary" into a component. The weights
   * are deployment configuration, and a hardcoded copy goes on claiming a
   * rubric the server has stopped applying.
   */
  rubric: () => api.get<StudentRubricOut>("/analysis/rubric"),

  targets: (graphId: UUID) => api.get<TargetSummaryResponse>(`/analysis/graphs/${graphId}/targets`),

  /** Scores arbitrary text and stores nothing: no submission, no score, no XP. */
  preview: (graphId: UUID, payload: AnalysisRequest) =>
    api.post<AnalysisResponse>(`/analysis/graphs/${graphId}/preview`, payload),
};
