import { api, type PageParams } from "./client";
import type {
  ClassCreate,
  ClassDetail,
  ClassEnrolRequest,
  ClassJoinRequest,
  ClassStudent,
  ClassUpdate,
  PageClassSummary,
  UUID,
} from "@/types/api";

export interface ClassListParams extends PageParams {
  is_active?: boolean;
}

export const classesApi = {
  /** Teachers see the classes they own; administrators see all of them. */
  list: (params: ClassListParams = {}) =>
    api.get<PageClassSummary>("/classes", { query: { ...params } }),

  get: (classId: UUID) => api.get<ClassDetail>(`/classes/${classId}`),

  create: (payload: ClassCreate) => api.post<ClassDetail>("/classes", payload),

  update: (classId: UUID, payload: ClassUpdate) =>
    api.patch<ClassDetail>(`/classes/${classId}`, payload),

  students: (classId: UUID) => api.get<ClassStudent[]>(`/classes/${classId}/students`),

  enrol: (classId: UUID, payload: ClassEnrolRequest) =>
    api.post<ClassStudent>(`/classes/${classId}/students`, payload),

  unenrol: (classId: UUID, userId: UUID) =>
    api.delete<void>(`/classes/${classId}/students/${userId}`),

  /** The student side: a join code, not an invitation. */
  join: (payload: ClassJoinRequest) => api.post<ClassDetail>("/classes/join", payload),
};
