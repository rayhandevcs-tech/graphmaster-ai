import type { UserRole } from "@/types/api";

/** The three roles. `learner` and `content_admin` from the early docs are obsolete. */
export const ROLES = ["student", "teacher", "admin"] as const;

export const ROLE_LABELS: Record<UserRole, string> = {
  student: "Student",
  teacher: "Teacher",
  admin: "Administrator",
};

export function isStudent(role: UserRole | undefined): boolean {
  return role === "student";
}

/**
 * Most teaching surfaces admit administrators too — a class an administrator
 * does not teach is still refused by the API, which is where that rule lives.
 */
export function isTeacherOrAdmin(role: UserRole | undefined): boolean {
  return role === "teacher" || role === "admin";
}

export function isAdmin(role: UserRole | undefined): boolean {
  return role === "admin";
}

/** Where signing in lands. Each role's work starts somewhere different. */
export function homePathForRole(role: UserRole | undefined): string {
  switch (role) {
    case "teacher":
      return "/teacher/dashboard";
    case "admin":
      return "/admin/users";
    case "student":
      return "/dashboard";
    default:
      return "/";
  }
}
