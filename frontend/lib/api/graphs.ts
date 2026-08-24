import { api, type PageParams } from "./client";
import type {
  Difficulty,
  GraphAuthoringDetail,
  GraphCreate,
  GraphDetail,
  GraphPublishRequest,
  GraphType,
  GraphUpdate,
  PageGraphSummary,
  TargetVocabularyOut,
  TargetVocabularyReplace,
  UUID,
} from "@/types/api";

export interface GraphListParams extends PageParams {
  graph_type?: GraphType;
  difficulty?: Difficulty;
  search?: string;
  /** Teachers and admins only; a student asking is refused, not quietly ignored. */
  include_unpublished?: boolean;
}

export interface RandomGraphParams {
  graph_type?: GraphType;
  difficulty?: Difficulty;
  /** Avoids handing back the graph the student just practised. */
  exclude_id?: UUID;
}

/**
 * A graph as the caller is allowed to see it.
 *
 * Students receive `GraphDetail`, which has no `reference_description` field at
 * all — the model answer is released only in the result payload, after the
 * attempt is marked. Teachers receive the authoring view. The union is the
 * honest type: which one arrives depends on the caller's role, so a component
 * that wants the model answer has to narrow first.
 */
export type Graph = GraphAuthoringDetail | GraphDetail;

export function isAuthoringDetail(graph: Graph): graph is GraphAuthoringDetail {
  return "reference_description" in graph;
}

export const graphsApi = {
  list: (params: GraphListParams = {}) =>
    api.get<PageGraphSummary>("/graphs", { query: { ...params } }),

  get: (graphId: UUID) => api.get<Graph>(`/graphs/${graphId}`),

  /** The "Start practice" entry point. */
  random: (params: RandomGraphParams = {}) =>
    api.get<Graph>("/graphs/random", { query: { ...params } }),

  create: (payload: GraphCreate) => api.post<GraphAuthoringDetail>("/graphs", payload),

  update: (graphId: UUID, payload: GraphUpdate) =>
    api.patch<GraphAuthoringDetail>(`/graphs/${graphId}`, payload),

  /** 409 if any student has attempted it — history is never orphaned. */
  remove: (graphId: UUID) => api.delete<void>(`/graphs/${graphId}`),

  /** Refused with 409 unless the graph has at least one *required* target term. */
  setPublished: (graphId: UUID, payload: GraphPublishRequest) =>
    api.post<GraphAuthoringDetail>(`/graphs/${graphId}/publish`, payload),

  targetVocabulary: (graphId: UUID) =>
    api.get<TargetVocabularyOut[]>(`/graphs/${graphId}/target-vocabulary`),

  replaceTargetVocabulary: (graphId: UUID, payload: TargetVocabularyReplace) =>
    api.put<TargetVocabularyOut[]>(`/graphs/${graphId}/target-vocabulary`, payload),
};
