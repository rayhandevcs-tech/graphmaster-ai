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

/**
 * Which roles a path belongs to.
 *
 * Mirrors the `<Protected roles={...}>` on each page, in one place, because
 * the sign-in redirect needs to know the answer *before* the page it is about
 * to send someone to has rendered and refused them.
 *
 * Anything unlisted belongs to every signed-in role — the page itself still
 * guards, so an unlisted path can at worst send someone to a screen that then
 * redirects them.
 */
const ROUTE_ROLES: readonly { prefix: string; roles: readonly UserRole[] }[] = [
  { prefix: "/teacher", roles: ["teacher", "admin"] },
  { prefix: "/admin", roles: ["admin"] },
  { prefix: "/dashboard", roles: ["student"] },
  { prefix: "/practice", roles: ["student"] },
  { prefix: "/leaderboard", roles: ["student"] },
  { prefix: "/achievements", roles: ["student"] },
  { prefix: "/submissions", roles: ["student"] },
];

/**
 * Whether `path` is a page this role may actually open.
 *
 * The sign-in form honours a `next` parameter so a student who followed a link
 * to a graph lands on that graph rather than on their dashboard. Without this
 * check it also honoured a `next` pointing at a teacher's screen: sign in as a
 * student and the first thing you saw was "This page is not for your account",
 * which reads as the product being broken rather than as a link being stale.
 */
export function roleCanVisit(path: string, role: UserRole | undefined): boolean {
  if (!role) return false;

  // Compare the pathname only: `/practice?foo=1` and `/practice#x` are the
  // same page, and a query string must not defeat the prefix match.
  const pathname = path.split(/[?#]/)[0] ?? path;
  const entry = ROUTE_ROLES.find(
    (candidate) => pathname === candidate.prefix || pathname.startsWith(`${candidate.prefix}/`),
  );

  return entry ? entry.roles.includes(role) : true;
}
