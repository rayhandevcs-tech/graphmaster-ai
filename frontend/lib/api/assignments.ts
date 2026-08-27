import { api, type PageParams } from "./client";
import type {
  AssignmentCreate,
  AssignmentDetail,
  AssignmentProgress,
  AssignmentSummary,
  AssignmentUpdate,
  Page,
  UUID,
} from "@/types/api";

export interface AssignmentListParams extends PageParams {
  class_id?: UUID;
  /**
   * Teachers only, in practice. A student's list is already filtered to open
   * work by the server — closed work is not theirs to see.
   */
  is_active?: boolean;
}

export const assignmentsApi = {
  /**
   * One endpoint, two audiences.
   *
   * A teacher receives every class they own; a student receives the open work
   * set for their own section. The narrowing happens on the server, so this
   * function does not need to know which of the two is calling.
   */
  list: (params: AssignmentListParams = {}) =>
    api.get<Page<AssignmentSummary>>("/assignments", { query: { ...params } }),

  get: (assignmentId: UUID) => api.get<AssignmentDetail>(`/assignments/${assignmentId}`),

  create: (payload: AssignmentCreate) => api.post<AssignmentDetail>("/assignments", payload),

  update: (assignmentId: UUID, payload: AssignmentUpdate) =>
    api.patch<AssignmentDetail>(`/assignments/${assignmentId}`, payload),

  /** Who has submitted and who has not, counted against enrolment. */
  progress: (assignmentId: UUID) =>
    api.get<AssignmentProgress>(`/assignments/${assignmentId}/progress`),
};
