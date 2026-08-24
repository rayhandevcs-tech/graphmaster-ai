import { api, type PageParams } from "./client";
import type {
  AdminUserUpdateRequest,
  LevelProgress,
  PageUserListItem,
  PublicUserProfile,
  StudentDashboard,
  UserProfile,
  UserRole,
  UserUpdateRequest,
  UUID,
} from "@/types/api";

export interface UserListParams extends PageParams {
  role?: UserRole;
  class_id?: UUID;
  is_active?: boolean;
  search?: string;
}

export const usersApi = {
  me: () => api.get<UserProfile>("/users/me"),

  updateMe: (payload: UserUpdateRequest) => api.patch<UserProfile>("/users/me", payload),

  /** The student dashboard aggregate (FR-10.1 – FR-10.5). */
  dashboard: () => api.get<StudentDashboard>("/users/me/dashboard"),

  level: () => api.get<LevelProgress>("/users/me/level"),

  /** Name, avatar, level and badges — never another student's email or scores. */
  publicProfile: (userId: UUID) => api.get<PublicUserProfile>(`/users/${userId}`),

  list: (params: UserListParams = {}) =>
    api.get<PageUserListItem>("/users", { query: { ...params } }),

  /** Administrators only: role, class and active status. */
  adminUpdate: (userId: UUID, payload: AdminUserUpdateRequest) =>
    api.patch<UserProfile>(`/users/${userId}`, payload),
};
